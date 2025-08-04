#!/usr/bin/env python3
"""
Web Interaction Toolkit MCP Server
A modern MCP server for web scraping and API interaction with human behavior simulation
"""

import asyncio
import json
import random
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup
from fastmcp import FastMCP
from pydantic import BaseModel, Field, HttpUrl

# Initialize MCP server
mcp = FastMCP("web-interaction-toolkit")

# Global API connections storage
api_connections: Dict[str, Dict[str, Any]] = {}


class ScrapeOptions(BaseModel):
    """Options for web scraping"""
    simulate_human: bool = Field(default=True, description="Simulate human-like behavior")
    max_content_length: int = Field(default=5000, description="Maximum content length to return")
    max_links: int = Field(default=50, description="Maximum number of links to extract")
    max_images: int = Field(default=20, description="Maximum number of images to extract")
    min_delay: float = Field(default=0.5, description="Minimum delay between requests (seconds)")
    max_delay: float = Field(default=2.0, description="Maximum delay between requests (seconds)")


class APIConnectionConfig(BaseModel):
    """Configuration for API connection"""
    name: str = Field(description="Name for this API connection")
    base_url: HttpUrl = Field(description="Base URL for the API")
    default_headers: Dict[str, str] = Field(default_factory=dict, description="Default headers for all requests")


class APIMethodConfig(BaseModel):
    """Configuration for API method"""
    connection_name: str = Field(description="Name of the API connection")
    method_name: str = Field(description="Name for this method")
    http_method: str = Field(pattern="^(GET|POST)$", description="HTTP method (GET or POST)")
    endpoint: str = Field(description="API endpoint (relative to base URL)")
    headers: Dict[str, str] = Field(default_factory=dict, description="Headers for this specific method")
    params: Dict[str, Any] = Field(default_factory=dict, description="Query parameters")
    body: Dict[str, Any] = Field(default_factory=dict, description="Request body (for POST requests)")


def get_random_user_agent() -> str:
    """Generate a random user agent to simulate different browsers"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
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
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': get_random_user_agent()
    }
    
    # Add referer for some requests to appear more natural
    if random.choice([True, False]):
        headers['Referer'] = 'https://www.google.com/'
    
    # Add custom headers if provided
    if custom_headers:
        headers.update(custom_headers)
        
    return headers


@mcp.tool()
async def scrape_webpage(
    url: str,
    options: Optional[ScrapeOptions] = None
) -> Dict[str, Any]:
    """
    Scrape a webpage and extract content while simulating human behavior
    
    Args:
        url: The URL to scrape
        options: Scraping options including human simulation settings
        
    Returns:
        Dictionary containing page content, links, images, and metadata
    """
    if options is None:
        options = ScrapeOptions()
    
    try:
        if options.simulate_human:
            await simulate_human_delay(options.min_delay, options.max_delay)
            headers = prepare_request_headers()
        else:
            headers = {'User-Agent': get_random_user_agent()}
        
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers, ssl=False) as response:
                response.raise_for_status()
                content = await response.text()
                
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
                
                # Extract links
                links = []
                for link in soup.find_all('a', href=True):
                    absolute_url = urljoin(url, link['href'])
                    links.append({
                        'text': link.get_text().strip(),
                        'url': absolute_url
                    })
                
                # Extract images
                images = []
                for img in soup.find_all('img', src=True):
                    absolute_url = urljoin(url, img['src'])
                    images.append({
                        'alt': img.get('alt', ''),
                        'url': absolute_url
                    })
                
                return {
                    "success": True,
                    "url": url,
                    "title": title,
                    "content": text[:options.max_content_length],
                    "links": links[:options.max_links],
                    "images": images[:options.max_images],
                    "status_code": response.status
                }
                
    except Exception as e:
        return {
            "success": False,
            "url": url,
            "error": str(e),
            "content": ""
        }


@mcp.tool()
async def create_api_connection(
    config: APIConnectionConfig
) -> str:
    """
    Create a new API connection configuration
    
    Args:
        config: API connection configuration
        
    Returns:
        Success message
    """
    api_connections[config.name] = {
        "base_url": str(config.base_url).rstrip('/'),
        "default_headers": config.default_headers,
        "methods": {}
    }
    
    return f"API connection '{config.name}' created successfully with base URL: {config.base_url}"


@mcp.tool()
async def add_api_method(
    config: APIMethodConfig
) -> str:
    """
    Add a method to an existing API connection
    
    Args:
        config: API method configuration
        
    Returns:
        Success message or error
    """
    if config.connection_name not in api_connections:
        return f"API connection '{config.connection_name}' not found"
    
    api_connections[config.connection_name]["methods"][config.method_name] = {
        "method": config.http_method,
        "endpoint": config.endpoint,
        "headers": config.headers,
        "params": config.params,
        "body": config.body
    }
    
    return f"Method '{config.method_name}' added to API connection '{config.connection_name}'"


@mcp.tool()
async def execute_api_call(
    connection_name: str,
    method_name: str,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
    simulate_human: bool = True
) -> Dict[str, Any]:
    """
    Execute an API call using a configured connection and method
    
    Args:
        connection_name: Name of the API connection
        method_name: Name of the method to execute
        params: Override parameters for this call
        body: Override body for this call
        simulate_human: Whether to simulate human-like behavior
        
    Returns:
        API response data
    """
    if connection_name not in api_connections:
        return {"success": False, "error": f"API connection '{connection_name}' not found"}
    
    connection = api_connections[connection_name]
    if method_name not in connection["methods"]:
        return {"success": False, "error": f"Method '{method_name}' not found in connection '{connection_name}'"}
    
    method = connection["methods"][method_name]
    
    # Simulate human delay if requested
    if simulate_human:
        await simulate_human_delay(0.5, 1.5)
    
    try:
        # Prepare headers
        headers = connection["default_headers"].copy()
        headers.update(method["headers"])
        headers.update(prepare_request_headers())
        
        # Prepare URL
        url = connection["base_url"] + method["endpoint"]
        
        # Prepare parameters and body
        request_params = method["params"].copy()
        if params:
            request_params.update(params)
        
        request_body = method["body"].copy()
        if body:
            request_body.update(body)
        
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            if method["method"] == "GET":
                async with session.get(
                    url,
                    headers=headers,
                    params=request_params,
                    ssl=False
                ) as response:
                    response.raise_for_status()
                    try:
                        response_data = await response.json()
                    except:
                        response_data = {"content": await response.text()}
                    
                    return {
                        "success": True,
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "data": response_data
                    }
            
            elif method["method"] == "POST":
                async with session.post(
                    url,
                    headers=headers,
                    params=request_params,
                    json=request_body,
                    ssl=False
                ) as response:
                    response.raise_for_status()
                    try:
                        response_data = await response.json()
                    except:
                        response_data = {"content": await response.text()}
                    
                    return {
                        "success": True,
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "data": response_data
                    }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    
    # Default return for unsupported methods
    return {
        "success": False,
        "error": f"Unsupported HTTP method: {method.get('method', 'unknown')}"
    }


@mcp.tool()
async def list_api_connections() -> List[str]:
    """
    List all configured API connections
    
    Returns:
        List of connection names
    """
    return list(api_connections.keys())


@mcp.tool()
async def get_api_connection_details(
    connection_name: str
) -> Dict[str, Any]:
    """
    Get details of a specific API connection
    
    Args:
        connection_name: Name of the API connection
        
    Returns:
        Connection details or error
    """
    if connection_name not in api_connections:
        return {"error": f"API connection '{connection_name}' not found"}
    
    connection = api_connections[connection_name]
    return {
        "name": connection_name,
        "base_url": connection["base_url"],
        "default_headers": connection["default_headers"],
        "methods": list(connection["methods"].keys())
    }


@mcp.resource("api://connections")
async def list_connections_resource() -> str:
    """List all API connections as a resource"""
    connections = []
    for name, details in api_connections.items():
        connections.append({
            "name": name,
            "base_url": details["base_url"],
            "methods_count": len(details["methods"])
        })
    return json.dumps(connections, indent=2)


@mcp.resource("api://connections/{name}")
async def get_connection_resource(name: str) -> str:
    """Get detailed information about a specific API connection"""
    if name not in api_connections:
        return json.dumps({"error": f"Connection '{name}' not found"})
    
    connection = api_connections[name]
    return json.dumps({
        "name": name,
        "base_url": connection["base_url"],
        "default_headers": connection["default_headers"],
        "methods": connection["methods"]
    }, indent=2)


def main():
    """Main entry point for the MCP server"""
    mcp.run()


# Run the server
if __name__ == "__main__":
    main()