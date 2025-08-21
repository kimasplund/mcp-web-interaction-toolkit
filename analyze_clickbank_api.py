#!/usr/bin/env python3
"""
Deep dive into ClickBank's actual API by monitoring network traffic
"""

import asyncio
import aiohttp
import json
from urllib.parse import urljoin

async def find_real_api():
    """Try to find the real API endpoint by analyzing the form submission"""
    
    # Based on the __NEXT_DATA__, the real page is /master/sign-in
    base_url = "https://accounts.clickbank.com"
    
    # Common Next.js API patterns
    potential_endpoints = [
        "/api/auth/signin",
        "/api/auth/callback/credentials",
        "/api/auth/login",
        "/api/master/signin",
        "/api/master/sign-in", 
        "/api/login",
        "/api/v1/auth/login",
        "/api/v2/auth/login",
        "/master/api/sign-in",
        "/master/sign-in",
        "/_next/auth/signin",
        "/_next/auth/callback/credentials",
    ]
    
    # Try with the event ID from __NEXT_DATA__
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://accounts.clickbank.com',
        'Referer': 'https://accounts.clickbank.com/login.htm',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    test_payload = {
        "username": "test@example.com",
        "password": "testpassword",
        "eventId": "cc9adfc7-cd6c-4c46-b10a-f2e8e33073a7",  # From __NEXT_DATA__
    }
    
    print("Testing potential API endpoints:")
    print("="*60)
    
    async with aiohttp.ClientSession() as session:
        # First, get cookies from the login page
        async with session.get(f"{base_url}/login.htm", headers={'User-Agent': headers['User-Agent']}) as response:
            await response.text()
            print(f"Got cookies: {list(session.cookie_jar)}")
        
        for endpoint in potential_endpoints:
            url = urljoin(base_url, endpoint)
            print(f"\nTesting: {url}")
            
            try:
                async with session.post(
                    url,
                    json=test_payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    status = response.status
                    
                    # Different status codes tell us different things
                    if status == 200:
                        print(f"  ✅ 200 OK - Possible valid endpoint!")
                        text = await response.text()
                        print(f"  Response preview: {text[:200]}")
                    elif status == 400:
                        print(f"  ⚠️  400 Bad Request - Endpoint exists but wrong format")
                        text = await response.text()
                        print(f"  Error: {text[:200]}")
                    elif status == 401:
                        print(f"  ⚠️  401 Unauthorized - Endpoint exists, needs auth")
                    elif status == 403:
                        print(f"  🚫 403 Forbidden - Blocked by WAF")
                    elif status == 404:
                        print(f"  ❌ 404 Not Found - Endpoint doesn't exist")
                    elif status == 405:
                        print(f"  ⚠️  405 Method Not Allowed - Try GET instead of POST")
                    else:
                        print(f"  ❓ {status} - Unexpected status")
                        
            except asyncio.TimeoutError:
                print(f"  ⏱️  Timeout - Endpoint might be rate limited")
            except Exception as e:
                print(f"  ❌ Error: {str(e)[:100]}")
    
    print("\n" + "="*60)
    print("\nNow trying form-encoded instead of JSON...")
    print("="*60)
    
    # Try form-encoded data
    form_headers = headers.copy()
    form_headers['Content-Type'] = 'application/x-www-form-urlencoded'
    
    form_data = {
        'username': 'test@example.com',
        'password': 'testpassword',
    }
    
    async with aiohttp.ClientSession() as session:
        # Get cookies again
        async with session.get(f"{base_url}/login.htm", headers={'User-Agent': headers['User-Agent']}) as response:
            await response.text()
        
        # Try the most likely endpoints with form data
        likely_endpoints = [
            "/master/sign-in",  # The actual page route
            "/api/auth/signin",
            "/api/login",
        ]
        
        for endpoint in likely_endpoints:
            url = urljoin(base_url, endpoint)
            print(f"\nTesting with form data: {url}")
            
            try:
                async with session.post(
                    url,
                    data=form_data,
                    headers=form_headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    status = response.status
                    print(f"  Status: {status}")
                    
                    if status in [200, 400, 401]:
                        text = await response.text()
                        print(f"  Response: {text[:300]}")
                        
            except Exception as e:
                print(f"  Error: {str(e)[:100]}")

if __name__ == "__main__":
    asyncio.run(find_real_api())