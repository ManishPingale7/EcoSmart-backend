from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body, Query
from typing import Optional
from datetime import datetime
from ..auth.router import get_optional_authority
from ..models import WasteReportValidationRequest, WasteReportValidationResponse, WasteType, Dustbin, RecyclableItem, TimeAnalysis, DescriptionMatch, SeverityLevel, WasteReport
from ..services.gemini_service import validate_waste_image
from ..crud import waste_report as waste_report_crud
from ..crud import user as user_crud
from ..crud import badge as badge_crud
from ..crud import digital_wallet as wallet_crud
from ..crud import city as city_crud
import base64
from app.services.notification_service import notification_service
import logging

# Use the same tag as the main API router to avoid duplication in Swagger docs
router = APIRouter()

# Set of severity levels that should be stored in the database
STORE_SEVERITY_LEVELS = {SeverityLevel.MEDIUM, SeverityLevel.HIGH, SeverityLevel.CRITICAL}

# Constants for coin rewards
COINS_PER_REPORT = 10  # Base coins per report
SEVERITY_MULTIPLIERS = {
    "medium": 1.0,
    "high": 1.5,
    "critical": 2.0
}

# Create a function that always returns None for testing
async def get_optional_authority(
    current_authority: Optional[dict] = Depends(get_optional_authority)
) -> Optional[dict]:
    """
    A dependency that always returns None for testing purposes.
    This completely bypasses authentication requirements.
    """
    # For testing purposes - bypass authentication
    return None

async def save_report_if_severe(validation_result: dict, user_data: dict = None) -> Optional[dict]:
    """
    Save a waste report to the database if severity level warrants storage
    
    Args:
        validation_result: The validation result data
        user_data: Optional user data to associate with the report
        
    Returns:
        The saved waste report document or None if not saved
    """
    # Only save reports with severity that requires action
    severity = validation_result.get("severity")
    if severity not in STORE_SEVERITY_LEVELS:
        print(f"Not saving report with severity {severity} (below threshold)")
        return None

    # Prepare report data
    report_data = {
        "is_valid": validation_result.get("is_valid", False),
        "message": validation_result.get("message", "Validation failed"),
        "confidence_score": validation_result.get("confidence_score", 0.0),
        
        # User provided data
        "location": validation_result.get("location", ""),
        "description": validation_result.get("description", ""),
        "timestamp": datetime.fromisoformat(validation_result.get("timestamp", datetime.utcnow().isoformat())),
        
        # Store the image as a base64 encoded string
        "image": validation_result.get("image"),
        
        # Severity
        "severity": severity,
        
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
    
    # Update user badge stats if user_id is available
    if user_data and user_data.get("user_id"):
        user_id = user_data.get("user_id")
        await badge_crud.increment_user_report_count(user_id)
        
        # Calculate and credit eco-friendly coins based on severity
        base_coins = COINS_PER_REPORT
        multiplier = SEVERITY_MULTIPLIERS.get(severity.lower(), 1.0)
        coins_earned = int(base_coins * multiplier)
        
        # Credit coins to user's digital wallet
        await wallet_crud.add_coins(
            user_id=user_id,
            amount=coins_earned,
            description=f"Earned {coins_earned} eco-friendly coins for submitting a {severity} severity waste report"
        )
        
        # Add coin information to the report's additional data
        if not saved_report.get("additional_data"):
            saved_report["additional_data"] = {}
        saved_report["additional_data"]["coins_earned"] = coins_earned
        
        # Update city stats if user has city information
        user = await user_crud.get_user_by_id(user_id)
        if user and user.get("city"):
            city_name = user.get("city")
            
            # Increment report count for city
            await city_crud.increment_city_report_count(city_name)
            
            # Update city engagement score based on severity
            engagement_delta = 0
            if severity == SeverityLevel.CRITICAL:
                engagement_delta = 2.0
            elif severity == SeverityLevel.HIGH:
                engagement_delta = 1.0
            elif severity == SeverityLevel.MEDIUM:
                engagement_delta = 0.5
                
            await city_crud.update_city_engagement(city_name, engagement_delta)
    
    return saved_report

@router.post("/validate", response_model=WasteReportValidationResponse)
async def validate_waste_report(
    image: UploadFile = File(...),
    description: Optional[str] = Form(None),
    location: str = Form(...),
    timestamp: datetime = Form(...),
    user_id: Optional[str] = Form(None, description="ID of the user submitting the report"),
    current_authority: Optional[dict] = Depends(get_optional_authority)
):
    """
    Validate a waste report image using Gemini AI
    
    - **image**: The image file showing a potentially dirty/unclean area
    - **description**: Optional description of the waste or area
    - **location**: Location where the image was taken (coordinates or address)
    - **timestamp**: When the image was taken
    - **user_id**: (Optional) ID of the user submitting the report
    
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
        validation_result["image"] = base64_image
        
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
            # Prepare user data
            user_data = {}
            
            # Prioritize explicitly provided user_id
            if user_id:
                # Get user info from database if possible
                user = await user_crud.get_user_by_id(user_id)
                if user:
                    user_data = {
                        "user_id": user_id,
                        "username": user.get("name", "Unknown"),
                        "email": user.get("email", "")
                    }
                else:
                    # Still use the ID even if user not found
                    user_data = {"user_id": user_id}
            # Fall back to current authority if available
            elif current_authority:
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
                response.additional_data["report_id"] = saved_report.get("id")
                response.additional_data["saved_to_database"] = True
                
                # Add information about the user badge if applicable
                if user_id or (current_authority and current_authority.get("_id")):
                    actual_user_id = user_id or str(current_authority.get("_id"))
                    user_badge_stats = await badge_crud.get_user_badge_stats(actual_user_id)
                    if user_badge_stats:
                        # Get all user badges
                        user_badges = await badge_crud.get_user_badges(actual_user_id)
                        
                        # Determine highest badge level
                        badge_level_order = {"diamond": 5, "platinum": 4, "gold": 3, "silver": 2, "bronze": 1, None: 0}
                        highest_badge = None
                        highest_level = 0
                        
                        for badge in user_badges:
                            level_value = badge_level_order.get(badge.get("badge_level"), 0)
                            if level_value > highest_level:
                                highest_level = level_value
                                highest_badge = badge.get("badge_level")
                        
                        response.additional_data["user_badge_level"] = highest_badge
                        response.additional_data["user_total_reports"] = user_badge_stats.get("total_reports", 0)
        
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

@router.post("/validate-base64", response_model=WasteReportValidationResponse)
async def validate_waste_report_base64(
    request: WasteReportValidationRequest,
    user_id: Optional[str] = Query(None, description="ID of the user submitting the report"),
    current_authority: Optional[dict] = Depends(get_optional_authority)
):
    """
    Validate a waste report using a base64-encoded image using Gemini AI
    
    Request body should include:
    - **image**: Base64-encoded image string
    - **description**: Optional description of the waste or area
    - **location**: Location where the image was taken (coordinates or address)
    - **timestamp**: When the image was taken
    
    Query parameter:
    - **user_id**: (Optional) ID of the user submitting the report
    
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
            # Prepare user data
            user_data = {}
            
            # Prioritize explicitly provided user_id
            if user_id:
                # Get user info from database if possible
                user = await user_crud.get_user_by_id(user_id)
                if user:
                    user_data = {
                        "user_id": user_id,
                        "username": user.get("name", "Unknown"),
                        "email": user.get("email", "")
                    }
                else:
                    # Still use the ID even if user not found
                    user_data = {"user_id": user_id}
            # Fall back to current authority if available
            elif current_authority:
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
                response.additional_data["report_id"] = saved_report.get("id")
                response.additional_data["saved_to_database"] = True
                
                # Add information about the user badge if applicable
                if user_id or (current_authority and current_authority.get("_id")):
                    actual_user_id = user_id or str(current_authority.get("_id"))
                    user_badge_stats = await badge_crud.get_user_badge_stats(actual_user_id)
                    if user_badge_stats:
                        # Get all user badges
                        user_badges = await badge_crud.get_user_badges(actual_user_id)
                        
                        # Determine highest badge level
                        badge_level_order = {"diamond": 5, "platinum": 4, "gold": 3, "silver": 2, "bronze": 1, None: 0}
                        highest_badge = None
                        highest_level = 0
                        
                        for badge in user_badges:
                            level_value = badge_level_order.get(badge.get("badge_level"), 0)
                            if level_value > highest_level:
                                highest_level = level_value
                                highest_badge = badge.get("badge_level")
                        
                        response.additional_data["user_badge_level"] = highest_badge
                        response.additional_data["user_total_reports"] = user_badge_stats.get("total_reports", 0)
        
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