#!/usr/bin/env python3
"""
MCP Web Interaction Toolkit - INTEGRATED ENHANCED SERVER
Combines all circumvention features:
- Spring Security authentication
- Persistent API discovery
- JavaScript extraction (__NEXT_DATA__, etc.)
- Advanced form detection
- Session management
"""

import asyncio
import json
import logging
import secrets
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse, urljoin, parse_qs
from contextlib import asynccontextmanager

import aiohttp
from aiohttp import ClientTimeout, TCPConnector
from bs4 import BeautifulSoup
from fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== Configuration ==================
class Config:
    """Centralized configuration"""
    MAX_CONTENT_LENGTH = 50000
    REQUEST_TIMEOUT = 30
    MAX_RETRIES = 3
    RETRY_DELAY = 1
    CONNECTION_LIMIT = 10
    CACHE_TTL = 300  # 5 minutes
    API_DISCOVERY_DIR = ".api_discovery"
    SESSION_TIMEOUT = 1800  # 30 minutes

# ================== Models ==================
class ScrapeOptions(BaseModel):
    """Options for web scraping"""
    simulate_human: bool = Field(default=True, description="Simulate human-like behavior")
    min_delay: float = Field(default=0.5, description="Minimum delay between requests (seconds)")
    max_delay: float = Field(default=2, description="Maximum delay between requests (seconds)")
    max_content_length: int = Field(default=5000, description="Maximum content length to return")
    max_links: int = Field(default=50, description="Maximum number of links to extract")
    max_images: int = Field(default=20, description="Maximum number of images to extract")
    use_cache: bool = Field(default=True, description="Use cache for repeated requests")
    follow_redirects: bool = Field(default=True, description="Follow HTTP redirects")
    extract_js: bool = Field(default=True, description="Extract JavaScript data (__NEXT_DATA__, etc.)")

    @field_validator('min_delay', 'max_delay')
    @classmethod
    def validate_delays(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Delays must be non-negative")
        return v

# ================== API Discovery System ==================
class PersistentAPIDiscovery:
    """Persistent API endpoint discovery with caching"""
    
    def __init__(self, storage_dir: str = Config.API_DISCOVERY_DIR):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.discovered_apis: Dict[str, Dict[str, Any]] = {}
        self._load_existing_discoveries()
        
    def _load_existing_discoveries(self):
        """Load all existing API discoveries from storage"""
        for json_file in self.storage_dir.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    domain = json_file.stem
                    self.discovered_apis[domain] = json.load(f)
                    logger.info(f"Loaded {domain}: {len(self.discovered_apis[domain].get('endpoints', []))} endpoints")
            except Exception as e:
                logger.error(f"Failed to load {json_file}: {e}")
                
    def get_domain_from_url(self, url: str) -> str:
        """Extract domain from URL"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
        
    def save_discovery(self, url: str, discovery_data: Dict[str, Any]):
        """Save discovery data for a domain"""
        domain = self.get_domain_from_url(url)
        file_path = self.storage_dir / f"{domain}.json"
        
        # Merge with existing data
        existing_data = {}
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    existing_data = json.load(f)
            except:
                pass
                
        # Merge endpoints avoiding duplicates
        existing_endpoints = {ep['url']: ep for ep in existing_data.get('endpoints', [])}
        new_endpoints = {ep['url']: ep for ep in discovery_data.get('endpoints', [])}
        existing_endpoints.update(new_endpoints)
        
        final_data = {
            'domain': domain,
            'last_updated': datetime.now().isoformat(),
            'discovery_count': existing_data.get('discovery_count', 0) + 1,
            'endpoints': list(existing_endpoints.values()),
            'authentication': discovery_data.get('authentication', existing_data.get('authentication', {})),
            'javascript_data': discovery_data.get('javascript_data', existing_data.get('javascript_data', {}))
        }
        
        # Save to file
        with open(file_path, 'w') as f:
            json.dump(final_data, f, indent=2)
            
        self.discovered_apis[domain] = final_data
        logger.info(f"Saved discovery for {domain}: {len(final_data['endpoints'])} endpoints")
        
    def get_discovery(self, url: str) -> Optional[Dict[str, Any]]:
        """Get cached discovery for a domain"""
        domain = self.get_domain_from_url(url)
        return self.discovered_apis.get(domain)

# ================== Enhanced Web Scraper ==================
class EnhancedWebScraper:
    """Advanced web scraper with circumvention features"""
    
    def __init__(self):
        self.sessions: Dict[str, aiohttp.ClientSession] = {}
        self.cache: Dict[str, Tuple[Any, datetime]] = {}
        self.api_discovery = PersistentAPIDiscovery()
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) Firefox/122.0'
        ]
        
    def get_headers(self, simulate_human: bool = True) -> Dict[str, str]:
        """Get browser-like headers"""
        if not simulate_human:
            return {'User-Agent': 'MCP-Web-Toolkit/1.0'}
            
        return {
            'User-Agent': secrets.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Not A(Brand";v="121", "Google Chrome";v="121"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1'
        }
        
    async def get_session(self, base_url: str) -> aiohttp.ClientSession:
        """Get or create session for a domain"""
        domain = urlparse(base_url).netloc
        
        if domain not in self.sessions:
            connector = TCPConnector(limit=Config.CONNECTION_LIMIT, ssl=True)
            timeout = ClientTimeout(total=Config.REQUEST_TIMEOUT)
            jar = aiohttp.CookieJar()
            self.sessions[domain] = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                cookie_jar=jar
            )
            
        return self.sessions[domain]
        
    def extract_javascript_data(self, html: str) -> Dict[str, Any]:
        """Extract JavaScript data including __NEXT_DATA__"""
        js_data = {}
        
        # Extract __NEXT_DATA__
        next_data_match = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>([^<]+)</script>',
            html, re.IGNORECASE
        )
        if next_data_match:
            try:
                js_data['__NEXT_DATA__'] = json.loads(next_data_match.group(1))
            except:
                pass
                
        # Extract window assignments
        window_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({[^;]+});',
            r'window\.config\s*=\s*({[^;]+});',
            r'window\._env_\s*=\s*({[^;]+});'
        ]
        
        for pattern in window_patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                try:
                    parsed = json.loads(match)
                    js_data[pattern.split('window.')[1].split('=')[0].strip()] = parsed
                except:
                    pass
                    
        return js_data
        
    def extract_api_endpoints(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """Extract API endpoints from HTML/JavaScript"""
        endpoints = []
        
        # Common API patterns
        api_patterns = [
            r'["\']/(api/[^"\']+)["\']',
            r'fetch\(["\']([^"\']+)["\']',
            r'axios\.[get|post|put|delete]+\(["\']([^"\']+)["\']',
            r'url:\s*["\']([^"\']+)["\']',
            r'endpoint:\s*["\']([^"\']+)["\']',
            r'["\']https?://[^"\']+/api/[^"\']+["\']'
        ]
        
        for pattern in api_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                    
                # Make absolute URL
                if match.startswith('/'):
                    endpoint_url = urljoin(base_url, match)
                elif match.startswith('http'):
                    endpoint_url = match
                else:
                    endpoint_url = urljoin(base_url, '/' + match)
                    
                # Detect method from context
                method = 'GET'
                if 'login' in match.lower() or 'auth' in match.lower():
                    method = 'POST'
                    
                endpoints.append({
                    'url': endpoint_url,
                    'method': method,
                    'discovered_at': datetime.now().isoformat()
                })
                
        return endpoints
        
    def detect_authentication_type(self, html: str, url: str) -> Dict[str, Any]:
        """Detect authentication mechanism"""
        soup = BeautifulSoup(html, 'html.parser')
        auth_info = {
            'type': 'unknown',
            'details': {}
        }
        
        # Check for Spring Security
        if 'spring' in html.lower() or '/api/login' in html:
            auth_info['type'] = 'spring_security'
            auth_info['details']['login_endpoint'] = urljoin(url, '/api/login')
            
            # Look for CSRF token
            csrf_meta = soup.find('meta', {'name': '_csrf'})
            if csrf_meta:
                auth_info['details']['csrf_token'] = csrf_meta.get('content')
                
        # Check for form-based auth
        login_form = soup.find('form', {'action': re.compile(r'login|signin|auth', re.I)})
        if login_form:
            auth_info['type'] = 'form_based' if auth_info['type'] == 'unknown' else 'hybrid'
            auth_info['details']['form_action'] = urljoin(url, login_form.get('action', '/'))
            auth_info['details']['form_method'] = login_form.get('method', 'POST').upper()
            
            # Extract form fields
            fields = {}
            for input_field in login_form.find_all('input'):
                field_name = input_field.get('name')
                if field_name:
                    fields[field_name] = input_field.get('value', '')
            auth_info['details']['form_fields'] = fields
            
        # Check for OAuth
        if 'oauth' in html.lower() or 'authorize' in html.lower():
            auth_info['oauth_detected'] = True
            
        return auth_info
        
    async def scrape_with_discovery(self, url: str, options: ScrapeOptions) -> Dict[str, Any]:
        """Scrape webpage with full API discovery"""
        try:
            session = await self.get_session(url)
            headers = self.get_headers(options.simulate_human)
            
            # Add delay for human simulation
            if options.simulate_human:
                delay = random.uniform(options.min_delay, options.max_delay)
                await asyncio.sleep(delay)
                
            async with session.get(url, headers=headers, allow_redirects=options.follow_redirects) as response:
                html = await response.text()
                
                # Extract data
                soup = BeautifulSoup(html, 'html.parser')
                
                # JavaScript extraction
                js_data = {}
                if options.extract_js:
                    js_data = self.extract_javascript_data(html)
                    
                # API discovery
                endpoints = self.extract_api_endpoints(html, url)
                auth_info = self.detect_authentication_type(html, url)
                
                # Save discovery
                discovery_data = {
                    'endpoints': endpoints,
                    'authentication': auth_info,
                    'javascript_data': js_data
                }
                self.api_discovery.save_discovery(url, discovery_data)
                
                # Extract content
                title = soup.title.string if soup.title else None
                
                # Extract text content
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text()
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)
                
                # Limit content length
                if len(text) > options.max_content_length:
                    text = text[:options.max_content_length] + "..."
                    
                # Extract links
                links = []
                for link in soup.find_all('a', href=True)[:options.max_links]:
                    links.append({
                        'text': link.get_text(strip=True),
                        'url': urljoin(url, link['href'])
                    })
                    
                # Extract images
                images = []
                for img in soup.find_all('img', src=True)[:options.max_images]:
                    images.append({
                        'alt': img.get('alt', ''),
                        'url': urljoin(url, img['src'])
                    })
                    
                # Get cookies
                cookies = {}
                for cookie in session.cookie_jar:
                    cookies[cookie.key] = cookie.value
                    
                return {
                    'success': True,
                    'url': str(response.url),
                    'title': title,
                    'content': text,
                    'links': links,
                    'images': images,
                    'status_code': response.status,
                    'headers': dict(response.headers),
                    'cookies': cookies,
                    'discovery': discovery_data,
                    'cached': False,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Scraping error: {e}")
            return {
                'success': False,
                'url': url,
                'error': str(e),
                'error_type': type(e).__name__,
                'timestamp': datetime.now().isoformat()
            }
            
    async def smart_login(
        self,
        login_url: str,
        username: str,
        password: str,
        use_discovery: bool = True
    ) -> Dict[str, Any]:
        """Smart login with automatic detection and Spring Security support"""
        
        try:
            # Check for cached discovery
            discovery = None
            if use_discovery:
                discovery = self.api_discovery.get_discovery(login_url)
                
            session = await self.get_session(login_url)
            headers = self.get_headers(simulate_human=True)
            
            # First, load the login page
            async with session.get(login_url, headers=headers) as response:
                html = await response.text()
                
            # Detect authentication type if not in cache
            if not discovery:
                auth_info = self.detect_authentication_type(html, login_url)
                endpoints = self.extract_api_endpoints(html, login_url)
                js_data = self.extract_javascript_data(html)
                
                discovery = {
                    'authentication': auth_info,
                    'endpoints': endpoints,
                    'javascript_data': js_data
                }
                
                # Save discovery
                self.api_discovery.save_discovery(login_url, discovery)
            else:
                auth_info = discovery.get('authentication', {})
                
            # Perform login based on detected type
            if auth_info.get('type') == 'spring_security':
                # Spring Security JSON login
                login_endpoint = auth_info['details'].get('login_endpoint', '/api/login')
                if not login_endpoint.startswith('http'):
                    login_endpoint = urljoin(login_url, login_endpoint)
                    
                # Prepare JSON payload
                login_data = {
                    'username': username,
                    'password': password
                }
                
                # Add CSRF if present
                csrf_token = auth_info['details'].get('csrf_token')
                if csrf_token:
                    headers['X-CSRF-TOKEN'] = csrf_token
                    
                headers['Content-Type'] = 'application/json'
                headers['Accept'] = 'application/json'
                
                # Perform login
                async with session.post(
                    login_endpoint,
                    json=login_data,
                    headers=headers,
                    allow_redirects=False
                ) as login_response:
                    
                    response_data = {}
                    try:
                        response_data = await login_response.json()
                    except:
                        response_data = {'text': await login_response.text()}
                        
                    # Get session cookies
                    cookies = {}
                    for cookie in session.cookie_jar:
                        cookies[cookie.key] = cookie.value
                        
                    return {
                        'success': login_response.status in [200, 302],
                        'status_code': login_response.status,
                        'response': response_data,
                        'cookies': cookies,
                        'auth_type': 'spring_security',
                        'session_id': cookies.get('JSESSIONID'),
                        'location': login_response.headers.get('Location')
                    }
                    
            elif auth_info.get('type') in ['form_based', 'hybrid']:
                # Traditional form login
                form_action = auth_info['details'].get('form_action', login_url)
                form_fields = auth_info['details'].get('form_fields', {})
                
                # Update form fields with credentials
                form_fields.update({
                    'username': username,
                    'email': username,  # Some forms use email
                    'password': password
                })
                
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
                
                async with session.post(
                    form_action,
                    data=form_fields,
                    headers=headers,
                    allow_redirects=True
                ) as login_response:
                    
                    final_url = str(login_response.url)
                    response_html = await login_response.text()
                    
                    # Check for success indicators
                    success = (
                        login_response.status == 200 and
                        'dashboard' in final_url.lower() or
                        'welcome' in response_html.lower() or
                        'logout' in response_html.lower()
                    )
                    
                    cookies = {}
                    for cookie in session.cookie_jar:
                        cookies[cookie.key] = cookie.value
                        
                    return {
                        'success': success,
                        'status_code': login_response.status,
                        'final_url': final_url,
                        'cookies': cookies,
                        'auth_type': 'form_based',
                        'session_id': cookies.get('JSESSIONID') or cookies.get('sessionid')
                    }
                    
            else:
                return {
                    'success': False,
                    'error': 'Unable to detect authentication type',
                    'discovery': discovery
                }
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
            
    async def cleanup(self):
        """Clean up resources"""
        for session in self.sessions.values():
            await session.close()
        self.sessions.clear()
        self.cache.clear()

# ================== MCP Server ==================
# Initialize FastMCP server
mcp = FastMCP("mcp-web-interaction-toolkit-integrated")
scraper = EnhancedWebScraper()

@mcp.tool()
async def scrape_webpage(
    url: str,
    options: Optional[ScrapeOptions] = None
) -> Dict[str, Any]:
    """
    Scrape a webpage with full discovery and circumvention features
    
    Args:
        url: The URL to scrape
        options: Scraping options
        
    Returns:
        Scraped content with discovery data
    """
    if options is None:
        options = ScrapeOptions()
        
    return await scraper.scrape_with_discovery(url, options)

@mcp.tool()
async def smart_login(
    login_url: str,
    username: str,
    password: str,
    use_discovery: bool = True,
    use_spring_security: bool = False
) -> Dict[str, Any]:
    """
    Smart login with automatic authentication detection
    Supports Spring Security, form-based, and hybrid authentication
    
    Args:
        login_url: URL of the login page
        username: Username or email
        password: Password
        use_discovery: Use cached discovery data
        use_spring_security: Force Spring Security mode
        
    Returns:
        Login result with session cookies
    """
    return await scraper.smart_login(login_url, username, password, use_discovery)

@mcp.tool()
async def discover_api_endpoints(
    url: str,
    html_content: Optional[str] = None,
    save_to_cache: bool = True
) -> Dict[str, Any]:
    """
    Discover and cache API endpoints from a webpage
    
    Args:
        url: URL to analyze
        html_content: Optional HTML content (if already fetched)
        save_to_cache: Save discovery to persistent cache
        
    Returns:
        Discovered API endpoints and authentication info
    """
    if html_content is None:
        result = await scraper.scrape_with_discovery(url, ScrapeOptions())
        if not result['success']:
            return result
        discovery = result.get('discovery', {})
    else:
        endpoints = scraper.extract_api_endpoints(html_content, url)
        auth_info = scraper.detect_authentication_type(html_content, url)
        js_data = scraper.extract_javascript_data(html_content)
        
        discovery = {
            'endpoints': endpoints,
            'authentication': auth_info,
            'javascript_data': js_data
        }
        
        if save_to_cache:
            scraper.api_discovery.save_discovery(url, discovery)
            
    return {
        'success': True,
        'discovery': discovery,
        'cached': save_to_cache
    }

@mcp.tool()
async def get_cached_discovery(url: str) -> Dict[str, Any]:
    """
    Get cached API discovery for a domain
    
    Args:
        url: URL to get discovery for
        
    Returns:
        Cached discovery data or None
    """
    discovery = scraper.api_discovery.get_discovery(url)
    
    if discovery:
        return {
            'success': True,
            'discovery': discovery
        }
    else:
        return {
            'success': False,
            'message': 'No cached discovery found for this domain'
        }

@mcp.tool()
async def extract_javascript_data(url: str) -> Dict[str, Any]:
    """
    Extract JavaScript data from a webpage (__NEXT_DATA__, window objects, etc.)
    
    Args:
        url: URL to extract JavaScript from
        
    Returns:
        Extracted JavaScript data
    """
    result = await scraper.scrape_with_discovery(
        url, 
        ScrapeOptions(extract_js=True)
    )
    
    if result['success']:
        return {
            'success': True,
            'javascript_data': result['discovery'].get('javascript_data', {}),
            'url': url
        }
    else:
        return result

# Note: FastMCP handles cleanup automatically
# Manual cleanup can be done if needed by calling scraper.cleanup()

if __name__ == "__main__":
    # Run the server
    import sys
    mcp.run()