import sys
import os
import json
import logging

# Ensure sys.stdout handles UTF-8
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add backend to path (go up two levels from backend/workers/tasks)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

def run_sub(document_id: str):
    from app.models.document import Document
    from app.config import get_settings
    from workers.tasks.orchestrator import get_sync_db
    
    settings = get_settings()
    db = get_sync_db()
    
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error(f"Document {document_id} not found")
            sys.exit(1)
            
        results = {}
        
        # Try Marker first (generally better for Bangla books)
        if settings.enable_marker:
            try:
                from engines.understanding.marker_engine import MarkerEngine
                logger.info("Initializing Marker engine in subprocess...")
                engine = MarkerEngine()
                marker_result = engine.understand(doc.file_path)
                results["marker"] = marker_result
                logger.info(
                    f"Marker completed: {len(marker_result.get('markdown', ''))} characters "
                    f"in {marker_result.get('processing_time_ms', 0):.0f}ms"
                )
                engine.cleanup()
            except Exception as e:
                logger.warning(f"Marker engine failed in subprocess: {e}")
        else:
            logger.info("Marker engine is disabled in configuration")
            
        # Try Docling as secondary/fallback
        if settings.enable_docling:
            try:
                from engines.understanding.docling_engine import DoclingEngine
                logger.info("Initializing Docling engine in subprocess...")
                engine = DoclingEngine()
                docling_result = engine.understand(doc.file_path)
                results["docling"] = docling_result
                logger.info(
                    f"Docling completed: {len(docling_result.get('markdown', ''))} characters "
                    f"in {docling_result.get('processing_time_ms', 0):.0f}ms"
                )
                engine.cleanup()
            except Exception as e:
                logger.warning(f"Docling engine failed in subprocess: {e}")
        else:
            logger.info("Docling engine is disabled in configuration")
            
        # Save results
        best_markdown = ""
        best_engine = ""
        if "marker" in results and results["marker"].get("markdown"):
            best_markdown = results["marker"]["markdown"]
            best_engine = "marker"
        elif "docling" in results and results["docling"].get("markdown"):
            best_markdown = results["docling"]["markdown"]
            best_engine = "docling"
            
        if best_markdown:
            understanding_data = json.dumps({
                "engine": best_engine,
                "markdown": best_markdown,
                "engines_tried": list(results.keys()),
            }, ensure_ascii=False)
            doc.understanding_json = understanding_data
            db.commit()
            logger.info(
                f"Successfully saved {len(best_markdown)} chars of understanding text "
                f"from {best_engine} engine"
            )
        else:
            logger.warning("No understanding text extracted by any engine in subprocess")
            
    except Exception as e:
        logger.error(f"Error in document understanding subprocess execution: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Usage: python run_understanding_sub.py <document_id>")
        sys.exit(1)
    run_sub(sys.argv[1])
