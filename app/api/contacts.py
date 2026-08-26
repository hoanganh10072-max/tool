from fastapi import APIRouter, HTTPException

from app.automation.exceptions import ContactNotFoundError, LoginRequiredError, UserActionRequiredError, ZaloAutomationError
from app.schemas.contact import ContactSearchRequest
from app.services.messaging_service import AutomationBusyError, ValidationError, messaging_service

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.post("/search")
async def search_contact(payload: ContactSearchRequest):
    try:
        return await messaging_service.search_contact(payload.phone)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AutomationBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ContactNotFoundError as exc:
        return {"success": True, "phone": payload.phone, "found": False, "name": None, "status": "NOT_FOUND", "message": str(exc)}
    except (LoginRequiredError, UserActionRequiredError) as exc:
        return {"success": False, "phone": payload.phone, "found": False, "name": None, "status": exc.status, "message": str(exc)}
    except ZaloAutomationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
