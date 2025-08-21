#!/usr/bin/env python3
"""
Enhanced API Discovery with Persistent Storage
Saves discovered API endpoints to domain-specific JSON files
"""

import asyncio
import json
import re
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse, urljoin
from datetime import datetime, timedelta
import logging
import hashlib

logger = logging.getLogger(__name__)

class PersistentAPIDiscovery:
    """
    Discovers API endpoints and saves them to domain-specific JSON files
    Creates files like: .api_discovery/clickbank.com.json
    """
    
    def __init__(self, storage_dir: str = ".api_discovery"):
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
                    logger.info(f"Loaded API discovery for {domain}: {len(self.discovered_apis[domain].get('endpoints', []))} endpoints")
            except Exception as e:
                logger.error(f"Failed to load {json_file}: {e}")
                
    def get_domain_from_url(self, url: str) -> str:
        """Extract domain from URL for consistent naming"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www. prefix for consistency
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
        
    def get_discovery_file(self, url: str) -> Path:
        """Get the JSON file path for a given URL's domain"""
        domain = self.get_domain_from_url(url)
        return self.storage_dir / f"{domain}.json"
        
    def save_discovery(self, url: str, discovery_data: Dict[str, Any]):
        """Save discovery data for a domain"""
        domain = self.get_domain_from_url(url)
        file_path = self.get_discovery_file(url)
        
        # Merge with existing data if file exists
        existing_data = {}
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    existing_data = json.load(f)
            except:
                pass
                
        # Merge endpoints, avoiding duplicates
        existing_endpoints = {ep['url']: ep for ep in existing_data.get('endpoints', [])}
        new_endpoints = {ep['url']: ep for ep in discovery_data.get('endpoints', [])}
        existing_endpoints.update(new_endpoints)
        
        # Prepare final data
        final_data = {
            'domain': domain,
            'last_updated': datetime.now().isoformat(),
            'discovery_count': existing_data.get('discovery_count', 0) + 1,
            'endpoints': list(existing_endpoints.values()),
            'authentication': discovery_data.get('authentication', existing_data.get('authentication', {})),
            'metadata': {
                'total_endpoints': len(existing_endpoints),
                'auth_endpoints': len([ep for ep in existing_endpoints.values() 
                                      if any(kw in ep['url'].lower() for kw in ['auth', 'login', 'token'])]),
                'methods': list(set(ep.get('method', 'GET') for ep in existing_endpoints.values())),
                'has_working_login': discovery_data.get('has_working_login', 
                                                       existing_data.get('metadata', {}).get('has_working_login', False))
            }
        }
        
        # Save to file
        with open(file_path, 'w') as f:
            json.dump(final_data, f, indent=2)
            
        # Update in-memory cache
        self.discovered_apis[domain] = final_data
        
        logger.info(f"Saved API discovery for {domain}: {len(final_data['endpoints'])} total endpoints")
        
    def get_cached_discovery(self, url: str) -> Optional[Dict[str, Any]]:
        """Get cached discovery data for a domain"""
        domain = self.get_domain_from_url(url)
        
        # Check in-memory cache first
        if domain in self.discovered_apis:
            return self.discovered_apis[domain]
            
        # Try to load from file
        file_path = self.get_discovery_file(url)
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    self.discovered_apis[domain] = data
                    return data
            except:
                pass
                
        return None
        
    def analyze_and_store(self, url: str, html_content: str, 
                         intercepted_requests: List[Dict] = None,
                         successful_login: Dict = None) -> Dict[str, Any]:
        """
        Analyze page content and network requests, then store discoveries
        """
        domain = self.get_domain_from_url(url)
        endpoints = []
        
        # Extract from HTML/JavaScript
        js_endpoints = self._extract_from_javascript(html_content, url)
        endpoints.extend(js_endpoints)
        
        # Add intercepted requests if provided
        if intercepted_requests:
            for req in intercepted_requests:
                endpoints.append({
                    'url': req['url'],
                    'method': req.get('method', 'GET'),
                    'source': 'network_intercept',
                    'headers_hint': self._analyze_headers(req.get('headers', {})),
                    'payload_structure': self._analyze_payload(req.get('post_data')),
                    'timestamp': req.get('timestamp', datetime.now().isoformat())
                })
                
        # If we have a successful login, mark the endpoint
        if successful_login:
            login_endpoint = successful_login.get('endpoint')
            if login_endpoint:
                for ep in endpoints:
                    if ep['url'] == login_endpoint:
                        ep['verified_working'] = True
                        ep['required_fields'] = successful_login.get('required_fields', [])
                        ep['authentication_type'] = successful_login.get('auth_type', 'unknown')
                        
        discovery_data = {
            'endpoints': endpoints,
            'authentication': {
                'login_url': url,
                'discovered_at': datetime.now().isoformat(),
                'requires_javascript': self._check_requires_javascript(html_content),
                'form_based': self._check_has_form(html_content),
                'api_based': len([ep for ep in endpoints if 'api' in ep['url'].lower()]) > 0,
                'successful_login': successful_login is not None
            },
            'has_working_login': successful_login is not None
        }
        
        self.save_discovery(url, discovery_data)
        return discovery_data
        
    def _extract_from_javascript(self, content: str, base_url: str) -> List[Dict[str, Any]]:
        """Extract API endpoints from JavaScript code"""
        endpoints = []
        
        # Patterns to find API endpoints
        patterns = [
            # Fetch API
            (r'fetch\s*\(\s*["\']([^"\']+)["\']', 'fetch'),
            # Axios
            (r'axios\.\w+\s*\(\s*["\']([^"\']+)["\']', 'axios'),
            # jQuery AJAX
            (r'\$\.ajax\s*\(\s*\{[^}]*url\s*:\s*["\']([^"\']+)["\']', 'jquery'),
            # XMLHttpRequest
            (r'\.open\s*\(\s*["\'](\w+)["\'],\s*["\']([^"\']+)["\']', 'xhr'),
            # API route definitions
            (r'["\'](/api/[^"\']+)["\']', 'api_route'),
            (r'["\'](/auth/[^"\']+)["\']', 'auth_route'),
            (r'["\'](/login[^"\']*)["\']', 'login_route'),
            (r'["\'](/signin[^"\']*)["\']', 'signin_route'),
            (r'["\'](/session[^"\']*)["\']', 'session_route'),
            (r'["\'](/token[^"\']*)["\']', 'token_route'),
        ]
        
        for pattern, source_type in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if isinstance(match, tuple):
                    # For patterns that capture method and URL
                    if len(match) == 2:
                        method, endpoint_url = match
                        method = method.upper()
                    else:
                        endpoint_url = match[0]
                        method = 'POST' if any(kw in endpoint_url.lower() for kw in ['login', 'auth', 'token']) else 'GET'
                else:
                    endpoint_url = match
                    method = 'POST' if any(kw in endpoint_url.lower() for kw in ['login', 'auth', 'token']) else 'GET'
                
                # Normalize URL
                if not endpoint_url.startswith('http'):
                    endpoint_url = urljoin(base_url, endpoint_url)
                    
                # Skip non-API URLs
                if any(ext in endpoint_url for ext in ['.css', '.js', '.jpg', '.png', '.gif', '.svg', '.ico']):
                    continue
                    
                endpoints.append({
                    'url': endpoint_url,
                    'method': method,
                    'source': source_type,
                    'discovered_from': 'javascript_analysis',
                    'confidence': 'high' if source_type in ['fetch', 'axios', 'jquery'] else 'medium'
                })
                
        # Deduplicate by URL
        seen_urls = set()
        unique_endpoints = []
        for ep in endpoints:
            if ep['url'] not in seen_urls:
                seen_urls.add(ep['url'])
                unique_endpoints.append(ep)
                
        return unique_endpoints
        
    def _analyze_headers(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """Analyze headers to understand authentication requirements"""
        analysis = {
            'has_auth': False,
            'auth_type': None,
            'content_type': headers.get('Content-Type', ''),
            'custom_headers': []
        }
        
        for header, value in headers.items():
            header_lower = header.lower()
            if 'authorization' in header_lower:
                analysis['has_auth'] = True
                if 'bearer' in value.lower():
                    analysis['auth_type'] = 'bearer'
                elif 'basic' in value.lower():
                    analysis['auth_type'] = 'basic'
                else:
                    analysis['auth_type'] = 'custom'
                    
            elif header_lower.startswith('x-'):
                analysis['custom_headers'].append(header)
                
        return analysis
        
    def _analyze_payload(self, payload_data: Any) -> Dict[str, Any]:
        """Analyze payload structure"""
        if not payload_data:
            return {'type': 'none'}
            
        if isinstance(payload_data, str):
            try:
                payload_data = json.loads(payload_data)
            except:
                return {'type': 'raw_string', 'length': len(payload_data)}
                
        if isinstance(payload_data, dict):
            return {
                'type': 'json',
                'fields': list(payload_data.keys()),
                'has_credentials': any(field in payload_data for field in ['username', 'password', 'email', 'pass']),
                'field_count': len(payload_data)
            }
            
        return {'type': 'unknown'}
        
    def _check_requires_javascript(self, html_content: str) -> bool:
        """Check if page requires JavaScript"""
        indicators = [
            'noscript',
            'enable javascript',
            'javascript is required',
            'js-enabled',
            '__NEXT_DATA__',  # Next.js
            'window.React',    # React
            'ng-app',          # Angular
            'v-app',           # Vue
        ]
        
        html_lower = html_content.lower()
        return any(indicator.lower() in html_lower for indicator in indicators)
        
    def _check_has_form(self, html_content: str) -> bool:
        """Check if page has a traditional form"""
        return '<form' in html_content.lower()
        
    def get_best_login_endpoint(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get the best login endpoint for a domain based on discoveries
        """
        discovery = self.get_cached_discovery(url)
        if not discovery:
            return None
            
        endpoints = discovery.get('endpoints', [])
        
        # First, look for verified working endpoints
        for ep in endpoints:
            if ep.get('verified_working'):
                return ep
                
        # Then, look for high-confidence login endpoints
        login_keywords = ['login', 'signin', 'auth', 'authenticate', 'session']
        for ep in endpoints:
            if any(kw in ep['url'].lower() for kw in login_keywords):
                if ep.get('method') == 'POST' and ep.get('confidence') == 'high':
                    return ep
                    
        # Finally, return any login-related endpoint
        for ep in endpoints:
            if any(kw in ep['url'].lower() for kw in login_keywords):
                return ep
                
        return None
        
    def export_all_discoveries(self) -> Dict[str, Any]:
        """Export all discoveries as a single JSON structure"""
        all_discoveries = {}
        
        for json_file in self.storage_dir.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    domain = json_file.stem
                    all_discoveries[domain] = json.load(f)
            except:
                pass
                
        return all_discoveries
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about discovered APIs"""
        stats = {
            'total_domains': 0,
            'total_endpoints': 0,
            'domains_with_working_login': 0,
            'api_based_sites': 0,
            'form_based_sites': 0,
            'domains': []
        }
        
        for domain, data in self.discovered_apis.items():
            stats['total_domains'] += 1
            stats['total_endpoints'] += len(data.get('endpoints', []))
            
            if data.get('metadata', {}).get('has_working_login'):
                stats['domains_with_working_login'] += 1
                
            auth_info = data.get('authentication', {})
            if auth_info.get('api_based'):
                stats['api_based_sites'] += 1
            if auth_info.get('form_based'):
                stats['form_based_sites'] += 1
                
            stats['domains'].append({
                'domain': domain,
                'endpoints': len(data.get('endpoints', [])),
                'last_updated': data.get('last_updated'),
                'has_working_login': data.get('metadata', {}).get('has_working_login', False)
            })
            
        return stats


# Integration with MCP Server
class MCPAPIDiscoveryExtension:
    """Extension for MCP server to add API discovery capabilities"""
    
    def __init__(self):
        self.discovery = PersistentAPIDiscovery()
        
    async def discover_and_login(
        self,
        login_url: str,
        username: str,
        password: str,
        use_cached: bool = True
    ) -> Dict[str, Any]:
        """
        Discover API endpoints and attempt login
        Uses cached discoveries if available
        """
        
        # Check for cached discovery
        if use_cached:
            cached = self.discovery.get_cached_discovery(login_url)
            if cached:
                best_endpoint = self.discovery.get_best_login_endpoint(login_url)
                if best_endpoint:
                    logger.info(f"Using cached endpoint: {best_endpoint['url']}")
                    # Attempt login with cached endpoint
                    result = await self._try_endpoint_login(
                        best_endpoint,
                        username,
                        password
                    )
                    if result.get('success'):
                        return result
                        
        # If no cache or cached login failed, discover new endpoints
        # This would integrate with the browser automation from api_discovery.py
        # For now, return a placeholder
        return {
            'success': False,
            'message': 'Full discovery would be implemented here',
            'cached_data': self.discovery.get_cached_discovery(login_url)
        }
        
    async def _try_endpoint_login(
        self,
        endpoint: Dict[str, Any],
        username: str,
        password: str
    ) -> Dict[str, Any]:
        """Try to login using a specific endpoint"""
        import aiohttp
        
        # Prepare payload based on endpoint hints
        payload = {
            'username': username,
            'password': password
        }
        
        # Adjust field names based on discovery
        if endpoint.get('required_fields'):
            # Map to discovered field names
            field_mapping = {
                'email': username,
                'user': username,
                'login': username,
                'pass': password,
                'pwd': password
            }
            payload = {}
            for field in endpoint['required_fields']:
                if field in field_mapping:
                    payload[field] = field_mapping[field]
                elif field == 'username':
                    payload[field] = username
                elif field == 'password':
                    payload[field] = password
                    
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint['url'],
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Update discovery with successful login
                        self.discovery.save_discovery(
                            endpoint['url'],
                            {
                                'endpoints': [{
                                    **endpoint,
                                    'verified_working': True,
                                    'last_successful_login': datetime.now().isoformat()
                                }],
                                'has_working_login': True
                            }
                        )
                        
                        return {
                            'success': True,
                            'endpoint': endpoint['url'],
                            'response': data
                        }
        except Exception as e:
            logger.error(f"Login failed for {endpoint['url']}: {e}")
            
        return {'success': False, 'endpoint': endpoint['url']}


# Example usage and testing
def print_discovery_stats():
    """Print statistics about discovered APIs"""
    discovery = PersistentAPIDiscovery()
    stats = discovery.get_statistics()
    
    print("\n" + "="*60)
    print("API Discovery Statistics")
    print("="*60)
    print(f"Total Domains: {stats['total_domains']}")
    print(f"Total Endpoints: {stats['total_endpoints']}")
    print(f"Sites with Working Login: {stats['domains_with_working_login']}")
    print(f"API-based Sites: {stats['api_based_sites']}")
    print(f"Form-based Sites: {stats['form_based_sites']}")
    
    if stats['domains']:
        print("\nDiscovered Domains:")
        for domain_info in stats['domains']:
            status = "✓" if domain_info['has_working_login'] else "○"
            print(f"  {status} {domain_info['domain']}: {domain_info['endpoints']} endpoints")
    print("="*60)


if __name__ == "__main__":
    # Test the discovery system
    discovery = PersistentAPIDiscovery()
    
    # Simulate discovering endpoints for ClickBank
    test_html = '''
    <script>
        fetch('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({username: user, password: pass})
        });
        
        axios.post('/api/v1/authenticate', credentials);
        
        $.ajax({
            url: '/api/session/create',
            method: 'POST'
        });
    </script>
    '''
    
    result = discovery.analyze_and_store(
        'https://accounts.clickbank.com/login.htm',
        test_html,
        intercepted_requests=[
            {
                'url': 'https://accounts.clickbank.com/api/auth/login',
                'method': 'POST',
                'headers': {'Content-Type': 'application/json'},
                'post_data': '{"username":"test","password":"test"}'
            }
        ]
    )
    
    print("Discovery saved!")
    print(json.dumps(result, indent=2))
    
    # Print statistics
    print_discovery_stats()
    
    # Show best endpoint
    best = discovery.get_best_login_endpoint('https://accounts.clickbank.com/login.htm')
    if best:
        print(f"\nBest login endpoint: {best['url']}")