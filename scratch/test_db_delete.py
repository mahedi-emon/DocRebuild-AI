import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import select
from app.database import async_session_factory
from app.models.document import Document
from app.models.job import Job
from app.models.report import Report
from app.models.page import Page

async def test_db():
    print("Connecting to database...")
    async with async_session_factory() as session:
        # Fetch documents
        res = await session.execute(select(Document))
        docs = res.scalars().all()
        print(f"Total documents in database: {len(docs)}")
        
        for doc in docs:
            print(f"- Doc ID: {doc.id}, Filename: {doc.original_filename}, Status: {doc.status}")
            
            # Fetch jobs, reports, pages count
            jobs_res = await session.execute(select(Job).where(Job.document_id == doc.id))
            jobs = jobs_res.scalars().all()
            print(f"  Jobs count: {len(jobs)}")
            for j in jobs:
                print(f"    - Job ID: {j.id}, Status: {j.status}")
                
            pages_res = await session.execute(select(Page).where(Page.document_id == doc.id))
            pages = pages_res.scalars().all()
            print(f"  Pages count: {len(pages)}")
            
            reports_res = await session.execute(select(Report).where(Report.document_id == doc.id))
            reports = reports_res.scalars().all()
            print(f"  Reports count: {len(reports)}")
            
            # Try to delete document in a dry-run style (or commit if we want to actually test)
            print(f"Attempting to delete document: {doc.id}")
            try:
                await session.delete(doc)
                await session.flush()
                print("Flush success!")
                # Let's commit it so we actually delete the test documents
                await session.commit()
                print("Commit success! Document deleted.")
            except Exception as e:
                await session.rollback()
                print(f"FAILED to delete document: {e}")

if __name__ == "__main__":
    asyncio.run(test_db())
