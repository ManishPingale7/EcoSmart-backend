from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Dict, Any
import base64
from ..services.waste_categorization_service import analyze_waste_image
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_waste(
    image: UploadFile = File(...)
) -> Dict[str, Any]:
    """
    Analyze an image of waste to categorize types and determine recyclability
    
    - **image**: The image file showing waste materials
    
    Returns a detailed analysis of waste types and recyclability information
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
            logger.info(f"Received image: {image.filename}, size: {image_size_kb:.2f} KB")
            
            # Convert to base64
            base64_image = base64.b64encode(image_content).decode("utf-8")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Error reading image file: {str(e)}"
            )
        
        # Analyze the image
        analysis_result = await analyze_waste_image(base64_image)
        
        # Check for errors in the analysis
        if "error" in analysis_result:
            raise HTTPException(
                status_code=500,
                detail=f"Error analyzing waste image: {analysis_result['error']}"
            )
        
        return analysis_result
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error processing waste analysis request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        ) 