from fastapi import APIRouter, Depends
from ..auth.router import get_current_authority
from .waste_validation import router as waste_router

router = APIRouter(prefix="/api", tags=["API"])

# Include waste validation routes under /api/waste path
router.include_router(waste_router, prefix="/waste")

 