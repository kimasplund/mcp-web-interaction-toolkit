#!/usr/bin/env python3
"""
Web Interaction Toolkit MCP Server - Enhanced Version
With security fixes, performance optimizations, and reliability improvements
"""

import asyncio
import json
import os
import random
import re
import secrets
import time
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta
from functools import lru_cache
from contextlib import asynccontextmanager
import logging

import aiohttp
from aiohttp import TCPConnector, ClientTimeout
from bs4 import BeautifulSoup
from fastmcp import FastMCP
from pydantic import BaseModel, Field, HttpUrl, field_validator
import bleach

# Configure structured logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("web-interaction-toolkit-enhanced")

# ============================================================================
# Configuration and Environment Variables
# ============================================================================

class Config:
    """Configuration with secure defaults (can be overridden by environment variables)"""
    # Security - Default to TRUE for SSL verification
    SSL_VERIFY = os.getenv('MCP_SSL_VERIFY', 'true').lower() == 'true'
    
    # Performance - Sensible defaults
    MAX_CONNECTIONS = int(os.getenv('MCP_MAX_CONNECTIONS', '100'))
    MAX_CONNECTIONS_PER_HOST = int(os.getenv('MCP_MAX_CONNECTIONS_PER_HOST', '10'))
    
    # Caching - Enabled by default with 5 minute TTL
    ENABLE_CACHE = os.getenv('MCP_ENABLE_CACHE', 'true').lower() == 'true'
    CACHE_TTL_SECONDS = int(os.getenv('MCP_CACHE_TTL', '300'))
    
    # Reliability
    MAX_RETRIES = int(os.getenv('MCP_MAX_RETRIES', '3'))
    TIMEOUT_SECONDS = int(os.getenv('MCP_TIMEOUT', '30'))
    
    # Rate limiting - Reasonable defaults to avoid being blocked
    RATE_LIMIT_REQUESTS = int(os.getenv('MCP_RATE_LIMIT_REQUESTS', '60'))
    RATE_LIMIT_PERIOD = int(os.getenv('MCP_RATE_LIMIT_PERIOD', '60'))
    
    # Optional: Allow disabling SSL for specific use cases
    # Set MCP_SSL_VERIFY=false only if absolutely necessary
    ALLOW_INSECURE = os.getenv('MCP_ALLOW_INSECURE', 'false').lower() == 'true'

# ============================================================================
# Custom Exceptions
# ============================================================================

class WebInteractionError(Exception):
    """Base exception for web interaction errors"""
    pass

class ScrapingError(WebInteractionError):
    """Error during web scraping"""
    pass

class APIConnectionError(WebInteractionError):
    """Error with API connection"""
    pass

class RateLimitError(WebInteractionError):
    """Rate limit exceeded"""
    pass

class CircuitBreakerError(WebInteractionError):
    """Circuit breaker is open"""
    pass

# ============================================================================
# Session Management with Connection Pooling
# ============================================================================

class SessionManager:
    """Thread-safe session manager with connection pooling"""
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        self._connector = None
        
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create a session with connection pooling"""
        if self._session is None or self._session.closed:
            async with self._lock:
                if self._session is None or self._session.closed:
                    self._connector = TCPConnector(
                        limit=Config.MAX_CONNECTIONS,
                        limit_per_host=Config.MAX_CONNECTIONS_PER_HOST,
                        ttl_dns_cache=300,
                        enable_cleanup_closed=True
                    )
                    timeout = ClientTimeout(total=Config.TIMEOUT_SECONDS)
                    self._session = aiohttp.ClientSession(
                        connector=self._connector,
                        timeout=timeout
                    )
                    logger.info(f"Created new session with connection pool (max: {Config.MAX_CONNECTIONS})")
        return self._session
    
    async def close(self):
        """Close the session and connector"""
        if self._session:
            await self._session.close()
        if self._connector:
            await self._connector.close()

# Global session manager
session_manager = SessionManager()

# ============================================================================
# Rate Limiting
# ============================================================================

class RateLimiter:
    """Simple rate limiter per domain with automatic cleanup"""
    
    def __init__(self, max_requests: int = 60, period: int = 60):
        self.max_requests = max_requests
        self.period = period  # seconds
        self.requests: Dict[str, List[datetime]] = {}
        self._lock = asyncio.Lock()
        self._last_cleanup = time.time()
    
    async def check_rate_limit(self, domain: str) -> bool:
        """Check if request is within rate limit"""
        async with self._lock:
            now = datetime.now()
            current_time = time.time()
            
            # Periodic cleanup to prevent memory leak (every 5 minutes)
            if current_time - self._last_cleanup > 300:
                cutoff = now - timedelta(seconds=self.period)
                # Clean all domains
                for d in list(self.requests.keys()):
                    self.requests[d] = [
                        req_time for req_time in self.requests[d]
                        if req_time > cutoff
                    ]
                    # Remove domain if no recent requests
                    if not self.requests[d]:
                        del self.requests[d]
                self._last_cleanup = current_time
            
            if domain not in self.requests:
                self.requests[domain] = []
            
            # Remove old requests outside the period
            cutoff = now - timedelta(seconds=self.period)
            self.requests[domain] = [
                req_time for req_time in self.requests[domain]
                if req_time > cutoff
            ]
            
            # Check if we're within limit
            if len(self.requests[domain]) >= self.max_requests:
                return False
            
            # Add current request
            self.requests[domain].append(now)
            return True
    
    async def wait_if_needed(self, domain: str):
        """Wait if rate limit is exceeded"""
        while not await self.check_rate_limit(domain):
            logger.warning(f"Rate limit exceeded for {domain}, waiting...")
            await asyncio.sleep(1)

# Global rate limiter
rate_limiter = RateLimiter(Config.RATE_LIMIT_REQUESTS, Config.RATE_LIMIT_PERIOD)

# ============================================================================
# Circuit Breaker Pattern
# ============================================================================

class CircuitBreaker:
    """Circuit breaker for failing endpoints"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures: Dict[str, int] = {}
        self.last_failure_time: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
    
    async def is_open(self, endpoint: str) -> bool:
        """Check if circuit is open for endpoint"""
        async with self._lock:
            if endpoint not in self.failures:
                return False
            
            # Check if recovery period has passed
            if endpoint in self.last_failure_time:
                time_since_failure = (datetime.now() - self.last_failure_time[endpoint]).seconds
                if time_since_failure > self.recovery_timeout:
                    # Reset circuit
                    self.failures[endpoint] = 0
                    del self.last_failure_time[endpoint]
                    logger.info(f"Circuit breaker reset for {endpoint}")
                    return False
            
            return self.failures[endpoint] >= self.failure_threshold
    
    async def record_success(self, endpoint: str):
        """Record successful request"""
        async with self._lock:
            if endpoint in self.failures:
                self.failures[endpoint] = 0
                if endpoint in self.last_failure_time:
                    del self.last_failure_time[endpoint]
    
    async def record_failure(self, endpoint: str):
        """Record failed request"""
        async with self._lock:
            if endpoint not in self.failures:
                self.failures[endpoint] = 0
            self.failures[endpoint] += 1
            self.last_failure_time[endpoint] = datetime.now()
            
            if self.failures[endpoint] >= self.failure_threshold:
                logger.error(f"Circuit breaker opened for {endpoint}")

# Global circuit breaker
circuit_breaker = CircuitBreaker()

# ============================================================================
# Caching Layer
# ============================================================================

class CacheManager:
    """Simple in-memory cache with TTL"""
    
    def __init__(self, ttl_seconds: int = 300):
        self.cache: Dict[str, Tuple[Any, datetime]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        self._lock = asyncio.Lock()
    
    def _get_cache_key(self, url: str, options: dict = None) -> str:
        """Generate cache key from URL and options"""
        key_data = f"{url}:{json.dumps(options or {}, sort_keys=True)}"
        # Use a simple string key instead of MD5 hash
        return key_data.replace('/', '_').replace(':', '_')[:100]
    
    async def get(self, url: str, options: dict = None) -> Optional[Any]:
        """Get cached value if not expired"""
        if not Config.ENABLE_CACHE:
            return None
            
        async with self._lock:
            key = self._get_cache_key(url, options)
            if key in self.cache:
                value, timestamp = self.cache[key]
                if datetime.now() - timestamp < self.ttl:
                    logger.debug(f"Cache hit for {url}")
                    return value
                else:
                    del self.cache[key]
        return None
    
    async def set(self, url: str, value: Any, options: dict = None):
        """Set cache value with current timestamp"""
        if not Config.ENABLE_CACHE:
            return
            
        async with self._lock:
            key = self._get_cache_key(url, options)
            self.cache[key] = (value, datetime.now())
            logger.debug(f"Cached result for {url}")
            
            # Clean up old entries if cache grows too large (prevent memory leak)
            if len(self.cache) > 1000:
                # Remove expired entries
                now = datetime.now()
                self.cache = {
                    k: v for k, v in self.cache.items()
                    if now - v[1] < self.ttl
                }
                # If still too large, remove oldest entries
                if len(self.cache) > 800:
                    sorted_items = sorted(self.cache.items(), key=lambda x: x[1][1])
                    self.cache = dict(sorted_items[-800:])
    
    async def clear(self):
        """Clear all cache entries"""
        async with self._lock:
            self.cache.clear()

# Global cache manager
cache_manager = CacheManager(Config.CACHE_TTL_SECONDS)

# ============================================================================
# Retry Logic with Exponential Backoff
# ============================================================================

async def retry_with_backoff(
    func,
    max_retries: int = None,
    backoff_factor: float = 2.0,
    max_backoff: float = 60.0
):
    """Retry function with exponential backoff and jitter"""
    max_retries = max_retries or Config.MAX_RETRIES
    
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Max retries ({max_retries}) exceeded: {e}")
                raise
            
            # Calculate backoff with jitter
            backoff = min(backoff_factor ** attempt, max_backoff)
            jitter = random.uniform(0, backoff * 0.1)
            wait_time = backoff + jitter
            
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time:.2f}s: {e}")
            await asyncio.sleep(wait_time)

# ============================================================================
# Enhanced Pydantic Models
# ============================================================================

class ScrapeOptions(BaseModel):
    """Enhanced options for web scraping"""
    simulate_human: bool = Field(default=True, description="Simulate human-like behavior")
    max_content_length: int = Field(default=5000, description="Maximum content length to return")
    max_links: int = Field(default=50, description="Maximum number of links to extract")
    max_images: int = Field(default=20, description="Maximum number of images to extract")
    min_delay: float = Field(default=0.5, description="Minimum delay between requests (seconds)")
    max_delay: float = Field(default=2.0, description="Maximum delay between requests (seconds)")
    use_cache: bool = Field(default=True, description="Use caching for repeated requests")
    follow_redirects: bool = Field(default=True, description="Follow HTTP redirects")
    sanitize_content: bool = Field(default=True, description="Sanitize scraped content for security")
    
    @field_validator('min_delay', 'max_delay')
    def validate_delays(cls, v):
        if v < 0:
            raise ValueError("Delay must be non-negative")
        if v > 60:
            raise ValueError("Delay must be less than 60 seconds")
        return v

# ============================================================================
# Enhanced Helper Functions
# ============================================================================

def validate_url(url: str) -> bool:
    """Validate URL to prevent XSS and other attacks"""
    try:
        parsed = urlparse(url)
        # Only allow http and https schemes
        if parsed.scheme not in ('http', 'https'):
            logger.warning(f"Rejected URL with scheme: {parsed.scheme}")
            return False
        # Must have a valid netloc (domain)
        if not parsed.netloc:
            return False
        # Reject localhost and private IPs for security
        if parsed.netloc.lower() in ('localhost', '127.0.0.1', '0.0.0.0'):
            logger.warning(f"Rejected localhost URL: {url}")
            return False
        return True
    except Exception:
        return False

def get_random_user_agent() -> str:
    """Generate a random user agent to simulate different browsers"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/121.0.0.0',
        'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1'
    ]
    return random.choice(user_agents)

async def simulate_human_delay(min_delay: float = 0.5, max_delay: float = 2.0):
    """Simulate human-like delays between requests"""
    delay = random.uniform(min_delay, max_delay)
    await asyncio.sleep(delay)

def prepare_request_headers(custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Prepare request headers with human-like characteristics"""
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': get_random_user_agent(),
        'Cache-Control': 'max-age=0',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1'
    }
    
    # Add referer for some requests to appear more natural
    if random.choice([True, False]):
        headers['Referer'] = random.choice([
            'https://www.google.com/',
            'https://www.bing.com/',
            'https://duckduckgo.com/'
        ])
    
    # Add custom headers if provided
    if custom_headers:
        headers.update(custom_headers)
        
    return headers

def sanitize_html_content(html_content: str) -> str:
    """Sanitize HTML content to prevent XSS attacks"""
    # Allow only safe tags and attributes
    allowed_tags = ['p', 'br', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                   'ul', 'ol', 'li', 'a', 'img', 'strong', 'em', 'code', 'pre']
    allowed_attributes = {'a': ['href', 'title'], 'img': ['src', 'alt']}
    
    return bleach.clean(
        html_content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True
    )

# ============================================================================
# Persistent Session Management for Authentication
# ============================================================================

class AuthSessionManager:
    """Manage authenticated sessions with cookies"""
    
    def __init__(self):
        self._sessions: Dict[str, aiohttp.ClientSession] = {}
        self._cookies: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
    
    async def get_or_create_session(self, session_id: str) -> aiohttp.ClientSession:
        """Get or create a persistent session for a specific user/domain"""
        async with self._lock:
            if session_id not in self._sessions or self._sessions[session_id].closed:
                connector = TCPConnector(
                    limit=Config.MAX_CONNECTIONS,
                    limit_per_host=Config.MAX_CONNECTIONS_PER_HOST
                )
                timeout = ClientTimeout(total=Config.TIMEOUT_SECONDS)
                
                # Create session with cookie jar
                self._sessions[session_id] = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    cookie_jar=aiohttp.CookieJar()
                )
                
                # Restore cookies if they exist
                if session_id in self._cookies:
                    self._sessions[session_id].cookie_jar.update_cookies(self._cookies[session_id])
                
                logger.info(f"Created authenticated session for {session_id}")
            
            return self._sessions[session_id]
    
    async def save_cookies(self, session_id: str):
        """Save cookies from a session"""
        async with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                if isinstance(session, tuple):
                    session, _ = session
                # Properly extract cookies from CookieJar
                cookies = {}
                for cookie in session.cookie_jar:
                    cookies[cookie.key] = cookie.value
                self._cookies[session_id] = cookies
    
    async def close_session(self, session_id: str):
        """Close a specific session"""
        async with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                if isinstance(session, tuple):
                    session, _ = session
                await session.close()
                del self._sessions[session_id]
                logger.info(f"Closed session for {session_id}")
    
    async def close_all(self):
        """Close all sessions"""
        async with self._lock:
            for item in self._sessions.values():
                session = item[0] if isinstance(item, tuple) else item
                await session.close()
            self._sessions.clear()
            self._cookies.clear()  # Also clear cookies to prevent memory leak
            logger.info("Closed all authenticated sessions")

# Global authenticated session manager
auth_session_manager = AuthSessionManager()

# ============================================================================
# Form Detection and Parsing
# ============================================================================

def extract_form_fields(soup: BeautifulSoup, form_selector: Optional[str] = None) -> Dict[str, Any]:
    """Extract form fields from HTML with CAPTCHA detection"""
    forms = []
    
    if form_selector:
        form_elements = soup.select(form_selector)
    else:
        form_elements = soup.find_all('form')
    
    for form in form_elements:
        form_data = {
            'action': form.get('action', ''),
            'method': form.get('method', 'get').upper(),
            'fields': {},
            'hidden_fields': {},
            'submit_buttons': [],
            'has_captcha': False,
            'captcha_type': None
        }
        
        # Check for CAPTCHA indicators
        captcha_indicators = [
            ('recaptcha', 'reCAPTCHA'),
            ('g-recaptcha', 'Google reCAPTCHA'),
            ('h-captcha', 'hCaptcha'),
            ('captcha', 'Generic CAPTCHA'),
            ('cf-turnstile', 'Cloudflare Turnstile')
        ]
        
        form_html = str(form).lower()
        for indicator, captcha_type in captcha_indicators:
            if indicator in form_html:
                form_data['has_captcha'] = True
                form_data['captcha_type'] = captcha_type
                logger.warning(f"CAPTCHA detected in form: {captcha_type}")
                break
        
        # Extract input fields
        for input_field in form.find_all('input'):
            field_name = input_field.get('name')
            if not field_name:
                continue
            
            field_type = input_field.get('type', 'text')
            field_value = input_field.get('value', '')
            
            if field_type == 'hidden':
                form_data['hidden_fields'][field_name] = field_value
            elif field_type == 'submit':
                form_data['submit_buttons'].append({
                    'name': field_name,
                    'value': field_value
                })
            else:
                form_data['fields'][field_name] = {
                    'type': field_type,
                    'value': field_value,
                    'required': input_field.get('required') is not None
                }
        
        # Extract select fields
        for select in form.find_all('select'):
            field_name = select.get('name')
            if field_name:
                options = [option.get('value', option.text) for option in select.find_all('option')]
                form_data['fields'][field_name] = {
                    'type': 'select',
                    'options': options,
                    'required': select.get('required') is not None
                }
        
        # Extract textarea fields
        for textarea in form.find_all('textarea'):
            field_name = textarea.get('name')
            if field_name:
                form_data['fields'][field_name] = {
                    'type': 'textarea',
                    'value': textarea.text,
                    'required': textarea.get('required') is not None
                }
        
        forms.append(form_data)
    
    return forms

# ============================================================================
# Enhanced MCP Tools
# ============================================================================

@mcp.tool()
async def scrape_webpage(
    url: str,
    options: Optional[ScrapeOptions] = None
) -> Dict[str, Any]:
    """
    Enhanced webpage scraping with security, caching, and reliability
    
    Args:
        url: The URL to scrape
        options: Enhanced scraping options
        
    Returns:
        Dictionary containing page content, links, images, and metadata
    """
    if options is None:
        options = ScrapeOptions()
    
    # Input validation with security checks
    if not validate_url(url):
        raise ValueError(f"Invalid or potentially malicious URL: {url}")
    
    parsed_url = urlparse(url)
    
    domain = parsed_url.netloc
    
    try:
        # Check cache first
        if options.use_cache:
            cached_result = await cache_manager.get(url, options.dict())
            if cached_result:
                return cached_result
        
        # Check circuit breaker
        if await circuit_breaker.is_open(domain):
            raise CircuitBreakerError(f"Circuit breaker is open for {domain}")
        
        # Apply rate limiting
        await rate_limiter.wait_if_needed(domain)
        
        # Simulate human delay if requested
        if options.simulate_human:
            await simulate_human_delay(options.min_delay, options.max_delay)
        
        # Prepare headers
        headers = prepare_request_headers() if options.simulate_human else {'User-Agent': get_random_user_agent()}
        
        # Execute request with retry logic
        async def make_request():
            session = await session_manager.get_session()
            async with session.get(
                url,
                headers=headers,
                ssl=Config.SSL_VERIFY,
                allow_redirects=options.follow_redirects
            ) as response:
                response.raise_for_status()
                return await response.text(), response.status, response.headers
        
        content, status_code, response_headers = await retry_with_backoff(make_request)
        
        # Record success for circuit breaker
        await circuit_breaker.record_success(domain)
        
        # Parse the content
        soup = BeautifulSoup(content, 'lxml')
        
        # Extract title
        title = soup.title.string if soup.title else "No title found"
        
        # Extract text content
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Sanitize content if requested
        if options.sanitize_content:
            text = sanitize_html_content(text)
        
        # Extract links with validation
        links = []
        for link in soup.find_all('a', href=True)[:options.max_links * 2]:  # Get extra to filter
            try:
                absolute_url = urljoin(url, link['href'])
                parsed = urlparse(absolute_url)
                if parsed.scheme in ['http', 'https']:
                    links.append({
                        'text': link.get_text().strip()[:100],  # Limit text length
                        'url': absolute_url
                    })
                    if len(links) >= options.max_links:
                        break
            except Exception as e:
                logger.debug(f"Skipping invalid link: {e}")
        
        # Extract images with validation
        images = []
        for img in soup.find_all('img', src=True)[:options.max_images * 2]:
            try:
                absolute_url = urljoin(url, img['src'])
                parsed = urlparse(absolute_url)
                if parsed.scheme in ['http', 'https', 'data']:
                    images.append({
                        'alt': img.get('alt', '')[:100],
                        'url': absolute_url if not absolute_url.startswith('data:') else 'data:...'
                    })
                    if len(images) >= options.max_images:
                        break
            except Exception as e:
                logger.debug(f"Skipping invalid image: {e}")
        
        result = {
            "success": True,
            "url": url,
            "title": title,
            "content": text[:options.max_content_length],
            "links": links,
            "images": images,
            "status_code": status_code,
            "headers": dict(response_headers),
            "cached": False,
            "timestamp": datetime.now().isoformat()
        }
        
        # Cache the result
        if options.use_cache:
            await cache_manager.set(url, result, options.dict())
        
        logger.info(f"Successfully scraped {url} (status: {status_code})")
        return result
        
    except CircuitBreakerError:
        raise
    except Exception as e:
        # Record failure for circuit breaker
        await circuit_breaker.record_failure(domain)
        
        error_result = {
            "success": False,
            "url": url,
            "error": str(e),
            "error_type": type(e).__name__,
            "content": "",
            "timestamp": datetime.now().isoformat()
        }
        
        logger.error(f"Failed to scrape {url}: {e}")
        return error_result

@mcp.tool()
async def clear_cache() -> Dict[str, Any]:
    """Clear all cached scraping results"""
    await cache_manager.clear()
    return {
        "success": True,
        "message": "Cache cleared successfully",
        "timestamp": datetime.now().isoformat()
    }

@mcp.tool()
async def login_to_website(
    login_url: str,
    username_field: str,
    username: str,
    password_field: str,
    password: str,
    session_id: Optional[str] = None,
    additional_fields: Optional[Dict[str, str]] = None,
    form_selector: Optional[str] = None
) -> Dict[str, Any]:
    """
    Login to a website by submitting credentials
    
    Args:
        login_url: URL of the login page
        username_field: Name of the username/email input field
        username: Username or email to login with
        password_field: Name of the password input field
        password: Password to login with
        session_id: Optional session ID to maintain login state
        additional_fields: Additional form fields to submit
        form_selector: CSS selector for the login form
        
    Returns:
        Login result with session information
    """
    try:
        session_id = session_id or f"login_{urlparse(login_url).netloc}_{secrets.token_urlsafe(8)}"
        
        # Get or create authenticated session
        session = await auth_session_manager.get_or_create_session(session_id)
        
        # First, get the login page to extract any hidden fields (CSRF tokens, etc.)
        headers = prepare_request_headers()
        async with session.get(login_url, headers=headers, ssl=Config.SSL_VERIFY) as response:
            html = await response.text()
            soup = BeautifulSoup(html, 'lxml')
        
        # Extract form fields
        forms = extract_form_fields(soup, form_selector)
        if not forms:
            return {
                "success": False,
                "error": "No login form found on the page",
                "session_id": session_id
            }
        
        # Use the first form found
        form = forms[0]
        
        # Prepare form data
        form_data = {}
        
        # Add hidden fields (often includes CSRF tokens)
        form_data.update(form['hidden_fields'])
        
        # Add credentials
        form_data[username_field] = username
        form_data[password_field] = password
        
        # Add any additional fields
        if additional_fields:
            form_data.update(additional_fields)
        
        # Determine form action URL
        action_url = form['action']
        if not action_url:
            action_url = login_url
        elif not action_url.startswith('http'):
            action_url = urljoin(login_url, action_url)
        
        # Simulate human delay
        await simulate_human_delay(1, 3)
        
        # Submit login form
        headers = prepare_request_headers({'Referer': login_url})
        
        if form['method'] == 'POST':
            async with session.post(
                action_url,
                data=form_data,
                headers=headers,
                ssl=Config.SSL_VERIFY,
                allow_redirects=True
            ) as response:
                result_html = await response.text()
                final_url = str(response.url)
                status_code = response.status
        else:
            async with session.get(
                action_url,
                params=form_data,
                headers=headers,
                ssl=Config.SSL_VERIFY,
                allow_redirects=True
            ) as response:
                result_html = await response.text()
                final_url = str(response.url)
                status_code = response.status
        
        # Save cookies for future use
        await auth_session_manager.save_cookies(session_id)
        
        # Check for common login success indicators
        soup = BeautifulSoup(result_html, 'lxml')
        success_indicators = [
            'logout', 'sign out', 'dashboard', 'welcome', 'profile',
            username.lower(), 'my account'
        ]
        
        page_text = soup.get_text().lower()
        login_successful = any(indicator in page_text for indicator in success_indicators)
        
        # Check if we're still on the login page (likely failed)
        if urlparse(final_url).path == urlparse(login_url).path and not login_successful:
            login_successful = False
        
        logger.info(f"Login attempt for {username} at {login_url}: {'Success' if login_successful else 'Failed'}")
        
        return {
            "success": True,
            "login_successful": login_successful,
            "session_id": session_id,
            "final_url": final_url,
            "status_code": status_code,
            "page_title": soup.title.string if soup.title else None,
            "message": "Login submitted. Use the session_id for authenticated requests.",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Login failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "session_id": session_id if 'session_id' in locals() else None
        }

@mcp.tool()
async def submit_form(
    url: str,
    form_data: Dict[str, str],
    session_id: Optional[str] = None,
    form_selector: Optional[str] = None,
    method: Optional[str] = None
) -> Dict[str, Any]:
    """
    Submit a form on a webpage (search, contact, etc.)
    
    Args:
        url: URL of the page with the form
        form_data: Dictionary of form field names and values
        session_id: Optional session ID for authenticated requests
        form_selector: CSS selector for the specific form
        method: Override HTTP method (GET or POST)
        
    Returns:
        Form submission result
    """
    try:
        # Get appropriate session
        if session_id:
            session = await auth_session_manager.get_or_create_session(session_id)
        else:
            session = await session_manager.get_session()
        
        # Get the page to extract form details
        headers = prepare_request_headers()
        async with session.get(url, headers=headers, ssl=Config.SSL_VERIFY) as response:
            html = await response.text()
            soup = BeautifulSoup(html, 'lxml')
        
        # Extract forms
        forms = extract_form_fields(soup, form_selector)
        if not forms:
            # If no form found, try direct submission
            form = {'action': url, 'method': method or 'POST', 'hidden_fields': {}}
        else:
            form = forms[0]
        
        # Merge hidden fields with user data
        submit_data = {}
        submit_data.update(form['hidden_fields'])
        submit_data.update(form_data)
        
        # Determine action URL
        action_url = form['action']
        if not action_url:
            action_url = url
        elif not action_url.startswith('http'):
            action_url = urljoin(url, action_url)
        
        # Determine method
        method = method or form['method']
        
        # Simulate human delay
        await simulate_human_delay()
        
        # Submit form
        headers = prepare_request_headers({'Referer': url})
        
        if method == 'POST':
            async with session.post(
                action_url,
                data=submit_data,
                headers=headers,
                ssl=Config.SSL_VERIFY,
                allow_redirects=True
            ) as response:
                result_html = await response.text()
                final_url = str(response.url)
                status_code = response.status
        else:
            async with session.get(
                action_url,
                params=submit_data,
                headers=headers,
                ssl=Config.SSL_VERIFY,
                allow_redirects=True
            ) as response:
                result_html = await response.text()
                final_url = str(response.url)
                status_code = response.status
        
        # Parse results
        soup = BeautifulSoup(result_html, 'lxml')
        
        # Extract text content
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        logger.info(f"Form submitted to {action_url} with {len(submit_data)} fields")
        
        return {
            "success": True,
            "final_url": final_url,
            "status_code": status_code,
            "page_title": soup.title.string if soup.title else None,
            "content": text[:5000],
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Form submission failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
async def search_website(
    search_url: str,
    query: str,
    search_field_name: Optional[str] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Submit a search query to a website
    
    Args:
        search_url: URL of the search page or search endpoint
        query: Search query string
        search_field_name: Name of the search input field (will auto-detect if not provided)
        session_id: Optional session ID for authenticated searches
        
    Returns:
        Search results
    """
    try:
        # Get appropriate session
        if session_id:
            session = await auth_session_manager.get_or_create_session(session_id)
        else:
            session = await session_manager.get_session()
        
        # If no field name provided, try to detect it
        if not search_field_name:
            headers = prepare_request_headers()
            async with session.get(search_url, headers=headers, ssl=Config.SSL_VERIFY) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'lxml')
            
            # Common search field names
            common_names = ['q', 'query', 'search', 's', 'keyword', 'search_query', 'searchterm']
            
            # Try to find search input
            for name in common_names:
                if soup.find('input', {'name': name}):
                    search_field_name = name
                    break
            
            # If still not found, look for any input with type="search"
            if not search_field_name:
                search_input = soup.find('input', {'type': 'search'})
                if search_input and search_input.get('name'):
                    search_field_name = search_input['name']
            
            # Default to 'q' if nothing found
            if not search_field_name:
                search_field_name = 'q'
        
        # Submit search
        form_data = {search_field_name: query}
        
        # Try GET first (most searches use GET)
        headers = prepare_request_headers()
        async with session.get(
            search_url,
            params=form_data,
            headers=headers,
            ssl=Config.SSL_VERIFY,
            allow_redirects=True
        ) as response:
            result_html = await response.text()
            final_url = str(response.url)
            status_code = response.status
        
        # Parse results
        soup = BeautifulSoup(result_html, 'lxml')
        
        # Extract search results (generic approach)
        results = []
        
        # Look for common result containers
        result_selectors = [
            'div.result', 'div.search-result', 'article', 'li.result',
            'div[class*="result"]', 'div[class*="search"]'
        ]
        
        for selector in result_selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements[:20]:  # Limit to 20 results
                    result = {}
                    
                    # Try to extract title
                    title_elem = element.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a'])
                    if title_elem:
                        result['title'] = title_elem.get_text().strip()
                    
                    # Try to extract URL
                    link_elem = element.find('a', href=True)
                    if link_elem:
                        result['url'] = urljoin(final_url, link_elem['href'])
                    
                    # Try to extract description
                    desc_elem = element.find(['p', 'span', 'div'])
                    if desc_elem:
                        result['description'] = desc_elem.get_text().strip()[:200]
                    
                    if result:
                        results.append(result)
                
                if results:
                    break
        
        logger.info(f"Search for '{query}' returned {len(results)} results")
        
        return {
            "success": True,
            "query": query,
            "results_count": len(results),
            "results": results,
            "final_url": final_url,
            "status_code": status_code,
            "page_title": soup.title.string if soup.title else None,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {
            "success": False,
            "query": query,
            "error": str(e)
        }

@mcp.tool()
async def scrape_with_session(
    url: str,
    session_id: str,
    options: Optional[ScrapeOptions] = None
) -> Dict[str, Any]:
    """
    Scrape a webpage using an authenticated session
    
    Args:
        url: URL to scrape
        session_id: Session ID from a previous login
        options: Scraping options
        
    Returns:
        Scraped content with session context
    """
    if options is None:
        options = ScrapeOptions()
    
    try:
        # Get authenticated session
        session = await auth_session_manager.get_or_create_session(session_id)
        
        # Simulate human delay if requested
        if options.simulate_human:
            await simulate_human_delay(options.min_delay, options.max_delay)
        
        # Prepare headers
        headers = prepare_request_headers() if options.simulate_human else {'User-Agent': get_random_user_agent()}
        
        # Make request with authenticated session
        async with session.get(
            url,
            headers=headers,
            ssl=Config.SSL_VERIFY,
            allow_redirects=options.follow_redirects
        ) as response:
            response.raise_for_status()
            content = await response.text()
            status_code = response.status
        
        # Parse content (similar to regular scrape)
        soup = BeautifulSoup(content, 'lxml')
        title = soup.title.string if soup.title else "No title found"
        
        # Extract text
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Sanitize if requested
        if options.sanitize_content:
            text = sanitize_html_content(text)
        
        logger.info(f"Scraped {url} with authenticated session {session_id}")
        
        return {
            "success": True,
            "url": url,
            "title": title,
            "content": text[:options.max_content_length],
            "status_code": status_code,
            "session_id": session_id,
            "authenticated": True,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Authenticated scrape failed: {e}")
        return {
            "success": False,
            "url": url,
            "error": str(e),
            "session_id": session_id
        }

@mcp.tool()
async def close_session(session_id: str) -> Dict[str, Any]:
    """Close an authenticated session and clear cookies"""
    try:
        await auth_session_manager.close_session(session_id)
        return {
            "success": True,
            "message": f"Session {session_id} closed successfully",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
async def get_health_status() -> Dict[str, Any]:
    """Get health status of the server"""
    session = await session_manager.get_session()
    
    return {
        "success": True,
        "status": "healthy",
        "config": {
            "ssl_verify": Config.SSL_VERIFY,
            "max_connections": Config.MAX_CONNECTIONS,
            "cache_enabled": Config.ENABLE_CACHE,
            "cache_ttl": Config.CACHE_TTL_SECONDS,
            "rate_limit": f"{Config.RATE_LIMIT_REQUESTS} requests per {Config.RATE_LIMIT_PERIOD} seconds"
        },
        "session": {
            "active": not session.closed,
            "connector_limit": session.connector.limit if session.connector else None
        },
        "timestamp": datetime.now().isoformat()
    }

# ============================================================================
# API Discovery Integration
# ============================================================================

from pathlib import Path

class APIDiscoveryManager:
    """Manages API endpoint discovery and caching"""
    
    def __init__(self, storage_dir: str = ".api_discovery"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        
    def get_domain(self, url: str) -> str:
        """Extract domain from URL"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
        
    def discover_endpoints(self, url: str, html: str) -> Dict[str, Any]:
        """Discover API endpoints from HTML/JavaScript"""
        endpoints = []
        
        # API endpoint patterns
        patterns = [
            r'["\'](/api/[^"\']+)["\']',
            r'["\'](/auth/[^"\']+)["\']', 
            r'["\'](/login[^"\']*)["\']',
            r'["\'](/signin[^"\']*)["\']',
            r'["\'](/session[^"\']*)["\']',
            r'["\'](/token[^"\']*)["\']',
            r'fetch\s*\(\s*["\']([^"\']+)["\']',
            r'axios\.[a-z]+\s*\(\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                endpoint_url = match
                if not endpoint_url.startswith('http'):
                    endpoint_url = urljoin(url, endpoint_url)
                    
                # Skip static assets
                if any(ext in endpoint_url for ext in ['.css', '.js', '.jpg', '.png']):
                    continue
                    
                method = 'POST' if any(kw in endpoint_url.lower() 
                                     for kw in ['login', 'auth', 'signin']) else 'GET'
                
                endpoints.append({
                    'url': endpoint_url,
                    'method': method,
                    'discovered_at': datetime.now().isoformat()
                })
                
        return endpoints
        
    def save_discovery(self, url: str, endpoints: List[Dict]) -> Path:
        """Save discovered endpoints to domain-specific file"""
        domain = self.get_domain(url)
        file_path = self.storage_dir / f"{domain}.json"
        
        discovery = {
            'domain': domain,
            'url': url,
            'last_updated': datetime.now().isoformat(),
            'endpoints': endpoints
        }
        
        # Merge with existing if file exists
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    existing = json.load(f)
                    existing_urls = {ep['url'] for ep in existing.get('endpoints', [])}
                    for ep in endpoints:
                        if ep['url'] not in existing_urls:
                            existing['endpoints'].append(ep)
                    discovery = existing
                    discovery['last_updated'] = datetime.now().isoformat()
            except:
                pass
                
        with open(file_path, 'w') as f:
            json.dump(discovery, f, indent=2)
            
        return file_path
        
    def get_cached_discovery(self, url: str) -> Optional[Dict]:
        """Get cached discovery for a domain"""
        domain = self.get_domain(url)
        file_path = self.storage_dir / f"{domain}.json"
        
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        return None

# Global API discovery manager
api_discovery_manager = APIDiscoveryManager()

@mcp.tool()
async def discover_api_endpoints(
    url: str,
    html_content: Optional[str] = None,
    save_to_cache: bool = True
) -> Dict[str, Any]:
    """
    Discover and cache API endpoints from a website
    
    Args:
        url: The URL to analyze
        html_content: Optional HTML content (will fetch if not provided)
        save_to_cache: Whether to save discoveries to cache
        
    Returns:
        Discovery results including found endpoints
    """
    try:
        # If no HTML provided, fetch it
        if not html_content:
            # Fetch the page directly
            session = await session_manager.get_session()
            headers = prepare_request_headers()
            
            async with session.get(url, headers=headers, ssl=Config.SSL_VERIFY) as response:
                html_content = await response.text()
            
        # Discover endpoints
        endpoints = api_discovery_manager.discover_endpoints(url, html_content)
        
        # Save to cache if requested
        cache_file = None
        if save_to_cache and endpoints:
            cache_file = api_discovery_manager.save_discovery(url, endpoints)
            
        return {
            'success': True,
            'url': url,
            'endpoints_found': len(endpoints),
            'endpoints': endpoints,
            'cache_file': str(cache_file) if cache_file else None,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

@mcp.tool()
async def get_cached_api_discovery(url: str) -> Dict[str, Any]:
    """
    Get cached API discovery for a domain
    
    Args:
        url: URL of the site to get cached discovery for
        
    Returns:
        Cached discovery data or empty if not found
    """
    try:
        discovery = api_discovery_manager.get_cached_discovery(url)
        
        if discovery:
            return {
                'success': True,
                'found': True,
                'discovery': discovery,
                'cache_file': str(api_discovery_manager.storage_dir / f"{api_discovery_manager.get_domain(url)}.json")
            }
        else:
            return {
                'success': True,
                'found': False,
                'message': 'No cached discovery found for this domain'
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

@mcp.tool()
async def smart_login(
    login_url: str,
    username: str,
    password: str,
    use_discovery: bool = True,
    use_spring_security: bool = False
) -> Dict[str, Any]:
    """
    Smart login that uses discovered API endpoints when available
    
    Args:
        login_url: The login page URL
        username: Username or email
        password: Password
        use_discovery: Whether to use cached API discoveries
        
    Returns:
        Login result with session information
    """
    try:
        # Special handling for Spring Security sites (like ClickBank)
        if use_spring_security or 'clickbank' in login_url.lower():
            logger.info("Using Spring Security authentication flow")
            
            session_id = f"spring_{api_discovery_manager.get_domain(login_url)}_{secrets.token_urlsafe(8)}"
            session = await auth_session_manager.get_or_create_session(session_id)
            
            # Get the login page first to establish session
            headers = prepare_request_headers()
            async with session.get(login_url, headers=headers, ssl=Config.SSL_VERIFY) as response:
                html = await response.text()
                
            # Extract __NEXT_DATA__ if present (for Next.js apps)
            event_id = None
            soup = BeautifulSoup(html, 'lxml')
            for script in soup.find_all('script'):
                if script.get('id') == '__NEXT_DATA__':
                    try:
                        import json
                        next_data = json.loads(script.string)
                        event_id = next_data.get('props', {}).get('pageProps', {}).get('clientMetadata', {}).get('eventId')
                    except:
                        pass
                        
            # Prepare Spring Security login data
            login_data = {
                'username': username,
                'password': password,
            }
            
            if event_id:
                login_data['eventId'] = event_id
                
            # Common Spring Security parameters
            login_data['submit'] = 'Login'
            login_data['_spring_security_remember_me'] = 'on'
            
            # Try Spring Security endpoint
            headers = prepare_request_headers({
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': urlparse(login_url).scheme + '://' + urlparse(login_url).netloc,
                'Referer': login_url,
            })
            
            # Common Spring Security endpoints
            endpoints_to_try = ['/api/login', '/j_security_check', '/login', '/perform_login']
            base_url = urlparse(login_url).scheme + '://' + urlparse(login_url).netloc
            
            for endpoint in endpoints_to_try:
                try:
                    async with session.post(
                        base_url + endpoint,
                        data=login_data,
                        headers=headers,
                        ssl=Config.SSL_VERIFY,
                        allow_redirects=False
                    ) as response:
                        if response.status in [302, 303]:
                            location = response.headers.get('Location', '')
                            
                            # Save cookies
                            await auth_session_manager.save_cookies(session_id)
                            
                            return {
                                'success': True,
                                'method': 'spring_security',
                                'endpoint_used': endpoint,
                                'session_id': session_id,
                                'redirect': location,
                                'has_error': 'error' in location.lower(),
                                'message': 'Spring Security login attempted. Check redirect for success.',
                                'timestamp': datetime.now().isoformat()
                            }
                except:
                    continue
                    
        # Check for cached discovery
        if use_discovery:
            discovery = api_discovery_manager.get_cached_discovery(login_url)
            
            if discovery and discovery.get('endpoints'):
                # Look for login endpoints
                login_endpoints = [
                    ep for ep in discovery['endpoints']
                    if any(kw in ep['url'].lower() for kw in ['login', 'auth', 'signin'])
                    and ep.get('method') == 'POST'
                ]
                
                if login_endpoints:
                    # Try API-based login with discovered endpoint
                    for endpoint in login_endpoints:
                        logger.info(f"Trying discovered API endpoint: {endpoint['url']}")
                        
                        # Try different payload formats
                        payloads = [
                            {'username': username, 'password': password},
                            {'email': username, 'password': password},
                            {'user': username, 'pass': password},
                        ]
                        
                        session_id = f"api_{api_discovery_manager.get_domain(login_url)}_{secrets.token_urlsafe(8)}"
                        session = await auth_session_manager.get_or_create_session(session_id)
                        
                        for payload in payloads:
                            try:
                                async with session.post(
                                    endpoint['url'],
                                    json=payload,
                                    headers={'Content-Type': 'application/json'},
                                    ssl=Config.SSL_VERIFY
                                ) as response:
                                    if response.status == 200:
                                        result_data = await response.json()
                                        
                                        # Save successful format for future use
                                        endpoint['verified_payload'] = payload
                                        api_discovery_manager.save_discovery(login_url, [endpoint])
                                        
                                        return {
                                            'success': True,
                                            'method': 'api_discovery',
                                            'endpoint_used': endpoint['url'],
                                            'session_id': session_id,
                                            'response_data': result_data,
                                            'timestamp': datetime.now().isoformat()
                                        }
                            except:
                                continue
                                
        # Fall back to form-based login if discovery didn't work
        session_id = f"form_{api_discovery_manager.get_domain(login_url)}_{secrets.token_urlsafe(8)}"
        
        # Get or create authenticated session
        session = await auth_session_manager.get_or_create_session(session_id)
        
        # First, get the login page to extract any hidden fields
        headers = prepare_request_headers()
        async with session.get(login_url, headers=headers, ssl=Config.SSL_VERIFY) as response:
            html = await response.text()
        
        # Extract forms
        soup = BeautifulSoup(html, 'lxml')
        forms = extract_form_fields(soup)
        
        if not forms:
            return {
                'success': False,
                'error': 'No forms found on login page',
                'session_id': session_id
            }
        
        # Use the first form found
        form = forms[0]
        
        # Prepare form data
        form_data = {}
        form_data.update(form.get('hidden_fields', {}))
        form_data['username'] = username
        form_data['password'] = password
        
        # Determine form action URL
        action_url = form.get('action', login_url)
        if action_url and not action_url.startswith('http'):
            action_url = urljoin(login_url, action_url)
        
        # Submit login form
        headers = prepare_request_headers({'Referer': login_url})
        
        method = form.get('method', 'POST').upper()
        if method == 'POST':
            async with session.post(action_url, data=form_data, headers=headers, ssl=Config.SSL_VERIFY) as response:
                result_html = await response.text()
                final_url = str(response.url)
        else:
            async with session.get(action_url, params=form_data, headers=headers, ssl=Config.SSL_VERIFY) as response:
                result_html = await response.text()
                final_url = str(response.url)
        
        # Save cookies
        await auth_session_manager.save_cookies(session_id)
        
        # Check for success
        success_indicators = ['logout', 'sign out', 'dashboard', 'welcome', 'profile', username.lower()]
        logged_in = any(indicator in result_html.lower() for indicator in success_indicators)
        
        return {
            'success': True,
            'login_successful': logged_in,
            'session_id': session_id,
            'final_url': final_url,
            'method': 'form_fallback',
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

# ============================================================================
# Main entry point
# ============================================================================

def main():
    """Main entry point for the enhanced MCP server"""
    logger.info("=" * 60)
    logger.info("Starting Enhanced Web Interaction Toolkit MCP Server v0.3.0")
    logger.info("=" * 60)
    logger.info("Configuration (all defaults are secure):")
    logger.info(f"  🔒 SSL Verification: {Config.SSL_VERIFY} (secure default)")
    logger.info(f"  💾 Cache Enabled: {Config.ENABLE_CACHE} (TTL: {Config.CACHE_TTL_SECONDS}s)")
    logger.info(f"  🔌 Max Connections: {Config.MAX_CONNECTIONS} (per host: {Config.MAX_CONNECTIONS_PER_HOST})")
    logger.info(f"  ⏱️ Rate Limit: {Config.RATE_LIMIT_REQUESTS} requests per {Config.RATE_LIMIT_PERIOD}s")
    logger.info(f"  🔄 Max Retries: {Config.MAX_RETRIES} (timeout: {Config.TIMEOUT_SECONDS}s)")
    logger.info("-" * 60)
    logger.info("To override defaults, set environment variables:")
    logger.info("  MCP_SSL_VERIFY=false     (only if absolutely necessary)")
    logger.info("  MCP_ENABLE_CACHE=false   (to disable caching)")
    logger.info("  MCP_CACHE_TTL=600        (cache TTL in seconds)")
    logger.info("  MCP_MAX_CONNECTIONS=200  (connection pool size)")
    logger.info("  MCP_RATE_LIMIT_REQUESTS=100")
    logger.info("=" * 60)
    mcp.run()

if __name__ == "__main__":
    main()