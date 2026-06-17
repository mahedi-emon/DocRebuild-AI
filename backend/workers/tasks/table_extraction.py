"""Table Extraction Task — Stage 6"""
from __future__ import annotations
import logging, numpy as np
from PIL import Image
from app.models.page import Page
from app.utils.image_utils import crop_region
from app.config import get_settings
logger = logging.getLogger(__name__)
settings = get_settings()

def extract_tables(document_id: str, job_id: str) -> dict:
    from workers.tasks.orchestrator import get_sync_db
    db = get_sync_db()
    try:
        pages = db.query(Page).filter(Page.document_id == document_id).order_by(Page.page_number).all()
        if settings.enable_table_transformer:
            try:
                from engines.tables.table_transformer import TableTransformerEngine
                tt = TableTransformerEngine()
                for page in pages:
                    if not page.image_path: continue
                    layout = page.layout_json or {}
                    table_elements = [e for e in layout.get("elements", []) if e.get("type") == "table"]
                    if not table_elements: continue
                    image = np.array(Image.open(page.image_path).convert("RGB"))
                    tables = []
                    for elem in table_elements:
                        bbox = elem.get("bbox", [])
                        if len(bbox) == 4:
                            table_img = crop_region(image, tuple(int(x) for x in bbox))
                            structure = tt.recognize_structure(table_img)
                            tables.append({"bbox": bbox, "structure": structure, "cells": []})
                    page.tables_json = tables
                    db.commit()
                tt.cleanup()
            except Exception as e:
                logger.warning(f"Table extraction failed: {e}")
        else:
            logger.info("Table Transformer engine is disabled in configuration")
        return {"status": "success"}
    finally: db.close()
