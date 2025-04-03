from typing import Optional
from pydantic import BaseModel

class CleanupVerificationResponse(BaseModel):
    """Simplified response model for cleanup verification"""
    status: str  # "verified", "not_clean", or "location_mismatch"
    is_same_location: bool
    is_clean: bool
    improvement_percentage: float

class WasteReport(BaseModel):
    # ... existing code ... 