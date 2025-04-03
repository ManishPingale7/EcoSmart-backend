from fastapi import APIRouter, Depends, HTTPException, Path, Query, UploadFile, File
from typing import List, Optional
from ..auth.router import get_optional_authority
from ..crud import waste_report as waste_report_crud
from ..models import WasteReport, WasteReportStatus, CleanupVerificationResponse
from bson.errors import InvalidId
from datetime import datetime
import json
from ..config import get_settings
import base64
from ..services.gemini_service import compare_cleanup_images
from bson.objectid import ObjectId
from ..database import get_database
from datetime import datetime  # Ensure datetime is imported

settings = get_settings()

router = APIRouter()

@router.get("/reports")
async def get_waste_reports(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    severity: Optional[str] = Query(None, description="Filter by severity (Medium, High, Critical)"),
    status: Optional[str] = Query(None, description="Filter by status (pending, in_progress, resolved)"),
    location: Optional[str] = Query(None, description="Text search in location field"),
    current_authority: Optional[dict] = Depends(get_optional_authority)
):
    """
    Get a list of waste reports with filtering options
    
    Only reports with Medium, High, or Critical severity are stored in the database.
    Results are sorted by creation date (newest first).
    """
    try:
        reports = await waste_report_crud.get_waste_reports(
            skip=skip,
            limit=limit,
            severity=severity,
            status=status,
            location_query=location
        )
        
        # Convert reports to Pydantic models for proper serialization
        serialized_reports = [WasteReport.from_mongo(report) for report in reports]
        
        return {
            "count": len(serialized_reports),
            "results": serialized_reports
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving waste reports: {str(e)}"
        )

@router.get("/reports/{report_id}", response_model=WasteReport)
async def get_waste_report(
    report_id: str = Path(..., description="The ID of the waste report"),
    current_authority: Optional[dict] = Depends(get_optional_authority)
):
    """
    Get a specific waste report by ID
    """
    try:
        report = await waste_report_crud.get_waste_report(report_id)
        if not report:
            raise HTTPException(
                status_code=404,
                detail=f"Waste report with ID {report_id} not found"
            )
            
        # Convert to Pydantic model for proper serialization
        return WasteReport.from_mongo(report)
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report ID format: {report_id}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving waste report: {str(e)}"
        )

@router.patch("/reports/{report_id}", response_model=WasteReport)
async def update_report_status(
    report_id: str = Path(..., description="The ID of the waste report"),
    status: str = Query(..., description="New status (pending, in_progress, resolved)"),
    current_authority: Optional[dict] = Depends(get_optional_authority)
):
    """
    Update the status of a waste report
    """
    # Validate status
    valid_statuses = [status.value for status in WasteReportStatus]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    try:
        updated_report = await waste_report_crud.update_waste_report_status(report_id, status)
        if not updated_report:
            raise HTTPException(
                status_code=404,
                detail=f"Waste report with ID {report_id} not found"
            )
            
        # Convert to Pydantic model for proper serialization
        return WasteReport.from_mongo(updated_report)
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report ID format: {report_id}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating waste report status: {str(e)}"
        )

@router.post("/reports/{report_id}/comments", response_model=WasteReport)
async def add_report_comment(
    report_id: str = Path(..., description="The ID of the waste report"),
    comment: str = Query(..., description="Comment text"),
    current_authority: Optional[dict] = Depends(get_optional_authority)
):
    """
    Add a comment to a waste report
    """
    try:
        # Prepare comment data
        comment_data = {
            "text": comment,
            "user_id": "test_user" if not current_authority else str(current_authority.get("_id")),
            "username": "Test User" if not current_authority else current_authority.get("username"),
            "role": "tester" if not current_authority else current_authority.get("role", "authority")
        }
        
        updated_report = await waste_report_crud.add_waste_report_comment(report_id, comment_data)
        if not updated_report:
            raise HTTPException(
                status_code=404,
                detail=f"Waste report with ID {report_id} not found"
            )
            
        # Convert to Pydantic model for proper serialization
        return WasteReport.from_mongo(updated_report)
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report ID format: {report_id}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error adding comment to waste report: {str(e)}"
        )

@router.delete("/reports/{report_id}")
async def delete_waste_report(
    report_id: str = Path(..., description="The ID of the waste report"),
    current_authority: Optional[dict] = Depends(get_optional_authority)
):
    """
    Delete a waste report
    """
    # Skip admin check during testing
    if current_authority and current_authority.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can delete waste reports"
        )
    
    try:
        deleted = await waste_report_crud.delete_waste_report(report_id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Waste report with ID {report_id} not found"
            )
        return {"message": f"Waste report with ID {report_id} deleted successfully"}
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report ID format: {report_id}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting waste report: {str(e)}"
        )

@router.post("/reports/{report_id}/verify-cleanup", response_model=CleanupVerificationResponse)
async def verify_cleanup(
    report_id: str,
    after_image: UploadFile = File(...),
    current_authority: Optional[dict] = Depends(get_optional_authority)
):
    """
    Verify cleanup of a waste report by comparing before and after images.
    Returns simplified response with verification status and key information.
    """
    try:
        # Get the original report
        report_data = await waste_report_crud.get_waste_report(report_id)
        if not report_data:
            raise HTTPException(status_code=404, detail="Report not found")

        # Convert to model
        report = WasteReport.from_mongo(report_data)

        # Get the original image
        before_image = report.image  # Access image directly from WasteReport model
        if not before_image:
            raise HTTPException(
                status_code=400,
                detail="Original image not found in the report. Cannot verify cleanup."
            )

        # Validate and read the after image
        if not after_image.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only images are allowed."
            )
        
        after_image_content = await after_image.read()
        after_image_base64 = base64.b64encode(after_image_content).decode('utf-8')

        # Call Gemini service for comparison
        comparison_result = await compare_cleanup_images(before_image, after_image_base64)
        
        # Extract key information from comparison
        is_same_location = comparison_result.get("is_same_location", False)
        is_clean = comparison_result.get("is_clean", False)
        improvement_percentage = comparison_result.get("improvement_percentage", 0)
        
        # Determine verification status
        if not is_same_location:
            verification_status = "location_mismatch"
        elif not is_clean:
            verification_status = "not_clean"
        else:
            verification_status = "verified"
            # Update report status to done
            await update_waste_report_status(report_id, "done", comparison_result)

        # Prepare simplified response
        response_data = {
            "status": verification_status,
            "is_same_location": is_same_location,
            "is_clean": is_clean,
            "improvement_percentage": improvement_percentage
        }

        return CleanupVerificationResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error verifying cleanup: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Error verifying cleanup: {str(e)}"
        )

async def update_waste_report_status(report_id: str, status: str, verification_details: dict) -> bool:
    """
    Update the status of a waste report in the database.
    """
    try:
        # Get the database connection
        db = await get_database()
        
        # Update the report status and verification details
        result = await db["waste_reports"].update_one(
            {"_id": ObjectId(report_id)},
            {
                "$set": {
                    "status": status,
                    "verification_details": verification_details,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return result.modified_count > 0
        
    except Exception as e:
        print(f"Error updating waste report status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error updating waste report status: {str(e)}"
        ) 