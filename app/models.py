from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from bson import ObjectId

class AuthorityBase(BaseModel):
    username: str
    email: EmailStr
    role: str = "authority"

class AuthorityCreate(AuthorityBase):
    password: str

class Authority(AuthorityBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AuthorityLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class GoogleUser(BaseModel):
    email: EmailStr
    name: str
    picture: Optional[str] = None
    google_id: str

class WasteReportValidationRequest(BaseModel):
    image: str  # Base64 encoded image
    description: Optional[str] = None
    location: str  # Coordinates or address
    timestamp: datetime
    
class WasteType(BaseModel):
    types: str  # Comma-separated list of waste types
    confidence: str  # Comma-separated list of confidence values matching each waste type

class Dustbin(BaseModel):
    is_present: bool
    is_full: Optional[bool] = None
    fullness_percentage: Optional[float] = None
    waste_outside: Optional[bool] = None
    waste_outside_description: Optional[str] = None

class RecyclableItem(BaseModel):
    items: str  # Comma-separated list of recyclable items
    recyclable: bool
    notes: Optional[str] = None

class TimeAnalysis(BaseModel):
    time_appears_valid: bool
    lighting_condition: Optional[str] = None
    notes: Optional[str] = None

class DescriptionMatch(BaseModel):
    matches_image: bool
    confidence: int
    notes: Optional[str] = None

class SeverityLevel(str, Enum):
    CLEAN = "Clean"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"

class WasteReportValidationResponse(BaseModel):
    is_valid: bool
    message: str
    confidence_score: Optional[float] = None
    
    # Waste Types (flattened)
    waste_types: str  # Comma-separated list of waste types
    waste_type_confidences: str  # Comma-separated list of confidence values
    
    # Severity
    severity: Optional[SeverityLevel] = None
    
    # Dustbins (flattened)
    dustbin_present: bool = False
    dustbin_full: Optional[bool] = None
    dustbin_fullness_percentage: Optional[float] = None
    waste_outside: Optional[bool] = None
    waste_outside_description: Optional[str] = None
    
    # Recyclable Items (flattened)
    recyclable_items: str  # Comma-separated list of recyclable items
    is_recyclable: bool = False
    recyclable_notes: Optional[str] = None
    
    # Time Analysis (flattened)
    time_appears_valid: bool = True
    lighting_condition: Optional[str] = None
    time_analysis_notes: Optional[str] = None
    
    # Description Match (flattened)
    description_matches_image: bool = True
    description_match_confidence: Optional[int] = None
    description_match_notes: Optional[str] = None
    
    # Additional Data
    additional_data: Optional[Dict[str, Any]] = None

class WasteReportComment(BaseModel):
    text: str
    user_id: str
    username: str
    role: str
    timestamp: datetime

class WasteReportStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"

class CleanupVerification(BaseModel):
    is_same_location: bool
    location_match_confidence: float
    location_match_reasons: List[str]
    cleanup_successful: bool
    cleanup_confidence_score: float
    observations: str
    before_condition: str
    after_condition: str
    matching_features: List[str]
    concerns: List[str]
    verified_by: Optional[Dict[str, Any]] = None
    verification_timestamp: datetime

class WasteReport(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    is_valid: bool
    message: str
    confidence_score: float
    severity: SeverityLevel
    location: str
    description: str
    timestamp: datetime
    waste_types: str
    waste_type_confidences: Optional[str] = None
    dustbin_present: bool
    dustbin_full: Optional[bool] = None
    dustbin_fullness_percentage: Optional[float] = None
    waste_outside: Optional[bool] = None
    waste_outside_description: Optional[str] = None
    recyclable_items: str
    is_recyclable: bool
    recyclable_notes: Optional[str] = None
    time_appears_valid: bool
    lighting_condition: Optional[str] = None
    time_analysis_notes: Optional[str] = None
    description_matches_image: bool
    description_match_confidence: Optional[float] = None
    description_match_notes: Optional[str] = None
    additional_data: Optional[Dict] = {}
    submitted_by: Optional[Dict] = {}
    status: str = "pending"
    image: Optional[str] = None  # Base64 encoded image
    cleanup_verification: Optional[CleanupVerification] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            ObjectId: lambda v: str(v)
        }

    @classmethod
    def from_mongo(cls, data: dict):
        """Convert MongoDB document to WasteReport model"""
        if not data:
            return None
            
        # Convert _id to string if it exists
        if "_id" in data:
            data["_id"] = str(data["_id"])
            
        # Convert timestamp to datetime if it's a string
        if "timestamp" in data and isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
            
        return cls(**data)

class CleanupVerificationResponse(BaseModel):
    """Simplified response model for cleanup verification"""
    status: str  # "verified", "not_clean", or "location_mismatch"
    is_same_location: bool
    is_clean: bool
    improvement_percentage: float 