#!/usr/bin/env python3
"""Direct test of ClickBank login"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json

async def test_clickbank_login():
    """Test ClickBank login directly"""
    
    username = "kim.asplund@gmail.com"
    password = "WEL-VGL-Vv6-Tem-K14"
    login_url = "https://accounts.clickbank.com/login.htm"
    
    print("🔐 Testing ClickBank login...")
    print(f"📧 Username: {username[:3]}***")
    
    # Create session with proper headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
        # Step 1: Get the login page
        print("\n📄 Fetching login page...")
        async with session.get(login_url, headers=headers) as response:
            html = await response.text()
            print(f"✅ Got login page (status: {response.status})")
        
        # Step 2: Parse the form
        soup = BeautifulSoup(html, 'lxml')
        
        # Look for form fields
        print("\n🔍 Analyzing form structure...")
        
        # Find all input fields
        inputs = soup.find_all('input')
        print(f"Found {len(inputs)} input fields")
        
        for inp in inputs:
            field_type = inp.get('type', 'text')
            field_name = inp.get('name', inp.get('id', 'unnamed'))
            field_value = inp.get('value', '')
            print(f"  - {field_type}: {field_name} = {field_value[:20] if field_value else '(empty)'}")
        
        # Check for Next.js or React forms (they might use JavaScript)
        scripts = soup.find_all('script')
        has_nextjs = any('_next' in str(script) for script in scripts)
        print(f"\n📊 Page uses Next.js/React: {has_nextjs}")
        
        if has_nextjs:
            print("⚠️  This is a Next.js application - form submission might be handled via JavaScript")
            print("The form might require:")
            print("  1. API endpoint submission instead of form POST")
            print("  2. CSRF tokens or other security measures")
            print("  3. JavaScript execution for proper submission")
            
            # Look for API endpoints in the scripts
            for script in scripts:
                script_text = str(script)
                if 'api' in script_text.lower() or 'login' in script_text.lower():
                    if 'api/login' in script_text or 'api/auth' in script_text:
                        print(f"\n🔗 Found potential API endpoint in script")
                        # Extract a snippet around the API mention
                        idx = script_text.lower().find('api')
                        if idx > 0:
                            snippet = script_text[max(0, idx-50):min(len(script_text), idx+100)]
                            print(f"  Snippet: ...{snippet}...")
        
        # Try to find the actual form action
        forms = soup.find_all('form')
        print(f"\n📝 Found {len(forms)} forms")
        for i, form in enumerate(forms):
            print(f"\nForm {i+1}:")
            print(f"  Action: {form.get('action', 'not specified')}")
            print(f"  Method: {form.get('method', 'GET')}")
            
        # Since this is a modern SPA, the actual login might need to be done via API
        print("\n🚀 For modern SPAs like this ClickBank page, you typically need to:")
        print("  1. Find the API endpoint (often /api/login or similar)")
        print("  2. Send JSON payload with credentials")
        print("  3. Handle JWT tokens or session cookies in response")
        
        return {
            'has_nextjs': has_nextjs,
            'forms_found': len(forms),
            'inputs_found': len(inputs),
            'recommendation': 'Use browser automation tools like Playwright for JavaScript-heavy sites'
        }

async def main():
    result = await test_clickbank_login()
    print("\n" + "="*60)
    print("📊 Analysis Results:")
    print(json.dumps(result, indent=2))
    print("="*60)
    print("\n⚠️  Remember to change your password after testing!")

if __name__ == "__main__":
    asyncio.run(main())