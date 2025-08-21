#!/usr/bin/env python3
"""
Test the integrated MCP server with all circumvention features
"""

import asyncio
import json
from server_integrated import EnhancedWebScraper, ScrapeOptions

async def test_integrated_features():
    """Test all integrated features"""
    scraper = EnhancedWebScraper()
    
    print("=" * 60)
    print("INTEGRATED MCP SERVER TEST")
    print("=" * 60)
    
    # Test 1: Basic scraping with discovery
    print("\n1. Testing webpage scraping with API discovery...")
    result = await scraper.scrape_with_discovery(
        "https://example.com",
        ScrapeOptions(extract_js=True)
    )
    print(f"   - Success: {result.get('success')}")
    print(f"   - Title: {result.get('title')}")
    if result.get('discovery'):
        print(f"   - Endpoints found: {len(result['discovery'].get('endpoints', []))}")
        print(f"   - Auth type: {result['discovery'].get('authentication', {}).get('type')}")
    
    # Test 2: JavaScript extraction
    print("\n2. Testing JavaScript extraction...")
    result = await scraper.scrape_with_discovery(
        "https://www.google.com",
        ScrapeOptions(extract_js=True)
    )
    if result.get('success'):
        js_data = result.get('discovery', {}).get('javascript_data', {})
        print(f"   - JavaScript objects found: {len(js_data)}")
        for key in list(js_data.keys())[:3]:
            print(f"     • {key}")
    
    # Test 3: API discovery persistence
    print("\n3. Testing API discovery persistence...")
    
    # Check if discovery was saved
    discovery = scraper.api_discovery.get_discovery("https://example.com")
    if discovery:
        print(f"   - Cached discovery found for example.com")
        print(f"   - Last updated: {discovery.get('last_updated')}")
        print(f"   - Discovery count: {discovery.get('discovery_count')}")
    
    # Test 4: Authentication detection
    print("\n4. Testing authentication detection...")
    
    # Test with a known login page (GitHub as example)
    result = await scraper.scrape_with_discovery(
        "https://github.com/login",
        ScrapeOptions()
    )
    
    if result.get('success'):
        auth_info = result.get('discovery', {}).get('authentication', {})
        print(f"   - Auth type detected: {auth_info.get('type')}")
        if auth_info.get('details'):
            print(f"   - Form action: {auth_info['details'].get('form_action')}")
            print(f"   - Form fields: {len(auth_info['details'].get('form_fields', {}))}")
    
    # Test 5: Smart login (mock test - won't actually login)
    print("\n5. Testing smart login detection...")
    
    # This is a mock test - it will detect the auth type but won't actually login
    login_result = await scraper.smart_login(
        "https://github.com/login",
        "test@example.com",
        "testpassword",
        use_discovery=True
    )
    
    print(f"   - Auth type used: {login_result.get('auth_type', 'unknown')}")
    print(f"   - Status code: {login_result.get('status_code')}")
    
    # Test 6: Check persistent storage
    print("\n6. Checking persistent storage...")
    
    from pathlib import Path
    storage_dir = Path(".api_discovery")
    if storage_dir.exists():
        json_files = list(storage_dir.glob("*.json"))
        print(f"   - Discovery files created: {len(json_files)}")
        for file in json_files[:3]:
            print(f"     • {file.name}")
            
    # Cleanup
    await scraper.cleanup()
    print("\n✅ All tests completed!")
    
    return True

if __name__ == "__main__":
    asyncio.run(test_integrated_features())