#!/usr/bin/env python3
"""
API Discovery and JavaScript Authentication Handler
Enhances the MCP server with capabilities to handle modern SPAs
"""

import asyncio
import json
import re
import base64
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse, urljoin
from datetime import datetime, timedelta
import logging

import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, Request, Response
import jwt

logger = logging.getLogger(__name__)

class APIEndpointDiscovery:
    """Discovers and maps API endpoints from JavaScript code and network traffic"""
    
    def __init__(self):
        self.discovered_endpoints: Dict[str, Dict[str, Any]] = {}
        self.api_patterns = [
            r'/api/[\w/]+',
            r'/auth/[\w/]+',
            r'/login[\w/]*',
            r'/signin[\w/]*',
            r'/session[\w/]*',
            r'/token[\w/]*',
            r'\.json\(\)',
            r'fetch\(["\']([^"\']+)["\']',
            r'axios\.[get|post|put|delete]\(["\']([^"\']+)["\']',
            r'XMLHttpRequest.*open\(["\'][^"\']+["\'],\s*["\']([^"\']+)["\']'
        ]
        
    def analyze_javascript(self, js_content: str, base_url: str) -> List[Dict[str, Any]]:
        """Extract potential API endpoints from JavaScript code"""
        endpoints = []
        
        for pattern in self.api_patterns:
            matches = re.findall(pattern, js_content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                    
                # Clean and normalize the endpoint
                endpoint = match.strip()
                if not endpoint.startswith('http'):
                    endpoint = urljoin(base_url, endpoint)
                
                # Try to determine the method
                method = 'POST' if 'login' in endpoint.lower() or 'auth' in endpoint.lower() else 'GET'
                
                # Look for request payload patterns nearby
                payload_pattern = self._find_payload_pattern(js_content, match)
                
                endpoints.append({
                    'url': endpoint,
                    'method': method,
                    'source': 'javascript',
                    'payload_hint': payload_pattern,
                    'discovered_at': datetime.now().isoformat()
                })
                
        return endpoints
    
    def _find_payload_pattern(self, js_content: str, endpoint: str) -> Optional[Dict]:
        """Find potential payload structure near the endpoint reference"""
        # Look for JSON structures near the endpoint
        context_window = 500
        idx = js_content.find(endpoint)
        if idx == -1:
            return None
            
        context = js_content[max(0, idx-context_window):min(len(js_content), idx+context_window)]
        
        # Common patterns for login payloads
        patterns = {
            'username_password': r'\{[^}]*["\'](?:username|email|user)["\']:[^,}]+,[^}]*["\']password["\']:[^}]+\}',
            'credentials': r'\{[^}]*["\']credentials["\']:[^}]+\}',
            'token': r'\{[^}]*["\']token["\']:[^}]+\}',
        }
        
        for name, pattern in patterns.items():
            if re.search(pattern, context, re.IGNORECASE):
                return {'type': name, 'pattern': pattern}
                
        return None


class BrowserAuthenticationHandler:
    """Handles authentication using a headless browser with JavaScript execution"""
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.intercepted_requests: List[Dict[str, Any]] = []
        self.discovered_tokens: Dict[str, str] = {}
        
    async def initialize(self):
        """Initialize Playwright browser"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        
    async def close(self):
        """Clean up browser resources"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    async def intercept_and_login(
        self,
        login_url: str,
        username: str,
        password: str,
        username_selector: str = None,
        password_selector: str = None
    ) -> Dict[str, Any]:
        """
        Login using browser automation and intercept all network requests
        """
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        page = await context.new_page()
        
        # Set up request interception
        intercepted_apis = []
        intercepted_tokens = {}
        
        async def handle_request(request: Request):
            """Intercept outgoing requests"""
            if any(keyword in request.url for keyword in ['api', 'auth', 'login', 'token']):
                intercepted_apis.append({
                    'url': request.url,
                    'method': request.method,
                    'headers': dict(request.headers),
                    'post_data': request.post_data,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Check for tokens in headers
                auth_header = request.headers.get('authorization', '')
                if auth_header:
                    intercepted_tokens['authorization'] = auth_header
                    
        async def handle_response(response: Response):
            """Intercept responses to extract tokens"""
            if any(keyword in response.url for keyword in ['api', 'auth', 'login', 'token']):
                try:
                    # Try to get response body
                    body = await response.body()
                    if body:
                        try:
                            json_data = json.loads(body)
                            # Look for common token fields
                            for field in ['token', 'access_token', 'accessToken', 'jwt', 'sessionId', 'session_id']:
                                if field in json_data:
                                    intercepted_tokens[field] = json_data[field]
                        except json.JSONDecodeError:
                            pass
                            
                    # Check response headers for tokens
                    for header_name, header_value in response.headers.items():
                        if 'token' in header_name.lower() or 'session' in header_name.lower():
                            intercepted_tokens[header_name] = header_value
                            
                except Exception as e:
                    logger.debug(f"Could not process response: {e}")
                    
        # Attach handlers
        page.on('request', handle_request)
        page.on('response', handle_response)
        
        # Navigate to login page
        await page.goto(login_url, wait_until='networkidle')
        
        # Auto-detect form fields if selectors not provided
        if not username_selector:
            username_selector = await self._find_username_field(page)
        if not password_selector:
            password_selector = await self._find_password_field(page)
            
        # Fill in credentials
        if username_selector and password_selector:
            await page.fill(username_selector, username)
            await page.fill(password_selector, password)
            
            # Find and click submit button
            submit_button = await self._find_submit_button(page)
            if submit_button:
                # Intercept the login API call
                await submit_button.click()
                
                # Wait for navigation or API response
                try:
                    await page.wait_for_navigation(timeout=5000)
                except:
                    # May be an SPA that doesn't navigate
                    await asyncio.sleep(2)
                    
        # Extract tokens from localStorage and sessionStorage
        storage_tokens = await self._extract_storage_tokens(page)
        intercepted_tokens.update(storage_tokens)
        
        # Get cookies
        cookies = await context.cookies()
        
        # Check if login was successful
        success = await self._check_login_success(page)
        
        await context.close()
        
        return {
            'success': success,
            'intercepted_apis': intercepted_apis,
            'tokens': intercepted_tokens,
            'cookies': cookies,
            'final_url': page.url,
            'discovered_endpoints': self._analyze_intercepted_apis(intercepted_apis)
        }
        
    async def _find_username_field(self, page: Page) -> Optional[str]:
        """Auto-detect username/email field"""
        selectors = [
            'input[name="username"]',
            'input[name="email"]',
            'input[name="user"]',
            'input[name="login"]',
            'input[type="email"]',
            'input[type="text"][placeholder*="email" i]',
            'input[type="text"][placeholder*="username" i]',
        ]
        
        for selector in selectors:
            if await page.query_selector(selector):
                return selector
        return None
        
    async def _find_password_field(self, page: Page) -> Optional[str]:
        """Auto-detect password field"""
        selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[name="pass"]',
            'input[name="pwd"]',
        ]
        
        for selector in selectors:
            if await page.query_selector(selector):
                return selector
        return None
        
    async def _find_submit_button(self, page: Page) -> Optional[Any]:
        """Auto-detect submit button"""
        selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Login")',
            'button:has-text("Sign in")',
            'button:has-text("Submit")',
            '*[role="button"]:has-text("Login")',
        ]
        
        for selector in selectors:
            element = await page.query_selector(selector)
            if element:
                return element
        return None
        
    async def _extract_storage_tokens(self, page: Page) -> Dict[str, str]:
        """Extract tokens from localStorage and sessionStorage"""
        tokens = {}
        
        # Extract from localStorage
        local_storage = await page.evaluate('''() => {
            const items = {};
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                items[key] = localStorage.getItem(key);
            }
            return items;
        }''')
        
        # Extract from sessionStorage
        session_storage = await page.evaluate('''() => {
            const items = {};
            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                items[key] = sessionStorage.getItem(key);
            }
            return items;
        }''')
        
        # Look for token-like values
        for storage_name, storage_data in [('localStorage', local_storage), ('sessionStorage', session_storage)]:
            for key, value in storage_data.items():
                if any(keyword in key.lower() for keyword in ['token', 'auth', 'session', 'jwt']):
                    tokens[f"{storage_name}_{key}"] = value
                elif self._looks_like_token(value):
                    tokens[f"{storage_name}_{key}"] = value
                    
        return tokens
        
    def _looks_like_token(self, value: str) -> bool:
        """Check if a string looks like a token"""
        if not value or len(value) < 20:
            return False
            
        # JWT pattern
        if value.count('.') == 2 and all(len(part) > 10 for part in value.split('.')):
            return True
            
        # Long random string
        if len(value) > 30 and re.match(r'^[a-zA-Z0-9_-]+$', value):
            return True
            
        return False
        
    async def _check_login_success(self, page: Page) -> bool:
        """Check if login was successful"""
        # Look for common success indicators
        success_indicators = [
            'dashboard', 'welcome', 'logout', 'sign out', 'profile',
            'account', 'settings', 'home'
        ]
        
        page_content = await page.content()
        page_url = page.url
        
        for indicator in success_indicators:
            if indicator in page_content.lower() or indicator in page_url.lower():
                return True
                
        # Check if we're still on login page
        if 'login' in page_url.lower() or 'signin' in page_url.lower():
            return False
            
        return True
        
    def _analyze_intercepted_apis(self, intercepted_apis: List[Dict]) -> Dict[str, Any]:
        """Analyze intercepted API calls to understand the authentication flow"""
        auth_endpoints = []
        
        for api in intercepted_apis:
            if any(keyword in api['url'].lower() for keyword in ['auth', 'login', 'token', 'session']):
                auth_endpoints.append({
                    'url': api['url'],
                    'method': api['method'],
                    'has_auth_header': 'authorization' in {k.lower() for k in api['headers'].keys()},
                    'post_data_structure': self._analyze_post_data(api.get('post_data'))
                })
                
        return {
            'auth_endpoints': auth_endpoints,
            'total_apis_found': len(intercepted_apis),
            'authentication_flow': self._determine_auth_flow(auth_endpoints)
        }
        
    def _analyze_post_data(self, post_data: Optional[str]) -> Optional[Dict]:
        """Analyze structure of POST data"""
        if not post_data:
            return None
            
        try:
            data = json.loads(post_data)
            return {
                'fields': list(data.keys()),
                'has_username': any(field in data for field in ['username', 'email', 'user']),
                'has_password': 'password' in data or 'pass' in data,
                'field_count': len(data)
            }
        except:
            return {'type': 'non-json', 'length': len(post_data)}
            
    def _determine_auth_flow(self, auth_endpoints: List[Dict]) -> str:
        """Determine the type of authentication flow"""
        if not auth_endpoints:
            return 'unknown'
            
        # Check for OAuth/JWT
        if any(ep['has_auth_header'] for ep in auth_endpoints):
            if any('token' in ep['url'].lower() for ep in auth_endpoints):
                return 'jwt_token_based'
            return 'bearer_token'
            
        # Check for session-based
        if any('session' in ep['url'].lower() for ep in auth_endpoints):
            return 'session_based'
            
        # Check for basic auth
        if len(auth_endpoints) == 1 and auth_endpoints[0].get('post_data_structure', {}).get('has_password'):
            return 'simple_post'
            
        return 'complex_flow'


class EnhancedAuthenticationClient:
    """Client that combines API discovery with browser automation"""
    
    def __init__(self):
        self.api_discovery = APIEndpointDiscovery()
        self.browser_handler = BrowserAuthenticationHandler()
        self.sessions: Dict[str, aiohttp.ClientSession] = {}
        
    async def smart_login(
        self,
        login_url: str,
        username: str,
        password: str,
        prefer_api: bool = True
    ) -> Dict[str, Any]:
        """
        Intelligently login using the best available method
        First tries to discover and use API endpoints, falls back to browser automation
        """
        
        # Step 1: Try to discover API endpoints from the page
        async with aiohttp.ClientSession() as session:
            async with session.get(login_url) as response:
                html = await response.text()
                
        soup = BeautifulSoup(html, 'lxml')
        
        # Extract JavaScript to analyze
        scripts = soup.find_all('script')
        all_js = '\n'.join(str(script) for script in scripts)
        
        # Discover potential API endpoints
        discovered_endpoints = self.api_discovery.analyze_javascript(all_js, login_url)
        
        if discovered_endpoints and prefer_api:
            # Try API-based login first
            for endpoint in discovered_endpoints:
                if 'login' in endpoint['url'].lower() or 'auth' in endpoint['url'].lower():
                    result = await self._try_api_login(
                        endpoint['url'],
                        username,
                        password,
                        endpoint.get('payload_hint')
                    )
                    if result.get('success'):
                        return result
                        
        # Fall back to browser automation
        await self.browser_handler.initialize()
        try:
            result = await self.browser_handler.intercept_and_login(
                login_url,
                username,
                password
            )
            
            # Store any discovered tokens for future use
            if result.get('tokens'):
                self._store_tokens(login_url, result['tokens'])
                
            return result
        finally:
            await self.browser_handler.close()
            
    async def _try_api_login(
        self,
        api_url: str,
        username: str,
        password: str,
        payload_hint: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Try to login using discovered API endpoint"""
        
        # Construct payload based on hint or common patterns
        payloads_to_try = [
            {'username': username, 'password': password},
            {'email': username, 'password': password},
            {'user': username, 'pass': password},
            {'login': username, 'password': password},
        ]
        
        async with aiohttp.ClientSession() as session:
            for payload in payloads_to_try:
                try:
                    async with session.post(
                        api_url,
                        json=payload,
                        headers={'Content-Type': 'application/json'}
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # Look for tokens in response
                            tokens = {}
                            for field in ['token', 'access_token', 'accessToken', 'jwt', 'sessionId']:
                                if field in data:
                                    tokens[field] = data[field]
                                    
                            if tokens:
                                return {
                                    'success': True,
                                    'method': 'api',
                                    'endpoint': api_url,
                                    'tokens': tokens,
                                    'response': data
                                }
                except Exception as e:
                    logger.debug(f"API login attempt failed: {e}")
                    continue
                    
        return {'success': False, 'method': 'api', 'error': 'All API attempts failed'}
        
    def _store_tokens(self, url: str, tokens: Dict[str, str]):
        """Store tokens for future authenticated requests"""
        domain = urlparse(url).netloc
        if domain not in self.sessions:
            self.sessions[domain] = {}
        self.sessions[domain]['tokens'] = tokens
        self.sessions[domain]['timestamp'] = datetime.now()
        
    async def make_authenticated_request(
        self,
        url: str,
        method: str = 'GET',
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make authenticated request using stored tokens"""
        domain = urlparse(url).netloc
        
        if domain not in self.sessions or 'tokens' not in self.sessions[domain]:
            return {'error': 'No authentication tokens available for this domain'}
            
        tokens = self.sessions[domain]['tokens']
        
        # Prepare headers with authentication
        headers = {}
        
        # Add Bearer token if available
        for token_field in ['access_token', 'accessToken', 'token', 'jwt']:
            if token_field in tokens:
                headers['Authorization'] = f"Bearer {tokens[token_field]}"
                break
                
        # Add session token if available
        if 'sessionId' in tokens or 'session_id' in tokens:
            session_id = tokens.get('sessionId') or tokens.get('session_id')
            headers['X-Session-Id'] = session_id
            
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                headers=headers,
                json=data if method in ['POST', 'PUT', 'PATCH'] else None,
                params=data if method == 'GET' else None
            ) as response:
                return {
                    'status': response.status,
                    'data': await response.text(),
                    'headers': dict(response.headers)
                }


# Example usage
async def test_enhanced_auth():
    """Test the enhanced authentication system"""
    client = EnhancedAuthenticationClient()
    
    # Test with ClickBank
    result = await client.smart_login(
        'https://accounts.clickbank.com/login.htm',
        'test@example.com',
        'password123'
    )
    
    print("Login Result:")
    print(json.dumps(result, indent=2))
    
    if result.get('success') and result.get('tokens'):
        # Make authenticated request
        auth_result = await client.make_authenticated_request(
            'https://accounts.clickbank.com/api/user/profile',
            'GET'
        )
        print("\nAuthenticated Request Result:")
        print(json.dumps(auth_result, indent=2))


if __name__ == "__main__":
    # Note: This requires playwright to be installed:
    # pip install playwright
    # playwright install chromium
    asyncio.run(test_enhanced_auth())