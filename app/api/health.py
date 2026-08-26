from fastapi import APIRouter

from app.services.messaging_service import messaging_service

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    status = await messaging_service.zalo_status()
    return {"status": "ok", "browser": status["browser"], "zalo_login": status["zalo_login"], "zalo_status": status["status"]}
