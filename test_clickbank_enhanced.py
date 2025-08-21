#!/usr/bin/env python3
"""
Enhanced ClickBank login test with aggressive human simulation
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import json
import random
import time

async def test_clickbank_with_full_simulation():
    """Test ClickBank with maximum human simulation"""
    
    username = "kim.asplund@gmail.com"
    password = "WEL-VGL-Vv6-Tem-K14"
    
    # Create session with cookie jar
    jar = aiohttp.CookieJar()
    connector = aiohttp.TCPConnector(ssl=True)
    
    # Use a real Chrome user agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Sec-Ch-Ua': '"Not A(Brand";v="121", "Google Chrome";v="121", "Chromium";v="121"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Cache-Control': 'max-age=0'
    }
    
    async with aiohttp.ClientSession(connector=connector, cookie_jar=jar) as session:
        # Step 1: Visit the main ClickBank page first (like a human would)
        print("1. Visiting ClickBank homepage...")
        async with session.get('https://www.clickbank.com', headers=headers) as response:
            await response.text()
            print(f"   Homepage status: {response.status}")
            
        # Human-like delay
        await asyncio.sleep(random.uniform(2, 4))
        
        # Step 2: Navigate to login page
        print("2. Navigating to login page...")
        headers['Referer'] = 'https://www.clickbank.com'
        headers['Sec-Fetch-Site'] = 'same-site'
        
        async with session.get('https://accounts.clickbank.com/login.htm', headers=headers) as response:
            html = await response.text()
            print(f"   Login page status: {response.status}")
            
            # Save cookies
            cookies = session.cookie_jar.filter_cookies('https://accounts.clickbank.com')
            print(f"   Cookies received: {list(cookies.keys())}")
            
        # Parse the page
        soup = BeautifulSoup(html, 'lxml')
        
        # Look for Next.js data
        next_data = None
        for script in soup.find_all('script'):
            if '__NEXT_DATA__' in str(script):
                print("3. Found Next.js data in page")
                # Try to extract the data
                script_text = str(script.string) if script.string else ''
                if 'buildId' in script_text:
                    print("   Build ID found - this is a Next.js app")
                    
        # Look for form inputs
        inputs = soup.find_all('input')
        print(f"4. Found {len(inputs)} input fields")
        for inp in inputs:
            print(f"   - {inp.get('type', 'text')}: {inp.get('name', inp.get('id', 'unnamed'))}")
            
        # Human-like delay before typing
        await asyncio.sleep(random.uniform(1, 2))
        
        # Step 3: Try to find the actual API endpoint
        print("\n5. Attempting login via form submission...")
        
        # Prepare form data
        form_data = {
            'username': username,
            'password': password
        }
        
        # Update headers for form submission
        headers['Referer'] = 'https://accounts.clickbank.com/login.htm'
        headers['Origin'] = 'https://accounts.clickbank.com'
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        
        # Try form submission
        async with session.post(
            'https://accounts.clickbank.com/login.htm',
            data=form_data,
            headers=headers,
            allow_redirects=True
        ) as response:
            result_html = await response.text()
            print(f"   Form submission status: {response.status}")
            print(f"   Final URL: {response.url}")
            
            # Check for success
            if 'dashboard' in str(response.url).lower() or 'account' in result_html.lower():
                print("   ✅ Login successful!")
            else:
                print("   ❌ Login failed - still on login page")
                
        # Step 4: Try API endpoints with session cookies
        print("\n6. Testing API endpoints with session...")
        
        # Try JSON API
        api_headers = headers.copy()
        api_headers['Content-Type'] = 'application/json'
        api_headers['X-Requested-With'] = 'XMLHttpRequest'
        
        api_payload = json.dumps({
            'username': username,
            'password': password
        })
        
        async with session.post(
            'https://accounts.clickbank.com/api/auth/login',
            data=api_payload,
            headers=api_headers
        ) as response:
            print(f"   API endpoint status: {response.status}")
            if response.status == 200:
                data = await response.text()
                print(f"   API response: {data[:200]}")
            elif response.status == 403:
                print("   API blocked by CloudFront")
            else:
                print(f"   API error: {response.status}")
                
    print("\n" + "="*60)
    print("Test complete. Remember to change your password!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_clickbank_with_full_simulation())