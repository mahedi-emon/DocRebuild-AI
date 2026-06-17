"""Vision Validation Task — Stage 5"""
from __future__ import annotations
import logging, numpy as np
from PIL import Image
from app.models.page import Page
logger = logging.getLogger(__name__)

def validate_with_vision(document_id: str, job_id: str) -> dict:
    from workers.tasks.orchestrator import get_sync_db
    from app.config import get_settings
    
    settings = get_settings()
    db = get_sync_db()
    try:
        pages = db.query(Page).filter(Page.document_id == document_id).order_by(Page.page_number).all()
        
        # Determine which engine to use based on configuration
        engine = None
        engine_name = "None"
        
        if settings.enable_internvl:
            try:
                from engines.vision.internvl_engine import InternVLEngine
                engine = InternVLEngine()
                engine_name = "InternVL"
            except Exception as e:
                logger.error(f"Failed to import/initialize InternVL engine: {e}")
                
        if engine is None and settings.enable_qwen_vl:
            try:
                from engines.vision.qwen_vl_engine import QwenVLEngine
                engine = QwenVLEngine()
                engine_name = "Qwen-VL"
            except Exception as e:
                logger.error(f"Failed to import/initialize Qwen-VL engine: {e}")
                
        if engine is None and settings.enable_florence2:
            try:
                from engines.vision.florence2_engine import Florence2Engine
                engine = Florence2Engine()
                engine_name = "Florence-2"
            except Exception as e:
                logger.error(f"Failed to import/initialize Florence-2 engine: {e}")
                
        if engine is None:
            logger.info("No vision engines are enabled or initialized. Skipping vision validation.")
            return {"status": "skipped"}
            
        logger.info(f"Using {engine_name} engine for vision validation.")
        try:
            for page in pages:
                if not page.image_path or not page.ocr_json: continue
                image = np.array(Image.open(page.image_path).convert("RGB"))
                ocr_text = page.ocr_json.get("full_text", "")
                
                result = engine.validate_text(image, ocr_text)
                if not result["matches"]:
                    logger.info(
                        f"Page {page.page_number} ({engine_name}): Vision disagrees "
                        f"(sim={result['similarity']:.2f})"
                    )
            engine.cleanup()
        except Exception as e:
            logger.warning(f"Vision validation processing failed: {e}")
            
        return {"status": "success"}
    finally: db.close()
