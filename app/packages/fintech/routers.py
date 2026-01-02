from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional
import logging

from app.packages.fintech.schemas import (
    CreateWalletRequest, WalletResponse,
    BankTransferRequest, BankTransferResponse,
    WalletOperationRequest, WalletOperationResponse,
    WalletEnquiryRequest, WalletEnquiryResponse,
    WalletTransactionsRequest, WalletTransactionsResponse,
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
        result = fintech_service.create_wallet(
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


# ============= 3. Credit Wallet =============
@router.post("/wallet/credit", response_model=WalletOperationResponse, status_code=status.HTTP_200_OK)
async def credit_wallet(request: WalletOperationRequest):
    """
    Credit a wallet.
    
    This endpoint adds funds to a wallet account.
    """
    try:
        result = fintech_service.credit_wallet(
            account_no=request.accountNo,
            narration=request.narration,
            total_amount=request.totalAmount,
            transaction_id=request.transactionId,
            merchant_fee_account=request.merchant.merchantFeeAccount,
            merchant_fee_amount=request.merchant.merchantFeeAmount,
            is_fee=request.merchant.isFee,
            transaction_type=request.transactionType
        )
        return WalletOperationResponse(
            message="Wallet credited successfully",
            **result
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Wallet credit failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Wallet credit failed"
        )


# ============= 4. Debit Wallet =============
@router.post("/wallet/debit", response_model=WalletOperationResponse, status_code=status.HTTP_200_OK)
async def debit_wallet(request: WalletOperationRequest):
    """
    Debit a wallet.
    
    This endpoint deducts funds from a wallet account.
    """
    try:
        result = fintech_service.debit_wallet(
            account_no=request.accountNo,
            narration=request.narration,
            total_amount=request.totalAmount,
            transaction_id=request.transactionId,
            merchant_fee_account=request.merchant.merchantFeeAccount,
            merchant_fee_amount=request.merchant.merchantFeeAmount,
            is_fee=request.merchant.isFee,
            transaction_type=request.transactionType
        )
        return WalletOperationResponse(
            message="Wallet debited successfully",
            **result
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Wallet debit failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Wallet debit failed"
        )


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
