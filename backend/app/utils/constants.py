"""
Constants — Shared constants used across the application.
"""

# ── Pipeline Stage Labels (for UI display) ──
STAGE_LABELS = {
    "queued": "Queued",
    "pdf_ingestion": "PDF Ingestion",
    "layout_analysis": "Layout Analysis",
    "ocr_ensemble": "OCR Ensemble",
    "document_understanding": "Document Understanding",
    "vision_validation": "Vision Validation",
    "table_extraction": "Table Extraction",
    "math_recognition": "Math Recognition",
    "bangla_validation": "Bangla Validation",
    "docx_reconstruction": "DOCX Reconstruction",
    "quality_assurance": "Quality Assurance",
    "self_correction": "Self-Correction",
    "visual_verification": "Visual Verification",
    "completed": "Completed",
    "failed": "Failed",
}

# ── Layout Element Types ──
class LayoutType:
    TITLE = "title"
    SUBTITLE = "subtitle"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    IMAGE = "image"
    FIGURE = "figure"
    CAPTION = "caption"
    EQUATION = "equation"
    EXERCISE = "exercise"
    LIST = "list"
    HEADER = "header"
    FOOTER = "footer"
    PAGE_NUMBER = "page_number"
    SIDEBAR = "sidebar"
    WORKSHEET = "worksheet"
    UNKNOWN = "unknown"


ALL_LAYOUT_TYPES = [
    LayoutType.TITLE,
    LayoutType.SUBTITLE,
    LayoutType.PARAGRAPH,
    LayoutType.TABLE,
    LayoutType.IMAGE,
    LayoutType.FIGURE,
    LayoutType.CAPTION,
    LayoutType.EQUATION,
    LayoutType.EXERCISE,
    LayoutType.LIST,
    LayoutType.HEADER,
    LayoutType.FOOTER,
    LayoutType.PAGE_NUMBER,
    LayoutType.SIDEBAR,
    LayoutType.WORKSHEET,
]

# ── OCR Engine Names ──
class OCREngine:
    SURYA = "surya"
    PADDLEOCR = "paddleocr"
    TESSERACT = "tesseract"
    EASYOCR = "easyocr"
    TROCR = "trocr"
    DOCTR = "doctr"


# ── Default OCR Ensemble Weights ──
DEFAULT_OCR_WEIGHTS = {
    OCREngine.SURYA: 1.0,
    OCREngine.PADDLEOCR: 0.9,
    OCREngine.TESSERACT: 0.6,
    OCREngine.EASYOCR: 0.8,
    OCREngine.TROCR: 0.85,
    OCREngine.DOCTR: 0.85,
}

# ── Bangla Unicode Range ──
BANGLA_UNICODE_START = 0x0980
BANGLA_UNICODE_END = 0x09FF

# ── Common Bangla OCR Error Mappings ──
BANGLA_OCR_CONFUSIONS = {
    "ব": ["র", "র্"],
    "ম": ["শ"],
    "ন": ["ণ"],
    "শ": ["ষ"],
    "জ": ["য"],
    "ত": ["ৎ"],
    "প": ["ষ"],
}

# ── Supported Page Sizes (in points, 1pt = 1/72 inch) ──
PAGE_SIZES = {
    "A4": (595.28, 841.89),
    "Letter": (612, 792),
    "Legal": (612, 1008),
    "A3": (841.89, 1190.55),
    "B5": (498.90, 708.66),
}
