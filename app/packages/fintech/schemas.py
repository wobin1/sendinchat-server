from pydantic import BaseModel, Field, EmailStr
from decimal import Decimal
from typing import Optional, List
from datetime import datetime


# ============= Wallet Creation =============
class CreateWalletRequest(BaseModel):
    """Schema for wallet creation request."""
    bvn: str = Field(..., min_length=11, max_length=11, description="Bank Verification Number")
    dateOfBirth: str = Field(..., description="Date of birth")
    gender: int = Field(..., ge=1, le=2, description="Gender: 1=Male, 2=Female")
    lastName: str = Field(..., min_length=1)
    otherNames: str = Field(..., min_length=1)
    phoneNo: str = Field(..., min_length=10, max_length=11)
    transactionTrackingRef: str
    accountName: str
    placeOfBirth: str
    address: str
    nationalIdentityNo: str
    nextOfKinPhoneNo: str
    nextOfKinName: str
    email: EmailStr


class WalletResponse(BaseModel):
    """Schema for wallet response."""
    accountNo: str
    accountName: str
    bvn: str
    balance: float
    status: str = "success"
    message: str = "Wallet created successfully"
    
    class Config:
        from_attributes = True


# ============= Bank Transfer =============
class BankAccount(BaseModel):
    """Bank account details for transfer."""
    bank: str = Field(..., description="Bank code")
    name: str = Field(..., description="Account name")
    number: str = Field(..., description="Account number")
    senderaccountnumber: str = Field(..., description="Sender account number")
    sendername: str = Field(..., description="Sender name")


class Customer(BaseModel):
    """Customer details."""
    account: BankAccount


class Order(BaseModel):
    """Order details."""
    amount: str = Field(..., description="Transfer amount")
    country: str
    currency: str
    description: str


class TransactionDetails(BaseModel):
    """Transaction details."""
    reference: str
    sessionId: str


class Merchant(BaseModel):
    """Merchant fee details."""
    isFee: bool
    merchantFeeAccount: str
    merchantFeeAmount: str


class BankTransferRequest(BaseModel):
    """Schema for bank transfer request."""
    customer: Customer
    narration: str
    order: Order
    transaction: TransactionDetails
    merchant: Merchant
    code: Optional[str] = None
    message: Optional[str] = None


class BankTransferResponse(BaseModel):
    """Schema for bank transfer response."""
    status: str = "success"
    message: str = "Transfer successful"
    transactionReference: str
    amount: str
    recipientAccount: str
    recipientBank: str


# ============= Credit/Debit Wallet =============
class WalletOperationRequest(BaseModel):
    """Schema for wallet credit/debit request."""
    accountNo: str = Field(..., min_length=10, max_length=10)
    narration: str
    totalAmount: float = Field(..., gt=0)
    transactionId: str
    merchant: Merchant
    transactionType: str


class WalletOperationResponse(BaseModel):
    """Schema for wallet operation response."""
    status: str = "success"
    message: str
    transactionId: str
    accountNo: str
    amount: float
    newBalance: float


# ============= Wallet Enquiry =============
class WalletEnquiryRequest(BaseModel):
    """Schema for wallet enquiry request."""
    accountNo: str = Field(..., min_length=10, max_length=10)


class WalletEnquiryResponse(BaseModel):
    """Schema for wallet enquiry response."""
    accountNo: str
    accountName: str
    balance: float
    phoneNo: str
    email: str
    status: str = "active"


# ============= Wallet Transactions =============
class WalletTransactionsRequest(BaseModel):
    """Schema for wallet transactions request."""
    accountNumber: str
    fromDate: str = Field(..., description="Start date (YYYY-MM-DD)")
    toDate: str = Field(..., description="End date (YYYY-MM-DD)")
    numberOfItems: str = Field(default="100", description="Max number of items")


class TransactionItem(BaseModel):
    """Individual transaction item."""
    id: str
    type: str
    amount: float
    narration: str
    reference: str
    status: str
    createdAt: str
    otherParty: Optional[str] = None


class WalletTransactionsResponse(BaseModel):
    """Schema for wallet transactions response."""
    accountNumber: str
    transactions: List[TransactionItem]
    totalCount: int


# ============= Bank List =============
class BankInfo(BaseModel):
    """Bank information."""
    code: str
    name: str


class BankListResponse(BaseModel):
    """Schema for bank list response."""
    banks: List[BankInfo]
    count: int


# ============= Client Authentication =============
class ClientAuthRequest(BaseModel):
    """Schema for client authentication request."""
    username: Optional[str] = None
    password: Optional[str] = None
    clientId: str
    clientSecret: str


class ClientAuthResponse(BaseModel):
    """Schema for client authentication response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    client_name: str


# ============= Legacy Schemas (for backward compatibility) =============
class TransferRequest(BaseModel):
    """Schema for P2P transfer request (legacy)."""
    sender_id: int = Field(..., gt=0)
    receiver_id: int = Field(..., gt=0)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class TransactionOut(BaseModel):
    """Schema for transaction output (legacy)."""
    id: int
    sender_id: int
    receiver_id: int
    amount: Decimal
    status: str
    
    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v)
        }

