"""
Third-party wallet API client.
Handles authentication and API requests to the external wallet service.
"""
import httpx
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from app.core.config import settings

logger = logging.getLogger(__name__)


class WalletAPIError(Exception):
    """Custom exception for wallet API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class WalletAPIClient:
    """Client for interacting with the third-party wallet API."""
    
    def __init__(self):
        self.base_url = settings.WALLET_API_BASE_URL
        self.auth_url = settings.WALLET_AUTH_API_BASE_URL
        self.username = settings.WALLET_API_USERNAME
        self.password = settings.WALLET_API_PASSWORD
        self.client_id = settings.WALLET_API_CLIENT_ID
        self.client_secret = settings.WALLET_API_CLIENT_SECRET
        self.timeout = settings.WALLET_API_TIMEOUT
        
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
    
    def _is_token_valid(self) -> bool:
        """Check if the current access token is still valid."""
        if not self._access_token or not self._token_expiry:
            return False
        return datetime.utcnow() < self._token_expiry
    
    async def authenticate(self) -> Dict[str, Any]:
        """
        Authenticate with the third-party wallet API to get an access token.
        
        Returns:
            Dict containing authentication status and token info
            
        Raises:
            WalletAPIError: If authentication fails
        """
        logger.info("Authenticating with third-party wallet API")
        
        if not self.auth_url:
            raise WalletAPIError("WALLET_AUTH_API_BASE_URL is not configured")
            
        payload = {
            "username": self.username,
            "password": self.password,
            "clientId": self.client_id,
            "clientSecret": self.client_secret
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.auth_url}/authenticate",
                    json=payload
                )
                
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Authentication failed: {response.status_code} - {error_detail}")
                    raise WalletAPIError(f"Authentication failed: {error_detail}")
                
                data = response.json()
                self._access_token = data.get("accessToken")
                
                if not self._access_token:
                    logger.error("Authentication successful but no access token received")
                    raise WalletAPIError("No access token in response")
                
                # Set expiry (default to 1 hour if not provided)
                expires_in = int(data.get("expiresIn", 3600))
                self._token_expiry = datetime.utcnow() + timedelta(seconds=expires_in - 60)  # 1 min buffer
                
                logger.info("Authentication successful, token retrieved")
                return data
                
        except httpx.RequestError as e:
            logger.error(f"Network error during authentication: {str(e)}")
            raise WalletAPIError(f"Network error during authentication: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {str(e)}")
            raise WalletAPIError(f"Authentication error: {str(e)}")
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers with the access token.
        Auto-refreshes token if expired.
        
        Returns:
            Dict containing authorization headers
        """
        if not self._is_token_valid():
            await self.authenticate()
            
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}"
        }
    
    async def create_wallet(self, wallet_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new wallet via the third-party API.
        
        Args:
            wallet_data: Wallet creation payload
            
        Returns:
            Dict containing wallet creation response
            
        Raises:
            WalletAPIError: If wallet creation fails
        """
        logger.info(f"Creating wallet for BVN: {wallet_data.get('bvn', 'N/A')}")
        
        try:
            headers = await self._get_auth_headers()
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/open_wallet",
                    json=wallet_data,
                    headers=headers
                )
                
                if response.status_code not in [200, 201]:
                    error_detail = response.text
                    logger.error(f"Wallet creation failed: {response.status_code} - {error_detail}")
                    raise WalletAPIError(f"Wallet creation failed: {error_detail}", status_code=response.status_code, response_text=error_detail)
                
                data = response.json()
                logger.info(f"Wallet created successfully: {data.get('accountNo', 'N/A')}")
                return data
                
        except httpx.RequestError as e:
            logger.error(f"Network error during wallet creation: {str(e)}")
            raise WalletAPIError(f"Network error during wallet creation: {str(e)}")
        except WalletAPIError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during wallet creation: {str(e)}")
            raise WalletAPIError(f"Wallet creation error: {str(e)}")
    
    async def credit_transfer(self, transfer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Credit a wallet via the third-party API.
        
        Args:
            transfer_data: Credit transfer payload
            
        Returns:
            Dict containing transfer response
            
        Raises:
            WalletAPIError: If credit transfer fails
        """
        logger.info(f"Processing credit transfer: {transfer_data.get('transactionId', 'N/A')}")
        
        try:
            headers = await self._get_auth_headers()
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/credit/transfer",
                    json=transfer_data,
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Credit transfer failed: {response.status_code} - {error_detail}")
                    raise WalletAPIError(f"Credit transfer failed: {error_detail}")
                
                data = response.json()
                logger.info(f"Credit transfer successful: {transfer_data.get('transactionId', 'N/A')}")
                return data
                
        except httpx.RequestError as e:
            logger.error(f"Network error during credit transfer: {str(e)}")
            raise WalletAPIError(f"Network error during credit transfer: {str(e)}")
        except WalletAPIError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during credit transfer: {str(e)}")
            raise WalletAPIError(f"Credit transfer error: {str(e)}")
    
    async def debit_transfer(self, transfer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Debit a wallet via the third-party API.
        
        Args:
            transfer_data: Debit transfer payload
            
        Returns:
            Dict containing transfer response
            
        Raises:
            WalletAPIError: If debit transfer fails
        """
        logger.info(f"Processing debit transfer: {transfer_data.get('transactionId', 'N/A')}")
        
        try:
            headers = await self._get_auth_headers()
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/debit/transfer",
                    json=transfer_data,
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Debit transfer failed: {response.status_code} - {error_detail}")
                    raise WalletAPIError(f"Debit transfer failed: {error_detail}")
                
                data = response.json()
                logger.info(f"Debit transfer successful: {transfer_data.get('transactionId', 'N/A')}")
                return data
                
        except httpx.RequestError as e:
            logger.error(f"Network error during debit transfer: {str(e)}")
            raise WalletAPIError(f"Network error during debit transfer: {str(e)}")
        except WalletAPIError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during debit transfer: {str(e)}")
            raise WalletAPIError(f"Debit transfer error: {str(e)}")
    
    async def upgrade_wallet(self, upgrade_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upgrade wallet account tier.
        
        Args:
            upgrade_data: Dictionary containing upgrade information
            
        Returns:
            Dict containing upgrade response
            
        Raises:
            WalletAPIError: If upgrade request fails
        """
        headers = await self._get_auth_headers()
        
        logger.info(f"Upgrading wallet account: {upgrade_data.get('accountNumber')}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/wallet_upgrade",
                    json=upgrade_data,
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Wallet upgrade failed: {response.status_code} - {error_detail}")
                    raise WalletAPIError(f"Wallet upgrade failed: {error_detail}")
                
                data = response.json()
                logger.info(f"Wallet upgrade request successful: {upgrade_data.get('accountNumber')}")
                return data
                
        except httpx.RequestError as e:
            logger.error(f"Network error during wallet upgrade: {str(e)}")
            raise WalletAPIError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during wallet upgrade: {str(e)}")
            raise WalletAPIError(f"Wallet upgrade error: {str(e)}")
    
    async def get_upgrade_status(self, account_number: str) -> Dict[str, Any]:
        """
        Get wallet upgrade status.
        
        Args:
            account_number: Wallet account number
            
        Returns:
            Dict containing upgrade status
            
        Raises:
            WalletAPIError: If status query fails
        """
        headers = await self._get_auth_headers()
        
        logger.info(f"Getting upgrade status for account: {account_number}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/upgrade_status",
                    json={"accountNumber": account_number},
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Upgrade status query failed: {response.status_code} - {error_detail}")
                    raise WalletAPIError(f"Upgrade status query failed: {error_detail}")
                
                data = response.json()
                logger.info(f"Upgrade status retrieved: {account_number}")
                return data
                
        except httpx.RequestError as e:
            logger.error(f"Network error during upgrade status query: {str(e)}")
            raise WalletAPIError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during upgrade status query: {str(e)}")
            raise WalletAPIError(f"Upgrade status query error: {str(e)}")
    
    async def get_wallet_by_bvn(self, bvn: str) -> Dict[str, Any]:
        """
        Get wallet information by BVN.
        
        Args:
            bvn: Bank Verification Number
            
        Returns:
            Dict containing wallet information, or None if wallet not found
            
        Raises:
            WalletAPIError: If wallet lookup fails (excluding "not found" cases)
        """
        headers = await self._get_auth_headers()
        
        logger.info(f"Getting wallet by BVN: {bvn[:3]}***")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/get_wallet",
                    json={"bvn": bvn},
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Wallet retrieved by BVN")
                    return data
                elif response.status_code == 400:
                    # Wallet not found - this is expected for new users
                    error_detail = response.text
                    logger.info(f"No wallet found for BVN: {error_detail}")
                    return None
                else:
                    error_detail = response.text
                    logger.error(f"Get wallet by BVN failed: {response.status_code} - {error_detail}")
                    raise WalletAPIError(f"Get wallet by BVN failed: {error_detail}", status_code=response.status_code, response_text=error_detail)
                
        except httpx.RequestError as e:
            logger.error(f"Network error during get wallet by BVN: {str(e)}")
            raise WalletAPIError(f"Network error: {str(e)}")
        except WalletAPIError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during get wallet by BVN: {str(e)}")
            raise WalletAPIError(f"Get wallet by BVN error: {str(e)}")

    async def get_banks(self) -> Dict[str, Any]:
        """
        Fetch list of all Banks.
        
        Returns:
            Dict containing list of banks
            
        Raises:
            WalletAPIError: If bank list query fails
        """
        headers = await self._get_auth_headers()
        logger.info("Fetching list of banks")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/get_banks",
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Get banks failed: {response.status_code} - {error_detail}")
                    raise WalletAPIError(f"Get banks failed: {error_detail}")
                
                data = response.json()
                logger.info("Banks list retrieved")
                return data
                
        except httpx.RequestError as e:
            logger.error(f"Network error during get banks: {str(e)}")
            raise WalletAPIError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during get banks: {str(e)}")
            raise WalletAPIError(f"Get banks error: {str(e)}")

    async def account_enquiry(self, enquiry_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify Account Details of other bank's account.
        
        Args:
            enquiry_data: Dictionary containing customer account information
            
        Returns:
            Dict containing account enquiry response
            
        Raises:
            WalletAPIError: If account enquiry fails
        """
        headers = await self._get_auth_headers()
        logger.info(f"Performing account enquiry")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/other_banks_enquiry",
                    json=enquiry_data,
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Account enquiry failed: {response.status_code} - {error_detail}")
                    raise WalletAPIError(f"Account enquiry failed: {error_detail}")
                
                data = response.json()
                logger.info("Account enquiry successful")
                return data
                
        except httpx.RequestError as e:
            logger.error(f"Network error during account enquiry: {str(e)}")
            raise WalletAPIError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during account enquiry: {str(e)}")
            raise WalletAPIError(f"Account enquiry error: {str(e)}")

    async def transfer_other_banks(self, transfer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transfer from customer wallet to other bank.
        
        Args:
            transfer_data: Transfer payload containing transaction, order, customer, etc.
            
        Returns:
            Dict containing transfer response
            
        Raises:
            WalletAPIError: If transfer fails
        """
        headers = await self._get_auth_headers()
        logger.info("Processing transfer to other bank")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/wallet_other_banks",
                    json=transfer_data,
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Other bank transfer failed: {response.status_code} - {error_detail}")
                    raise WalletAPIError(f"Other bank transfer failed: {error_detail}")
                
                data = response.json()
                logger.info("Other bank transfer request successful")
                return data
                
        except httpx.RequestError as e:
            logger.error(f"Network error during other bank transfer: {str(e)}")
            raise WalletAPIError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during other bank transfer: {str(e)}")
            raise WalletAPIError(f"Other bank transfer error: {str(e)}")

    async def get_transaction_history(self, history_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch a customer's transaction history.
        
        Args:
            history_data: Dictionary containing accountNumber, fromDate, toDate, numberOfItems
            
        Returns:
            Dict containing transaction history
            
        Raises:
            WalletAPIError: If transaction history lookup fails
        """
        headers = await self._get_auth_headers()
        logger.info(f"Fetching transaction history for account: {history_data.get('accountNumber')}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/wallet_transactions",
                    json=history_data,
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Transaction history failed: {response.status_code} - {error_detail}")
                    raise WalletAPIError(f"Transaction history failed: {error_detail}")
                
                data = response.json()
                logger.info("Transaction history retrieved")
                return data
                
        except httpx.RequestError as e:
            logger.error(f"Network error during transaction history: {str(e)}")
            raise WalletAPIError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during transaction history: {str(e)}")
            raise WalletAPIError(f"Transaction history error: {str(e)}")

    async def get_wallet_balance(self, account_no: str) -> Dict[str, Any]:
        """
        Fetch details of a customer's wallet including balance.
        
        Args:
            account_no: Wallet account number
            
        Returns:
            Dict containing wallet details
            
        Raises:
            WalletAPIError: If wallet enquiry fails
        """
        headers = await self._get_auth_headers()
        logger.info(f"Enquiring wallet details for: {account_no}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/wallet_enquiry",
                    json={"accountNo": account_no},
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Wallet enquiry failed: {response.status_code} - {error_detail}")
                    raise WalletAPIError(f"Wallet enquiry failed: {error_detail}")
                
                data = response.json()
                logger.info("Wallet enquiry successful")
                return data
                
        except httpx.RequestError as e:
            logger.error(f"Network error during wallet enquiry: {str(e)}")
            raise WalletAPIError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during wallet enquiry: {str(e)}")
            raise WalletAPIError(f"Wallet enquiry error: {str(e)}")



# Global client instance
wallet_api_client = WalletAPIClient()
