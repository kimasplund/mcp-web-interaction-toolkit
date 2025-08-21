#!/usr/bin/env python3
"""
Secure ClickBank login using environment variables
This script safely loads credentials and performs login
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

async def login_to_clickbank():
    """Login to ClickBank using credentials from environment"""
    
    # Get credentials from environment
    username = os.getenv('CLICKBANK_USERNAME')
    password = os.getenv('CLICKBANK_PASSWORD')
    
    if not username or not password:
        print("❌ Error: Missing credentials!")
        print("\nPlease create a .env file in the current directory with:")
        print("CLICKBANK_USERNAME=your_username")
        print("CLICKBANK_PASSWORD=your_password")
        print("\nYou can copy .env.example as a template:")
        print("  cp .env.example .env")
        return None
    
    print("🔐 Loading credentials from .env file...")
    print(f"📧 Username: {username[:3]}***" if len(username) > 3 else "***")
    print("🔒 Password: ***hidden***")
    
    # Import the MCP enhanced server
    from server_enhanced import auth_session_manager
    import aiohttp
    from bs4 import BeautifulSoup
    
    try:
        print("\n🌐 Attempting to login to ClickBank...")
        
        # Since we can't directly call the MCP tool from here,
        # we'll use the underlying functions
        session_id = f"clickbank_{username[:3]}"
        session = await auth_session_manager.get_or_create_session(session_id)
        
        # First, get the login page
        login_url = "https://accounts.clickbank.com/login.htm"
        
        async with session.get(login_url) as response:
            html = await response.text()
            
        # Parse the form
        soup = BeautifulSoup(html, 'lxml')
        
        # Find the login form
        form = soup.find('form')
        if not form:
            print("❌ Could not find login form")
            return None
            
        # Extract any hidden fields (CSRF tokens, etc.)
        hidden_fields = {}
        for hidden in form.find_all('input', type='hidden'):
            if hidden.get('name'):
                hidden_fields[hidden['name']] = hidden.get('value', '')
        
        # Prepare login data
        login_data = hidden_fields.copy()
        
        # ClickBank uses 'nick' for username and 'pass' for password
        # You may need to inspect the actual form field names
        login_data['email'] = username  # or 'nick' or 'username'
        login_data['password'] = password  # or 'pass'
        
        # Get form action URL
        action = form.get('action', login_url)
        if not action.startswith('http'):
            from urllib.parse import urljoin
            action = urljoin(login_url, action)
        
        # Submit login
        print("📤 Submitting login form...")
        async with session.post(action, data=login_data) as response:
            result_html = await response.text()
            
        # Check for success indicators
        success_indicators = ['logout', 'sign out', 'dashboard', 'welcome', 'account']
        result_lower = result_html.lower()
        
        logged_in = any(indicator in result_lower for indicator in success_indicators)
        
        if logged_in:
            print("✅ Successfully logged in to ClickBank!")
            
            # Save session for future use
            await auth_session_manager.save_cookies(session_id)
            
            return {
                'success': True,
                'session_id': session_id,
                'message': 'Login successful'
            }
        else:
            print("❌ Login may have failed. Please check credentials.")
            return {
                'success': False,
                'message': 'Login failed - check credentials'
            }
            
    except Exception as e:
        print(f"❌ Error during login: {e}")
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        # Don't close the session here if we want to keep it for future requests
        pass

async def main():
    """Main function"""
    print("=" * 60)
    print("🔐 ClickBank Secure Login")
    print("=" * 60)
    print()
    
    result = await login_to_clickbank()
    
    if result and result.get('success'):
        print("\n" + "=" * 60)
        print("✅ Login successful!")
        print(f"Session ID: {result.get('session_id')}")
        print("You can now use this session for authenticated requests")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ Login failed")
        if result:
            print(f"Details: {result.get('message', result.get('error', 'Unknown error'))}")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())