"""
Test script for third-party wallet API integration.
Run this to verify the integration is working correctly.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.packages.fintech.third_party_client import wallet_api_client, WalletAPIError
from app.core.config import settings


async def test_authentication():
    """Test authentication with third-party API."""
    print("\n=== Testing Authentication ===")
    try:
        result = await wallet_api_client.authenticate()
        print(f"✅ Authentication successful!")
        print(f"   Access Token: {result.get('access_token', 'N/A')[:20]}...")
        print(f"   Expires In: {result.get('expires_in', 'N/A')} seconds")
        return True
    except WalletAPIError as e:
        print(f"❌ Authentication failed: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False


async def test_wallet_creation():
    """Test wallet creation via third-party API."""
    print("\n=== Testing Wallet Creation ===")
    
    # Sample wallet data
    wallet_data = {
        "bvn": "12345678901",
        "dateOfBirth": "01/01/1990",
        "gender": "1",
        "lastName": "TestUser",
        "otherNames": "Integration",
        "phoneNo": "08012345678",
        "transactionTrackingRef": f"test-{int(asyncio.get_event_loop().time())}",
        "accountName": "Test Integration User",
        "placeOfBirth": "Lagos",
        "address": "Test Address, Lagos",
        "nationalIdentityNo": "12345678901",  # Must be 11 digits
        "nextOfKinPhoneNo": "08087654321",
        "nextOfKinName": "Test Next of Kin",
        "email": "test@example.com"
    }
    
    try:
        result = await wallet_api_client.create_wallet(wallet_data)
        print(f"✅ Wallet creation successful!")
        print(f"   Account Number: {result.get('accountNo', 'N/A')}")
        print(f"   Account Name: {result.get('accountName', 'N/A')}")
        print(f"   Balance: {result.get('balance', 'N/A')}")
        return result.get('accountNo')
    except WalletAPIError as e:
        print(f"❌ Wallet creation failed: {str(e)}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return None


async def test_credit_transfer(account_no: str):
    """Test credit transfer via third-party API."""
    print("\n=== Testing Credit Transfer ===")
    
    transfer_data = {
        "accountNo": account_no,
        "narration": "Test credit transaction",
        "totalAmount": "1000",
        "transactionId": f"test-credit-{asyncio.get_event_loop().time()}",
        "merchant": {
            "isFee": "false",
            "merchantFeeAccount": account_no,
            "merchantFeeAmount": "0"
        },
        "transactionType": "credit"
    }
    
    try:
        result = await wallet_api_client.credit_transfer(transfer_data)
        print(f"✅ Credit transfer successful!")
        print(f"   Transaction ID: {transfer_data['transactionId']}")
        print(f"   Amount: {transfer_data['totalAmount']}")
        print(f"   New Balance: {result.get('balance', 'N/A')}")
        return True
    except WalletAPIError as e:
        print(f"❌ Credit transfer failed: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False


async def test_debit_transfer(account_no: str):
    """Test debit transfer via third-party API."""
    print("\n=== Testing Debit Transfer ===")
    
    transfer_data = {
        "accountNo": account_no,
        "narration": "Test debit transaction",
        "totalAmount": "500",
        "transactionId": f"test-debit-{asyncio.get_event_loop().time()}",
        "merchant": {
            "isFee": "false",
            "merchantFeeAccount": account_no,
            "merchantFeeAmount": "0"
        },
        "transactionType": "debit"
    }
    
    try:
        result = await wallet_api_client.debit_transfer(transfer_data)
        print(f"✅ Debit transfer successful!")
        print(f"   Transaction ID: {transfer_data['transactionId']}")
        print(f"   Amount: {transfer_data['totalAmount']}")
        print(f"   New Balance: {result.get('balance', 'N/A')}")
        return True
    except WalletAPIError as e:
        print(f"❌ Debit transfer failed: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Third-Party Wallet API Integration Test")
    print("=" * 60)
    
    print(f"\nConfiguration:")
    print(f"  Base URL: {settings.WALLET_API_BASE_URL}")
    print(f"  Client ID: {settings.WALLET_API_CLIENT_ID}")
    print(f"  Timeout: {settings.WALLET_API_TIMEOUT}s")
    
    # Test authentication
    auth_success = await test_authentication()
    if not auth_success:
        print("\n⚠️  Authentication failed. Cannot proceed with other tests.")
        print("Please check your credentials in .env file.")
        return
    
    # Test wallet creation
    account_no = await test_wallet_creation()
    if not account_no:
        print("\n⚠️  Wallet creation failed. Cannot proceed with transfer tests.")
        return
    
    # Test credit transfer
    await test_credit_transfer(account_no)
    
    # Test debit transfer
    await test_debit_transfer(account_no)
    
    print("\n" + "=" * 60)
    print("Test suite completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
