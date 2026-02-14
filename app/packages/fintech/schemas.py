from pydantic import BaseModel, Field, EmailStr
from decimal import Decimal
from typing import Optional, List, Dict, Any
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
    isFee: str  # Changed to str to match third-party API ("true" or "false")
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


# ============= Other Bank enquiry =============
class OtherBankEnquiryRequest(BaseModel):
    """Schema for other bank account enquiry."""
    accountNumber: str
    bankCode: str


class ExternalTransferRequest(BaseModel):
    """Schema for external bank transfer from mobile."""
    amount: float
    recipientAccountNumber: str
    recipientName: str
    recipientBankCode: str
    narration: str


# ============= Wallet Transfer (P2P) =============
class WalletTransferRequest(BaseModel):
    """Schema for wallet-to-wallet transfer request."""
    senderAccountNo: str = Field(..., min_length=10, max_length=10, description="Sender's wallet account number")
    receiverAccountNo: str = Field(..., min_length=10, max_length=10, description="Receiver's wallet account number")
    amount: float = Field(..., gt=0, description="Transfer amount")
    narration: str = Field(..., description="Transfer description")
    transactionId: str = Field(..., description="Unique transaction reference")
    merchant: Merchant


class WalletTransferResponse(BaseModel):
    """Schema for wallet transfer response."""
    status: str = "success"
    message: str = "Transfer successful"
    transactionId: str
    senderAccountNo: str
    receiverAccountNo: str
    amount: float
    senderNewBalance: float
    receiverNewBalance: float


# ============= Credit/Debit Wallet (Internal Use Only) =============
class WalletOperationRequest(BaseModel):
    """Schema for wallet credit/debit request (internal use only)."""
    accountNo: str = Field(..., min_length=10, max_length=10)
    narration: str
    totalAmount: float = Field(..., gt=0)
    transactionId: str
    merchant: Merchant
    transactionType: str


class WalletOperationResponse(BaseModel):
    """Schema for wallet operation response (internal use only)."""
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


# ============= Account Upgrade =============
class WalletUpgradeRequest(BaseModel):
    """Schema for wallet account upgrade request."""
    accountNumber: str = Field(..., min_length=10, max_length=10, description="Wallet account number")
    bvn: str = Field(..., min_length=11, max_length=11, description="Bank Verification Number")
    nin: str = Field(..., min_length=11, max_length=11, description="National Identification Number")
    accountName: str
    phoneNumber: str = Field(..., pattern=r"^0\d{10}$", description="Phone number (11 digits)")
    tier: int = Field(..., ge=2, le=3, description="New tier (2 or 3)")
    email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    userPhoto: str = Field(..., description="Base64 encoded customer photo")
    idType: int = Field(..., ge=1, le=4, description="1=NIN, 2=Driver's License, 3=Voter's Card, 4=Int'l Passport")
    idNumber: str
    idIssueDate: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Format: yyyy-MM-dd")
    idExpiryDate: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Format: yyyy-MM-dd")
    idCardFront: str = Field(..., description="Base64 encoded ID card front image")
    idCardBack: Optional[str] = Field(None, description="Base64 encoded ID card back image")
    houseNumber: str
    streetName: str
    state: str
    city: str
    localGovernment: str
    pep: str = Field(..., pattern=r"^(YES|NO)$", description="Politically Exposed Person")
    customerSignature: str = Field(..., description="Base64 encoded signature")
    utilityBill: str = Field(..., description="Base64 encoded utility bill")
    nearestLandmark: str
    placeOfBirth: Optional[str] = None
    proofOfAddressVerification: Optional[str] = Field(None, description="Base64 encoded proof of address")


class WalletUpgradeResponse(BaseModel):
    """Schema for wallet upgrade response."""
    message: str
    status: str
    data: Optional[Dict[str, Any]] = None


# ============= Upgrade Status =============
class UpgradeStatusResponse(BaseModel):
    """Schema for upgrade status response."""
    message: str
    status: str
    accountNumber: str
    upgradeStatus: Optional[str] = None  # Approved, Declined, Pending
    tier: Optional[int] = None
    data: Optional[Dict[str, Any]] = None


# ============= Get Wallet by BVN =============
class GetWalletByBVNResponse(BaseModel):
    """Schema for get wallet by BVN response."""
    message: str
    status: str
    data: Optional[Dict[str, Any]] = None


# ============= Webhooks =============
class InflowWebhookPayload(BaseModel):
    """Schema for inflow notification webhook from third-party API."""
    accountNumber: str
    amount: float
    senderAccountNumber: Optional[str] = None
    senderName: Optional[str] = None
    narration: Optional[str] = None
    transactionReference: str
    transactionDate: str
    sessionId: Optional[str] = None
    responseCode: Optional[str] = None
    responseMessage: Optional[str] = None


class UpgradeStatusWebhookPayload(BaseModel):
    """Schema for upgrade status notification webhook from third-party API."""
    accountNumber: str
    upgradeStatus: str  # Approved, Declined, Pending
    tier: int
    reason: Optional[str] = None
    approvalDate: Optional[str] = None
    responseCode: Optional[str] = None
    responseMessage: Optional[str] = None


class WebhookResponse(BaseModel):
    """Standard webhook response."""
    status: str = "received"
    message: str = "Webhook processed successfully"


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


# ============= Standard API Response Wrappers =============
class StandardWalletResponse(BaseModel):
    """Standard response wrapper for wallet operations."""
    status: str
    message: str
    data: Optional[WalletResponse] = None


class StandardBankTransferResponse(BaseModel):
    """Standard response wrapper for bank transfer operations."""
    status: str
    message: str
    data: Optional[BankTransferResponse] = None


class StandardWalletTransferResponse(BaseModel):
    """Standard response wrapper for wallet transfer operations."""
    status: str
    message: str
    data: Optional[WalletTransferResponse] = None


class StandardWalletEnquiryResponse(BaseModel):
    """Standard response wrapper for wallet enquiry operations."""
    status: str
    message: str
    data: Optional[WalletEnquiryResponse] = None


class StandardWalletTransactionsResponse(BaseModel):
    """Standard response wrapper for wallet transactions operations."""
    status: str
    message: str
    data: Optional[WalletTransactionsResponse] = None


class StandardBankListResponse(BaseModel):
    """Standard response wrapper for bank list operations."""
    status: str
    message: str
    data: Optional[BankListResponse] = None


class StandardClientAuthResponse(BaseModel):
    """Standard response wrapper for client auth operations."""
    status: str
    message: str
    data: Optional[ClientAuthResponse] = None


class StandardWalletUpgradeResponse(BaseModel):
    """Standard response wrapper for wallet upgrade operations."""
    status: str
    message: str
    data: Optional[WalletUpgradeResponse] = None


class StandardUpgradeStatusResponse(BaseModel):
    """Standard response wrapper for upgrade status operations."""
    status: str
    message: str
    data: Optional[UpgradeStatusResponse] = None


class StandardGetWalletByBVNResponse(BaseModel):
    """Standard response wrapper for get wallet by BVN operations."""
    status: str
    message: str
    data: Optional[GetWalletByBVNResponse] = None


class StandardWebhookResponse(BaseModel):
    """Standard response wrapper for webhook operations."""
    status: str
    message: str
    data: Optional[WebhookResponse] = None
