from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from typing import Optional
from datetime import datetime
from ..auth.router import get_current_authority
from ..models import WasteReportValidationRequest, WasteReportValidationResponse, WasteType, Dustbin, RecyclableItem, TimeAnalysis, DescriptionMatch
from ..services.gemini_service import validate_waste_image
import base64

# Use the same tag as the main API router to avoid duplication in Swagger docs
router = APIRouter()

# TESTING ONLY: Comment out the current_authority dependency
# To re-enable auth, uncomment the parameter below and update function calls
@router.post("/validate", response_model=WasteReportValidationResponse)
async def validate_waste_report(
    image: UploadFile = File(...),
    description: Optional[str] = Form(None),
    location: str = Form(...),
    timestamp: datetime = Form(...),
    # Uncomment the line below to re-enable authentication
    # current_authority: dict = Depends(get_current_authority)
):
    """
    Validate a waste report image using Gemini AI
    
    - **image**: The image file showing a potentially dirty/unclean area
    - **description**: Optional description of the waste or area
    - **location**: Location where the image was taken (coordinates or address)
    - **timestamp**: When the image was taken
    
    Returns a validation response with confidence score, waste types, and severity level.
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
        
        # Convert the validation result to our response model
        response = WasteReportValidationResponse(
            is_valid=validation_result.get("is_valid", False),
            message=validation_result.get("message", "Validation failed"),
            confidence_score=validation_result.get("confidence_score"),
            waste_types=[
                WasteType(type=wt.get("type", ""), confidence=wt.get("confidence", 0.0))
                for wt in validation_result.get("waste_types", [])
            ],
            severity=validation_result.get("severity"),
            dustbins=[
                Dustbin(
                    is_present=db.get("is_present", False),
                    is_full=db.get("is_full"),
                    fullness_percentage=db.get("fullness_percentage"),
                    waste_outside=db.get("waste_outside"),
                    waste_outside_description=db.get("waste_outside_description")
                )
                for db in validation_result.get("dustbins", [])
            ],
            recyclable_items=[
                RecyclableItem(
                    item=ri.get("item", ""),
                    recyclable=ri.get("recyclable", False),
                    notes=ri.get("notes")
                )
                for ri in validation_result.get("recyclable_items", [])
            ],
            time_analysis=TimeAnalysis(
                time_appears_valid=validation_result.get("time_analysis", {}).get("time_appears_valid", True),
                lighting_condition=validation_result.get("time_analysis", {}).get("lighting_condition"),
                notes=validation_result.get("time_analysis", {}).get("notes")
            ),
            description_match=DescriptionMatch(
                matches_image=validation_result.get("description_match", {}).get("matches_image", True),
                confidence=validation_result.get("description_match", {}).get("confidence"),
                notes=validation_result.get("description_match", {}).get("notes")
            ),
            additional_data=validation_result.get("additional_data", {})
        )
        
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
    # Uncomment the line below to re-enable authentication
    # current_authority: dict = Depends(get_current_authority)
):
    """
    Validate a waste report using a base64-encoded image via Gemini AI
    
    Request body:
    - **image**: Base64 encoded image showing a potentially dirty/unclean area
    - **description**: Optional description of the waste or area
    - **location**: Location where the image was taken (coordinates or address)
    - **timestamp**: When the image was taken
    
    Returns a validation response with confidence score, waste types, and severity level.
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
        
        # Convert the validation result to our response model
        response = WasteReportValidationResponse(
            is_valid=validation_result.get("is_valid", False),
            message=validation_result.get("message", "Validation failed"),
            confidence_score=validation_result.get("confidence_score"),
            waste_types=[
                WasteType(type=wt.get("type", ""), confidence=wt.get("confidence", 0.0))
                for wt in validation_result.get("waste_types", [])
            ],
            severity=validation_result.get("severity"),
            dustbins=[
                Dustbin(
                    is_present=db.get("is_present", False),
                    is_full=db.get("is_full"),
                    fullness_percentage=db.get("fullness_percentage"),
                    waste_outside=db.get("waste_outside"),
                    waste_outside_description=db.get("waste_outside_description")
                )
                for db in validation_result.get("dustbins", [])
            ],
            recyclable_items=[
                RecyclableItem(
                    item=ri.get("item", ""),
                    recyclable=ri.get("recyclable", False),
                    notes=ri.get("notes")
                )
                for ri in validation_result.get("recyclable_items", [])
            ],
            time_analysis=TimeAnalysis(
                time_appears_valid=validation_result.get("time_analysis", {}).get("time_appears_valid", True),
                lighting_condition=validation_result.get("time_analysis", {}).get("lighting_condition"),
                notes=validation_result.get("time_analysis", {}).get("notes")
            ),
            description_match=DescriptionMatch(
                matches_image=validation_result.get("description_match", {}).get("matches_image", True),
                confidence=validation_result.get("description_match", {}).get("confidence"),
                notes=validation_result.get("description_match", {}).get("notes")
            ),
            additional_data=validation_result.get("additional_data", {})
        )
        
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