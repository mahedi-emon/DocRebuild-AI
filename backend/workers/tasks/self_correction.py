"""Self-Correction Task — Stage 11

Performs multi-pass correction on low-confidence OCR results:
1. Cleans OCR artifacts (noise characters, broken Unicode)
2. Normalizes Bangla text (NFC normalization, fix hasanta placement)
3. Re-validates and applies Bangla corrections
4. Updates corrected text in the database

Previously this only logged low-confidence pages without doing anything.
"""
from __future__ import annotations
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


def run_self_correction(document_id: str, job_id: str, max_passes: int = 3) -> dict:
    from workers.tasks.orchestrator import get_sync_db
    from app.models.page import Page
    from app.utils.text_utils import clean_ocr_artifacts, is_bangla_text, devanagari_to_bengali

    db = get_sync_db()
    try:
        pages = db.query(Page).filter(
            Page.document_id == document_id
        ).order_by(Page.page_number).all()

        total_corrections = 0
        passes_run = 0

        for pass_num in range(max_passes):
            pass_corrections = 0
            passes_run = pass_num + 1

            for page in pages:
                ocr = page.ocr_json or {}
                text = ocr.get("full_text", "")
                if not text:
                    continue

                confidence = ocr.get("overall_confidence", 1.0)
                original_text = text

                # Pass 1: Always clean OCR artifacts
                if pass_num == 0:
                    text = devanagari_to_bengali(text)
                    text = clean_ocr_artifacts(text)
                    text = _normalize_bangla_text(text)

                # Pass 2+: Fix specific patterns for low-confidence pages
                if confidence < 0.7:
                    text = _fix_bangla_ocr_patterns(text)
                    text = _remove_garbage_characters(text)

                # Check if text was actually changed
                if text != original_text:
                    ocr["full_text"] = text
                    if pass_num == 0:
                        ocr["full_text_pre_correction"] = original_text

                    # Also update line texts if available
                    if "lines" in ocr:
                        _update_line_texts(ocr, text)

                    page.ocr_json = ocr
                    db.commit()
                    pass_corrections += 1
                    logger.info(
                        f"Pass {pass_num + 1}: Page {page.page_number} corrected "
                        f"(conf={confidence:.2f})"
                    )

            total_corrections += pass_corrections
            if pass_corrections == 0:
                break

        logger.info(
            f"Self-correction complete: {total_corrections} corrections "
            f"across {passes_run} passes"
        )
        return {
            "status": "success",
            "corrections": total_corrections,
            "passes": passes_run,
        }
    finally:
        db.close()


def _normalize_bangla_text(text: str) -> str:
    """Normalize Bangla text: NFC normalization, fix common Unicode issues."""
    # NFC normalization for consistent character representation
    text = unicodedata.normalize("NFC", text)

    # Fix common Bangla Unicode issues
    # Remove zero-width characters that break text
    text = text.replace("\u200b", "")  # Zero-width space
    text = text.replace("\u200c", "")  # Zero-width non-joiner (keep where valid)
    text = text.replace("\u200d", "")  # Zero-width joiner (keep where valid)
    text = text.replace("\ufeff", "")  # BOM

    # Fix double hasanta (্্ -> ্)
    text = re.sub(r"্{2,}", "্", text)

    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _fix_bangla_ocr_patterns(text: str) -> str:
    """Fix known OCR error patterns specific to Bangla."""
    # Fix common Bangla OCR misrecognitions
    fixes = {
        # Digit/letter confusions
        "০0": "০",
        "0০": "০",
        "১1": "১",
        "1১": "১",
        # Common character confusions
        "রব": "র্ব",  # Missing hasanta
        "তত": "ত্ত",
        "কক": "ক্ক",
    }

    for wrong, right in fixes.items():
        if wrong in text:
            text = text.replace(wrong, right)

    return text


def _remove_garbage_characters(text: str) -> str:
    """Remove characters that are clearly OCR garbage in Bangla text."""
    # Remove isolated non-Bangla, non-English, non-punctuation characters
    # Keep: Bangla (0980-09FF), Latin (0020-007F), common punctuation, digits
    cleaned_chars = []
    for char in text:
        cp = ord(char)
        if (
            0x0980 <= cp <= 0x09FF  # Bangla
            or 0x0020 <= cp <= 0x007E  # Basic Latin
            or char in "\n\r\t।॥"  # Bangla punctuation + whitespace
            or cp in (0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D)  # Smart quotes/dashes
        ):
            cleaned_chars.append(char)
    return "".join(cleaned_chars)


def _update_line_texts(ocr: dict, corrected_full_text: str) -> None:
    """Try to update individual line texts from corrected full text."""
    lines = ocr.get("lines", [])
    corrected_lines = corrected_full_text.split("\n")

    # Simple mapping: if line counts match roughly, update 1:1
    if lines and len(corrected_lines) >= len(lines):
        for i, line in enumerate(lines):
            if i < len(corrected_lines):
                line["text"] = corrected_lines[i]
