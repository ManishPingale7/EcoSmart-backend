from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

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
    type: str
    confidence: float

class Dustbin(BaseModel):
    is_present: bool
    is_full: Optional[bool] = None
    fullness_percentage: Optional[float] = None
    waste_outside: Optional[bool] = None
    waste_outside_description: Optional[str] = None

class RecyclableItem(BaseModel):
    item: str
    recyclable: bool
    notes: Optional[str] = None

class TimeAnalysis(BaseModel):
    time_appears_valid: bool
    lighting_condition: Optional[str] = None
    notes: Optional[str] = None

class DescriptionMatch(BaseModel):
    matches_image: bool
    confidence: Optional[float] = None
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
    waste_types: Optional[List[WasteType]] = None
    severity: Optional[SeverityLevel] = None
    dustbins: Optional[List[Dustbin]] = None
    recyclable_items: Optional[List[RecyclableItem]] = None
    time_analysis: Optional[TimeAnalysis] = None
    description_match: Optional[DescriptionMatch] = None
    additional_data: Optional[Dict[str, Any]] = None 