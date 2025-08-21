#!/usr/bin/env python3
"""
Lightweight API Discovery Integration for MCP Server
This integrates with server_enhanced.py without requiring Playwright
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, urljoin
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class LightweightAPIDiscovery:
    """
    Lightweight API discovery that works with existing MCP server
    Analyzes HTML/JS without requiring browser automation
    """
    
    def __init__(self, storage_dir: str = ".api_discovery"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        
    def discover_from_html(self, url: str, html_content: str) -> Dict[str, Any]:
        """
        Discover API endpoints from HTML content
        This can be called after scraping a page
        """
        domain = urlparse(url).netloc.lower().replace('www.', '')
        endpoints = []
        
        # Extract JavaScript endpoints
        js_patterns = [
            # API URLs in strings
            r'["\'](/api/[^"\']+)["\']',
            r'["\'](/auth/[^"\']+)["\']',
            r'["\'](/login[^"\']*)["\']',
            r'["\'](/signin[^"\']*)["\']',
            r'["\'](/session[^"\']*)["\']',
            r'["\'](/token[^"\']*)["\']',
            r'["\']https?://[^"\']*(/api/[^"\']+)["\']',
            
            # Fetch calls
            r'fetch\s*\(\s*["\']([^"\']+)["\']',
            
            # Axios calls
            r'axios\.[a-z]+\s*\(\s*["\']([^"\']+)["\']',
            
            # Form actions
            r'<form[^>]*action=["\'"]([^"\'"]+)["\'""]',
            
            # AJAX URLs
            r'url\s*:\s*["\']([^"\']+)["\']',
            
            # Next.js API routes
            r'_next/data/[^/]+(/[^"\'.]+\.json)',
        ]
        
        for pattern in js_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                endpoint_url = match
                
                # Skip static assets
                if any(ext in endpoint_url for ext in ['.css', '.js', '.jpg', '.png', '.svg', '.ico', '.woff']):
                    continue
                    
                # Normalize URL
                if not endpoint_url.startswith('http'):
                    endpoint_url = urljoin(url, endpoint_url)
                    
                # Determine method based on endpoint
                method = 'POST' if any(kw in endpoint_url.lower() for kw in ['login', 'auth', 'signin', 'create', 'update']) else 'GET'
                
                endpoints.append({
                    'url': endpoint_url,
                    'method': method,
                    'discovered_at': datetime.now().isoformat(),
                    'pattern_matched': pattern[:30] + '...'
                })
                
        # Check for form fields to understand login structure
        form_fields = self._extract_form_fields(html_content)
        
        # Check for common frameworks
        frameworks = self._detect_frameworks(html_content)
        
        # Save discovery
        discovery = {
            'domain': domain,
            'url': url,
            'discovered_at': datetime.now().isoformat(),
            'endpoints': endpoints,
            'form_fields': form_fields,
            'frameworks': frameworks,
            'requires_javascript': self._requires_javascript(html_content)
        }
        
        # Save to file
        file_path = self.storage_dir / f"{domain}.json"
        
        # Merge with existing if file exists
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    existing = json.load(f)
                    # Merge endpoints
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
            
        logger.info(f"Discovered {len(endpoints)} endpoints for {domain}")
        return discovery
        
    def _extract_form_fields(self, html: str) -> Dict[str, Any]:
        """Extract form field information"""
        fields = {
            'inputs': [],
            'has_password_field': False,
            'has_email_field': False,
            'likely_username_field': None,
            'likely_password_field': None
        }
        
        # Find all input fields
        input_pattern = r'<input[^>]*(?:name|id)=["\'"]([^"\'"]+)["\'""][^>]*(?:type=["\'"]([^"\'"]+)["\'""])?'
        matches = re.findall(input_pattern, html, re.IGNORECASE)
        
        for name, input_type in matches:
            fields['inputs'].append({'name': name, 'type': input_type or 'text'})
            
            # Detect field purposes
            name_lower = name.lower()
            if input_type == 'password' or 'password' in name_lower or 'pass' in name_lower:
                fields['has_password_field'] = True
                fields['likely_password_field'] = name
            elif input_type == 'email' or 'email' in name_lower:
                fields['has_email_field'] = True
                fields['likely_username_field'] = name
            elif any(kw in name_lower for kw in ['username', 'user', 'login', 'account']):
                if not fields['likely_username_field']:
                    fields['likely_username_field'] = name
                    
        return fields
        
    def _detect_frameworks(self, html: str) -> List[str]:
        """Detect JavaScript frameworks used"""
        frameworks = []
        
        framework_indicators = {
            'Next.js': ['__NEXT_DATA__', '_next/', 'next.config'],
            'React': ['react.development', 'react.production', 'data-reactroot', 'React.createElement'],
            'Vue': ['vue.js', 'v-if=', 'v-for=', 'v-model='],
            'Angular': ['ng-app', 'ng-controller', 'angular.js'],
            'jQuery': ['jquery.min.js', '$.ajax', '$(document)'],
        }
        
        for framework, indicators in framework_indicators.items():
            if any(indicator in html for indicator in indicators):
                frameworks.append(framework)
                
        return frameworks
        
    def _requires_javascript(self, html: str) -> bool:
        """Check if page requires JavaScript"""
        js_indicators = [
            '<noscript>',
            'JavaScript is required',
            'Enable JavaScript',
            'This site requires JavaScript',
            '__NEXT_DATA__',  # Next.js always needs JS
        ]
        
        return any(indicator.lower() in html.lower() for indicator in js_indicators)
        
    def get_cached_endpoints(self, url: str) -> Optional[Dict[str, Any]]:
        """Get cached discovery for a domain"""
        domain = urlparse(url).netloc.lower().replace('www.', '')
        file_path = self.storage_dir / f"{domain}.json"
        
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    return json.load(f)
            except:
                pass
                
        return None
        
    def suggest_login_endpoint(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Suggest the best login endpoint based on discoveries
        Returns endpoint info with recommended payload structure
        """
        discovery = self.get_cached_endpoints(url)
        if not discovery:
            return None
            
        endpoints = discovery.get('endpoints', [])
        form_fields = discovery.get('form_fields', {})
        
        # Look for login-related endpoints
        login_endpoints = []
        for ep in endpoints:
            url_lower = ep['url'].lower()
            if any(kw in url_lower for kw in ['login', 'signin', 'auth', 'session']):
                if ep['method'] == 'POST':
                    login_endpoints.append(ep)
                    
        if not login_endpoints and endpoints:
            # No obvious login endpoint, but we have form fields
            if form_fields.get('has_password_field'):
                # Likely a form-based login
                return {
                    'type': 'form_submission',
                    'url': url,
                    'method': 'POST',
                    'username_field': form_fields.get('likely_username_field', 'username'),
                    'password_field': form_fields.get('likely_password_field', 'password'),
                    'recommendation': 'Use form submission with discovered fields'
                }
                
        if login_endpoints:
            # Return the most likely endpoint
            best = login_endpoints[0]
            return {
                'type': 'api_endpoint',
                'url': best['url'],
                'method': best['method'],
                'payload_suggestion': {
                    'username': '<username>',
                    'password': '<password>'
                },
                'alternative_fields': [
                    {'email': '<username>', 'password': '<password>'},
                    {'user': '<username>', 'pass': '<password>'},
                ],
                'recommendation': 'Try API endpoint with JSON payload'
            }
            
        return None
        
    def export_discoveries(self) -> Dict[str, Any]:
        """Export all discoveries"""
        discoveries = {}
        
        for json_file in self.storage_dir.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    domain = json_file.stem
                    discoveries[domain] = json.load(f)
            except:
                pass
                
        return discoveries


# Add this function to server_enhanced.py to integrate API discovery
async def discover_and_suggest_login(url: str, html_content: str) -> Dict[str, Any]:
    """
    Discover API endpoints and suggest login approach
    This can be added to server_enhanced.py
    """
    discovery = LightweightAPIDiscovery()
    
    # Discover from HTML
    discovered = discovery.discover_from_html(url, html_content)
    
    # Get suggestion
    suggestion = discovery.suggest_login_endpoint(url)
    
    return {
        'discovered_endpoints': len(discovered.get('endpoints', [])),
        'frameworks_detected': discovered.get('frameworks', []),
        'requires_javascript': discovered.get('requires_javascript', False),
        'login_suggestion': suggestion,
        'discovery_saved': True,
        'cache_file': f".api_discovery/{urlparse(url).netloc.lower().replace('www.', '')}.json"
    }


# Test the lightweight discovery
if __name__ == "__main__":
    import asyncio
    
    # Test with sample HTML
    test_html = '''
    <html>
    <head>
        <script>
            // Next.js app
            window.__NEXT_DATA__ = {};
            
            // Login API
            fetch('/api/auth/login', {
                method: 'POST',
                body: JSON.stringify({email: email, password: password})
            });
            
            // Another endpoint
            axios.post('/api/v2/authenticate', credentials);
        </script>
    </head>
    <body>
        <form action="/login" method="post">
            <input type="email" name="email" id="email">
            <input type="password" name="password" id="password">
            <button type="submit">Login</button>
        </form>
    </body>
    </html>
    '''
    
    async def test():
        result = await discover_and_suggest_login(
            'https://example.com/login',
            test_html
        )
        print(json.dumps(result, indent=2))
        
        # Check discovery
        discovery = LightweightAPIDiscovery()
        cached = discovery.get_cached_endpoints('https://example.com')
        if cached:
            print("\nCached discovery:")
            print(json.dumps(cached, indent=2))
            
    asyncio.run(test())