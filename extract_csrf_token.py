#!/usr/bin/env python3
"""
Extract CSRF token and all hidden fields from ClickBank login page
Expert-level Spring Security analysis
"""

import asyncio
import aiohttp
import re
import json
from bs4 import BeautifulSoup
from urllib.parse import parse_qs, urlparse

async def extract_csrf_and_auth_flow():
    """Deep extraction of CSRF tokens and authentication parameters"""
    
    print("="*60)
    print("SPRING SECURITY AUTHENTICATION ANALYSIS")
    print("="*60)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    jar = aiohttp.CookieJar()
    
    async with aiohttp.ClientSession(cookie_jar=jar) as session:
        # Get the login page
        print("\n1. Fetching login page...")
        async with session.get('https://accounts.clickbank.com/login.htm', headers=headers) as response:
            html = await response.text()
            initial_cookies = list(session.cookie_jar)
            print(f"   Cookies received: {[c.key for c in initial_cookies]}")
            
        soup = BeautifulSoup(html, 'lxml')
        
        # 2. Look for CSRF tokens in various places
        print("\n2. Searching for CSRF tokens...")
        csrf_token = None
        
        # Check meta tags
        meta_csrf = soup.find('meta', attrs={'name': re.compile('csrf', re.I)})
        if meta_csrf:
            csrf_token = meta_csrf.get('content')
            print(f"   ✅ Found in meta tag: {csrf_token}")
            
        # Check hidden input fields
        csrf_inputs = soup.find_all('input', attrs={'name': re.compile('csrf', re.I)})
        for inp in csrf_inputs:
            token = inp.get('value')
            if token:
                csrf_token = token
                print(f"   ✅ Found in input field '{inp.get('name')}': {token}")
                
        # Check for _csrf parameter specifically (Spring default)
        csrf_spring = soup.find('input', attrs={'name': '_csrf'})
        if csrf_spring:
            csrf_token = csrf_spring.get('value')
            print(f"   ✅ Found Spring _csrf: {csrf_token}")
            
        # Check JavaScript for CSRF tokens
        for script in soup.find_all('script'):
            if script.string:
                # Look for CSRF patterns in JavaScript
                patterns = [
                    r'csrf["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                    r'_csrf["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                    r'csrfToken["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                    r'X-CSRF-TOKEN["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                    r'window\.csrf\s*=\s*["\']([^"\']+)["\']',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, script.string, re.IGNORECASE)
                    if match:
                        csrf_token = match.group(1)
                        print(f"   ✅ Found in JavaScript: {csrf_token[:50]}...")
                        break
                        
        if not csrf_token:
            print("   ❌ No CSRF token found")
            
        # 3. Extract ALL form fields
        print("\n3. Extracting all form fields...")
        forms = soup.find_all('form')
        
        for i, form in enumerate(forms):
            print(f"\n   Form {i+1} (id='{form.get('id', 'none')}'):")
            
            # Get all inputs
            inputs = form.find_all(['input', 'button'])
            form_data = {}
            
            for inp in inputs:
                name = inp.get('name')
                value = inp.get('value', '')
                input_type = inp.get('type', 'text')
                
                if name:
                    form_data[name] = {
                        'type': input_type,
                        'value': value,
                        'id': inp.get('id', ''),
                        'required': inp.get('required') is not None
                    }
                    
                    if input_type == 'hidden':
                        print(f"      🔐 Hidden: {name} = '{value[:50]}...' " if value else f"      🔐 Hidden: {name} (empty)")
                    else:
                        print(f"      📝 {input_type}: {name} (id='{inp.get('id', '')}', required={inp.get('required') is not None})")
                        
            # Look for data attributes that might contain endpoints
            for attr, value in form.attrs.items():
                if 'data-' in attr or 'action' in attr:
                    print(f"      🔗 {attr}: {value}")
                    
        # 4. Test Spring Security standard endpoints
        print("\n4. Testing Spring Security authentication patterns...")
        
        # Common Spring Security login parameters
        test_patterns = [
            {'username': 'test', 'password': 'test'},
            {'j_username': 'test', 'j_password': 'test'},
            {'username': 'test', 'password': 'test', '_csrf': csrf_token} if csrf_token else None,
            {'j_username': 'test', 'j_password': 'test', '_csrf': csrf_token} if csrf_token else None,
        ]
        
        # Common Spring Security endpoints
        endpoints = [
            '/api/login',
            '/j_security_check',
            '/login',
            '/api/authenticate',
            '/perform_login',
        ]
        
        for endpoint in endpoints:
            url = f"https://accounts.clickbank.com{endpoint}"
            print(f"\n   Testing: {endpoint}")
            
            for params in test_patterns:
                if params is None:
                    continue
                    
                try:
                    form_data = aiohttp.FormData()
                    for key, value in params.items():
                        form_data.add_field(key, value or '')
                        
                    async with session.post(
                        url,
                        data=form_data,
                        headers={**headers, 'Referer': 'https://accounts.clickbank.com/login.htm'},
                        allow_redirects=False,
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        status = response.status
                        location = response.headers.get('Location', '')
                        
                        if status in [302, 303]:
                            if 'error' in location:
                                print(f"      ⚠️  {list(params.keys())} → Redirect with error")
                            else:
                                print(f"      ✅ {list(params.keys())} → Redirect to: {location}")
                        elif status == 200:
                            text = await response.text()
                            if 'error' in text.lower():
                                print(f"      ❌ {list(params.keys())} → Error in response")
                            else:
                                print(f"      ✅ {list(params.keys())} → 200 OK")
                        elif status == 401:
                            print(f"      🔒 {list(params.keys())} → 401 Unauthorized (correct endpoint!)")
                            
                except Exception as e:
                    if '404' not in str(e):
                        print(f"      ❌ Error: {str(e)[:50]}")
                        
        # 5. Analyze cookies for session tracking
        print("\n5. Session cookie analysis:")
        for cookie in session.cookie_jar:
            print(f"   🍪 {cookie.key}:")
            print(f"      Domain: {cookie['domain']}")
            print(f"      Path: {cookie['path']}")
            print(f"      Secure: {cookie.get('secure', False)}")
            print(f"      HttpOnly: {cookie.get('httponly', False)}")
            
    print("\n" + "="*60)
    print("RECOMMENDATIONS:")
    print("1. Use discovered CSRF token in _csrf parameter")
    print("2. Maintain session continuity with JSESSIONID")
    print("3. Use form-encoded data, not JSON")
    print("4. Include Referer header from login page")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(extract_csrf_and_auth_flow())