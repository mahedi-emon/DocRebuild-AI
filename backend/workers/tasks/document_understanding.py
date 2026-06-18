"""Document Understanding Task — Stage 4

Runs document understanding engines (Docling, Marker) to extract
high-quality structured text (markdown). Results are stored in the
Document model and used as the primary text source during DOCX reconstruction.
"""
from __future__ import annotations
import json
import logging
from app.models.document import Document
from app.config import get_settings
logger = logging.getLogger(__name__)
settings = get_settings()

def understand_document(document_id: str, job_id: str) -> dict:
    import subprocess
    import sys
    import os

    script_path = os.path.join(os.path.dirname(__file__), "run_understanding_sub.py")
    python_exe = sys.executable or "python"

    logger.info(f"Running document understanding in subprocess for document {document_id}...")
    try:
        # Run the subprocess with a timeout of 15 minutes (900 seconds)
        result = subprocess.run(
            [python_exe, script_path, document_id],
            capture_output=True,
            text=True,
            timeout=900,
        )
        if result.returncode != 0:
            logger.error(f"Understanding subprocess failed with exit code {result.returncode}")
            logger.error(f"Subprocess stderr:\n{result.stderr}")
            raise RuntimeError(f"Subprocess failed with code {result.returncode}: {result.stderr}")

        logger.info("Understanding subprocess completed successfully")
        return {"status": "success", "note": "completed in subprocess"}
    except subprocess.TimeoutExpired:
        logger.error("Understanding subprocess timed out after 900 seconds")
        raise RuntimeError("Understanding subprocess timed out")
    except Exception as e:
        logger.error(f"Failed to run understanding subprocess: {e}")
        raise
