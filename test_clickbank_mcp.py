#!/usr/bin/env python3
"""
Test ClickBank login using MCP enhanced server with env credentials
"""

import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

async def test_login_with_mcp():
    """Test login using the MCP tool directly"""
    
    username = os.getenv('CLICKBANK_USERNAME')
    password = os.getenv('CLICKBANK_PASSWORD')
    
    if not username or not password:
        print("❌ Please set CLICKBANK_USERNAME and CLICKBANK_PASSWORD in .env file")
        return
    
    print(f"🔐 Using credentials for: {username[:3]}***")
    
    # Here you would call the MCP tool through the MCP client
    # Since we're in Python, we can't directly call MCP tools
    # This is just to show the structure
    
    print("\n📝 To use with Claude Code MCP client:")
    print("1. Make sure your .env file has the credentials")
    print("2. In Claude Code, you can use:")
    print(f"""
await mcp__mcp-web-interaction-toolkit-enhanced__login_to_website(
    login_url="https://accounts.clickbank.com/login.htm",
    username_field="email",  # or check the actual field name
    username="{username[:3]}***",  # Use actual from env
    password_field="password",
    password="***hidden***",  # Use actual from env
)
    """)

if __name__ == "__main__":
    asyncio.run(test_login_with_mcp())