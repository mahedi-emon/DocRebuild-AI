"""
Text Utilities — String processing, normalization, and comparison helpers.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


def normalize_text(text: str) -> str:
    """Normalize Unicode text (NFC form), strip extra whitespace."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def text_similarity(text1: str, text2: str) -> float:
    """Calculate similarity ratio between two strings using SequenceMatcher."""
    if not text1 and not text2:
        return 1.0
    if not text1 or not text2:
        return 0.0
    return SequenceMatcher(None, text1, text2).ratio()


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate the Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]


def is_bangla_text(text: str) -> bool:
    """Check if text contains predominantly Bangla characters."""
    if not text:
        return False
    bangla_chars = sum(1 for c in text if "\u0980" <= c <= "\u09FF")
    alpha_chars = sum(1 for c in text if c.isalpha() or "\u0980" <= c <= "\u09FF")
    if alpha_chars == 0:
        return False
    return bangla_chars / alpha_chars > 0.5


def is_english_text(text: str) -> bool:
    """Check if text contains predominantly English (Latin) characters."""
    if not text:
        return False
    latin_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    alpha_chars = sum(1 for c in text if c.isalpha() or "\u0980" <= c <= "\u09FF")
    if alpha_chars == 0:
        return False
    return latin_chars / alpha_chars > 0.5


def detect_language(text: str) -> str:
    """Detect primary language of text: 'bn', 'en', or 'mixed'."""
    if not text or not text.strip():
        return "unknown"
    if is_bangla_text(text):
        return "bn"
    if is_english_text(text):
        return "en"
    return "mixed"


def clean_ocr_artifacts(text: str) -> str:
    """Remove common OCR artifacts and noise characters."""
    # Remove isolated special characters that are likely noise
    text = re.sub(r"(?<!\w)[|\\/_~`]{1,3}(?!\w)", "", text)
    # Fix common OCR substitutions
    text = text.replace("rn", "m") if "rn" in text else text
    # Remove excessive punctuation
    text = re.sub(r"([.!?]){3,}", r"\1\1\1", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def make_json_serializable(obj):
    """Recursively convert numpy data types to native Python types for JSON serialization."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(x) for x in obj]
    elif isinstance(obj, tuple):
        return tuple(make_json_serializable(x) for x in obj)
    elif isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return make_json_serializable(obj.tolist())
    else:
        return obj


def devanagari_to_bengali(text: str) -> str:
    """
    Transliterate Devanagari Unicode characters (0x0900 - 0x097F) 
    to their Bengali script equivalents (0x0980 - 0x09FF).
    """
    if not text:
        return text
    result = []
    for char in text:
        code = ord(char)
        # Devanagari range
        if 0x0900 <= code <= 0x097F:
            # Special character mappings
            if code == 0x0935:  # व -> ব
                result.append('\u09ac')
            elif code == 0x0930:  # र -> র
                result.append('\u09b0')
            else:
                # Standard offset shift
                shifted = code + 0x0080
                if 0x0980 <= shifted <= 0x09FF:
                    result.append(chr(shifted))
                else:
                    result.append(char)
        else:
            result.append(char)
    return "".join(result)

