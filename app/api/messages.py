from fastapi import APIRouter, HTTPException

from app.automation.exceptions import LoginRequiredError, UserActionRequiredError, ZaloAutomationError
from app.schemas.message import SendMessageRequest
from app.services.messaging_service import AutomationBusyError, ValidationError, messaging_service

router = APIRouter(prefix="/api/messages", tags=["messages"])


@router.post("/send")
async def send_message(payload: SendMessageRequest):
    try:
        return await messaging_service.send_single(payload.phone, payload.message)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AutomationBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (LoginRequiredError, UserActionRequiredError) as exc:
        return {"success": False, "phone": payload.phone, "status": exc.status, "message": str(exc)}
    except ZaloAutomationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
