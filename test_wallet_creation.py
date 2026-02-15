"""
Test script to verify the improved wallet creation logic.
This simulates the wallet onboarding flow for a user who already has a wallet.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.packages.fintech import service as fintech_service

async def test_duplicate_wallet():
    """Test wallet creation with a BVN that already has a wallet."""
    print("=" * 60)
    print("Testing Duplicate Wallet Creation")
    print("=" * 60)
    
    # Use the BVN from testuser_a511 who already has wallet 1100073795
    test_bvn = "22267599804"
    
    print(f"\n1. Testing with BVN: {test_bvn[:3]}***")
    print("   (This BVN already has a wallet in the system)")
    
    try:
        result = await fintech_service.create_wallet(
            bvn=test_bvn,
            date_of_birth="07/02/1990",
            gender=1,
            last_name="Test",
            other_names="User",
            phone_no="08012345678",
            transaction_tracking_ref="TEST123",
            account_name="Test User",
            place_of_birth="Lagos",
            address="123 Test Street",
            national_identity_no="12345678901",
            next_of_kin_phone_no="08087654321",
            next_of_kin_name="Next Kin",
            email="test@example.com"
        )
        
        print("\n✅ SUCCESS!")
        print(f"   Account Number: {result.get('accountNo')}")
        print(f"   Account Name: {result.get('accountName')}")
        print(f"   Balance: {result.get('balance')}")
        print(f"   BVN: {result.get('bvn')[:3]}***")
        
        return True
    except Exception as e:
        print(f"\n❌ FAILED: {str(e)}")
        return False

async def test_new_wallet():
    """Test wallet creation with a new BVN."""
    print("\n" + "=" * 60)
    print("Testing New Wallet Creation")
    print("=" * 60)
    
    # Use a new BVN
    test_bvn = "99999999999"
    
    print(f"\n2. Testing with BVN: {test_bvn}")
    print("   (This is a new BVN)")
    
    try:
        result = await fintech_service.create_wallet(
            bvn=test_bvn,
            date_of_birth="01/01/1995",
            gender=2,
            last_name="NewUser",
            other_names="Test",
            phone_no="08099999999",
            transaction_tracking_ref="NEW123",
            account_name="New Test User",
            place_of_birth="Abuja",
            address="456 New Street",
            national_identity_no="98765432109",
            next_of_kin_phone_no="08088888888",
            next_of_kin_name="Emergency Contact",
            email="newtest@example.com"
        )
        
        print("\n✅ SUCCESS!")
        print(f"   Account Number: {result.get('accountNo')}")
        print(f"   Account Name: {result.get('accountName')}")
        print(f"   Balance: {result.get('balance')}")
        
        return True
    except Exception as e:
        print(f"\n❌ FAILED: {str(e)}")
        # This is expected to fail if the third-party API rejects it
        print("   (This may be expected if the third-party API rejects the test BVN)")
        return False

async def main():
    print("\n🔍 Wallet Creation Test Suite\n")
    
    # Test 1: Duplicate wallet
    test1_passed = await test_duplicate_wallet()
    
    # Test 2: New wallet (may fail due to third-party API)
    test2_passed = await test_new_wallet()
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Duplicate Wallet Test: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"New Wallet Test: {'✅ PASSED' if test2_passed else '⚠️  SKIPPED/FAILED'}")
    print("\nNote: The new wallet test may fail if the third-party API")
    print("rejects the test BVN. The important test is the duplicate wallet test.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
