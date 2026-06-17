"""Math Recognition Task — Stage 7"""
from __future__ import annotations
import logging, numpy as np
from PIL import Image
from app.models.page import Page
from app.utils.image_utils import crop_region
from app.config import get_settings
logger = logging.getLogger(__name__)
settings = get_settings()

def recognize_math(document_id: str, job_id: str) -> dict:
    from workers.tasks.orchestrator import get_sync_db
    db = get_sync_db()
    try:
        pages = db.query(Page).filter(Page.document_id == document_id).order_by(Page.page_number).all()
        if settings.enable_pix2tex:
            try:
                from engines.math.pix2tex_engine import Pix2TexEngine
                pix2tex = Pix2TexEngine()
                for page in pages:
                    if not page.image_path: continue
                    layout = page.layout_json or {}
                    eq_elements = [e for e in layout.get("elements", []) if e.get("type") == "equation"]
                    if not eq_elements: continue
                    image = np.array(Image.open(page.image_path).convert("RGB"))
                    equations = []
                    for elem in eq_elements:
                        bbox = elem.get("bbox", [])
                        if len(bbox) == 4:
                            eq_img = crop_region(image, tuple(int(x) for x in bbox))
                            result = pix2tex.recognize(eq_img)
                            equations.append(result)
                    page.equations_json = equations
                    db.commit()
                pix2tex.cleanup()
            except Exception as e:
                logger.warning(f"Math recognition failed: {e}")
        else:
            logger.info("Math recognition (pix2tex) is disabled in configuration")
        return {"status": "success"}
    finally: db.close()
