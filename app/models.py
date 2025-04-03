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

class WasteReport(BaseModel):
    id: str
    validation_result: Dict[str, Any]
    submitted_by: Dict[str, Any] = {}
    severity: str
    location: str
    description: Optional[str] = None
    timestamp: str
    is_valid: bool
    confidence_score: float = 0
    status: WasteReportStatus = WasteReportStatus.PENDING
    created_at: datetime
    updated_at: datetime
    comments: Optional[List[Dict[str, Any]]] = []
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

    @classmethod
    def from_mongo(cls, mongo_doc: Dict[str, Any]):
        """
        Convert a MongoDB document to a Pydantic model, handling ObjectId conversion
        """
        if mongo_doc is None:
            return None
            
        # Convert _id to id string
        if "_id" in mongo_doc:
            mongo_doc["id"] = str(mongo_doc.pop("_id"))
            
        # Convert any ObjectId in nested dictionaries to strings
        cls._convert_object_ids(mongo_doc)
        
        return cls(**mongo_doc)
    
    @staticmethod
    def _convert_object_ids(data):
        """Recursively convert all ObjectId instances to strings"""
        from bson import ObjectId
        
        if isinstance(data, dict):
            for key, value in list(data.items()):
                if isinstance(value, ObjectId):
                    data[key] = str(value)
                elif isinstance(value, (dict, list)):
                    WasteReport._convert_object_ids(value)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, ObjectId):
                    data[i] = str(item)
                elif isinstance(item, (dict, list)):
                    WasteReport._convert_object_ids(item) 