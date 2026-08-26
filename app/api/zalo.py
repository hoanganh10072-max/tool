from fastapi import APIRouter, HTTPException

from app.automation.exceptions import BrowserDisconnectedError, TemporaryAutomationError
from app.services.messaging_service import messaging_service

router = APIRouter(prefix="/api/zalo", tags=["zalo"])


@router.post("/open")
async def open_zalo():
    try:
        return await messaging_service.open_zalo()
    except BrowserDisconnectedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TemporaryAutomationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Không mở được Zalo Web. Hãy thử bấm Mở Zalo lại.") from exc


@router.get("/status")
async def zalo_status():
    return await messaging_service.zalo_status()
