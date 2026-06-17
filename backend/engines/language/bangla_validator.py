"""
Bangla Validator — Complete Bangla text validation pipeline.

Orchestrates dictionary lookup, spell checking, and character verification
to detect and correct OCR errors in Bangla text.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.utils.text_utils import is_bangla_text

logger = logging.getLogger(__name__)

# Bangla Unicode ranges
BANGLA_VOWELS = set("অআইঈউঊঋএঐওঔ")
BANGLA_CONSONANTS = set("কখগঘঙচছজঝঞটঠডঢণতথদধনপফবভমযরলশষসহড়ঢ়য়")
BANGLA_VOWEL_SIGNS = set("ািীুূৃেৈোৌ")
BANGLA_SPECIAL = set("ংঃঁ্ৎ")
BANGLA_DIGITS = set("০১২৩৪৫৬৭৮৯")

ALL_BANGLA_CHARS = BANGLA_VOWELS | BANGLA_CONSONANTS | BANGLA_VOWEL_SIGNS | BANGLA_SPECIAL | BANGLA_DIGITS

# Common OCR confusion pairs in Bangla
OCR_CONFUSIONS = {
    "ব": ["র", "ৰ"],
    "ম": ["শ", "হ"],
    "ন": ["ণ"],
    "শ": ["ষ", "স"],
    "জ": ["য"],
    "ত": ["ৎ"],
    "প": ["ফ"],
    "দ": ["ধ"],
    "ক": ["খ"],
}


@dataclass
class ValidationResult:
    """Result of validating a single word."""
    word: str
    is_valid: bool
    issues: list[str]
    suggestions: list[str]
    confidence_adjustment: float  # Multiplier to apply to OCR confidence


class BanglaValidator:
    """Comprehensive Bangla text validation engine."""

    def __init__(self, dictionary_path: str | None = None):
        self._dictionary: set[str] = set()
        self._dictionary_path = dictionary_path
        self._trie_root: dict = {}
        self._loaded = False

    def load_dictionary(self) -> None:
        """Load Bangla dictionary from file."""
        if self._loaded:
            return

        if self._dictionary_path:
            try:
                from pathlib import Path
                path = Path(self._dictionary_path)
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        for line in f:
                            word = line.strip()
                            if word:
                                self._dictionary.add(word)
                                self._add_to_trie(word)
                    logger.info(f"Loaded {len(self._dictionary)} Bangla dictionary words")
            except Exception as e:
                logger.warning(f"Could not load dictionary: {e}")

        # Add common Bangla words as fallback
        common_words = [
            "এবং", "করে", "হয়", "করা", "যে", "এই", "তার", "থেকে", "সাথে",
            "দিয়ে", "বলে", "আর", "কিন্তু", "অথবা", "যদি", "তাহলে", "কারণ",
            "একটি", "সেই", "তিনি", "আমি", "তুমি", "আমরা", "তারা", "কোন",
            "নিচে", "উপরে", "মধ্যে", "বাংলাদেশ", "শিক্ষা", "বিদ্যালয়",
            "পাঠ", "অধ্যায়", "প্রশ্ন", "উত্তর", "সমস্যা", "সমাধান",
        ]
        for word in common_words:
            self._dictionary.add(word)
            self._add_to_trie(word)

        self._loaded = True

    def _add_to_trie(self, word: str) -> None:
        """Add a word to the trie for fast prefix lookup."""
        node = self._trie_root
        for char in word:
            if char not in node:
                node[char] = {}
            node = node[char]
        node["$"] = True  # End-of-word marker

    def _trie_search(self, word: str) -> bool:
        """Check if a word exists in the trie."""
        node = self._trie_root
        for char in word:
            if char not in node:
                return False
            node = node[char]
        return "$" in node

    def validate_word(self, word: str) -> ValidationResult:
        """Validate a single Bangla word."""
        self.load_dictionary()
        issues = []
        suggestions = []
        confidence = 1.0

        if not word or not is_bangla_text(word):
            return ValidationResult(
                word=word, is_valid=True, issues=[], suggestions=[],
                confidence_adjustment=1.0,
            )

        # 1. Character-level verification
        char_issues = self._verify_characters(word)
        issues.extend(char_issues)
        if char_issues:
            confidence *= 0.7

        # 2. Dictionary lookup
        if self._dictionary and word not in self._dictionary:
            # Try to find similar words
            similar = self._find_similar_words(word, max_results=3)
            if similar:
                issues.append(f"Word not in dictionary: '{word}'")
                suggestions.extend(similar)
                confidence *= 0.8
            else:
                # Could be a valid word not in our dictionary
                confidence *= 0.9

        # 3. Check for common OCR corruption patterns
        corruption = self._check_ocr_corruption(word)
        if corruption:
            issues.extend(corruption["issues"])
            suggestions.extend(corruption["suggestions"])
            confidence *= 0.6

        is_valid = len(issues) == 0

        return ValidationResult(
            word=word,
            is_valid=is_valid,
            issues=issues,
            suggestions=suggestions,
            confidence_adjustment=confidence,
        )

    def validate_text(self, text: str) -> dict:
        """
        Validate all Bangla words in a text.

        Returns:
            {
                'total_words': int,
                'valid_words': int,
                'invalid_words': list[ValidationResult],
                'corrected_text': str,
                'confidence': float
            }
        """
        self.load_dictionary()
        words = text.split()
        results = []
        corrected_words = []
        valid_count = 0

        for word in words:
            if is_bangla_text(word):
                result = self.validate_word(word)
                results.append(result)
                if result.is_valid:
                    valid_count += 1
                    corrected_words.append(word)
                elif result.suggestions:
                    corrected_words.append(result.suggestions[0])
                else:
                    corrected_words.append(word)
            else:
                valid_count += 1
                corrected_words.append(word)

        bangla_words = [r for r in results]
        overall_confidence = (
            valid_count / len(words) if words else 1.0
        )

        return {
            "total_words": len(words),
            "bangla_words": len(bangla_words),
            "valid_words": valid_count,
            "invalid_words": [
                {
                    "word": r.word,
                    "issues": r.issues,
                    "suggestions": r.suggestions,
                }
                for r in results if not r.is_valid
            ],
            "corrected_text": " ".join(corrected_words),
            "confidence": overall_confidence,
        }

    def _verify_characters(self, word: str) -> list[str]:
        """Verify character-level integrity of a Bangla word."""
        issues = []

        for i, char in enumerate(word):
            # Skip non-Bangla characters
            if not ("\u0980" <= char <= "\u09FF"):
                continue

            # Check for isolated vowel signs (should follow a consonant)
            if char in BANGLA_VOWEL_SIGNS:
                if i == 0:
                    issues.append(f"Vowel sign '{char}' at word start")
                elif word[i - 1] in BANGLA_VOWEL_SIGNS:
                    issues.append(f"Double vowel sign at position {i}")

            # Check for hasanta (virama) placement
            if char == "্":
                if i == 0 or i == len(word) - 1:
                    issues.append(f"Misplaced hasanta at position {i}")

        return issues

    def _check_ocr_corruption(self, word: str) -> dict | None:
        """Check for common OCR corruption patterns in Bangla."""
        issues = []
        suggestions = []

        # Check for repeated characters that are likely OCR errors
        for i in range(len(word) - 2):
            if word[i] == word[i + 1] == word[i + 2]:
                issues.append(f"Triple character repetition: '{word[i]}'")

        # Check known confusion pairs
        for correct, confusions in OCR_CONFUSIONS.items():
            for confused in confusions:
                if confused in word:
                    corrected = word.replace(confused, correct)
                    if corrected in self._dictionary:
                        issues.append(f"Possible OCR confusion: '{confused}' → '{correct}'")
                        suggestions.append(corrected)

        if issues:
            return {"issues": issues, "suggestions": suggestions}
        return None

    def _find_similar_words(self, word: str, max_results: int = 3) -> list[str]:
        """Find similar words in the dictionary using edit distance."""
        from app.utils.text_utils import levenshtein_distance

        if not self._dictionary:
            return []

        candidates = []
        for dict_word in self._dictionary:
            if abs(len(dict_word) - len(word)) > 2:
                continue
            dist = levenshtein_distance(word, dict_word)
            if dist <= 2:
                candidates.append((dict_word, dist))

        candidates.sort(key=lambda x: x[1])
        return [w for w, _ in candidates[:max_results]]
