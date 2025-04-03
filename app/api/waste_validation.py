from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from typing import Optional
from datetime import datetime
from ..auth.router import get_optional_authority
from ..models import WasteReportValidationRequest, WasteReportValidationResponse, WasteType, Dustbin, RecyclableItem, TimeAnalysis, DescriptionMatch, SeverityLevel, WasteReport
from ..services.gemini_service import validate_waste_image
from ..crud import waste_report as waste_report_crud
import base64
from app.services.notification_service import notification_service
import logging

# Use the same tag as the main API router to avoid duplication in Swagger docs
router = APIRouter()

# Set of severity levels that should be stored in the database
STORE_SEVERITY_LEVELS = {SeverityLevel.MEDIUM, SeverityLevel.HIGH, SeverityLevel.CRITICAL}

# Create a function that returns None when testing to bypass authentication
async def get_optional_authority(
    current_authority: Optional[dict] = Depends(get_optional_authority)
) -> Optional[dict]:
    """
    A dependency that attempts to get the current authority but returns None if it fails.
    This allows the endpoints to work without authentication during testing.
    """
    try:
        return current_authority
    except HTTPException:
        # For testing purposes only - bypass authentication if not authenticated
        return None

async def save_report_if_severe(validation_result: dict, user_data: dict = None) -> Optional[dict]:
    """
    Save a waste report to the database if its severity is Medium, High, or Critical
    
    Args:
        validation_result: The validated waste report data
        user_data: Additional user/authority data to include
        
    Returns:
        The saved report or None if not saved
    """
    # Check if severity meets the threshold for storing
    severity = validation_result.get("severity")
    
    if not severity or severity not in [level.value for level in STORE_SEVERITY_LEVELS]:
        print(f"Report with severity '{severity}' not stored in database")
        return None
    
    try:
        # Prepare report data with all fields at top level
        report_data = {
            # Basic info
            "is_valid": validation_result.get("is_valid", False),
            "message": validation_result.get("message", ""),
            "confidence_score": validation_result.get("confidence_score", 0),
            "severity": severity,
            
            # Location and description
            "location": validation_result.get("location", ""),
            "description": validation_result.get("description", ""),
            "timestamp": validation_result.get("timestamp", datetime.utcnow().isoformat()),
            
            # Store the original image
            "image": validation_result.get("image", ""),  # Store the base64 image
            
            # Waste Types
            "waste_types": validation_result.get("waste_types", {}).get("types", ""),
            "waste_type_confidences": validation_result.get("waste_types", {}).get("confidence", ""),
            
            # Dustbins
            "dustbin_present": validation_result.get("dustbins", {}).get("is_present", False),
            "dustbin_full": validation_result.get("dustbins", {}).get("is_full"),
            "dustbin_fullness_percentage": validation_result.get("dustbins", {}).get("fullness_percentage"),
            "waste_outside": validation_result.get("dustbins", {}).get("waste_outside"),
            "waste_outside_description": validation_result.get("dustbins", {}).get("waste_outside_description"),
            
            # Recyclable Items
            "recyclable_items": validation_result.get("recyclable_items", {}).get("items", ""),
            "is_recyclable": validation_result.get("recyclable_items", {}).get("recyclable", False),
            "recyclable_notes": validation_result.get("recyclable_items", {}).get("notes"),
            
            # Time Analysis
            "time_appears_valid": validation_result.get("time_analysis", {}).get("time_appears_valid", True),
            "lighting_condition": validation_result.get("time_analysis", {}).get("lighting_condition"),
            "time_analysis_notes": validation_result.get("time_analysis", {}).get("notes"),
            
            # Description Match
            "description_matches_image": validation_result.get("description_match", {}).get("matches_image", True),
            "description_match_confidence": validation_result.get("description_match", {}).get("confidence"),
            "description_match_notes": validation_result.get("description_match", {}).get("notes"),
            
            # Additional Data
            "additional_data": validation_result.get("additional_data", {}),
            
            # User Data
            "submitted_by": user_data or {},
            
            # Status
            "status": "pending"
        }
        
        # Save to database
        saved_report = await waste_report_crud.create_waste_report(report_data)
        print(f"Saved waste report with ID: {saved_report.get('id')} and severity: {severity}")
        
        # Send notification to admin
        try:
            await notification_service.send_waste_report_alert(report_data)
            logging.info(f"Notification sent for waste report {saved_report.get('id')}")
        except Exception as e:
            logging.error(f"Failed to send notification for waste report {saved_report.get('id')}: {str(e)}")
        
        # Make sure we return a serializable version of the report
        return WasteReport.from_mongo(saved_report)
    except Exception as e:
        print(f"Error saving waste report: {str(e)}")
        return None

# Make authentication optional for testing
@router.post("/validate", response_model=WasteReportValidationResponse)
async def validate_waste_report(
    image: UploadFile = File(...),
    description: Optional[str] = Form(None),
    location: str = Form(...),
    timestamp: datetime = Form(...),
    current_authority: Optional[dict] = Depends(get_optional_authority)
):
    """
    Validate a waste report image using Gemini AI
    
    - **image**: The image file showing a potentially dirty/unclean area
    - **description**: Optional description of the waste or area
    - **location**: Location where the image was taken (coordinates or address)
    - **timestamp**: When the image was taken
    
    Returns a validation response with confidence score, waste types, and severity level.
    If severity is Medium, High, or Critical, the report is stored in the database.
    """
    try:
        # Validate image file
        if not image.content_type or not image.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail=f"File must be an image. Received content type: {image.content_type}"
            )
            
        # Read the image file and convert to base64
        try:
            image_content = await image.read()
            
            # Check if image is empty
            if not image_content or len(image_content) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Image file is empty"
                )
                
            # Log image size for debugging
            image_size_kb = len(image_content) / 1024
            print(f"Received image: {image.filename}, size: {image_size_kb:.2f} KB, content-type: {image.content_type}")
            
            # Convert to base64
            base64_image = base64.b64encode(image_content).decode("utf-8")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Error reading image file: {str(e)}"
            )
        
        # Call Gemini for validation
        validation_result = await validate_waste_image(
            image=base64_image,
            description=description,
            location=location,
            timestamp=timestamp
        )
        
        # Add input data to validation result for storage
        validation_result["location"] = location
        validation_result["description"] = description
        validation_result["timestamp"] = timestamp.isoformat()
        validation_result["filename"] = image.filename
        validation_result["image"] = base64_image  # Store the base64 image
        
        # Convert the validation result to our response model
        response = WasteReportValidationResponse(
            is_valid=validation_result.get("is_valid", False),
            message=validation_result.get("message", "Validation failed"),
            confidence_score=validation_result.get("confidence_score"),
            
            # Waste Types
            waste_types=validation_result.get("waste_types", {}).get("types", ""),
            waste_type_confidences=validation_result.get("waste_types", {}).get("confidence", ""),
            
            # Severity
            severity=validation_result.get("severity"),
            
            # Dustbins
            dustbin_present=validation_result.get("dustbins", {}).get("is_present", False),
            dustbin_full=validation_result.get("dustbins", {}).get("is_full"),
            dustbin_fullness_percentage=validation_result.get("dustbins", {}).get("fullness_percentage"),
            waste_outside=validation_result.get("dustbins", {}).get("waste_outside"),
            waste_outside_description=validation_result.get("dustbins", {}).get("waste_outside_description"),
            
            # Recyclable Items
            recyclable_items=validation_result.get("recyclable_items", {}).get("items", ""),
            is_recyclable=validation_result.get("recyclable_items", {}).get("recyclable", False),
            recyclable_notes=validation_result.get("recyclable_items", {}).get("notes"),
            
            # Time Analysis
            time_appears_valid=validation_result.get("time_analysis", {}).get("time_appears_valid", True),
            lighting_condition=validation_result.get("time_analysis", {}).get("lighting_condition"),
            time_analysis_notes=validation_result.get("time_analysis", {}).get("notes"),
            
            # Description Match
            description_matches_image=validation_result.get("description_match", {}).get("matches_image", True),
            description_match_confidence=validation_result.get("description_match", {}).get("confidence"),
            description_match_notes=validation_result.get("description_match", {}).get("notes"),
            
            # Additional Data
            additional_data=validation_result.get("additional_data", {})
        )
        
        # Save to database if severity is Medium, High, or Critical
        if response.severity in STORE_SEVERITY_LEVELS:
            # Get user info if available (if auth is enabled)
            user_data = {}
            if current_authority:
                user_data = {
                    "user_id": str(current_authority.get("_id")),
                    "username": current_authority.get("username"),
                    "email": current_authority.get("email")
                }
            
            # Store in database
            saved_report = await save_report_if_severe(validation_result, user_data)
            
            # Add report ID to the response if saved
            if saved_report:
                if not response.additional_data:
                    response.additional_data = {}
                response.additional_data["report_id"] = saved_report.id
                response.additional_data["saved_to_database"] = True
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Error validating waste report: {str(e)}")
        print(f"Traceback: {error_traceback}")
        
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Error validating waste report: {str(e)}",
                "traceback": error_traceback
            }
        )

# TESTING ONLY: Comment out the current_authority dependency
# To re-enable auth, uncomment the parameter below and update function calls
@router.post("/validate-base64", response_model=WasteReportValidationResponse)
async def validate_waste_report_base64(
    request: WasteReportValidationRequest,
    current_authority: Optional[dict] = Depends(get_optional_authority)
):
    """
    Validate a waste report using a base64-encoded image via Gemini AI
    
    Request body:
    - **image**: Base64 encoded image showing a potentially dirty/unclean area
    - **description**: Optional description of the waste or area
    - **location**: Location where the image was taken (coordinates or address)
    - **timestamp**: When the image was taken
    
    Returns a validation response with confidence score, waste types, and severity level.
    If severity is Medium, High, or Critical, the report is stored in the database.
    """
    try:
        # Validate base64 image
        if not request.image:
            raise HTTPException(
                status_code=400,
                detail="Base64 image data is required"
            )
            
        # Basic validation of base64 string
        try:
            # Check if it's a data URL
            if "base64," in request.image:
                # Extract the image data after the prefix
                base64_content = request.image.split("base64,")[1]
            else:
                base64_content = request.image
                
            # Try to decode to check if it's valid base64
            try:
                decoded = base64.b64decode(base64_content)
                image_size_kb = len(decoded) / 1024
                print(f"Received base64 image, decoded size: {image_size_kb:.2f} KB")
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid base64 image data: {str(e)}"
                )
        except Exception as e:
            if "base64," not in request.image:
                raise HTTPException(
                    status_code=400, 
                    detail="Invalid base64 image format. Base64 string couldn't be processed."
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Error processing base64 image: {str(e)}"
                )
        
        # Call Gemini for validation
        validation_result = await validate_waste_image(
            image=request.image,
            description=request.description,
            location=request.location,
            timestamp=request.timestamp
        )
        
        # Add input data to validation result for storage
        validation_result["location"] = request.location
        validation_result["description"] = request.description
        validation_result["timestamp"] = request.timestamp.isoformat()
        validation_result["image"] = request.image  # Store the base64 image
        
        # Convert the validation result to our response model
        response = WasteReportValidationResponse(
            is_valid=validation_result.get("is_valid", False),
            message=validation_result.get("message", "Validation failed"),
            confidence_score=validation_result.get("confidence_score"),
            
            # Waste Types
            waste_types=validation_result.get("waste_types", {}).get("types", ""),
            waste_type_confidences=validation_result.get("waste_types", {}).get("confidence", ""),
            
            # Severity
            severity=validation_result.get("severity"),
            
            # Dustbins
            dustbin_present=validation_result.get("dustbins", {}).get("is_present", False),
            dustbin_full=validation_result.get("dustbins", {}).get("is_full"),
            dustbin_fullness_percentage=validation_result.get("dustbins", {}).get("fullness_percentage"),
            waste_outside=validation_result.get("dustbins", {}).get("waste_outside"),
            waste_outside_description=validation_result.get("dustbins", {}).get("waste_outside_description"),
            
            # Recyclable Items
            recyclable_items=validation_result.get("recyclable_items", {}).get("items", ""),
            is_recyclable=validation_result.get("recyclable_items", {}).get("recyclable", False),
            recyclable_notes=validation_result.get("recyclable_items", {}).get("notes"),
            
            # Time Analysis
            time_appears_valid=validation_result.get("time_analysis", {}).get("time_appears_valid", True),
            lighting_condition=validation_result.get("time_analysis", {}).get("lighting_condition"),
            time_analysis_notes=validation_result.get("time_analysis", {}).get("notes"),
            
            # Description Match
            description_matches_image=validation_result.get("description_match", {}).get("matches_image", True),
            description_match_confidence=validation_result.get("description_match", {}).get("confidence"),
            description_match_notes=validation_result.get("description_match", {}).get("notes"),
            
            # Additional Data
            additional_data=validation_result.get("additional_data", {})
        )
        
        # Save to database if severity is Medium, High, or Critical
        if response.severity in STORE_SEVERITY_LEVELS:
            # Get user info if available (if auth is enabled)
            user_data = {}
            if current_authority:
                user_data = {
                    "user_id": str(current_authority.get("_id")),
                    "username": current_authority.get("username"),
                    "email": current_authority.get("email")
                }
            
            # Store in database
            saved_report = await save_report_if_severe(validation_result, user_data)
            
            # Add report ID to the response if saved
            if saved_report:
                if not response.additional_data:
                    response.additional_data = {}
                response.additional_data["report_id"] = saved_report.id
                response.additional_data["saved_to_database"] = True
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Error validating waste report: {str(e)}")
        print(f"Traceback: {error_traceback}")
        
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Error validating waste report: {str(e)}",
                "traceback": error_traceback
            }
        ) 