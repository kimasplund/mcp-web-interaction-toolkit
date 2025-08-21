#!/usr/bin/env python3
"""
Extract and analyze ClickBank's JavaScript to find the real API endpoints
"""

import asyncio
import aiohttp
import re
import json
from bs4 import BeautifulSoup

async def extract_clickbank_javascript():
    """Extract all JavaScript from ClickBank login page"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    async with aiohttp.ClientSession() as session:
        # Get the login page
        async with session.get('https://accounts.clickbank.com/login.htm', headers=headers) as response:
            html = await response.text()
            
    soup = BeautifulSoup(html, 'lxml')
    
    print("="*60)
    print("CLICKBANK JAVASCRIPT ANALYSIS")
    print("="*60)
    
    # 1. Find __NEXT_DATA__ 
    for script in soup.find_all('script'):
        if script.string and '__NEXT_DATA__' in script.get('id', ''):
            print("\n1. Found __NEXT_DATA__ JSON:")
            print("-"*40)
            try:
                next_data = json.loads(script.string)
                print(f"Build ID: {next_data.get('buildId', 'unknown')}")
                print(f"Runtime Config: {next_data.get('runtimeConfig', {})}")
                print(f"Page: {next_data.get('page', 'unknown')}")
                
                # Look for API routes
                if 'props' in next_data:
                    props = next_data['props']
                    print(f"Props keys: {list(props.keys())}")
                    
                # Save for analysis
                with open('clickbank_next_data.json', 'w') as f:
                    json.dump(next_data, f, indent=2)
                print("Saved to clickbank_next_data.json")
                    
            except json.JSONDecodeError:
                print("Could not decode __NEXT_DATA__")
    
    # 2. Find JavaScript files
    print("\n2. JavaScript files referenced:")
    print("-"*40)
    js_files = []
    
    # Look for script tags with src
    for script in soup.find_all('script', src=True):
        src = script['src']
        if not src.startswith('http'):
            src = f"https://accounts.clickbank.com{src}"
        js_files.append(src)
        print(f"  - {src}")
    
    # 3. Look for inline JavaScript with API calls
    print("\n3. Inline JavaScript with API patterns:")
    print("-"*40)
    
    api_patterns = [
        r'/api/[^"\'\s]+',
        r'fetch\(["\']([^"\']+)',
        r'axios\.[a-z]+\(["\']([^"\']+)',
        r'endpoint["\']?\s*[:=]\s*["\']([^"\']+)',
        r'url["\']?\s*[:=]\s*["\']([^"\']+)',
        r'LOGIN_URL|AUTH_URL|API_URL',
        r'\.post\(["\']([^"\']+)',
        r'\.get\(["\']([^"\']+)',
    ]
    
    for script in soup.find_all('script'):
        if script.string:
            for pattern in api_patterns:
                matches = re.findall(pattern, script.string, re.IGNORECASE)
                if matches:
                    print(f"Pattern: {pattern[:30]}...")
                    for match in matches[:3]:  # First 3 matches
                        print(f"  Found: {match}")
    
    # 4. Download and analyze main JS bundles
    print("\n4. Downloading main JavaScript bundles...")
    print("-"*40)
    
    # Find _next/static chunks
    next_chunks = [js for js in js_files if '_next/static' in js]
    
    for js_url in next_chunks[:3]:  # First 3 chunks
        print(f"\nAnalyzing: {js_url.split('/')[-1]}")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(js_url, headers=headers) as response:
                    js_content = await response.text()
                    
                    # Look for authentication-related patterns
                    auth_patterns = [
                        r'["\']auth["\']',
                        r'["\']login["\']',
                        r'["\']signin["\']',
                        r'["\']password["\']',
                        r'["\']username["\']',
                        r'["\']email["\']',
                        r'/api/auth',
                        r'/api/login',
                        r'/api/session',
                    ]
                    
                    for pattern in auth_patterns:
                        if re.search(pattern, js_content, re.IGNORECASE):
                            # Extract context around the match
                            matches = re.finditer(pattern, js_content, re.IGNORECASE)
                            for match in list(matches)[:2]:
                                start = max(0, match.start() - 100)
                                end = min(len(js_content), match.end() + 100)
                                context = js_content[start:end]
                                print(f"  Found '{pattern}' in context:")
                                print(f"    ...{context}...")
                                break
                                
            except Exception as e:
                print(f"  Error downloading: {e}")
    
    # 5. Look for form action
    print("\n5. Form structure:")
    print("-"*40)
    forms = soup.find_all('form')
    for i, form in enumerate(forms):
        print(f"Form {i+1}:")
        print(f"  Action: {form.get('action', 'not specified')}")
        print(f"  Method: {form.get('method', 'GET')}")
        print(f"  ID: {form.get('id', 'none')}")
        print(f"  Onsubmit: {form.get('onsubmit', 'none')}")
        
        # Check for React/Next.js event handlers
        for attr in form.attrs:
            if 'data-' in attr or 'on' in attr.lower():
                print(f"  {attr}: {form[attr][:50]}...")
    
    print("\n" + "="*60)
    print("Analysis complete! Check clickbank_next_data.json")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(extract_clickbank_javascript())