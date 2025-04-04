from typing import Dict, Any, List, Optional
from datetime import datetime
from bson import ObjectId
from ..database import get_database
from ..models import DigitalWallet, EcoCoinTransaction

# Initialize database and collections
db = None
wallet_collection = None
transaction_collection = None

async def init_collections():
    global db, wallet_collection, transaction_collection
    db = await get_database()
    wallet_collection = db.digital_wallets
    transaction_collection = db.eco_coin_transactions

async def get_wallet_by_user_id(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get digital wallet by user ID
    """
    global wallet_collection
    if wallet_collection is None:
        await init_collections()
    wallet = await wallet_collection.find_one({"user_id": user_id})
    if wallet:
        wallet["id"] = str(wallet["_id"])
        del wallet["_id"]
    return wallet

async def create_wallet(user_id: str) -> Dict[str, Any]:
    """
    Create a new digital wallet for a user
    """
    global wallet_collection
    if wallet_collection is None:
        await init_collections()
    wallet_data = {
        "user_id": user_id,
        "balance": 0,
        "total_earned": 0,
        "total_spent": 0,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await wallet_collection.insert_one(wallet_data)
    wallet_data["id"] = str(result.inserted_id)
    del wallet_data["_id"]
    return wallet_data

async def add_coins(user_id: str, amount: int, description: str) -> Dict[str, Any]:
    """
    Add coins to a user's wallet
    """
    global wallet_collection, transaction_collection
    if wallet_collection is None or transaction_collection is None:
        await init_collections()
    # Get or create wallet
    wallet = await get_wallet_by_user_id(user_id)
    if not wallet:
        wallet = await create_wallet(user_id)
    
    # Update wallet balance
    update_data = {
        "$inc": {
            "balance": amount,
            "total_earned": amount
        },
        "$set": {
            "updated_at": datetime.utcnow()
        }
    }
    
    await wallet_collection.update_one(
        {"user_id": user_id},
        update_data
    )
    
    # Create transaction record
    transaction_data = {
        "user_id": user_id,
        "type": "earn",
        "amount": amount,
        "description": description,
        "created_at": datetime.utcnow()
    }
    
    result = await transaction_collection.insert_one(transaction_data)
    transaction_data["id"] = str(result.inserted_id)
    del transaction_data["_id"]
    
    # Get updated wallet
    updated_wallet = await get_wallet_by_user_id(user_id)
    return updated_wallet

async def get_wallet_transactions(user_id: str) -> List[Dict[str, Any]]:
    """
    Get all transactions for a user's wallet
    """
    global transaction_collection
    if transaction_collection is None:
        await init_collections()
    transactions = await transaction_collection.find(
        {"user_id": user_id}
    ).sort("created_at", -1).to_list(length=None)
    
    for transaction in transactions:
        transaction["id"] = str(transaction["_id"])
        del transaction["_id"]
    
    return transactions

async def redeem_benefit(
    user_id: str,
    benefit_id: str,
    coins_used: int,
    benefit_details: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Redeem a benefit using eco-friendly coins
    """
    global wallet_collection, transaction_collection
    if wallet_collection is None or transaction_collection is None:
        await init_collections()
    # Get wallet
    wallet = await get_wallet_by_user_id(user_id)
    if not wallet:
        raise ValueError(f"Wallet not found for user {user_id}")
    
    # Check balance
    if wallet["balance"] < coins_used:
        raise ValueError(f"Insufficient coins. Required: {coins_used}, Available: {wallet['balance']}")
    
    # Update wallet balance
    update_data = {
        "$inc": {
            "balance": -coins_used,
            "total_spent": coins_used
        },
        "$set": {
            "updated_at": datetime.utcnow()
        }
    }
    
    await wallet_collection.update_one(
        {"user_id": user_id},
        update_data
    )
    
    # Create transaction record
    transaction_data = {
        "user_id": user_id,
        "type": "spend",
        "amount": coins_used,
        "description": f"Redeemed benefit: {benefit_details['name']}",
        "created_at": datetime.utcnow(),
        "benefit_id": benefit_id,
        "benefit_details": benefit_details,
        "validity_days": benefit_details.get("validity_days")
    }
    
    result = await transaction_collection.insert_one(transaction_data)
    transaction_data["id"] = str(result.inserted_id)
    del transaction_data["_id"]
    
    return transaction_data 