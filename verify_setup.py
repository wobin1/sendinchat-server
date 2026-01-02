#!/usr/bin/env python3
"""
Verification script to check if the raw SQL setup is correct.
Run this before starting the application.
"""

import sys
import importlib.util

def check_module(module_name: str) -> bool:
    """Check if a Python module is installed."""
    spec = importlib.util.find_spec(module_name)
    return spec is not None

def main():
    print("🔍 Verifying SendInChat Backend Setup...\n")
    
    all_good = True
    
    # Check required modules
    required_modules = {
        "fastapi": "FastAPI",
        "uvicorn": "Uvicorn",
        "asyncpg": "asyncpg (PostgreSQL driver)",
        "jose": "python-jose (JWT)",
        "passlib": "passlib (password hashing)",
        "pydantic": "Pydantic",
        "pydantic_settings": "Pydantic Settings"
    }
    
    print("📦 Checking dependencies:")
    for module, name in required_modules.items():
        if check_module(module):
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name} - NOT FOUND")
            all_good = False
    
    # Check for SQLAlchemy (should NOT be present)
    print("\n🚫 Checking for removed dependencies:")
    if check_module("sqlalchemy"):
        print("  ⚠️  SQLAlchemy is still installed (should be removed)")
        print("     Run: pip uninstall sqlalchemy")
    else:
        print("  ✅ SQLAlchemy not found (correct)")
    
    # Check file structure
    print("\n📁 Checking file structure:")
    import os
    
    required_files = [
        "app/core/config.py",
        "app/core/security.py",
        "app/db/database.py",
        "app/users/models.py",
        "app/users/schemas.py",
        "app/users/routers.py",
        "app/packages/fintech/models.py",
        "app/packages/fintech/schemas.py",
        "app/packages/fintech/service.py",
        "app/packages/fintech/routers.py",
        "app/packages/chat/routers.py",
        "app/main.py",
        "requirements.txt",
        "schema.sql",
        ".env.example"
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} - NOT FOUND")
            all_good = False
    
    # Check for asyncpg usage in database.py
    print("\n🔧 Checking database configuration:")
    try:
        with open("app/db/database.py", "r") as f:
            content = f.read()
            if "import asyncpg" in content:
                print("  ✅ Using asyncpg")
            else:
                print("  ❌ asyncpg not imported")
                all_good = False
            
            if "sqlalchemy" in content.lower():
                print("  ⚠️  SQLAlchemy references found in database.py")
                all_good = False
            else:
                print("  ✅ No SQLAlchemy references")
    except FileNotFoundError:
        print("  ❌ database.py not found")
        all_good = False
    
    # Check .env file
    print("\n⚙️  Checking configuration:")
    if os.path.exists(".env"):
        print("  ✅ .env file exists")
    else:
        print("  ⚠️  .env file not found (copy from .env.example)")
    
    # Summary
    print("\n" + "="*50)
    if all_good:
        print("✨ All checks passed! Ready to run the application.")
        print("\nNext steps:")
        print("  1. Ensure PostgreSQL is running")
        print("  2. Create database: createdb sendinchat")
        print("  3. Configure .env file")
        print("  4. Run: python app/main.py")
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
