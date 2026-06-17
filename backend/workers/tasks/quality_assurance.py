"""Quality Assurance Task — Stage 10"""
from __future__ import annotations
import logging
from app.models.document import Document
from app.models.page import Page
from app.models.report import Report
logger = logging.getLogger(__name__)

def run_qa(document_id: str, job_id: str) -> dict:
    from workers.tasks.orchestrator import get_sync_db
    from qa.qa_pipeline import QAPipeline, ReportGenerator
    db = get_sync_db()
    try:
        pages = db.query(Page).filter(Page.document_id == document_id).order_by(Page.page_number).all()
        pages_data = [{"page_number": p.page_number, "ocr": p.ocr_json or {}, "layout": p.layout_json or {}, "tables": p.tables_json or [], "equations": p.equations_json or []} for p in pages]
        qa = QAPipeline()
        result = qa.run(pages_data)
        gen = ReportGenerator()
        for report_data in [gen.generate_qa_report(result), gen.generate_error_report(result), gen.generate_confidence_report(result)]:
            report = Report(document_id=document_id, report_type=report_data["report_type"], overall_score=report_data.get("overall_score"), data=report_data.get("data", report_data))
            db.add(report)
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc: doc.overall_confidence = result.overall_score
        for page_r in result.page_results:
            page = db.query(Page).filter(Page.document_id == document_id, Page.page_number == page_r.page_number).first()
            if page: page.overall_confidence = page_r.overall_score
        db.commit()
        return {"status": "success", "overall_score": result.overall_score}
    finally: db.close()
