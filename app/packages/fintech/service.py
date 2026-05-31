"""
Fintech service layer - handles all fintech operations via third-party wallet API.
"""
import json
import os
import threading
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import secrets
import logging
import asyncpg

from app.packages.fintech.third_party_client import wallet_api_client, WalletAPIError
from app.core.config import settings

logger = logging.getLogger(__name__)

# 9PSB wallet-to-other-bank response codes requiring TSQ (WAAS v3 section 1)
OTHER_BANK_TSQ_CODES = frozenset({"09", "96", "97", "98", "99"})
OTHER_BANK_SUCCESS_CODE = "00"

OTHER_BANK_USER_MESSAGES = {
    "51": "Insufficient funds in your wallet.",
    "08": "Account name does not match. Please verify the recipient details.",
    "61": "Transfer limit exceeded for your account tier.",
    "91": "Beneficiary bank is currently unavailable. Try again later.",
    "26": "Duplicate transaction reference. Check your transaction history.",
    "42": "Duplicate transaction reference. Check your transaction history.",
}

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


def normalize_transaction_reference(reference: Optional[str], prefix: str = "EXT") -> str:
    """Normalize to 9PSB max 25-char alphanumeric reference."""
    if reference:
        clean = "".join(c for c in reference if c.isalnum() or c in "-_")[:25]
        if clean:
            return clean
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    suffix = "".join(str(secrets.randbelow(10)) for _ in range(4))
    return f"{prefix}{ts}{suffix}"[:25]


def _extract_other_bank_response_code(result: Dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return ""
    data = result.get("data")
    if isinstance(data, dict):
        code = data.get("responseCode") or data.get("code")
        if code is not None:
            return str(code).strip()
    for key in ("responseCode", "code"):
        if result.get(key) is not None:
            return str(result[key]).strip()
    return ""


def _other_bank_status_from_result(result: Dict[str, Any]) -> str:
    """Map 9PSB payload to completed | pending | failed."""
    code = _extract_other_bank_response_code(result)
    top_status = str(result.get("status", "")).upper()
    if code == OTHER_BANK_SUCCESS_CODE or top_status == "SUCCESS":
        return "completed"
    if code in OTHER_BANK_TSQ_CODES or top_status == "PENDING":
        return "pending"
    return "failed"


def _other_bank_user_message(result: Dict[str, Any], fallback: str) -> str:
    code = _extract_other_bank_response_code(result)
    if code in OTHER_BANK_USER_MESSAGES:
        return OTHER_BANK_USER_MESSAGES[code]
    msg = result.get("message")
    if isinstance(msg, str) and msg.strip():
        return msg.strip()
    data = result.get("data")
    if isinstance(data, dict):
        inner = data.get("message") or data.get("responseMessage")
        if isinstance(inner, str) and inner.strip():
            return inner.strip()
    return fallback


async def _requery_other_bank_transfer(
    transaction_reference: str,
    amount: float,
    sender_account_no: str,
) -> Dict[str, Any]:
    """TSQ for wallet-to-other-bank using wallet_requery."""
    return await wallet_api_client.requery_transaction(
        transaction_id=transaction_reference,
        amount=amount,
        transaction_type="OTHER_BANKS",
        transaction_date=datetime.utcnow().strftime("%Y-%m-%d"),
        account_no=sender_account_no,
    )


async def assert_sender_available_balance(
    sender_account_no: str,
    amount: float,
    conn: Optional[asyncpg.Connection] = None,
) -> float:
    """
    Ensure sender has enough available balance (API balance minus locally held funds).
    Returns available balance after check.
    """
    wallet_data = await get_wallet_balance_api(sender_account_no)
    api_balance = float(
        wallet_data.get("availableBalance")
        or wallet_data.get("balance")
        or wallet_data.get("accountBalance")
        or 0.0
    )
    locked = 0.0
    if conn:
        row = await conn.fetchrow(
            "SELECT locked_balance FROM wallet_balances WHERE wallet_account = $1",
            sender_account_no,
        )
        if row:
            locked = float(row["locked_balance"])

    available = api_balance - locked
    if available < amount:
        raise ValueError(
            f"Insufficient balance. Available: {available:.2f}, "
            f"Held for pending transfers: {locked:.2f}, Required: {amount:.2f}"
        )
    return available


def _build_other_bank_transfer_payload(
    sender_account_no: str,
    sender_name: str,
    amount: float,
    recipient_account_no: str,
    recipient_name: str,
    recipient_bank_code: str,
    narration: str,
    transaction_reference: str,
) -> Dict[str, Any]:
    """Build wallet_other_banks request per WAAS v3."""
    merchant_code = (
        settings.WALLET_MERCHANT_SHORT_CODE.strip()
        or settings.WALLET_API_CLIENT_ID.strip()
        or "SENDCHAT"
    )
    return {
        "transaction": {
            "reference": transaction_reference,
            "senderAccountNumber": sender_account_no,
            "senderName": sender_name or "SendChat User",
        },
        "order": {
            "amount": amount,
            "currency": "NGN",
            "description": (narration or "Transfer")[:100],
        },
        "customer": {
            "accountNumber": recipient_account_no,
            "bankCode": recipient_bank_code,
            "accountName": recipient_name,
        },
        "merchant": {
            "shortCode": merchant_code,
        },
        "transactionType": "OTHER_BANKS",
        "narration": narration[:100],
        "isFee": False,
    }


async def _finalize_other_bank_transfer(
    transaction_reference: str,
    amount: float,
    sender_account_no: str,
    initial_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Apply TSQ when response is ambiguous; return result with transferStatus."""
    status = _other_bank_status_from_result(initial_result)
    result = initial_result

    if status == "pending":
        try:
            tsq = await _requery_other_bank_transfer(
                transaction_reference, amount, sender_account_no
            )
            tsq_status = _other_bank_status_from_result(tsq)
            if tsq_status == "completed":
                result = tsq
                status = "completed"
            elif tsq_status == "failed":
                result = tsq
                status = "failed"
            else:
                status = "pending"
        except Exception as e:
            logger.warning(f"TSQ after ambiguous other-bank transfer failed: {e}")

    result = dict(result) if isinstance(result, dict) else {"raw": result}
    result["transferStatus"] = status
    result["responseCode"] = _extract_other_bank_response_code(result)
    return result


# ============= 1. Create Wallet =============
async def create_wallet(
    bvn: Optional[str],
    date_of_birth: str,
    gender: int,
    last_name: str,
    other_names: str,
    phone_no: str,
    transaction_tracking_ref: str,
    account_name: str,
    place_of_birth: str,
    address: str,
    national_identity_no: Optional[str],
    nin_user_id: Optional[str],
    next_of_kin_phone_no: Optional[str],
    next_of_kin_name: Optional[str],
    email: str
) -> Dict[str, Any]:
    """
    Create a new wallet via third-party API.
    First checks if a wallet already exists for this BVN.
    
    Raises:
        ValueError: If wallet creation fails
        WalletAPIError: If third-party API request fails
    """
    # Step 0: Robust Validation - only for mandatory fields
    if not bvn and not national_identity_no:
        raise ValueError("Either BVN or NIN must be provided")
    
    if national_identity_no and not nin_user_id:
        raise ValueError("NIN User ID is required when NIN is provided")
    
    required_fields = {
        "date_of_birth": date_of_birth,
        "last_name": last_name,
        "other_names": other_names,
        "phone_no": phone_no,
        "address": address,
        "email": email
    }
    
    for field, value in required_fields.items():
        if not value or str(value).strip() == "":
            raise ValueError(f"Missing required field: {field}")
            
    # Validate date format (DD/MM/YYYY)
    try:
        if "/" in date_of_birth:
            day, month, year = date_of_birth.split("/")
            if len(year) != 4:
                raise ValueError("Invalid year in date_of_birth. Expected YYYY.")
        else:
             raise ValueError("Date of birth must be in DD/MM/YYYY format")
    except Exception:
        raise ValueError("Invalid date_of_birth format. Expected DD/MM/YYYY")

    # Step 1: Check if wallet already exists for this BVN (if provided)
    if bvn:
        logger.info(f"Checking for existing wallet with BVN: {bvn[:3]}***")
        try:
            existing_wallet = await wallet_api_client.get_wallet_by_bvn(bvn)
            if existing_wallet:
                account_no = existing_wallet.get("accountNo") or existing_wallet.get("accountNumber")
                if account_no:
                    logger.info(f"Found existing wallet for BVN: {account_no}")
                    
                    # Store in mock DB if not exists
                    db = JsonDatabase.read()
                    if not any(w['accountNo'] == account_no for w in db['wallets']):
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
                            "balance": existing_wallet.get("balance", 0.0),
                            "createdAt": datetime.utcnow().isoformat() + "Z"
                        }
                        db['wallets'].append(wallet)
                        JsonDatabase.write(db)
                    
                    return {
                        "accountNo": account_no,
                        "accountName": existing_wallet.get("accountName", account_name),
                        "bvn": bvn,
                        "balance": existing_wallet.get("balance", 0.0)
                    }
            else:
                logger.info(f"No existing wallet found for BVN")
        except WalletAPIError as e:
            # If get_wallet_by_bvn fails, log and continue to creation
            logger.info(f"BVN lookup failed: {str(e)}")
    else:
        existing_wallet = None
    
    # Step 2: Attempt to create new wallet
    wallet_data: Dict[str, Any] = {
        "dateOfBirth": date_of_birth,
        "gender": str(gender),
        "lastName": last_name,
        "otherNames": other_names,
        "phoneNo": phone_no,
        "transactionTrackingRef": transaction_tracking_ref,
        "address": address,
        "email": email
    }
    
    # Only include optional fields if they have values
    if bvn:
        wallet_data["bvn"] = bvn
    wallet_data["accountName"] = account_name or f"{last_name} {other_names}"
    wallet_data["placeOfBirth"] = place_of_birth
    if national_identity_no:
        wallet_data["nationalIdentityNo"] = national_identity_no
    if nin_user_id:
        wallet_data["ninUserId"] = nin_user_id
    if next_of_kin_phone_no:
        wallet_data["nextOfKinPhoneNo"] = next_of_kin_phone_no
    if next_of_kin_name:
        wallet_data["nextOfKinName"] = next_of_kin_name
    
    try:
        # Call third-party API
        result = await wallet_api_client.create_wallet(wallet_data)
        
        # Extract account number from nested data structure
        response_data = result.get("data", {})
        account_no = (
            response_data.get("accountNumber") or 
            response_data.get("accountNo") or 
            result.get("accountNumber") or 
            result.get("accountNo")
        )
        # Extract account name (fullName from data or fallback to provided name)
        extracted_account_name = (
            response_data.get("fullName") or 
            result.get("accountName") or 
            result.get("account_name") or 
            account_name
        )
        
        # Store wallet info in local database for reference
        db = JsonDatabase.read()
        wallet = {
            "accountNo": account_no,
            "accountName": extracted_account_name,
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
            "balance": result.get("balance", 0.0),
            "createdAt": datetime.utcnow().isoformat() + "Z"
        }
        db['wallets'].append(wallet)
        JsonDatabase.write(db)
        
        logger.info(f"Wallet created via third-party API: {account_no} for {extracted_account_name}")
        
        if not account_no:
            logger.error(f"Wallet created but no account number found in response: {result}")
            raise ValueError("Wallet created but no account number was returned from the provider.")

        return {
            "accountNo": account_no,
            "accountName": extracted_account_name,
            "bvn": bvn,
            "balance": response_data.get("balance") or result.get("balance", 0.0)
        }
    except WalletAPIError as e:
        # Step 3: Enhanced DUPLICATE error handling
        if e.response_text:
            try:
                import json
                error_data = json.loads(e.response_text)
                
                # Check for various DUPLICATE status formats
                is_duplicate = (
                    error_data.get("status") == "DUPLICATE" or
                    error_data.get("status") == "duplicate" or
                    error_data.get("responseCode") == "96" or
                    (error_data.get("status") == "FAILED" and (
                        "duplicate" in str(error_data.get("message", "")).lower() or
                        "already exists" in str(error_data.get("message", "")).lower()
                    )) or
                    "duplicate" in str(error_data.get("message", "")).lower() or
                    "already exists" in str(error_data.get("message", "")).lower()
                )
                
                if is_duplicate:
                    data = error_data.get("data", {})
                    # Try multiple field names for account number
                    account_no = (
                        data.get("accountNumber") or 
                        data.get("accountNo") or 
                        data.get("account_number") or
                        error_data.get("accountNumber") or
                        error_data.get("accountNo")
                    )
                    
                    if account_no:
                        logger.info(f"Duplicate wallet detected. Linking existing account: {account_no}")
                        # Store in mock DB if not exists
                        db = JsonDatabase.read()
                        if not any(w['accountNo'] == account_no for w in db['wallets']):
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
                            db['wallets'].append(wallet)
                            JsonDatabase.write(db)
                        
                        return {
                            "accountNo": account_no,
                            "accountName": account_name,
                            "bvn": bvn,
                            "balance": 0.0
                        }
                    else:
                        # No account number in response, try BVN lookup as fallback
                        logger.warning("DUPLICATE error but no account number in response. Attempting BVN lookup...")
                        try:
                            existing_wallet = await wallet_api_client.get_wallet_by_bvn(bvn)
                            if existing_wallet and existing_wallet.get("accountNo"):
                                account_no = existing_wallet.get("accountNo")
                                logger.info(f"Retrieved existing wallet via BVN lookup: {account_no}")
                                
                                # Store in mock DB
                                db = JsonDatabase.read()
                                if not any(w['accountNo'] == account_no for w in db['wallets']):
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
                                        "balance": existing_wallet.get("balance", 0.0),
                                        "createdAt": datetime.utcnow().isoformat() + "Z"
                                    }
                                    db['wallets'].append(wallet)
                                    JsonDatabase.write(db)
                                
                                return {
                                    "accountNo": account_no,
                                    "accountName": existing_wallet.get("accountName", account_name),
                                    "bvn": bvn,
                                    "balance": existing_wallet.get("balance", 0.0)
                                }
                        except Exception as lookup_err:
                            logger.error(f"BVN lookup fallback failed: {str(lookup_err)}")
            except Exception as parse_err:
                logger.error(f"Failed to parse DUPLICATE error response: {str(parse_err)}")

        logger.error(f"Third-party API error during wallet creation: {str(e)}")
        raise ValueError(f"Wallet creation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during wallet creation: {str(e)}")
        raise ValueError(f"Wallet creation failed: {str(e)}")



# ============= 2. Bank Transfer (legacy route → 9PSB wallet_other_banks) =============
async def bank_transfer(
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
    is_fee: bool,
    conn: Optional[asyncpg.Connection] = None,
) -> Dict[str, Any]:
    """
    Transfer funds to another bank via 9PSB wallet_other_banks.
    Legacy /fintech/transfer/bank payload; prefer /fintech/transfer/external for apps.
    """
    _ = (session_id, merchant_fee_account, merchant_fee_amount, is_fee)
    transfer_amount = float(amount)
    txn_ref = normalize_transaction_reference(reference or None, prefix="BNK")
    result = await transfer_to_other_bank(
        sender_account_no=sender_account,
        sender_name=sender_name,
        amount=transfer_amount,
        recipient_account_no=recipient_account,
        recipient_name=recipient_name,
        recipient_bank_code=recipient_bank,
        narration=narration,
        transaction_reference=txn_ref,
        conn=conn,
    )
    data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
    txn = data.get("transaction", {})
    cust = data.get("customer", {})
    return {
        "transactionReference": txn.get("reference") or result.get("transactionReference") or txn_ref,
        "amount": str(transfer_amount),
        "recipientAccount": cust.get("accountNumber", recipient_account),
        "recipientBank": cust.get("bankCode", recipient_bank),
        "transferStatus": result.get("transferStatus", "completed"),
        "responseCode": result.get("responseCode"),
    }


# ============= Account Management =============
async def upgrade_wallet(
    account_number: str,
    bvn: str,
    nin: str,
    account_name: str,
    phone_number: str,
    tier: int,
    email: str,
    user_photo: str,
    id_type: int,
    id_number: str,
    id_issue_date: str,
    id_expiry_date: Optional[str],
    id_card_front: str,
    id_card_back: Optional[str],
    house_number: str,
    street_name: str,
    state: str,
    city: str,
    local_government: str,
    pep: str,
    customer_signature: str,
    utility_bill: str,
    nearest_landmark: str,
    place_of_birth: Optional[str],
    proof_of_address_verification: Optional[str]
) -> Dict[str, Any]:
    """
    Upgrade wallet account tier.
    
    Raises:
        ValueError: If upgrade request fails
        WalletAPIError: If third-party API request fails
    """
    logger.info(f"Processing wallet upgrade for account: {account_number}")
    
    upgrade_data = {
        "accountNumber": account_number,
        "bvn": bvn,
        "nin": nin,
        "accountName": account_name,
        "phoneNumber": phone_number,
        "tier": tier,
        "email": email,
        "userPhoto": user_photo,
        "idType": id_type,
        "idNumber": id_number,
        "idIssueDate": id_issue_date,
        "idExpiryDate": id_expiry_date,
        "idCardFront": id_card_front,
        "idCardBack": id_card_back,
        "houseNumber": house_number,
        "streetName": street_name,
        "state": state,
        "city": city,
        "localGovernment": local_government,
        "pep": pep,
        "customerSignature": customer_signature,
        "utilityBill": utility_bill,
        "nearestLandmark": nearest_landmark,
        "placeOfBirth": place_of_birth,
        "proofOfAddressVerification": proof_of_address_verification
    }
    
    try:
        result = await wallet_api_client.upgrade_wallet(upgrade_data)
        
        # Log upgrade request locally
        db = JsonDatabase.read()
        upgrade_record = {
            "id": f"upgrade-{account_number}-{datetime.utcnow().timestamp()}",
            "accountNumber": account_number,
            "tier": tier,
            "status": "pending",
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "thirdPartyResponse": result
        }
        if 'upgradeRequests' not in db:
            db['upgradeRequests'] = []
        db['upgradeRequests'].append(upgrade_record)
        JsonDatabase.write(db)
        
        logger.info(f"Wallet upgrade request submitted: {account_number}")
        return result
        
    except WalletAPIError as e:
        logger.error(f"Third-party API error during wallet upgrade: {str(e)}")
        raise ValueError(f"Wallet upgrade failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during wallet upgrade: {str(e)}")
        raise ValueError(f"Wallet upgrade failed: {str(e)}")


def _is_upgrade_not_found(payload: Any) -> bool:
    """True when 9PSB has no upgrade request for this wallet (expected for tier-1 users)."""
    if isinstance(payload, dict):
        texts = [
            str(payload.get("message", "")),
            str(payload.get("status", "")),
        ]
        data = payload.get("data")
        if isinstance(data, dict):
            texts.append(str(data.get("message", "")))
            texts.append(str(data.get("status", "")))
        combined = " ".join(texts).lower()
        if "no record" in combined:
            return True
    text = str(payload).lower()
    return "no record found" in text or "no record" in text


async def get_upgrade_status(account_number: str) -> Dict[str, Any]:
    """
    Get wallet upgrade status.
    Returns upgradeStatus=None when the user has never submitted an upgrade request.
    """
    logger.info(f"Getting upgrade status for account: {account_number}")

    empty_status = {
        "message": "No upgrade request found",
        "status": "success",
        "accountNumber": account_number,
        "upgradeStatus": None,
        "tier": None,
        "data": None,
    }

    try:
        result = await wallet_api_client.get_upgrade_status(account_number)
        if _is_upgrade_not_found(result):
            logger.info(f"No upgrade record for account: {account_number}")
            return empty_status

        data = result.get("data", {}) if isinstance(result, dict) else {}
        if not isinstance(data, dict):
            data = {}

        upgrade_status = (
            data.get("status")
            or data.get("upgradeStatus")
            or result.get("upgradeStatus")
        )
        tier = data.get("tier") or result.get("tier")

        logger.info(f"Upgrade status retrieved: {account_number} -> {upgrade_status}")
        return {
            "message": result.get("message", "Upgrade status retrieved"),
            "status": "success",
            "accountNumber": account_number,
            "upgradeStatus": upgrade_status,
            "tier": tier,
            "data": data or None,
        }

    except WalletAPIError as e:
        if _is_upgrade_not_found(e.response_text or str(e)):
            logger.info(f"No upgrade record for account (API error): {account_number}")
            return empty_status
        logger.error(f"Third-party API error during upgrade status query: {str(e)}")
        raise ValueError(f"Upgrade status query failed: {str(e)}")
    except Exception as e:
        if _is_upgrade_not_found(str(e)):
            return empty_status
        logger.error(f"Unexpected error during upgrade status query: {str(e)}")
        raise ValueError(f"Upgrade status query failed: {str(e)}")


async def get_wallet_by_bvn(bvn: str) -> Dict[str, Any]:
    """
    Get wallet information by BVN.
    
    Raises:
        ValueError: If wallet lookup fails
        WalletAPIError: If third-party API request fails
    """
    logger.info(f"Getting wallet by BVN")
    
    try:
        result = await wallet_api_client.get_wallet_by_bvn(bvn)
        logger.info(f"Wallet retrieved by BVN")
        return result
        
    except WalletAPIError as e:
        logger.error(f"Third-party API error during get wallet by BVN: {str(e)}")
        raise ValueError(f"Get wallet by BVN failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during get wallet by BVN: {str(e)}")
        raise ValueError(f"Get wallet by BVN failed: {str(e)}")


# ============= Webhook Handlers =============
def handle_inflow_notification(webhook_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle inflow notification webhook from third-party API.
    
    This is called when funds are received in a wallet account.
    Logs the transaction and can trigger notifications to the user.
    
    Args:
        webhook_data: Webhook payload from third-party API
        
    Returns:
        Dict containing processing status
    """
    logger.info(f"Processing inflow notification for account: {webhook_data.get('accountNumber')}")
    
    try:
        db = JsonDatabase.read()
        
        # Log the inflow transaction
        inflow_record = {
            "id": webhook_data.get('transactionReference', f"inflow-{datetime.utcnow().timestamp()}"),
            "type": "inflow",
            "accountNumber": webhook_data.get('accountNumber'),
            "amount": webhook_data.get('amount'),
            "senderAccountNumber": webhook_data.get('senderAccountNumber'),
            "senderName": webhook_data.get('senderName'),
            "narration": webhook_data.get('narration'),
            "transactionReference": webhook_data.get('transactionReference'),
            "transactionDate": webhook_data.get('transactionDate'),
            "sessionId": webhook_data.get('sessionId'),
            "responseCode": webhook_data.get('responseCode'),
            "responseMessage": webhook_data.get('responseMessage'),
            "receivedAt": datetime.utcnow().isoformat() + "Z",
            "processed": True
        }
        
        if 'inflowNotifications' not in db:
            db['inflowNotifications'] = []
        db['inflowNotifications'].append(inflow_record)
        JsonDatabase.write(db)
        
        logger.info(f"Inflow notification processed: {webhook_data.get('transactionReference')}")
        
        # TODO: Send push notification to user
        # TODO: Update wallet balance if needed
        
        return {
            "status": "received",
            "message": "Inflow notification processed successfully",
            "transactionReference": webhook_data.get('transactionReference')
        }
        
    except Exception as e:
        logger.error(f"Error processing inflow notification: {str(e)}")
        raise ValueError(f"Failed to process inflow notification: {str(e)}")


def handle_upgrade_status_notification(webhook_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle upgrade status notification webhook from third-party API.
    
    This is called when a wallet upgrade request is approved or declined.
    Updates the local upgrade request status and can trigger notifications.
    
    Args:
        webhook_data: Webhook payload from third-party API
        
    Returns:
        Dict containing processing status
    """
    logger.info(f"Processing upgrade status notification for account: {webhook_data.get('accountNumber')}")
    
    try:
        db = JsonDatabase.read()
        account_number = webhook_data.get('accountNumber')
        upgrade_status = webhook_data.get('upgradeStatus')
        
        # Update existing upgrade request if found
        if 'upgradeRequests' in db:
            for request in db['upgradeRequests']:
                if request.get('accountNumber') == account_number and request.get('status') == 'pending':
                    request['status'] = upgrade_status.lower()
                    request['tier'] = webhook_data.get('tier')
                    request['reason'] = webhook_data.get('reason')
                    request['approvalDate'] = webhook_data.get('approvalDate')
                    request['updatedAt'] = datetime.utcnow().isoformat() + "Z"
                    break
        
        # Log the notification
        notification_record = {
            "id": f"upgrade-notif-{account_number}-{datetime.utcnow().timestamp()}",
            "accountNumber": account_number,
            "upgradeStatus": upgrade_status,
            "tier": webhook_data.get('tier'),
            "reason": webhook_data.get('reason'),
            "approvalDate": webhook_data.get('approvalDate'),
            "responseCode": webhook_data.get('responseCode'),
            "responseMessage": webhook_data.get('responseMessage'),
            "receivedAt": datetime.utcnow().isoformat() + "Z",
            "processed": True
        }
        
        if 'upgradeNotifications' not in db:
            db['upgradeNotifications'] = []
        db['upgradeNotifications'].append(notification_record)
        JsonDatabase.write(db)
        
        logger.info(f"Upgrade status notification processed: {account_number} - {upgrade_status}")
        
        # TODO: Send push notification to user
        # TODO: Update wallet tier if approved
        
        return {
            "status": "received",
            "message": "Upgrade status notification processed successfully",
            "accountNumber": account_number,
            "upgradeStatus": upgrade_status
        }
        
    except Exception as e:
        logger.error(f"Error processing upgrade status notification: {str(e)}")
        raise ValueError(f"Failed to process upgrade status notification: {str(e)}")




# ============= 3. Credit Wallet =============
async def credit_wallet(
    account_no: str,
    narration: str,
    total_amount: float,
    transaction_id: str,
    merchant_fee_account: str,
    merchant_fee_amount: str,
    is_fee: bool,
    transaction_type: str,
    conn: asyncpg.Connection = None
) -> Dict[str, Any]:
    """
    Credit a wallet via third-party API.
    
    Raises:
        ValueError: If credit transfer fails
        WalletAPIError: If third-party API request fails
    """
    # Prepare transfer data for third-party API
    transfer_data = {
        "accountNo": account_no,
        "narration": narration,
        "totalAmount": str(total_amount),
        "transactionId": transaction_id,
        "transactionType": transaction_type,
        "merchant": {
            "isFee": is_fee,
            "merchantFeeAccount": merchant_fee_account,
            "merchantFeeAmount": merchant_fee_amount
        },
    }
    
    try:
        # Call third-party API
        result = await wallet_api_client.credit_transfer(transfer_data)
        logger.info(f"!!! THIRD-PARTY CREDIT RESPONSE !!! for {account_no}: {json.dumps(result, indent=2)}")
        
        # Log transaction in local database
        db = JsonDatabase.read()
        transaction = {
            "id": transaction_id,
            "type": "credit",
            "accountNo": account_no,
            "amount": total_amount,
            "narration": narration,
            "reference": transaction_id,
            "status": "completed",
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "thirdPartyResponse": result
        }
        db['transactions'].append(transaction)
        JsonDatabase.write(db)

        # Sync with PostgreSQL wallet_balances if connection provided
        if conn:
            try:
                # Update or create wallet record with new balance from API
                data = result.get("data", {}) if isinstance(result, dict) else {}
                new_balance_api = data.get("balance", data.get("availableBalance", result.get("balance")))
                
                # Only update if we actually got a balance from the API
                if new_balance_api is not None:
                    await conn.execute(
                        """INSERT INTO wallet_balances (wallet_account, balance, locked_balance, last_synced_at)
                           VALUES ($1, $2, 0.0, NOW())
                           ON CONFLICT (wallet_account) DO UPDATE 
                           SET balance = $2, last_synced_at = NOW()""",
                        account_no, float(new_balance_api)
                    )
                    logger.info(f"Synced wallet_balances for {account_no} after credit: {new_balance_api}")
                else:
                    logger.warning(f"No balance data in API response for {account_no}, skipping local sync")
            except Exception as se:
                logger.warning(f"Failed to sync wallet_balances for {account_no}: {str(se)}")

        logger.info(f"Wallet credited via third-party API: {account_no} with {total_amount}")
        
        # Robust balance extraction
        data = result.get("data", {}) if isinstance(result, dict) else {}
        new_balance = data.get("balance", data.get("availableBalance", result.get("balance", 0.0)))
        
        return {
            "transactionId": transaction_id,
            "accountNo": account_no,
            "amount": total_amount,
            "newBalance": float(new_balance)
        }
    except WalletAPIError as e:
        logger.error(f"Third-party API error during credit transfer: {str(e)}")
        raise ValueError(f"Credit transfer failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during credit transfer: {str(e)}")
        raise ValueError(f"Credit transfer failed: {str(e)}")


# ============= 4. Debit Wallet =============
async def debit_wallet(
    account_no: str,
    narration: str,
    total_amount: float,
    transaction_id: str,
    merchant_fee_account: str,
    merchant_fee_amount: str,
    is_fee: bool,
    transaction_type: str,
    conn: asyncpg.Connection = None
) -> Dict[str, Any]:
    """
    Debit a wallet via third-party API.
    
    Raises:
        ValueError: If debit transfer fails
        WalletAPIError: If third-party API request fails
    """
    # Prepare transfer data for third-party API
    transfer_data = {
        "accountNo": account_no,
        "narration": narration,
        "totalAmount": str(total_amount),
        "transactionId": transaction_id,
        "transactionType": transaction_type,
        "merchant": {
            "isFee": is_fee,
            "merchantFeeAccount": merchant_fee_account,
            "merchantFeeAmount": merchant_fee_amount
        },
    }
    
    try:
        # Call third-party API
        result = await wallet_api_client.debit_transfer(transfer_data)
        logger.info(f"!!! THIRD-PARTY DEBIT RESPONSE !!! for {account_no}: {json.dumps(result, indent=2)}")
        
        # Log transaction in local database
        db = JsonDatabase.read()
        transaction = {
            "id": transaction_id,
            "type": "debit",
            "accountNo": account_no,
            "amount": -total_amount,
            "narration": narration,
            "reference": transaction_id,
            "status": "completed",
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "thirdPartyResponse": result
        }
        db['transactions'].append(transaction)
        JsonDatabase.write(db)

        # Sync with PostgreSQL wallet_balances if connection provided
        if conn:
            try:
                # Update or create wallet record with new balance from API
                data = result.get("data", {}) if isinstance(result, dict) else {}
                new_balance_api = data.get("balance", data.get("availableBalance", result.get("balance")))
                
                # Only update if we actually got a balance from the API
                if new_balance_api is not None:
                    await conn.execute(
                        """INSERT INTO wallet_balances (wallet_account, balance, locked_balance, last_synced_at)
                           VALUES ($1, $2, 0.0, NOW())
                           ON CONFLICT (wallet_account) DO UPDATE 
                           SET balance = $2, last_synced_at = NOW()""",
                        account_no, float(new_balance_api)
                    )
                    logger.info(f"Synced wallet_balances for {account_no} after debit: {new_balance_api}")
                else:
                    logger.warning(f"No balance data in API response for {account_no}, skipping local sync")
            except Exception as se:
                logger.warning(f"Failed to sync wallet_balances for {account_no}: {str(se)}")

        logger.info(f"Wallet debited via third-party API: {account_no} with {total_amount}")
        
        # Robust balance extraction
        data = result.get("data", {}) if isinstance(result, dict) else {}
        new_balance = data.get("balance", data.get("availableBalance", result.get("balance", 0.0)))

        return {
            "transactionId": transaction_id,
            "accountNo": account_no,
            "amount": total_amount,
            "newBalance": float(new_balance)
        }
    except WalletAPIError as e:
        logger.error(f"Third-party API error during debit transfer: {str(e)}")
        raise ValueError(f"Debit transfer failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during debit transfer: {str(e)}")
        raise ValueError(f"Debit transfer failed: {str(e)}")


# ============= 5. Wallet Transfer (P2P) =============
async def transfer_funds(
    sender_account_no: str,
    receiver_account_no: str,
    amount: float,
    narration: str,
    transaction_id: str,
    merchant_fee_account: str,
    merchant_fee_amount: str,
    is_fee: bool,
    conn: asyncpg.Connection = None
) -> Dict[str, Any]:
    """
    Transfer funds from sender wallet to receiver wallet.
    
    This function:
    1. Debits the sender's account
    2. Credits the receiver's account
    3. Logs both transactions
    
    Raises:
        ValueError: If transfer fails at any step
        WalletAPIError: If third-party API request fails
    """
    logger.info(f"Processing transfer: {amount} from {sender_account_no} to {receiver_account_no} (ID: {transaction_id})")
    
    # Step 0: Idempotency Check - Check if this transfer already completed or partially completed
    debit_already_done = False
    try:
        # First check if the CREDIT step already succeeded (= fully complete)
        logger.info(f"Checking idempotency for transaction {transaction_id} (checking CREDIT step)...")
        tsq_credit = await wallet_api_client.requery_transaction(
            transaction_id=f"{transaction_id}-credit",
            amount=amount,
            transaction_type='CREDIT',
            transaction_date=datetime.now().strftime('%Y-%m-%d'),
            account_no=receiver_account_no
        )
        if tsq_credit.get("status") == "SUCCESS" or tsq_credit.get("responseCode") == "00":
            logger.info(f"Transaction {transaction_id} fully completed (credit found). Returning existing success.")
            return {
                "transactionId": transaction_id,
                "senderAccountNo": sender_account_no,
                "receiverAccountNo": receiver_account_no,
                "amount": amount,
                "senderNewBalance": 0.0,
                "receiverNewBalance": 0.0,
                "isDuplicate": True
            }
    except Exception as e:
        logger.info(f"Credit idempotency check found no prior success for {transaction_id}: {str(e)}")
    
    # Check if DEBIT step already succeeded (= partially complete, need to skip to credit)
    try:
        logger.info(f"Checking if debit already succeeded for {transaction_id}...")
        tsq_debit = await wallet_api_client.requery_transaction(
            transaction_id=f"{transaction_id}-debit",
            amount=amount,
            transaction_type='DEBIT',
            transaction_date=datetime.now().strftime('%Y-%m-%d'),
            account_no=sender_account_no
        )
        if tsq_debit.get("status") == "SUCCESS" or tsq_debit.get("responseCode") == "00":
            logger.info(f"Debit for {transaction_id} already succeeded. Skipping debit, proceeding to credit only.")
            debit_already_done = True
    except Exception as e:
        logger.info(f"Debit idempotency check found no prior success for {transaction_id}: {str(e)}")
    
    # Step 1: Debit sender's account (skip if already done)
    sender_new_balance = 0.0
    if not debit_already_done:
        try:
            debit_result = await debit_wallet(
                account_no=sender_account_no,
                narration=f"Transfer to {receiver_account_no}: {narration}",
                total_amount=amount,
                transaction_id=f"{transaction_id}-debit",
                merchant_fee_account=merchant_fee_account,
                merchant_fee_amount=merchant_fee_amount,
                is_fee=is_fee,
                transaction_type="debit",
                conn=conn
            )
            sender_new_balance = debit_result.get("newBalance", 0.0)
            logger.info(f"Sender debited successfully. New balance: {sender_new_balance}")
        except Exception as e:
            logger.error(f"Failed to debit sender: {str(e)}")
            raise ValueError(f"Transfer failed: Unable to debit sender account - {str(e)}")
    else:
        logger.info(f"Skipping debit for {transaction_id} - already completed on bank side")

    
    # Step 2: Credit receiver's account
    try:
        credit_result = await credit_wallet(
            account_no=receiver_account_no,
            narration=f"Transfer from {sender_account_no}: {narration}",
            total_amount=amount,
            transaction_id=f"{transaction_id}-credit",
            merchant_fee_account=merchant_fee_account,
            merchant_fee_amount=merchant_fee_amount,
            is_fee=is_fee,
            transaction_type="credit",
            conn=conn
        )
        receiver_new_balance = credit_result.get("newBalance", 0.0)
        logger.info(f"Receiver credited successfully. New balance: {receiver_new_balance}")
    except Exception as e:
        logger.error(f"Failed to credit receiver: {str(e)}")
        # Note: In production, implement reversal logic here
        raise ValueError(f"Transfer failed: Sender debited but receiver credit failed - {str(e)}")
    
    # Log the complete transfer
    db = JsonDatabase.read()
    transfer_record = {
        "id": transaction_id,
        "type": "transfer",
        "senderAccountNo": sender_account_no,
        "receiverAccountNo": receiver_account_no,
        "amount": amount,
        "narration": narration,
        "status": "completed",
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "debitTransactionId": f"{transaction_id}-debit",
        "creditTransactionId": f"{transaction_id}-credit"
    }
    db['transactions'].append(transfer_record)
    JsonDatabase.write(db)
    
    logger.info(f"Transfer completed successfully: {transaction_id}")
    
    return {
        "transactionId": transaction_id,
        "senderAccountNo": sender_account_no,
        "receiverAccountNo": receiver_account_no,
        "amount": amount,
        "senderNewBalance": sender_new_balance,
        "receiverNewBalance": receiver_new_balance
    }


# ============= 6. Wallet Enquiry =============
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


# ============= 9. Escrow (Hold) Logic =============
async def hold_funds(account_no: str, amount: float, conn: asyncpg.Connection = None) -> Dict[str, Any]:
    """
    Deduct funds from balance and place in locked_balance using PostgreSQL.
    
    Raises:
        ValueError: If account not found or insufficient balance
    """
    logger.info(f"Holding {amount} for account {account_no}")
    
    # Get database connection
    if conn is None:
        from app.db.database import get_pool
        pool = await get_pool()
        conn = await pool.acquire()
        should_release = True
    else:
        should_release = False
    
    try:
        # Fetch actual balance from third-party API
        try:
            logger.info(f"Fetching balance from API for account {account_no}")
            api_wallet = await get_wallet_balance_api(account_no)
            actual_balance = float(api_wallet.get('availableBalance', api_wallet.get('balance', 0.0)))
            logger.info(f"✅ Fetched actual balance from API: {actual_balance} for account {account_no}")
        except Exception as e:
            logger.error(f"❌ Failed to fetch balance from API for {account_no}: {str(e)}")
            logger.error(f"   Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            actual_balance = None
        
        # Get or create wallet balance record
        wallet_record = await conn.fetchrow(
            "SELECT balance, locked_balance FROM wallet_balances WHERE wallet_account = $1",
            account_no
        )
        
        if not wallet_record:
            if actual_balance is None:
                logger.error(f"❌ Cannot create wallet_balances record for {account_no}")
                logger.error(f"   - Not in wallet_balances table")
                logger.error(f"   - API wallet enquiry failed (check logs above)")
                raise ValueError(f"Account {account_no} not found in database and API enquiry failed. Check server logs for API error details.")
            
            # Create new wallet balance record
            logger.info(f"✅ Creating wallet balance record for {account_no} with balance {actual_balance}")
            await conn.execute(
                """INSERT INTO wallet_balances (wallet_account, balance, locked_balance, last_synced_at)
                   VALUES ($1, $2, 0.0, NOW())""",
                account_no, actual_balance
            )
            current_balance = actual_balance
            locked_balance = 0.0
        else:
            # Update balance from API if available
            if actual_balance is not None:
                await conn.execute(
                    "UPDATE wallet_balances SET balance = $1, last_synced_at = NOW() WHERE wallet_account = $2",
                    actual_balance, account_no
                )
                current_balance = actual_balance
            else:
                current_balance = float(wallet_record['balance'])
            locked_balance = float(wallet_record['locked_balance'])
        
        available_balance = current_balance - locked_balance
        
        logger.info(f"Balance check - Total: {current_balance}, Locked: {locked_balance}, Available: {available_balance}, Required: {amount}")
        
        if available_balance < amount:
            raise ValueError(f"Insufficient balance. Available: {available_balance:.2f}, Locked: {locked_balance:.2f}, Required: {amount:.2f}")
        
        # Update balances
        # In this model, balance is TOTAL balance (Available + Locked)
        # hold_funds only increases locked_balance, does NOT change total balance
        new_balance = current_balance 
        new_locked = locked_balance + amount
        
        await conn.execute(
            """UPDATE wallet_balances 
               SET balance = $1, locked_balance = $2, last_synced_at = NOW() 
               WHERE wallet_account = $3""",
            new_balance, new_locked, account_no
        )
        
        logger.info(f"Held {amount} for {account_no}. Total balance: {new_balance}, Locked: {new_locked}")
        
        return {
            "accountNo": account_no,
            "amount": amount,
            "newBalance": new_balance,
            "lockedBalance": new_locked
        }
    finally:
        if should_release:
            await pool.release(conn)


async def release_funds(account_no: str, amount: float, conn: asyncpg.Connection = None) -> Dict[str, Any]:
    """
    Return funds from locked_balance to balance using PostgreSQL.
    
    Raises:
        ValueError: If account not found or insufficient locked balance
    """
    logger.info(f"Releasing {amount} for account {account_no}")
    
    # Get database connection
    if conn is None:
        from app.db.database import get_pool
        pool = await get_pool()
        conn = await pool.acquire()
        should_release = True
    else:
        should_release = False
    
    try:
        wallet_record = await conn.fetchrow(
            "SELECT balance, locked_balance FROM wallet_balances WHERE wallet_account = $1",
            account_no
        )
        
        if not wallet_record:
            raise ValueError(f"Account {account_no} not found")
        
        balance = float(wallet_record['balance'])
        locked_balance = float(wallet_record['locked_balance'])
        
        if locked_balance < amount:
            raise ValueError(f"Insufficient locked balance. Locked: {locked_balance}, Required: {amount}")
        
        # In this model, balance is TOTAL balance (Available + Locked)
        # release_funds only decreases locked_balance, does NOT change total balance
        new_balance = balance 
        new_locked = locked_balance - amount
        
        await conn.execute(
            """UPDATE wallet_balances 
               SET balance = $1, locked_balance = $2, last_synced_at = NOW() 
               WHERE wallet_account = $3""",
            new_balance, new_locked, account_no
        )
        
        logger.info(f"Released {amount} for {account_no}. Total balance: {new_balance}, Locked: {new_locked}")
        
        return {
            "accountNo": account_no,
            "amount": amount,
            "newBalance": new_balance,
            "lockedBalance": new_locked
        }
    finally:
        if should_release:
            await pool.release(conn)


async def complete_transfer_from_hold(
    sender_account: str,
    receiver_account: str,
    amount: float,
    narration: str = "Chat transfer completed",
    conn: asyncpg.Connection = None
) -> Dict[str, Any]:
    """
    Complete a transfer by moving funds from sender's locked_balance to receiver's balance.
    This function:
    1. Releases the held funds from sender's locked_balance
    2. Calls the third-party API to actually transfer the funds
    3. Updates local database balances
    """
    logger.info(f"🔄 COMPLETE_TRANSFER_FROM_HOLD called:")
    logger.info(f"   Sender Account: {sender_account}")
    logger.info(f"   Receiver Account: {receiver_account}")
    logger.info(f"   Amount: {amount}")
    logger.info(f"   Are they the same? {sender_account == receiver_account}")
    
    # Get database connection
    if conn is None:
        from app.db.database import get_pool
        pool = await get_pool()
        conn = await pool.acquire()
        should_release = True
    else:
        should_release = False
    
    try:
        # Get sender wallet balance
        sender_record = await conn.fetchrow(
            "SELECT balance, locked_balance FROM wallet_balances WHERE wallet_account = $1",
            sender_account
        )
        if not sender_record:
            raise ValueError(f"Sender account {sender_account} not found")
        
        sender_locked = float(sender_record['locked_balance'])
        if sender_locked < amount:
            raise ValueError(f"Insufficient locked balance for sender. Available: {sender_locked}, Required: {amount}")
        
        # Generate transaction ID for the actual transfer
        transaction_id = generate_transaction_id()
        
        # Step 1: Call the third-party API to actually transfer the funds
        logger.info(f"Calling third-party API to transfer {amount} from {sender_account} to {receiver_account}")
        try:
            # Debit sender's account via API
            debit_result = await debit_wallet(
                account_no=sender_account,
                narration=f"Transfer to {receiver_account}: {narration}",
                total_amount=amount,
                transaction_id=f"{transaction_id}-debit",
                merchant_fee_account="",
                merchant_fee_amount="0",
                is_fee=False,
                transaction_type="debit",
                conn=conn
            )
            logger.info(f"✅ Sender debited via API. New balance: {debit_result.get('newBalance', 0.0)}")
            
            # Credit receiver's account via API
            credit_result = await credit_wallet(
                account_no=receiver_account,
                narration=f"Transfer from {sender_account}: {narration}",
                total_amount=amount,
                transaction_id=f"{transaction_id}-credit",
                merchant_fee_account="",
                merchant_fee_amount="0",
                is_fee=False,
                transaction_type="credit",
                conn=conn
            )
            logger.info(f"✅ Receiver credited via API. New balance: {credit_result.get('newBalance', 0.0)}")
            
        except Exception as e:
            logger.error(f"❌ Third-party API transfer failed: {str(e)}")
            raise ValueError(f"Transfer failed: {str(e)}")
        
        # Step 2: Update local database - release locked funds
        # Total balance (balance column) was already updated/synced inside debit_wallet()
        new_sender_locked = sender_locked - amount
        
        await conn.execute(
            """UPDATE wallet_balances 
               SET locked_balance = $1, last_synced_at = NOW() 
               WHERE wallet_account = $2""",
            new_sender_locked, sender_account
        )
        
        # Sync receiver balance from API result if available
        data = credit_result.get("data", {}) if isinstance(credit_result, dict) else {}
        receiver_new_balance = data.get('balance', data.get('availableBalance', credit_result.get('newBalance')))
        
        if receiver_new_balance is not None:
            receiver_new_balance = float(receiver_new_balance)
            # Update receiver balance
            await conn.execute(
                """UPDATE wallet_balances 
                   SET balance = $1, last_synced_at = NOW() 
                   WHERE wallet_account = $2""",
                receiver_new_balance, receiver_account
            )
        else:
            # Fallback: fetch current balance from DB
            receiver_new_balance = await conn.fetchval(
                "SELECT balance FROM wallet_balances WHERE wallet_account = $1",
                receiver_account
            )
            logger.warning(f"No balance data returned after credit for {receiver_account}, using existing DB balance: {receiver_new_balance}")
        
        logger.info(f"✅ Transfer completed. Sender locked: {new_sender_locked}, Receiver balance: {receiver_new_balance}")
        
        return {
            "transactionId": transaction_id,
            "senderNewLockedBalance": new_sender_locked,
            "receiverNewBalance": receiver_new_balance
        }
    finally:
        if should_release:
            await pool.release(conn)


def _parse_banks_from_api_response(result: Any) -> List[Dict[str, Any]]:
    """
    Normalize 9PSB get_banks payloads into a list of bank dicts.
    Live API may return data as an array, or as { banks: [...] }, etc.
    """
    if isinstance(result, list):
        return result
    if not isinstance(result, dict):
        return []

    data = result.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("banks", "bankList", "items", "message"):
            nested = data.get(key)
            if isinstance(nested, list) and nested:
                return nested

    for key in ("banks", "bankList", "items"):
        nested = result.get(key)
        if isinstance(nested, list) and nested:
            return nested

    return []


def _normalize_bank_entry(entry: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Map varied bank field names to code + name."""
    if not isinstance(entry, dict):
        return None
    code = entry.get("code") or entry.get("bankCode") or entry.get("bank_code")
    name = entry.get("name") or entry.get("bankName") or entry.get("bank_name")
    if not code or not name:
        return None
    return {"code": str(code).strip(), "name": str(name).strip()}


def _dedupe_banks(banks: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """9PSB can return duplicate bank codes; keep first occurrence per code."""
    seen: set[str] = set()
    unique: List[Dict[str, str]] = []
    for bank in banks:
        code = bank["code"]
        if code in seen:
            continue
        seen.add(code)
        unique.append(bank)
    unique.sort(key=lambda b: b["name"].lower())
    return unique


async def get_banks_api() -> List[Dict[str, Any]]:
    """Fetch list of all banks from third-party API, with local fallback."""
    try:
        result = await wallet_api_client.get_banks()
        logger.info(f"get_banks raw response keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
        raw_banks = _parse_banks_from_api_response(result)
        banks = [b for b in (_normalize_bank_entry(x) for x in raw_banks) if b]
        banks = _dedupe_banks(banks)

        if banks:
            logger.info(f"Parsed {len(banks)} unique banks from 9PSB (raw entries: {len(raw_banks)})")
            return banks

        logger.warning("9PSB get_banks returned no parseable banks; using local bank list")
        return _dedupe_banks(get_bank_list()["banks"])
    except Exception as e:
        logger.error(f"Error fetching banks from 9PSB: {str(e)}")
        logger.info("Falling back to local bank list")
        return _dedupe_banks(get_bank_list()["banks"])


async def account_enquiry_other_bank(account_no: str, bank_code: str) -> Dict[str, Any]:
    """Verify details of an account in another bank."""
    enquiry_data = {
        "customer": {
            "accountNumber": account_no,
            "bankCode": bank_code
        }
    }
    try:
        result = await wallet_api_client.account_enquiry(enquiry_data)
        return result.get("data", {})
    except Exception as e:
        logger.error(f"Error in account enquiry: {str(e)}")
        raise ValueError(f"Account enquiry failed: {str(e)}")


async def transfer_to_other_bank(
    sender_account_no: str,
    amount: float,
    recipient_account_no: str,
    recipient_name: str,
    recipient_bank_code: str,
    narration: str,
    sender_name: str = "",
    transaction_reference: Optional[str] = None,
    conn: Optional[asyncpg.Connection] = None,
) -> Dict[str, Any]:
    """
    Transfer funds from a 9PSB wallet to another bank (wallet_other_banks).
    Runs balance check, calls 9PSB, TSQ on ambiguous codes, syncs local balance log.
    """
    if amount <= 0:
        raise ValueError("Transfer amount must be greater than zero")

    txn_ref = normalize_transaction_reference(transaction_reference, prefix="EXT")
    await assert_sender_available_balance(sender_account_no, amount, conn)

    transfer_data = _build_other_bank_transfer_payload(
        sender_account_no=sender_account_no,
        sender_name=sender_name,
        amount=amount,
        recipient_account_no=recipient_account_no,
        recipient_name=recipient_name,
        recipient_bank_code=recipient_bank_code,
        narration=narration,
        transaction_reference=txn_ref,
    )

    try:
        logger.info(f"External transfer payload: {json.dumps(transfer_data, indent=2)}")
        initial = await wallet_api_client.transfer_other_banks(transfer_data)
        logger.info(f"External transfer response: {json.dumps(initial, indent=2)}")

        result = await _finalize_other_bank_transfer(
            txn_ref, amount, sender_account_no, initial
        )
        transfer_status = result.get("transferStatus", "failed")

        if transfer_status == "completed":
            await get_wallet_balance_api(sender_account_no)
        elif transfer_status == "failed":
            msg = _other_bank_user_message(result, "Transfer to other bank failed")
            raise ValueError(msg)

        db = JsonDatabase.read()
        db["transactions"].append({
            "id": txn_ref,
            "type": "external_transfer",
            "accountNo": sender_account_no,
            "amount": -amount,
            "recipientAccount": recipient_account_no,
            "recipientName": recipient_name,
            "recipientBank": recipient_bank_code,
            "status": transfer_status,
            "reference": txn_ref,
            "responseCode": result.get("responseCode"),
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "thirdPartyResponse": result,
        })
        JsonDatabase.write(db)

        result["transactionReference"] = txn_ref
        return result
    except WalletAPIError as e:
        logger.error(f"9PSB other bank transfer error: {e}")
        if txn_ref:
            try:
                tsq = await _requery_other_bank_transfer(txn_ref, amount, sender_account_no)
                if _other_bank_status_from_result(tsq) == "completed":
                    tsq["transferStatus"] = "completed"
                    tsq["transactionReference"] = txn_ref
                    await get_wallet_balance_api(sender_account_no)
                    return tsq
            except Exception as tsq_err:
                logger.warning(f"TSQ after API error failed: {tsq_err}")
        raise ValueError(f"Transfer to other bank failed: {str(e)}")
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error in other bank transfer: {str(e)}")
        raise ValueError(f"Transfer to other bank failed: {str(e)}")


async def get_transactions_history_api(
    account_number: str,
    from_date: str = None,
    to_date: str = None,
    number_of_items: int = 20
) -> List[Dict[str, Any]]:
    """Fetch transaction history from third-party API."""
    if not from_date:
        from_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not to_date:
        to_date = datetime.utcnow().strftime('%Y-%m-%d')

    # 9PSB wallet_transactions allows at most ~31 days per request
    try:
        from_dt = datetime.strptime(from_date, '%Y-%m-%d')
        to_dt = datetime.strptime(to_date, '%Y-%m-%d')
        if (to_dt - from_dt).days > 30:
            from_dt = to_dt - timedelta(days=30)
            from_date = from_dt.strftime('%Y-%m-%d')
            logger.info(f"Clamped transaction history fromDate to {from_date} (30-day API limit)")
    except ValueError:
        from_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
        to_date = datetime.utcnow().strftime('%Y-%m-%d')

    history_data = {
        "accountNumber": account_number,
        "fromDate": from_date,
        "toDate": to_date,
        "numberOfItems": str(number_of_items)
    }
    logger.info(f"Fetching transaction history: account={account_number}, from={history_data['fromDate']}, to={history_data['toDate']}")
    try:
        result = await wallet_api_client.get_transaction_history(history_data)
        logger.info(f"!!! TRANSACTION HISTORY RAW RESPONSE !!!: {json.dumps(result, indent=2)}")

        if not isinstance(result, dict):
            logger.warning(f"Unexpected response type from API: {type(result)}")
            return []

        # Try known key paths for the transactions list.
        # IMPORTANT: do NOT use 'or' chaining — an empty list [] is falsy
        # and would cause fall-through to the string 'message' field.
        data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}

        for txns_val in [
            result.get("transactions"),
            data.get("transactions"),
            data.get("message"),   # The confirmed key from the live API
            result.get("items"),
        ]:
            if isinstance(txns_val, list):
                logger.info(f"Found {len(txns_val)} transactions")
                return txns_val

        logger.warning(f"No transaction list found in response keys. data keys: {list(data.keys())}")
        return []
    except Exception as e:
        logger.error(f"Error fetching transaction history: {str(e)}")
        # Return empty list so wallet UI still loads (history is non-critical)
        return []


async def get_wallet_balance_api(account_no: str) -> Dict[str, Any]:
    """Get wallet details and balance from third-party API."""
    try:
        result = await wallet_api_client.get_wallet_balance(account_no)
        logger.info(f"!!! THIRD-PARTY BALANCE RESPONSE !!! for {account_no}: {json.dumps(result, indent=2)}")
        if isinstance(result, dict) and result.get("status") == "SUCCESS":
            data = result.get("data", {})
            balance = data.get("availableBalance", data.get("balance"))
            
            if balance is not None:
                # Sync to PostgreSQL
                from app.db.database import get_pool
                try:
                    db_pool = await get_pool()
                    async with db_pool.acquire() as conn:
                        await conn.execute(
                            """INSERT INTO wallet_balances (wallet_account, balance, locked_balance, last_synced_at)
                               VALUES ($1, $2, 0.0, NOW())
                               ON CONFLICT (wallet_account) DO UPDATE 
                               SET balance = $2, last_synced_at = NOW()""",
                            account_no, float(balance)
                        )
                        logger.info(f"Synced local balance for {account_no} during enquiry: {balance}")
                except Exception as se:
                    logger.warning(f"Failed to sync local balance during enquiry: {str(se)}")
            
            return data
        return {}
    except Exception as e:
        logger.error(f"Error in wallet enquiry for {account_no}: {str(e)}")
        raise ValueError(f"Wallet enquiry failed: {str(e)}")
