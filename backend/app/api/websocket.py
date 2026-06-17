"""
WebSocket API — Real-time job progress updates.
"""

from __future__ import annotations

import json
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.job import Job, JobStatus

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections per job_id."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)

    def disconnect(self, websocket: WebSocket, job_id: str):
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def broadcast_to_job(self, job_id: str, message: dict):
        """Send a message to all WebSocket clients watching a specific job."""
        if job_id in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.append(connection)
            # Clean up dead connections
            for dead in dead_connections:
                self.disconnect(dead, job_id)


# Global connection manager (shared across the app)
manager = ConnectionManager()


@router.websocket("/ws/jobs/{job_id}")
async def websocket_job_progress(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time job progress updates.
    Polls the database every 1 second and pushes updates to the client.
    """
    await manager.connect(websocket, job_id)

    try:
        last_progress = -1.0
        last_stage = ""

        while True:
            # Poll database for job state
            async with async_session_factory() as session:
                result = await session.execute(select(Job).where(Job.id == job_id))
                job = result.scalar_one_or_none()

            if not job:
                await websocket.send_json({"error": "Job not found"})
                break

            # Only send updates when something changes
            if job.progress != last_progress or job.current_stage != last_stage:
                last_progress = job.progress
                last_stage = job.current_stage

                update = {
                    "type": "progress",
                    "job_id": job.id,
                    "status": job.status,
                    "current_stage": job.current_stage,
                    "progress": job.progress,
                    "stage_details": job.stage_details,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                if job.error_message:
                    update["error"] = job.error_message
                    update["error_stage"] = job.error_stage

                await websocket.send_json(update)

            # Stop polling if job is finished
            if job.status in [
                JobStatus.COMPLETED.value,
                JobStatus.FAILED.value,
                JobStatus.CANCELLED.value,
            ]:
                # Send final update
                final = {
                    "type": "completed" if job.status == JobStatus.COMPLETED.value else "failed",
                    "job_id": job.id,
                    "status": job.status,
                    "progress": job.progress,
                }
                await websocket.send_json(final)
                break

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, job_id)
