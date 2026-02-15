from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional
import logging
import asyncpg

from app.packages.fintech.schemas import (
    CreateWalletRequest, WalletResponse,
    BankTransferRequest, BankTransferResponse,
    WalletOperationRequest, WalletOperationResponse,
    WalletTransferRequest, WalletTransferResponse,
    WalletEnquiryRequest, WalletEnquiryResponse,
    WalletTransactionsRequest, WalletTransactionsResponse,
    WalletUpgradeRequest, WalletUpgradeResponse,
    UpgradeStatusResponse, GetWalletByBVNResponse,
    InflowWebhookPayload, UpgradeStatusWebhookPayload, WebhookResponse,
    BankListResponse, BankInfo,
    ClientAuthRequest, ClientAuthResponse,
    StandardWalletResponse, StandardBankTransferResponse,
    StandardWalletTransferResponse, StandardWalletEnquiryResponse,
    StandardWalletTransactionsResponse, StandardBankListResponse,
    StandardClientAuthResponse, StandardWalletUpgradeResponse,
    StandardUpgradeStatusResponse, StandardGetWalletByBVNResponse,
    StandardWebhookResponse,
    OtherBankEnquiryRequest, ExternalTransferRequest, TransactionItem
)
from app.packages.fintech import service as fintech_service
from app.users.routers import get_current_user
from app.users import service as user_service
from app.users.models import User
from app.db.database import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fintech", tags=["fintech"])


def parse_amount(val):
    """Robustly parse amount strings with commas and other formatting."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        # Remove commas and other non-numeric chars except dot
        clean_val = "".join(c for c in val if c.isdigit() or c == ".")
        try:
            return float(clean_val)
        except ValueError:
            return 0.0
    return 0.0


# ============= 1. Create Wallet =============
@router.post("/wallet/create", response_model=StandardWalletResponse, status_code=status.HTTP_201_CREATED)
async def create_wallet(request: CreateWalletRequest):
    """
    Create a new wallet.
    
    This endpoint creates a new wallet account with the provided KYC details.
    """
    try:
        result = await fintech_service.create_wallet(
            bvn=request.bvn,
            date_of_birth=request.dateOfBirth,
            gender=request.gender,
            last_name=request.lastName,
            other_names=request.otherNames,
            phone_no=request.phoneNo,
            transaction_tracking_ref=request.transactionTrackingRef,
            account_name=request.accountName,
            place_of_birth=request.placeOfBirth,
            address=request.address,
            national_identity_no=request.nationalIdentityNo,
            next_of_kin_phone_no=request.nextOfKinPhoneNo,
            next_of_kin_name=request.nextOfKinName,
            email=request.email
        )
        return {
            "status": "success",
            "message": "Wallet created successfully",
            "data": WalletResponse(**result)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e), "data": None}
        )
    except Exception as e:
        logger.error(f"Wallet creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Wallet creation failed", "data": None}
        )

@router.post("/wallet/onboard", response_model=StandardWalletResponse, status_code=status.HTTP_201_CREATED)
async def onboard_wallet(
    request: CreateWalletRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Create a new wallet and link it to the current user.
    If user already has a wallet, returns the existing wallet details.
    """
    try:
        # Check if user already has a wallet account
        if current_user.wallet_account:
            logger.info(f"User {current_user.username} already has wallet: {current_user.wallet_account}")
            
            # Fetch wallet details from third-party API
            try:
                wallet_details = await fintech_service.wallet_enquiry(current_user.wallet_account)
                return {
                    "status": "success",
                    "message": "Wallet already exists",
                    "data": WalletResponse(
                        accountNo=current_user.wallet_account,
                        accountName=wallet_details.get("accountName", current_user.username),
                        bvn=request.bvn,
                        balance=wallet_details.get("balance", 0.0)
                    )
                }
            except Exception as e:
                logger.warning(f"Failed to fetch existing wallet details: {str(e)}")
                # Return basic info even if enquiry fails
                return {
                    "status": "success",
                    "message": "Wallet already exists",
                    "data": WalletResponse(
                        accountNo=current_user.wallet_account,
                        accountName=current_user.username,
                        bvn=request.bvn,
                        balance=0.0
                    )
                }
        
        # 1. Create the wallet via fintech service
        result = await fintech_service.create_wallet(
            bvn=request.bvn,
            date_of_birth=request.dateOfBirth,
            gender=request.gender,
            last_name=request.lastName,
            other_names=request.otherNames,
            phone_no=request.phoneNo,
            transaction_tracking_ref=request.transactionTrackingRef,
            account_name=request.accountName,
            place_of_birth=request.placeOfBirth,
            address=request.address,
            national_identity_no=request.nationalIdentityNo,
            next_of_kin_phone_no=request.nextOfKinPhoneNo,
            next_of_kin_name=request.nextOfKinName,
            email=request.email
        )
        
        # 2. Link the account number to the user in the database
        account_no = result.get("accountNo")
        if account_no:
            await user_service.assign_wallet_account(conn, current_user.id, account_no)
            logger.info(f"Linked wallet {account_no} to user {current_user.username}")
        
        return {
            "status": "success",
            "message": "Wallet created and linked successfully",
            "data": WalletResponse(**result)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e), "data": None}
        )
    except Exception as e:
        logger.error(f"Wallet onboarding failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Wallet onboarding failed", "data": None}
        )


# ============= 2. Bank Transfer =============
@router.post("/transfer/bank", response_model=StandardBankTransferResponse, status_code=status.HTTP_200_OK)
async def bank_transfer(request: BankTransferRequest):
    """
    Transfer funds to another bank.
    
    This endpoint processes inter-bank transfers.
    """
    try:
        result = fintech_service.bank_transfer(
            sender_account=request.customer.account.senderaccountnumber,
            sender_name=request.customer.account.sendername,
            recipient_account=request.customer.account.number,
            recipient_name=request.customer.account.name,
            recipient_bank=request.customer.account.bank,
            amount=request.order.amount,
            narration=request.narration,
            reference=request.transaction.reference,
            session_id=request.transaction.sessionId,
            merchant_fee_account=request.merchant.merchantFeeAccount,
            merchant_fee_amount=request.merchant.merchantFeeAmount,
            is_fee=request.merchant.isFee
        )
        return {
            "status": "success",
            "message": "Bank transfer successful",
            "data": BankTransferResponse(**result)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e), "data": None}
        )
    except Exception as e:
        logger.error(f"Bank transfer failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Bank transfer failed", "data": None}
        )


@router.post("/transfer/external", response_model=StandardBankTransferResponse, status_code=status.HTTP_200_OK)
async def transfer_external(
    request: ExternalTransferRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Transfer funds from user's wallet to another bank.
    """
    if not current_user.wallet_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": "User does not have a wallet account", "data": None}
        )
    
    try:
        result = await fintech_service.transfer_to_other_bank(
            sender_account_no=current_user.wallet_account,
            amount=request.amount,
            recipient_account_no=request.recipientAccountNumber,
            recipient_name=request.recipientName,
            recipient_bank_code=request.recipientBankCode,
            narration=request.narration
        )
        # Transform result to BankTransferResponse
        # API return usually includes transactionReference, etc.
        data = result.get("data", {})
        txn = data.get("transaction", {})
        cust = data.get("customer", {})
        
        return {
            "status": "success",
            "message": "External transfer initiated successfully",
            "data": {
                "transactionReference": txn.get("reference", "N/A"),
                "amount": str(request.amount),
                "recipientAccount": cust.get("accountNumber", request.recipientAccountNumber),
                "recipientBank": cust.get("bankCode", request.recipientBankCode)
            }
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e), "data": None}
        )
    except Exception as e:
        logger.error(f"External transfer failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "External transfer failed", "data": None}
        )


@router.post("/enquiry/other-bank", response_model=StandardWalletEnquiryResponse, status_code=status.HTTP_200_OK)
async def other_bank_enquiry(request: OtherBankEnquiryRequest):
    """
    Verify account details in another bank.
    """
    try:
        result = await fintech_service.account_enquiry_other_bank(
            account_no=request.accountNumber,
            bank_code=request.bankCode
        )
        return {
            "status": "success",
            "message": "Account enquiry successful",
            "data": {
                "accountNo": result.get("accountNumber"),
                "accountName": result.get("accountName"),
                "balance": 0.0,  # Other bank enquiry doesn't return balance usually
                "phoneNo": "",
                "email": ""
            }
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e), "data": None}
        )
    except Exception as e:
        logger.error(f"Account enquiry failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Account enquiry failed", "data": None}
        )


# ============= 3. Wallet Transfer (P2P) =============
@router.post("/wallet/transfer", response_model=StandardWalletTransferResponse, status_code=status.HTTP_200_OK)
async def transfer_wallet(request: WalletTransferRequest):
    """
    Transfer funds between two wallet accounts.
    
    This endpoint debits the sender's account and credits the receiver's account.
    """
    logger.info(f"Transfer request: {request.senderAccountNo} -> {request.receiverAccountNo}, amount: {request.amount}")
    try:
        result = await fintech_service.transfer_funds(
            sender_account_no=request.senderAccountNo,
            receiver_account_no=request.receiverAccountNo,
            amount=request.amount,
            narration=request.narration,
            transaction_id=request.transactionId,
            merchant_fee_account=request.merchant.merchantFeeAccount,
            merchant_fee_amount=request.merchant.merchantFeeAmount,
            is_fee=request.merchant.isFee
        )
        logger.info(f"Transfer successful: {request.transactionId}")
        return {
            "status": "success",
            "message": "Transfer successful",
            "data": WalletTransferResponse(message="Transfer successful", **result)
        }
    except ValueError as e:
        logger.error(f"Transfer validation error: {str(e)}")
        logger.error(f"Request details: sender={request.senderAccountNo}, receiver={request.receiverAccountNo}, amount={request.amount}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e), "data": None}
        )
    except Exception as e:
        logger.error(f"Transfer failed: {str(e)}")
        logger.error(f"Request details: sender={request.senderAccountNo}, receiver={request.receiverAccountNo}, amount={request.amount}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error traceback:", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Transfer failed", "data": None}
        )


# Note: Credit and Debit endpoints removed - use transfer endpoint instead
# These operations are now internal only, called by the transfer function



# ============= 5. Wallet Enquiry =============
@router.post("/wallet/enquiry", response_model=StandardWalletEnquiryResponse, status_code=status.HTTP_200_OK)
async def wallet_enquiry(request: WalletEnquiryRequest):
    """
    Get wallet details and balance.
    
    This endpoint retrieves wallet information.
    """
    try:
        # Use API version if user has a wallet account, else fallback to mock (or vice-versa)
        # Actually, let's always use API version for consistency if it's integrated
        result = await fintech_service.get_wallet_balance_api(
            account_no=request.accountNo
        )
        return {
            "status": "success",
            "message": "Wallet enquiry successful",
            "data": WalletEnquiryResponse(
                accountNo=result.get("nuban", result.get("accountNumber", request.accountNo)),
                accountName=result.get("name", result.get("accountName", "Unknown")),
                balance=parse_amount(result.get("availableBalance", result.get("balance"))),
                phoneNo=result.get("phoneNo", result.get("phoneNumber", "")),
                email=result.get("email", ""),
                tier=str(result.get("tier", "1"))
            )
        }
    except ValueError as e:
        # Fallback to local DB for now to avoid breaking UI if API is down/throttled
        try:
            result = fintech_service.get_wallet_enquiry(account_no=request.accountNo)
            return {
                "status": "success",
                "message": "Wallet enquiry successful (local)",
                "data": WalletEnquiryResponse(**result)
            }
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": str(e), "data": None}
            )
    except Exception as e:
        logger.error(f"Wallet enquiry failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Wallet enquiry failed", "data": None}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "message": str(e), "data": None}
        )
    except Exception as e:
        logger.error(f"Wallet enquiry failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Wallet enquiry failed", "data": None}
        )


# ============= 6. Wallet Transactions =============
@router.post("/wallet/transactions", response_model=StandardWalletTransactionsResponse, status_code=status.HTTP_200_OK)
async def wallet_transactions(request: WalletTransactionsRequest):
    """
    Get wallet transaction history.
    
    This endpoint retrieves transaction history for a wallet within a date range.
    """
    try:
        result = await fintech_service.get_transactions_history_api(
            account_number=request.accountNumber,
            from_date=request.fromDate,
            to_date=request.toDate,
            number_of_items=int(request.numberOfItems)
        )
        
        # Ensure result is a list before iterating
        if not isinstance(result, list):
            logger.warning(f"Expected list for transactions, got {type(result)}: {result}")
            result = []

        # Transform API transactions to TransactionItem format
        txns = []
        for t in result:
            # Derive type and otherParty if possible
            is_credit = bool(t.get("credit"))
            is_debit = bool(t.get("debit"))
            txn_type = "CREDIT" if is_credit else "DEBIT" if is_debit else t.get("postingType", "TRANSFER")

            txns.append(TransactionItem(
                id=str(t.get("uniqueIdentifier", t.get("id", ""))),
                type=txn_type,
                amount=parse_amount(t.get("amount")),
                narration=t.get("narration", ""),
                reference=t.get("referenceID", t.get("reference", "")),
                status=t.get("status", "completed"),
                createdAt=t.get("transactionDate", ""),
                otherParty=t.get("otherParty")
            ))
            
        return {
            "status": "success",
            "message": "Wallet transactions retrieved successfully",
            "data": WalletTransactionsResponse(
                accountNumber=request.accountNumber,
                transactions=txns,
                totalCount=len(txns)
            )
        }

    except ValueError as e:
        # Fallback to local
        try:
            result = fintech_service.get_wallet_transactions(
                account_number=request.accountNumber,
                from_date=request.fromDate,
                to_date=request.toDate,
                number_of_items=request.numberOfItems
            )
            return {
                "status": "success",
                "message": "Wallet transactions retrieved successfully (local)",
                "data": WalletTransactionsResponse(**result)
            }
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": str(e), "data": None}
            )
    except Exception as e:
        logger.error(f"Wallet transactions query failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Wallet transactions query failed", "data": None}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e), "data": None}
        )
    except Exception as e:
        logger.error(f"Wallet transactions query failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Wallet transactions query failed", "data": None}
        )


# ============= 6.5 Pending Transactions =============
@router.get("/transactions/pending", response_model=StandardWalletTransactionsResponse)
async def get_pending_transactions(
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Get all pending transactions for the current user.
    
    These are usually chat-initiated transfers waiting for the receiver to accept.
    """
    try:
        records = await conn.fetch(
            """
            SELECT t.id, t.sender_id, u.username as sender_username, t.amount, t.status, t.created_at, m.id as message_id
            FROM transactions t
            JOIN users u ON t.sender_id = u.id
            LEFT JOIN messages m ON t.id::text = m.transaction_id
            WHERE t.receiver_id = $1 AND t.status = 'pending'
            ORDER BY t.created_at DESC
            """,
            current_user.id
        )
        
        txns = []
        for r in records:
            txns.append(TransactionItem(
                id=str(r['id']),
                type="transfer",
                amount=float(r['amount']),
                narration=f"Transfer from {r['sender_username']}",
                reference=f"PEND-{r['id']}",
                status=r['status'],
                createdAt=r['created_at'].isoformat(),
                otherParty=r['sender_username'],
                # Add extra fields that might be useful
                message_id=r['message_id']
            ))
            
        return {
            "status": "success",
            "message": "Pending transactions retrieved successfully",
            "data": WalletTransactionsResponse(
                accountNumber=current_user.wallet_account or "N/A",
                transactions=txns,
                totalCount=len(txns)
            )
        }
    except Exception as e:
        logger.error(f"Failed to fetch pending transactions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to fetch pending transactions", "data": None}
        )


# ============= 7. Get Bank List =============
@router.get("/banks", response_model=StandardBankListResponse, status_code=status.HTTP_200_OK)
async def get_banks():
    """
    Get list of supported banks.
    
    This endpoint returns all available banks for transfers.
    """
    try:
        result = await fintech_service.get_banks_api()
        banks = [BankInfo(code=b.get("code"), name=b.get("name")) for b in result]
        return {
            "status": "success",
            "message": "Bank list retrieved successfully",
            "data": BankListResponse(banks=banks, count=len(banks))
        }
    except Exception as e:
        # Fallback to local
        logger.warning(f"Bank list API failed, falling back to local: {str(e)}")
        result = fintech_service.get_bank_list()
        return {
            "status": "success",
            "message": "Bank list retrieved successfully (local)",
            "data": BankListResponse(**result)
        }
    except Exception as e:
        logger.error(f"Bank list retrieval failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Bank list retrieval failed", "data": None}
        )


# ============= 8. Client Authentication =============
@router.post("/auth", response_model=StandardClientAuthResponse, status_code=status.HTTP_200_OK)
async def authenticate_client(request: ClientAuthRequest):
    """
    Authenticate a client using credentials.
    
    This endpoint authenticates merchant/service clients.
    """
    try:
        result = fintech_service.authenticate_client(
            client_id=request.clientId,
            client_secret=request.clientSecret
        )
        return {
            "status": "success",
            "message": "Client authenticated successfully",
            "data": ClientAuthResponse(**result)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": str(e), "data": None}
        )
    except Exception as e:
        logger.error(f"Client authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Client authentication failed", "data": None}
        )


# ============= Account Management =============

# ============= 9. Wallet Upgrade =============
@router.post("/wallet/upgrade", response_model=StandardWalletUpgradeResponse, status_code=status.HTTP_200_OK)
async def upgrade_wallet(request: WalletUpgradeRequest):
    """
    Upgrade wallet account tier.
    
    This endpoint submits a request to upgrade the wallet from Tier 1 to Tier 2 or Tier 3.
    Requires additional KYC documents.
    """
    try:
        result = await fintech_service.upgrade_wallet(
            account_number=request.accountNumber,
            bvn=request.bvn,
            nin=request.nin,
            account_name=request.accountName,
            phone_number=request.phoneNumber,
            tier=request.tier,
            email=request.email,
            user_photo=request.userPhoto,
            id_type=request.idType,
            id_number=request.idNumber,
            id_issue_date=request.idIssueDate,
            id_expiry_date=request.idExpiryDate,
            id_card_front=request.idCardFront,
            id_card_back=request.idCardBack,
            house_number=request.houseNumber,
            street_name=request.streetName,
            state=request.state,
            city=request.city,
            local_government=request.localGovernment,
            pep=request.pep,
            customer_signature=request.customerSignature,
            utility_bill=request.utilityBill,
            nearest_landmark=request.nearestLandmark,
            place_of_birth=request.placeOfBirth,
            proof_of_address_verification=request.proofOfAddressVerification
        )
        return {
            "status": "success",
            "message": "Wallet upgrade request submitted successfully",
            "data": WalletUpgradeResponse(**result)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e), "data": None}
        )
    except Exception as e:
        logger.error(f"Wallet upgrade failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Wallet upgrade failed", "data": None}
        )


# ============= 10. Upgrade Status =============
@router.get("/wallet/upgrade-status/{accountNo}", response_model=StandardUpgradeStatusResponse, status_code=status.HTTP_200_OK)
async def get_upgrade_status(accountNo: str):
    """
    Get wallet upgrade status.
    
    This endpoint checks the status of a wallet upgrade request.
    """
    try:
        result = await fintech_service.get_upgrade_status(accountNo)
        return {
            "status": "success",
            "message": "Upgrade status retrieved successfully",
            "data": UpgradeStatusResponse(accountNumber=accountNo, **result)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e), "data": None}
        )
    except Exception as e:
        logger.error(f"Upgrade status query failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Upgrade status query failed", "data": None}
        )


# ============= 11. Get Wallet by BVN =============
@router.get("/wallet/by-bvn/{bvn}", response_model=StandardGetWalletByBVNResponse, status_code=status.HTTP_200_OK)
async def get_wallet_by_bvn(bvn: str):
    """
    Get wallet information by BVN.
    
    This endpoint retrieves wallet details using the Bank Verification Number.
    """
    try:
        result = await fintech_service.get_wallet_by_bvn(bvn)
        return {
            "status": "success",
            "message": "Wallet retrieved successfully",
            "data": GetWalletByBVNResponse(**result)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e), "data": None}
        )
    except Exception as e:
        logger.error(f"Get wallet by BVN failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Get wallet by BVN failed", "data": None}
        )


# ============= Webhooks =============

# ============= 12. Inflow Notification Webhook =============
@router.post("/webhooks/inflow", response_model=StandardWebhookResponse, status_code=status.HTTP_200_OK)
async def inflow_webhook(payload: InflowWebhookPayload):
    """
    Webhook endpoint for inflow notifications from third-party API.
    
    This endpoint receives notifications when funds are credited to a wallet account.
    The third-party API calls this endpoint to notify about incoming transfers.
    """
    try:
        result = fintech_service.handle_inflow_notification(payload.dict())
        return {
            "status": "success",
            "message": "Webhook processed successfully",
            "data": WebhookResponse(**result)
        }
    except ValueError as e:
        logger.error(f"Inflow webhook processing failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e), "data": None}
        )
    except Exception as e:
        logger.error(f"Inflow webhook error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Webhook processing failed", "data": None}
        )


# ============= 13. Upgrade Status Notification Webhook =============
@router.post("/webhooks/upgrade-status", response_model=StandardWebhookResponse, status_code=status.HTTP_200_OK)
async def upgrade_status_webhook(payload: UpgradeStatusWebhookPayload):
    """
    Webhook endpoint for upgrade status notifications from third-party API.
    
    This endpoint receives notifications when a wallet upgrade request is approved or declined.
    The third-party API calls this endpoint to notify about upgrade status changes.
    """
    try:
        result = fintech_service.handle_upgrade_status_notification(payload.dict())
        return {
            "status": "success",
            "message": "Webhook processed successfully",
            "data": WebhookResponse(**result)
        }
    except ValueError as e:
        logger.error(f"Upgrade status webhook processing failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e), "data": None}
        )
    except Exception as e:
        logger.error(f"Upgrade status webhook error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Webhook processing failed", "data": None}
        )
