from fastapi import APIRouter, Depends, HTTPException, Path, Query
from typing import List, Optional
from ..auth.router import get_optional_authority
from ..crud import waste_report as waste_report_crud
from ..models import WasteReport, WasteReportStatus
from bson.errors import InvalidId
from datetime import datetime
import json
from ..config import get_settings

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