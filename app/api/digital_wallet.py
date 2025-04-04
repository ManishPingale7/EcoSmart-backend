from fastapi import APIRouter, HTTPException, Depends, Path, Body
from typing import Dict, Any, List
from datetime import datetime
from ..models import DigitalWallet, EcoCoinTransaction, Benefit
from ..crud import digital_wallet as wallet_crud
from ..auth.router import get_optional_authority
from bson.errors import InvalidId

router = APIRouter(
    tags=["Digital Wallet"],
    responses={404: {"description": "Not found"}},
)

# Constants for coin rewards
COINS_PER_REPORT = 5  # Base coins per report
SEVERITY_MULTIPLIERS = {
    "medium": 1.0,    # 5 coins
    "high": 1.2,      # 6 coins
    "critical": 1.5   # 7.5 coins (rounded to 8)
}

@router.get("/benefits", 
    response_model=List[Benefit],
    summary="Get available benefits",
    description="Get a list of all available medical benefits that can be redeemed with eco-friendly coins"
)
async def get_available_benefits():
    """
    Get list of available benefits that can be redeemed with eco-friendly coins
    """
    return [
        {
            "id": "med_1",
            "name": "15% off on Health Check-up",
            "coins_required": 500,
            "description": "Get 15% discount on basic health check-up at partner clinics (max discount ₹500)",
            "validity_days": 30
        },
        {
            "id": "med_2",
            "name": "20% off on Dental Treatment",
            "coins_required": 750,
            "description": "20% discount on basic dental treatments at partner clinics (max discount ₹800)",
            "validity_days": 45
        },
        {
            "id": "med_3",
            "name": "15% off on Eye Treatment",
            "coins_required": 600,
            "description": "15% discount on basic eye treatments at partner opticians (max discount ₹600)",
            "validity_days": 45
        },
        {
            "id": "med_4",
            "name": "20% off on Physiotherapy",
            "coins_required": 800,
            "description": "20% discount on physiotherapy sessions at partner clinics (max discount ₹1000)",
            "validity_days": 60
        },
        {
            "id": "med_5",
            "name": "25% off on Health Camp",
            "coins_required": 1000,
            "description": "25% discount on basic health camp packages (max discount ₹1200)",
            "validity_days": 60
        },
        {
            "id": "med_6",
            "name": "10% off on Medical Consultation",
            "coins_required": 400,
            "description": "10% discount on medical consultations at partner clinics (max discount ₹300)",
            "validity_days": 30
        },
        {
            "id": "med_7",
            "name": "20% off on Diagnostic Tests",
            "coins_required": 900,
            "description": "20% discount on basic diagnostic test packages at partner labs (max discount ₹1000)",
            "validity_days": 60
        },
        {
            "id": "med_8",
            "name": "15% off on Medical Equipment",
            "coins_required": 1200,
            "description": "15% discount on basic medical equipment at partner stores (max discount ₹1500)",
            "validity_days": 90
        },
        {
            "id": "med_9",
            "name": "10% off on Medicines",
            "coins_required": 450,
            "description": "10% discount on medicines at partner pharmacies (max discount ₹500)",
            "validity_days": 30
        },
        {
            "id": "med_10",
            "name": "15% off on Health Insurance",
            "coins_required": 1500,
            "description": "15% discount on basic health insurance premiums from partner insurers (max discount ₹2000)",
            "validity_days": 90
        }
    ]

@router.get("/{user_id}", 
    response_model=DigitalWallet,
    summary="Get user's digital wallet",
    description="Retrieve the digital wallet information and balance for a specific user"
)
async def get_digital_wallet(
    user_id: str = Path(..., description="The ID of the user")
):
    """
    Get digital wallet information for a user
    """
    try:
        wallet = await wallet_crud.get_wallet_by_user_id(user_id)
        if not wallet:
            raise HTTPException(
                status_code=404,
                detail=f"Digital wallet not found for user {user_id}"
            )
        return wallet
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user ID format: {user_id}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving digital wallet: {str(e)}"
        )

@router.get("/{user_id}/transactions", 
    response_model=List[EcoCoinTransaction],
    summary="Get wallet transactions",
    description="Retrieve the transaction history for a user's digital wallet"
)
async def get_wallet_transactions(
    user_id: str = Path(..., description="The ID of the user")
):
    """
    Get transaction history for a user's wallet
    """
    try:
        transactions = await wallet_crud.get_wallet_transactions(user_id)
        return transactions
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user ID format: {user_id}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving wallet transactions: {str(e)}"
        )

@router.post("/{user_id}/redeem/{benefit_id}",
    summary="Redeem a benefit",
    description="Redeem a medical benefit using eco-friendly coins from the user's digital wallet"
)
async def redeem_benefit(
    user_id: str = Path(..., description="The ID of the user"),
    benefit_id: str = Path(..., description="The ID of the benefit to redeem")
):
    """
    Redeem a benefit using eco-friendly coins
    """
    try:
        # Get available benefits
        benefits = await get_available_benefits()
        benefit = next((b for b in benefits if b["id"] == benefit_id), None)
        
        if not benefit:
            raise HTTPException(
                status_code=404,
                detail=f"Benefit with ID {benefit_id} not found"
            )
            
        # Get user's wallet
        wallet = await wallet_crud.get_wallet_by_user_id(user_id)
        if not wallet:
            raise HTTPException(
                status_code=404,
                detail=f"Digital wallet not found for user {user_id}"
            )
            
        # Check if user has enough coins
        if wallet["balance"] < benefit["coins_required"]:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient coins. Required: {benefit['coins_required']}, Available: {wallet['balance']}"
            )
            
        # Redeem the benefit
        transaction = await wallet_crud.redeem_benefit(
            user_id=user_id,
            benefit_id=benefit_id,
            coins_used=benefit["coins_required"],
            benefit_details=benefit
        )
        
        return {
            "message": f"Successfully redeemed {benefit['name']}",
            "transaction_id": transaction["id"],
            "coins_used": benefit["coins_required"],
            "remaining_balance": wallet["balance"] - benefit["coins_required"],
            "validity_days": benefit["validity_days"]
        }
        
    except HTTPException:
        raise
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user ID format: {user_id}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error redeeming benefit: {str(e)}"
        ) 