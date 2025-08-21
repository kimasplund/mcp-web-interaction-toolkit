#!/usr/bin/env python3
"""
Real ClickBank login using the discovered Spring Security endpoint
"""

import asyncio
import aiohttp

async def clickbank_login():
    """Login to ClickBank using the real endpoint"""
    
    username = "kim.asplund@gmail.com"
    password = "WEL-VGL-Vv6-Tem-K14"
    
    # Create session with cookie jar
    jar = aiohttp.CookieJar()
    connector = aiohttp.TCPConnector(ssl=True)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    async with aiohttp.ClientSession(connector=connector, cookie_jar=jar) as session:
        # Step 1: Get the login page to establish session
        print("1. Getting login page for session...")
        async with session.get('https://accounts.clickbank.com/login.htm', headers=headers) as response:
            await response.text()
            print(f"   Status: {response.status}")
            cookies = list(session.cookie_jar)
            print(f"   Cookies: {len(cookies)}")
            
        # Step 2: Try the Spring Security endpoint
        print("\n2. Attempting login via /api/login (Spring Security)...")
        
        # Spring Security typically uses form-encoded data
        login_data = aiohttp.FormData()
        login_data.add_field('username', username)
        login_data.add_field('password', password)
        
        # Update headers for form submission
        form_headers = headers.copy()
        form_headers['Referer'] = 'https://accounts.clickbank.com/login.htm'
        form_headers['Origin'] = 'https://accounts.clickbank.com'
        
        async with session.post(
            'https://accounts.clickbank.com/api/login',
            data=login_data,
            headers=form_headers,
            allow_redirects=False  # Don't follow redirects to see where it sends us
        ) as response:
            print(f"   Status: {response.status}")
            
            # Check for redirect (successful login often redirects)
            if 'Location' in response.headers:
                print(f"   ✅ Redirect to: {response.headers['Location']}")
                
            # Check response body
            text = await response.text()
            
            # Check for error or success
            if 'error' in text.lower() or 'failed' in text.lower():
                print(f"   ❌ Login failed")
                print(f"   Response: {text[:500]}")
            elif response.status == 302 or response.status == 303:
                print(f"   ✅ Login appears successful (redirect)")
            elif 'dashboard' in text.lower() or 'welcome' in text.lower():
                print(f"   ✅ Login successful!")
            else:
                print(f"   ❓ Unknown response")
                print(f"   Response preview: {text[:500]}")
                
        # Step 3: Check if we can access authenticated content
        print("\n3. Checking authentication status...")
        
        # Try to access a protected page
        async with session.get(
            'https://accounts.clickbank.com/account',
            headers=headers,
            allow_redirects=False
        ) as response:
            print(f"   Account page status: {response.status}")
            if response.status == 200:
                print(f"   ✅ Successfully authenticated!")
            elif response.status == 302:
                print(f"   ➡️  Redirect: {response.headers.get('Location', 'unknown')}")
                
        # Show final cookies
        print("\n4. Final session cookies:")
        for cookie in session.cookie_jar:
            print(f"   - {cookie.key}: {cookie.value[:20]}...")
            
    print("\n" + "="*60)
    print("Remember to change your password after testing!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(clickbank_login())