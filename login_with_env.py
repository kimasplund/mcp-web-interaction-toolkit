#!/usr/bin/env python3
"""
Secure login helper that reads credentials from environment variables
"""

import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import sys

# Add parent directory to path to import server_enhanced
sys.path.insert(0, str(Path(__file__).parent))

async def secure_login_demo():
    """Demonstrate secure login using environment variables"""
    
    # Load .env file from current directory
    env_path = Path(__file__).parent / '.env'
    if not env_path.exists():
        print("❌ No .env file found!")
        print("Please create a .env file with your credentials.")
        print("You can copy .env.example as a template:")
        print("  cp .env.example .env")
        print("  # Then edit .env with your actual credentials")
        return False
    
    load_dotenv(env_path)
    
    # Get credentials from environment
    username = os.getenv('CLICKBANK_USERNAME')
    password = os.getenv('CLICKBANK_PASSWORD')
    
    if not username or not password:
        print("❌ Missing credentials in .env file!")
        print("Please set CLICKBANK_USERNAME and CLICKBANK_PASSWORD in your .env file")
        return False
    
    print("✅ Credentials loaded from .env file")
    print(f"📧 Username: {username[:3]}***" if len(username) > 3 else "***")
    print("🔒 Password: ***hidden***")
    
    # Here you would use the MCP tool to login
    # For now, just showing how to securely load credentials
    print("\n📝 To use with MCP enhanced server:")
    print("from server_enhanced import auth_session_manager")
    print("# Then call the login_to_website tool with these credentials")
    
    return True

async def main():
    """Main function"""
    print("=" * 60)
    print("Secure Login Helper")
    print("=" * 60)
    print()
    
    success = await secure_login_demo()
    
    if success:
        print("\n✅ Ready to use credentials securely!")
    else:
        print("\n⚠️  Please set up your .env file first")
    
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())