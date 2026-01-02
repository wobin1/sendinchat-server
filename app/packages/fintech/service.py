"""
Fintech service layer - handles all fintech operations with JSON mock database.
"""
import json
import os
import threading
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import secrets
import logging

logger = logging.getLogger(__name__)

# Path to JSON database
DB_PATH = os.path.join(os.path.dirname(__file__), "mock_db.json")

# Thread lock for database operations
db_lock = threading.Lock()


class JsonDatabase:
    """Thread-safe JSON database manager."""
    
    @staticmethod
    def read() -> Dict[str, Any]:
        """Read the entire database."""
        with db_lock:
            try:
                with open(DB_PATH, 'r') as f:
                    return json.load(f)
            except FileNotFoundError:
                logger.error(f"Database file not found: {DB_PATH}")
                return {"wallets": [], "transactions": [], "banks": [], "clients": []}
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in database file: {DB_PATH}")
                return {"wallets": [], "transactions": [], "banks": [], "clients": []}
    
    @staticmethod
    def write(data: Dict[str, Any]) -> None:
        """Write the entire database."""
        with db_lock:
            with open(DB_PATH, 'w') as f:
                json.dump(data, f, indent=2)


# ============= Helper Functions =============
def generate_account_number() -> str:
    """Generate a unique 10-digit account number."""
    db = JsonDatabase.read()
    while True:
        account_no = '1' + ''.join([str(secrets.randbelow(10)) for _ in range(9)])
        # Check if account number already exists
        if not any(w['accountNo'] == account_no for w in db['wallets']):
            return account_no


def generate_transaction_id() -> str:
    """Generate a unique transaction ID."""
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    random_suffix = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    return f"TXN{timestamp}{random_suffix}"


def generate_reference() -> str:
    """Generate a unique transaction reference."""
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    random_suffix = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    return f"REF{timestamp}{random_suffix}"


# ============= 1. Create Wallet =============
def create_wallet(
    bvn: str,
    date_of_birth: str,
    gender: int,
    last_name: str,
    other_names: str,
    phone_no: str,
    transaction_tracking_ref: str,
    account_name: str,
    place_of_birth: str,
    address: str,
    national_identity_no: str,
    next_of_kin_phone_no: str,
    next_of_kin_name: str,
    email: str
) -> Dict[str, Any]:
    """
    Create a new wallet.
    
    Raises:
        ValueError: If BVN already exists or validation fails
    """
    db = JsonDatabase.read()
    
    # Check if BVN already exists
    if any(w['bvn'] == bvn for w in db['wallets']):
        raise ValueError(f"Wallet with BVN {bvn} already exists")
    
    # Generate account number
    account_no = generate_account_number()
    
    # Create wallet object
    wallet = {
        "accountNo": account_no,
        "accountName": account_name,
        "bvn": bvn,
        "dateOfBirth": date_of_birth,
        "gender": gender,
        "lastName": last_name,
        "otherNames": other_names,
        "phoneNo": phone_no,
        "email": email,
        "placeOfBirth": place_of_birth,
        "address": address,
        "nationalIdentityNo": national_identity_no,
        "nextOfKinPhoneNo": next_of_kin_phone_no,
        "nextOfKinName": next_of_kin_name,
        "balance": 0.0,
        "createdAt": datetime.utcnow().isoformat() + "Z"
    }
    
    # Add to database
    db['wallets'].append(wallet)
    JsonDatabase.write(db)
    
    logger.info(f"Wallet created: {account_no} for {account_name}")
    
    return {
        "accountNo": account_no,
        "accountName": account_name,
        "bvn": bvn,
        "balance": 0.0
    }


# ============= 2. Bank Transfer =============
def bank_transfer(
    sender_account: str,
    sender_name: str,
    recipient_account: str,
    recipient_name: str,
    recipient_bank: str,
    amount: str,
    narration: str,
    reference: str,
    session_id: str,
    merchant_fee_account: str,
    merchant_fee_amount: str,
    is_fee: bool
) -> Dict[str, Any]:
    """
    Transfer funds to another bank.
    
    Raises:
        ValueError: If sender account not found or insufficient balance
    """
    db = JsonDatabase.read()
    
    # Find sender wallet
    sender_wallet = next((w for w in db['wallets'] if w['accountNo'] == sender_account), None)
    if not sender_wallet:
        raise ValueError(f"Sender account {sender_account} not found")
    
    # Convert amount to float
    transfer_amount = float(amount)
    fee_amount = float(merchant_fee_amount) if is_fee else 0.0
    total_debit = transfer_amount + fee_amount
    
    # Check balance
    if sender_wallet['balance'] < total_debit:
        raise ValueError(f"Insufficient balance. Available: {sender_wallet['balance']}, Required: {total_debit}")
    
    # Deduct from sender
    sender_wallet['balance'] -= total_debit
    
    # Create transaction record
    transaction = {
        "id": generate_transaction_id(),
        "type": "bank_transfer",
        "accountNo": sender_account,
        "amount": -transfer_amount,
        "fee": -fee_amount if is_fee else 0.0,
        "narration": narration,
        "reference": reference,
        "sessionId": session_id,
        "recipientAccount": recipient_account,
        "recipientName": recipient_name,
        "recipientBank": recipient_bank,
        "status": "completed",
        "createdAt": datetime.utcnow().isoformat() + "Z"
    }
    
    db['transactions'].append(transaction)
    JsonDatabase.write(db)
    
    logger.info(f"Bank transfer: {amount} from {sender_account} to {recipient_account} at bank {recipient_bank}")
    
    return {
        "transactionReference": reference,
        "amount": amount,
        "recipientAccount": recipient_account,
        "recipientBank": recipient_bank
    }


# ============= 3. Credit Wallet =============
def credit_wallet(
    account_no: str,
    narration: str,
    total_amount: float,
    transaction_id: str,
    merchant_fee_account: str,
    merchant_fee_amount: str,
    is_fee: bool,
    transaction_type: str
) -> Dict[str, Any]:
    """
    Credit a wallet.
    
    Raises:
        ValueError: If account not found
    """
    db = JsonDatabase.read()
    
    # Find wallet
    wallet = next((w for w in db['wallets'] if w['accountNo'] == account_no), None)
    if not wallet:
        raise ValueError(f"Account {account_no} not found")
    
    # Calculate net credit (total - merchant fee)
    fee_amount = float(merchant_fee_amount) if is_fee else 0.0
    net_credit = total_amount - fee_amount
    
    # Credit wallet
    wallet['balance'] += net_credit
    new_balance = wallet['balance']
    
    # Create transaction record
    transaction = {
        "id": transaction_id,
        "type": "credit",
        "accountNo": account_no,
        "amount": net_credit,
        "fee": fee_amount if is_fee else 0.0,
        "narration": narration,
        "reference": transaction_id,
        "transactionType": transaction_type,
        "status": "completed",
        "createdAt": datetime.utcnow().isoformat() + "Z"
    }
    
    db['transactions'].append(transaction)
    JsonDatabase.write(db)
    
    logger.info(f"Wallet credited: {account_no} with {net_credit}")
    
    return {
        "transactionId": transaction_id,
        "accountNo": account_no,
        "amount": net_credit,
        "newBalance": new_balance
    }


# ============= 4. Debit Wallet =============
def debit_wallet(
    account_no: str,
    narration: str,
    total_amount: float,
    transaction_id: str,
    merchant_fee_account: str,
    merchant_fee_amount: str,
    is_fee: bool,
    transaction_type: str
) -> Dict[str, Any]:
    """
    Debit a wallet.
    
    Raises:
        ValueError: If account not found or insufficient balance
    """
    db = JsonDatabase.read()
    
    # Find wallet
    wallet = next((w for w in db['wallets'] if w['accountNo'] == account_no), None)
    if not wallet:
        raise ValueError(f"Account {account_no} not found")
    
    # Calculate total debit (amount + merchant fee)
    fee_amount = float(merchant_fee_amount) if is_fee else 0.0
    total_debit = total_amount + fee_amount
    
    # Check balance
    if wallet['balance'] < total_debit:
        raise ValueError(f"Insufficient balance. Available: {wallet['balance']}, Required: {total_debit}")
    
    # Debit wallet
    wallet['balance'] -= total_debit
    new_balance = wallet['balance']
    
    # Create transaction record
    transaction = {
        "id": transaction_id,
        "type": "debit",
        "accountNo": account_no,
        "amount": -total_amount,
        "fee": -fee_amount if is_fee else 0.0,
        "narration": narration,
        "reference": transaction_id,
        "transactionType": transaction_type,
        "status": "completed",
        "createdAt": datetime.utcnow().isoformat() + "Z"
    }
    
    db['transactions'].append(transaction)
    JsonDatabase.write(db)
    
    logger.info(f"Wallet debited: {account_no} with {total_debit}")
    
    return {
        "transactionId": transaction_id,
        "accountNo": account_no,
        "amount": total_amount,
        "newBalance": new_balance
    }


# ============= 5. Wallet Enquiry =============
def get_wallet_enquiry(account_no: str) -> Dict[str, Any]:
    """
    Get wallet details and balance.
    
    Raises:
        ValueError: If account not found
    """
    db = JsonDatabase.read()
    
    # Find wallet
    wallet = next((w for w in db['wallets'] if w['accountNo'] == account_no), None)
    if not wallet:
        raise ValueError(f"Account {account_no} not found")
    
    return {
        "accountNo": wallet['accountNo'],
        "accountName": wallet['accountName'],
        "balance": wallet['balance'],
        "phoneNo": wallet['phoneNo'],
        "email": wallet['email']
    }


# ============= 6. Wallet Transactions =============
def get_wallet_transactions(
    account_number: str,
    from_date: str,
    to_date: str,
    number_of_items: str
) -> Dict[str, Any]:
    """
    Get wallet transaction history.
    
    Raises:
        ValueError: If account not found or invalid date format
    """
    db = JsonDatabase.read()
    
    # Find wallet
    wallet = next((w for w in db['wallets'] if w['accountNo'] == account_number), None)
    if not wallet:
        raise ValueError(f"Account {account_number} not found")
    
    # Parse dates
    try:
        from_datetime = datetime.strptime(from_date, '%Y-%m-%d')
        to_datetime = datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)  # Include end date
    except ValueError:
        raise ValueError("Invalid date format. Use YYYY-MM-DD")
    
    # Filter transactions
    filtered_transactions = []
    for txn in db['transactions']:
        if txn.get('accountNo') == account_number:
            try:
                txn_date = datetime.fromisoformat(txn['createdAt'].replace('Z', '+00:00'))
                if from_datetime <= txn_date < to_datetime:
                    filtered_transactions.append({
                        "id": txn['id'],
                        "type": txn['type'],
                        "amount": txn['amount'],
                        "narration": txn.get('narration', ''),
                        "reference": txn.get('reference', txn['id']),
                        "status": txn['status'],
                        "createdAt": txn['createdAt'],
                        "otherParty": txn.get('recipientAccount') or txn.get('senderAccount')
                    })
            except (ValueError, KeyError):
                continue
    
    # Sort by date (newest first) and limit
    filtered_transactions.sort(key=lambda x: x['createdAt'], reverse=True)
    max_items = int(number_of_items)
    filtered_transactions = filtered_transactions[:max_items]
    
    return {
        "accountNumber": account_number,
        "transactions": filtered_transactions,
        "totalCount": len(filtered_transactions)
    }


# ============= 7. Get Bank List =============
def get_bank_list() -> Dict[str, Any]:
    """Get list of supported banks."""
    db = JsonDatabase.read()
    
    return {
        "banks": db['banks'],
        "count": len(db['banks'])
    }


# ============= 8. Client Authentication =============
def authenticate_client(client_id: str, client_secret: str) -> Dict[str, Any]:
    """
    Authenticate a client using credentials.
    
    Raises:
        ValueError: If credentials are invalid
    """
    db = JsonDatabase.read()
    
    # Find client
    client = next(
        (c for c in db['clients'] if c['clientId'] == client_id and c['clientSecret'] == client_secret),
        None
    )
    
    if not client:
        raise ValueError("Invalid client credentials")
    
    if not client.get('isActive', True):
        raise ValueError("Client account is inactive")
    
    # Generate access token (mock - just a random string)
    access_token = secrets.token_urlsafe(32)
    
    logger.info(f"Client authenticated: {client_id}")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 3600,
        "client_name": client.get('name', 'Unknown Client')
    }
