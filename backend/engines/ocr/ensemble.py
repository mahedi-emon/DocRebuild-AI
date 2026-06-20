"""
OCR Ensemble Engine — The Core of DocRebuild AI

For every text region on a page:
1. Runs all enabled OCR engines in parallel
2. Normalizes bounding boxes to a common coordinate space
3. Aligns words across engines using IoU-based bbox matching
4. For each aligned word position:
   - Collects all candidate texts from different engines
   - Applies weighted majority voting with Levenshtein distance clustering
   - Selects the highest-confidence candidate
5. Outputs fused OCRResult with per-word confidence and source attribution
"""

from __future__ import annotations

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

import numpy as np

from engines.ocr.base_ocr import BaseOCREngine, OCRResult, OCRLine, OCRWord
from app.config import get_settings
from app.utils.text_utils import levenshtein_distance, normalize_text, devanagari_to_bengali
from app.utils.image_utils import compute_iou

logger = logging.getLogger(__name__)
settings = get_settings()

# Default engine weights (tuned for Bangla/English textbooks)
DEFAULT_WEIGHTS = {
    "surya": 1.0,
    "paddleocr": 0.7,
    "tesseract": 0.6,
    "easyocr": 0.85,
    "trocr": 0.5,
    "doctr": 0.5,
}

# Engines that genuinely support Bangla
BANGLA_CAPABLE_ENGINES = {"surya", "tesseract", "easyocr"}


class OCREnsemble:
    """
    Multi-OCR ensemble engine with weighted voting fusion.

    Architecture:
    - Each OCR engine runs independently on the same image
    - Results are aligned at the word level using bounding box IoU
    - Weighted voting selects the best candidate for each word position
    - Low-confidence words are flagged for vision model validation
    """

    def __init__(
        self,
        engines: list[BaseOCREngine] | None = None,
        weights: dict[str, float] | None = None,
        min_engines: int = 3,
        iou_threshold: float = 0.4,
        confidence_threshold: float = 0.7,
        max_workers: int = 4,
    ):
        self._engines = engines or []
        self._weights = weights or DEFAULT_WEIGHTS
        self._min_engines = min_engines
        self._iou_threshold = iou_threshold
        self._confidence_threshold = confidence_threshold
        self._max_workers = max_workers

    def add_engine(self, engine: BaseOCREngine) -> None:
        """Register an OCR engine."""
        self._engines.append(engine)

    def initialize_engines(self) -> list[str]:
        """Initialize all registered engines. Returns names of successfully initialized engines."""
        initialized = []
        for engine in self._engines:
            try:
                engine.initialize()
                initialized.append(engine.name)
                logger.info(f"Initialized OCR engine: {engine.name}")
            except Exception as e:
                logger.warning(f"Failed to initialize {engine.name}: {e}")
        return initialized

    def run_all_engines(
        self,
        image: np.ndarray,
        languages: list[str] | None = None,
    ) -> dict[str, OCRResult]:
        """
        Run all engines in parallel on the same image.

        Returns:
            Dict mapping engine name -> OCRResult
        """
        results = {}

        # Filter engines: if Bangla is requested, only run engines that support Bangla
        engines_to_run = self._engines
        if languages:
            if "bn" in languages:
                engines_to_run = [e for e in self._engines if "bn" in e.supported_languages]
                logger.info(f"Page contains Bangla; running only Bangla-capable engines: {[e.name for e in engines_to_run]}")
            else:
                engines_to_run = [e for e in self._engines if any(lang in e.supported_languages for lang in languages)]

        if not engines_to_run:
            logger.warning("No OCR engines match the requested languages. Using all registered engines as fallback.")
            engines_to_run = self._engines

        def _run_engine(engine: BaseOCREngine) -> tuple[str, OCRResult | None]:
            try:
                result = engine.recognize(image, languages)
                return engine.name, result
            except Exception as e:
                logger.error(f"Engine {engine.name} failed: {e}")
                return engine.name, None

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = {
                executor.submit(_run_engine, engine): engine
                for engine in engines_to_run
            }
            for future in as_completed(futures):
                name, result = future.result()
                if result is not None:
                    results[name] = result

        logger.info(
            f"OCR ensemble: {len(results)}/{len(self._engines)} engines succeeded"
        )
        return results

    def fuse_results(self, engine_results: dict[str, OCRResult]) -> OCRResult:
        """
        Fuse results from multiple OCR engines using weighted voting.

        Algorithm:
        1. Collect all words from all engines
        2. Build spatial clusters by matching words with overlapping bboxes
        3. For each cluster, select the best word using weighted voting
        4. Reconstruct lines from selected words

        For Bangla-dominant pages with few engines, falls back to line-level
        fusion which produces much better results than word-level alignment.
        """
        if not engine_results:
            return OCRResult(engine="ensemble")

        if len(engine_results) == 1:
            # Single engine, use directly
            name, result = next(iter(engine_results.items()))
            result.engine = "ensemble"
            return result

        start_time = time.time()

        # Check if this is a Bangla-dominant page (any engine supports it)
        is_bangla_page = any(
            name in BANGLA_CAPABLE_ENGINES for name in engine_results
        )

        if is_bangla_page:
            # Use line-level fusion for Bangla pages — more reliable
            fused_result = self._fuse_line_level(engine_results)
        else:
            fused_result = self._fuse_word_level(engine_results)

        elapsed = (time.time() - start_time) * 1000
        total_engine_time = sum(r.processing_time_ms for r in engine_results.values())
        fused_result.processing_time_ms = elapsed + total_engine_time
        return fused_result

    def _fuse_line_level(self, engine_results: dict[str, OCRResult]) -> OCRResult:
        """
        Line-level fusion: align entire lines by y-coordinate overlap,
        then pick the best line text from the highest-weighted engine.
        Much more reliable for Bangla than word-level IoU matching.
        """
        # Collect all lines from all engines with their weights
        all_engine_lines: list[tuple[OCRLine, str, float]] = []
        for engine_name, result in engine_results.items():
            weight = self._weights.get(engine_name, 0.5)
            for line in result.lines:
                all_engine_lines.append((line, engine_name, weight))

        if not all_engine_lines:
            return OCRResult(engine="ensemble")

        # Cluster lines by vertical overlap
        line_clusters: list[list[tuple[OCRLine, str, float]]] = []
        used = set()

        for i, (line_i, eng_i, w_i) in enumerate(all_engine_lines):
            if i in used:
                continue
            cluster = [(line_i, eng_i, w_i)]
            used.add(i)
            y_center_i = (line_i.bbox[1] + line_i.bbox[3]) / 2
            height_i = max(line_i.bbox[3] - line_i.bbox[1], 10)

            for j, (line_j, eng_j, w_j) in enumerate(all_engine_lines):
                if j in used or eng_j == eng_i:
                    continue
                y_center_j = (line_j.bbox[1] + line_j.bbox[3]) / 2
                if abs(y_center_i - y_center_j) < height_i * 0.7:
                    cluster.append((line_j, eng_j, w_j))
                    used.add(j)

            line_clusters.append(cluster)

        # For each cluster, pick the best line
        fused_lines = []
        fused_words = []
        line_id = 0

        for cluster in sorted(line_clusters, key=lambda c: c[0][0].bbox[1]):
            # Score each line: weight * confidence * text_length_bonus
            best_line = None
            best_score = -1.0

            for line, eng_name, weight in cluster:
                text_len_bonus = min(len(line.text) / 10.0, 2.0) if line.text else 0
                score = weight * line.confidence * (1 + text_len_bonus)
                if score > best_score:
                    best_score = score
                    best_line = line

            if best_line and best_line.text.strip():
                # Update line/word IDs
                best_line.line_id = line_id
                for wi, word in enumerate(best_line.words):
                    word.line_id = line_id
                    word.word_index = wi
                    word.engine = "ensemble"
                    fused_words.append(word)
                best_line.confidence = best_score / max(len(cluster), 1)
                fused_lines.append(best_line)
                line_id += 1

        result = OCRResult(
            lines=fused_lines,
            words=fused_words,
            engine="ensemble",
        )
        result.compute_full_text()
        result.compute_overall_confidence()
        return result

    def _fuse_word_level(self, engine_results: dict[str, OCRResult]) -> OCRResult:
        """Original word-level fusion using IoU-based spatial clustering."""
        # Step 1: Collect all words with their engine weights
        all_candidates: list[tuple[OCRWord, float]] = []
        for engine_name, result in engine_results.items():
            weight = self._weights.get(engine_name, 0.5)
            for word in result.words:
                all_candidates.append((word, weight))

        # Step 2: Cluster words by spatial proximity (IoU-based)
        clusters = self._cluster_words(all_candidates)

        # Step 3: Vote within each cluster
        fused_words = []
        for cluster in clusters:
            best_word = self._vote(cluster)
            if best_word:
                fused_words.append(best_word)

        # Step 4: Reconstruct lines from fused words
        lines = self._reconstruct_lines(fused_words)

        result = OCRResult(
            lines=lines,
            words=fused_words,
            engine="ensemble",
        )
        result.compute_full_text()
        result.compute_overall_confidence()
        return result

    def _cluster_words(
        self,
        candidates: list[tuple[OCRWord, float]],
    ) -> list[list[tuple[OCRWord, float]]]:
        """
        Group word candidates by spatial overlap using IoU-based matching.
        Words from different engines with overlapping bboxes form a cluster.
        """
        if not candidates:
            return []

        clusters: list[list[tuple[OCRWord, float]]] = []
        used = set()

        for i, (word_i, weight_i) in enumerate(candidates):
            if i in used:
                continue

            cluster = [(word_i, weight_i)]
            used.add(i)

            for j, (word_j, weight_j) in enumerate(candidates):
                if j in used:
                    continue
                # Don't cluster words from the same engine
                if word_j.engine == word_i.engine:
                    continue

                iou = compute_iou(word_i.bbox, word_j.bbox)
                if iou >= self._iou_threshold:
                    cluster.append((word_j, weight_j))
                    used.add(j)

            clusters.append(cluster)

        return clusters

    def _vote(
        self,
        cluster: list[tuple[OCRWord, float]],
    ) -> OCRWord | None:
        """
        Select the best word from a cluster using weighted voting.

        Strategy:
        1. Group candidates by text similarity (Levenshtein clustering)
        2. Calculate weighted score for each text group
        3. Select the group with highest score
        4. Return the candidate with highest individual confidence from that group
        """
        if not cluster:
            return None

        if len(cluster) == 1:
            word, weight = cluster[0]
            word.confidence = word.confidence * weight
            return word

        # Group by text similarity
        text_groups: dict[str, list[tuple[OCRWord, float]]] = {}

        for word, weight in cluster:
            normalized = normalize_text(word.text)
            if not normalized:
                continue

            # Find matching group
            matched = False
            for group_text in list(text_groups.keys()):
                distance = levenshtein_distance(normalized, group_text)
                max_len = max(len(normalized), len(group_text), 1)
                similarity = 1 - (distance / max_len)
                if similarity >= 0.7:  # 70% similarity threshold
                    text_groups[group_text].append((word, weight))
                    matched = True
                    break

            if not matched:
                text_groups[normalized] = [(word, weight)]

        if not text_groups:
            return cluster[0][0] if cluster else None

        # Score each text group
        best_text = None
        best_score = -1.0

        for group_text, members in text_groups.items():
            # Score = sum of (confidence * engine_weight) for all agreeing engines
            score = sum(word.confidence * weight for word, weight in members)
            # Bonus for more engines agreeing
            agreement_bonus = len(members) / len(cluster)
            total_score = score * (1 + agreement_bonus)

            if total_score > best_score:
                best_score = total_score
                best_text = group_text

        if best_text is None:
            return cluster[0][0]

        # Select the best candidate from the winning group
        winning_group = text_groups[best_text]
        best_candidate = max(
            winning_group, key=lambda x: x[0].confidence * x[1]
        )

        result_word = OCRWord(
            text=devanagari_to_bengali(best_candidate[0].text),
            bbox=best_candidate[0].bbox,
            confidence=best_score / max(len(cluster), 1),
            language=best_candidate[0].language,
            engine="ensemble",
            line_id=best_candidate[0].line_id,
            word_index=best_candidate[0].word_index,
        )
        return result_word

    def _reconstruct_lines(self, words: list[OCRWord]) -> list[OCRLine]:
        """
        Reconstruct text lines from scattered words using spatial clustering.
        Groups words that are vertically aligned into lines, sorted left-to-right.
        """
        if not words:
            return []

        # Sort words by y-center coordinate
        words_sorted = sorted(words, key=lambda w: (w.bbox[1] + w.bbox[3]) / 2)

        lines = []
        current_line_words = [words_sorted[0]]
        current_y_center = (words_sorted[0].bbox[1] + words_sorted[0].bbox[3]) / 2

        for word in words_sorted[1:]:
            word_y_center = (word.bbox[1] + word.bbox[3]) / 2
            word_height = word.bbox[3] - word.bbox[1]

            # If y-center is within half the word height, same line
            if abs(word_y_center - current_y_center) < max(word_height * 0.5, 10):
                current_line_words.append(word)
            else:
                # Finalize current line
                line = self._build_line(current_line_words, len(lines))
                lines.append(line)
                current_line_words = [word]
                current_y_center = word_y_center

        # Don't forget the last line
        if current_line_words:
            line = self._build_line(current_line_words, len(lines))
            lines.append(line)

        return lines

    def _build_line(self, words: list[OCRWord], line_id: int) -> OCRLine:
        """Build an OCRLine from a list of words, sorted left-to-right."""
        # Sort words by x-coordinate (left to right)
        words_sorted = sorted(words, key=lambda w: w.bbox[0])

        # Update word metadata
        for i, word in enumerate(words_sorted):
            word.line_id = line_id
            word.word_index = i

        line = OCRLine(words=words_sorted, line_id=line_id)
        line.compute_text()
        line.compute_bbox()
        line.confidence = (
            sum(w.confidence for w in words_sorted) / len(words_sorted)
            if words_sorted
            else 0.0
        )
        return line

    def recognize(
        self,
        image: np.ndarray,
        languages: list[str] | None = None,
    ) -> OCRResult:
        """
        Complete ensemble recognition pipeline.

        1. Run all engines in parallel
        2. Fuse results with weighted voting
        3. Return unified OCRResult
        """
        # Run all engines
        engine_results = self.run_all_engines(image, languages)

        if len(engine_results) < self._min_engines:
            logger.warning(
                f"Only {len(engine_results)}/{self._min_engines} minimum engines succeeded"
            )

        # Fuse results
        fused = self.fuse_results(engine_results)

        # Store per-engine results as metadata
        fused_dict = fused.to_dict()
        fused_dict["per_engine"] = {
            name: {
                "word_count": len(result.words),
                "confidence": result.overall_confidence,
                "time_ms": result.processing_time_ms,
            }
            for name, result in engine_results.items()
        }

        return fused

    def get_low_confidence_words(
        self,
        result: OCRResult,
        threshold: float | None = None,
    ) -> list[OCRWord]:
        """Get words below the confidence threshold (candidates for vision validation)."""
        threshold = threshold or self._confidence_threshold
        return [w for w in result.words if w.confidence < threshold]

    def cleanup_all(self) -> None:
        """Release resources from all engines."""
        for engine in self._engines:
            try:
                engine.cleanup()
            except Exception as e:
                logger.warning(f"Cleanup failed for {engine.name}: {e}")


def create_ensemble() -> OCREnsemble:
    """
    Factory function to create an OCR ensemble with all enabled engines.
    Reads engine toggles from application settings.
    Gracefully skips engines that fail to import.
    """
    engines = []

    engine_configs = [
        (settings.enable_tesseract, "engines.ocr.tesseract_engine", "TesseractOCREngine"),
        (settings.enable_easyocr, "engines.ocr.easyocr_engine", "EasyOCREngine"),
        (settings.enable_paddleocr, "engines.ocr.paddle_engine", "PaddleOCREngine"),
        (settings.enable_surya, "engines.ocr.surya_engine", "SuryaOCREngine"),
        (settings.enable_trocr, "engines.ocr.trocr_engine", "TrOCREngine"),
        (settings.enable_doctr, "engines.ocr.doctr_engine", "DocTREngine"),
    ]

    for enabled, module_path, class_name in engine_configs:
        if not enabled:
            continue
        try:
            import importlib
            module = importlib.import_module(module_path)
            engine_class = getattr(module, class_name)
            engines.append(engine_class())
            logger.info(f"Registered OCR engine: {class_name}")
        except Exception as e:
            logger.warning(f"Could not register {class_name}: {e}")

    if not engines:
        logger.warning("No OCR engines could be registered! OCR will produce empty results.")

    # Use min(len(engines), settings value) so we don't require more engines than available
    min_engines = min(len(engines), settings.ensemble_min_engines) if engines else 0

    ensemble = OCREnsemble(
        engines=engines,
        min_engines=max(min_engines, 1),
        confidence_threshold=settings.ocr_confidence_threshold,
    )

    logger.info(f"OCR Ensemble created with {len(engines)} engines, min_engines={max(min_engines, 1)}")
    return ensemble
