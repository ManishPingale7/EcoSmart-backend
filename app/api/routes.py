from fastapi import APIRouter, Depends
from ..auth.router import get_current_authority, get_optional_authority
from .waste_validation import router as waste_router
from .waste_reports import router as reports_router
from .user import router as user_router
from .badges import router as badges_router
from .digital_wallet import router as digital_wallet_router
from .pickup import router as pickup_router
from .city import router as city_router

router = APIRouter(prefix="/api", tags=["API"])

# Include waste validation routes under /api/waste path
router.include_router(waste_router, prefix="/waste")

# Include waste reports management routes
router.include_router(reports_router, prefix="/waste")

# Include user routes
router.include_router(user_router, prefix="")

# Include badge system routes
router.include_router(badges_router, prefix="/badges")

# Include digital wallet routes
router.include_router(digital_wallet_router, prefix="/digital-wallet")

# Include pickup routes
router.include_router(pickup_router, prefix="/pickup")

# Include city leaderboard routes
router.include_router(city_router, prefix="/cities")

 