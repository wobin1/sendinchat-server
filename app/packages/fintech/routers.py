from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional
import logging

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
    BankListResponse,
    ClientAuthRequest, ClientAuthResponse
)
from app.packages.fintech import service as fintech_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fintech", tags=["fintech"])


# ============= 1. Create Wallet =============
@router.post("/wallet/create", response_model=WalletResponse, status_code=status.HTTP_201_CREATED)
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
        return WalletResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Wallet creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Wallet creation failed"
        )


# ============= 2. Bank Transfer =============
@router.post("/transfer/bank", response_model=BankTransferResponse, status_code=status.HTTP_200_OK)
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
        return BankTransferResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Bank transfer failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bank transfer failed"
        )


# ============= 3. Wallet Transfer (P2P) =============
@router.post("/wallet/transfer", response_model=WalletTransferResponse, status_code=status.HTTP_200_OK)
async def transfer_wallet(request: WalletTransferRequest):
    """
    Transfer funds between two wallet accounts.
    
    This endpoint debits the sender's account and credits the receiver's account.
    """
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
        return WalletTransferResponse(
            message="Transfer successful",
            **result
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Transfer failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transfer failed"
        )


# Note: Credit and Debit endpoints removed - use transfer endpoint instead
# These operations are now internal only, called by the transfer function



# ============= 5. Wallet Enquiry =============
@router.post("/wallet/enquiry", response_model=WalletEnquiryResponse, status_code=status.HTTP_200_OK)
async def wallet_enquiry(request: WalletEnquiryRequest):
    """
    Get wallet details and balance.
    
    This endpoint retrieves wallet information.
    """
    try:
        result = fintech_service.get_wallet_enquiry(
            account_no=request.accountNo
        )
        return WalletEnquiryResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Wallet enquiry failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Wallet enquiry failed"
        )


# ============= 6. Wallet Transactions =============
@router.post("/wallet/transactions", response_model=WalletTransactionsResponse, status_code=status.HTTP_200_OK)
async def wallet_transactions(request: WalletTransactionsRequest):
    """
    Get wallet transaction history.
    
    This endpoint retrieves transaction history for a wallet within a date range.
    """
    try:
        result = fintech_service.get_wallet_transactions(
            account_number=request.accountNumber,
            from_date=request.fromDate,
            to_date=request.toDate,
            number_of_items=request.numberOfItems
        )
        return WalletTransactionsResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Wallet transactions query failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Wallet transactions query failed"
        )


# ============= 7. Get Bank List =============
@router.get("/banks", response_model=BankListResponse, status_code=status.HTTP_200_OK)
async def get_banks():
    """
    Get list of supported banks.
    
    This endpoint returns all available banks for transfers.
    """
    try:
        result = fintech_service.get_bank_list()
        return BankListResponse(**result)
    except Exception as e:
        logger.error(f"Bank list retrieval failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bank list retrieval failed"
        )


# ============= 8. Client Authentication =============
@router.post("/auth", response_model=ClientAuthResponse, status_code=status.HTTP_200_OK)
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
        return ClientAuthResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Client authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Client authentication failed"
        )


# ============= Account Management =============

# ============= 9. Wallet Upgrade =============
@router.post("/wallet/upgrade", response_model=WalletUpgradeResponse, status_code=status.HTTP_200_OK)
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
        return WalletUpgradeResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Wallet upgrade failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Wallet upgrade failed"
        )


# ============= 10. Upgrade Status =============
@router.get("/wallet/upgrade-status/{accountNo}", response_model=UpgradeStatusResponse, status_code=status.HTTP_200_OK)
async def get_upgrade_status(accountNo: str):
    """
    Get wallet upgrade status.
    
    This endpoint checks the status of a wallet upgrade request.
    """
    try:
        result = await fintech_service.get_upgrade_status(accountNo)
        return UpgradeStatusResponse(
            accountNumber=accountNo,
            **result
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Upgrade status query failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upgrade status query failed"
        )


# ============= 11. Get Wallet by BVN =============
@router.get("/wallet/by-bvn/{bvn}", response_model=GetWalletByBVNResponse, status_code=status.HTTP_200_OK)
async def get_wallet_by_bvn(bvn: str):
    """
    Get wallet information by BVN.
    
    This endpoint retrieves wallet details using the Bank Verification Number.
    """
    try:
        result = await fintech_service.get_wallet_by_bvn(bvn)
        return GetWalletByBVNResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Get wallet by BVN failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Get wallet by BVN failed"
        )


# ============= Webhooks =============

# ============= 12. Inflow Notification Webhook =============
@router.post("/webhooks/inflow", response_model=WebhookResponse, status_code=status.HTTP_200_OK)
async def inflow_webhook(payload: InflowWebhookPayload):
    """
    Webhook endpoint for inflow notifications from third-party API.
    
    This endpoint receives notifications when funds are credited to a wallet account.
    The third-party API calls this endpoint to notify about incoming transfers.
    """
    try:
        result = fintech_service.handle_inflow_notification(payload.dict())
        return WebhookResponse(**result)
    except ValueError as e:
        logger.error(f"Inflow webhook processing failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Inflow webhook error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )


# ============= 13. Upgrade Status Notification Webhook =============
@router.post("/webhooks/upgrade-status", response_model=WebhookResponse, status_code=status.HTTP_200_OK)
async def upgrade_status_webhook(payload: UpgradeStatusWebhookPayload):
    """
    Webhook endpoint for upgrade status notifications from third-party API.
    
    This endpoint receives notifications when a wallet upgrade request is approved or declined.
    The third-party API calls this endpoint to notify about upgrade status changes.
    """
    try:
        result = fintech_service.handle_upgrade_status_notification(payload.dict())
        return WebhookResponse(**result)
    except ValueError as e:
        logger.error(f"Upgrade status webhook processing failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Upgrade status webhook error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )


