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
    pass


class WalletAPIClient:
    """Client for interacting with the third-party wallet API."""
    
    def __init__(self):
        self.base_url = settings.WALLET_API_BASE_URL
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
        Authenticate with the third-party wallet API.
        Note: This creates authentication headers for subsequent requests.
        The third-party API uses credentials in request headers rather than a separate auth endpoint.
        
        Returns:
            Dict containing authentication status
            
        Raises:
            WalletAPIError: If authentication setup fails
        """
        logger.info("Setting up authentication for third-party wallet API")
        
        try:
            # For this API, we don't have a separate auth endpoint
            # Authentication is done via credentials in each request
            # We'll just validate that credentials are set
            if not self.client_id or not self.client_secret:
                raise WalletAPIError("Client ID and Client Secret are required")
            
            # Mark as authenticated
            self._access_token = "authenticated"  # Placeholder since we use credentials directly
            self._token_expiry = datetime.utcnow() + timedelta(hours=24)
            
            logger.info("Authentication credentials validated")
            return {
                "status": "authenticated",
                "message": "Using credential-based authentication"
            }
                
        except Exception as e:
            logger.error(f"Authentication setup error: {str(e)}")
            raise WalletAPIError(f"Authentication error: {str(e)}")
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers with credentials.
        
        Returns:
            Dict containing authorization headers with credentials
        """
        # Build auth headers with credentials
        headers = {
            "Content-Type": "application/json",
            "username": self.username,
            "password": self.password,
            "clientId": self.client_id,
            "clientSecret": self.client_secret
        }
        
        return headers
    
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
                    raise WalletAPIError(f"Wallet creation failed: {error_detail}")
                
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
            Dict containing wallet information
            
        Raises:
            WalletAPIError: If wallet lookup fails
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
                
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Get wallet by BVN failed: {response.status_code} - {error_detail}")
                    raise WalletAPIError(f"Get wallet by BVN failed: {error_detail}")
                
                data = response.json()
                logger.info(f"Wallet retrieved by BVN")
                return data
                
        except httpx.RequestError as e:
            logger.error(f"Network error during get wallet by BVN: {str(e)}")
            raise WalletAPIError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during get wallet by BVN: {str(e)}")
            raise WalletAPIError(f"Get wallet by BVN error: {str(e)}")



# Global client instance
wallet_api_client = WalletAPIClient()
