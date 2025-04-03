from datetime import datetime
from typing import Dict, Any, List, Optional
from bson import ObjectId
from app.database import database

# Collection name
waste_reports_collection = database["waste_reports"]

async def create_waste_report(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new waste report in the database.
    Only reports with severity Medium, High, or Critical should be stored.
    
    Args:
        report_data: Validated waste report data
        
    Returns:
        The created waste report document
    """
    # Add timestamps
    report_data["created_at"] = datetime.utcnow()
    report_data["updated_at"] = datetime.utcnow()
    
    # Add report status
    report_data["status"] = "pending"  # pending, in_progress, resolved
    
    # Insert the document
    result = await waste_reports_collection.insert_one(report_data)
    
    # Add the ID to the data
    report_data["id"] = str(result.inserted_id)
    
    return report_data

async def get_waste_report(report_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a waste report by ID
    
    Args:
        report_id: The ID of the waste report
        
    Returns:
        The waste report document or None if not found
    """
    report = await waste_reports_collection.find_one({"_id": ObjectId(report_id)})
    if report:
        report["id"] = str(report["_id"])
    return report

async def get_waste_reports(
    skip: int = 0, 
    limit: int = 100,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    location_query: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get a list of waste reports with filtering options
    
    Args:
        skip: Number of documents to skip
        limit: Maximum number of documents to return
        severity: Filter by severity level
        status: Filter by status
        location_query: Text search in location field
        
    Returns:
        List of waste report documents
    """
    # Build query
    query = {}
    
    if severity:
        query["severity"] = severity
        
    if status:
        query["status"] = status
        
    if location_query:
        query["location"] = {"$regex": location_query, "$options": "i"}
    
    # Execute query
    cursor = waste_reports_collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
    
    # Convert to list and add string IDs
    reports = []
    async for report in cursor:
        report["id"] = str(report["_id"])
        reports.append(report)
        
    return reports

async def update_waste_report_status(report_id: str, status: str) -> Optional[Dict[str, Any]]:
    """
    Update the status of a waste report
    
    Args:
        report_id: The ID of the waste report
        status: New status (pending, in_progress, resolved)
        
    Returns:
        The updated waste report document or None if not found
    """
    result = await waste_reports_collection.update_one(
        {"_id": ObjectId(report_id)},
        {
            "$set": {
                "status": status,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    if result.modified_count:
        return await get_waste_report(report_id)
    return None

async def add_waste_report_comment(report_id: str, comment: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Add a comment to a waste report
    
    Args:
        report_id: The ID of the waste report
        comment: Comment data
        
    Returns:
        The updated waste report document or None if not found
    """
    # Add timestamp to comment
    comment["timestamp"] = datetime.utcnow()
    
    result = await waste_reports_collection.update_one(
        {"_id": ObjectId(report_id)},
        {
            "$push": {"comments": comment},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    if result.modified_count:
        return await get_waste_report(report_id)
    return None

async def delete_waste_report(report_id: str) -> bool:
    """
    Delete a waste report
    
    Args:
        report_id: The ID of the waste report
        
    Returns:
        True if deleted, False otherwise
    """
    result = await waste_reports_collection.delete_one({"_id": ObjectId(report_id)})
    return result.deleted_count > 0 