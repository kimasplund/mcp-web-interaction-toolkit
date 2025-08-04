#!/usr/bin/env python3
"""
Tests for Web Interaction Toolkit MCP Server
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from server import (
    scrape_webpage,
    create_api_connection,
    add_api_method,
    execute_api_call,
    list_api_connections,
    get_api_connection_details,
    get_random_user_agent,
    simulate_human_delay,
    prepare_request_headers,
    ScrapeOptions,
    APIConnectionConfig,
    APIMethodConfig,
    api_connections
)


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_get_random_user_agent(self):
        """Test that get_random_user_agent returns a valid user agent"""
        ua = get_random_user_agent()
        assert isinstance(ua, str)
        assert len(ua) > 0
        assert "Mozilla" in ua
    
    @pytest.mark.asyncio
    async def test_simulate_human_delay(self):
        """Test that simulate_human_delay waits for appropriate time"""
        import time
        start = time.time()
        await simulate_human_delay(0.1, 0.2)
        end = time.time()
        duration = end - start
        assert 0.1 <= duration <= 0.3  # Allow some tolerance
    
    def test_prepare_request_headers(self):
        """Test that prepare_request_headers returns proper headers"""
        headers = prepare_request_headers()
        assert isinstance(headers, dict)
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        
        # Test with custom headers
        custom = {"X-Custom": "value"}
        headers = prepare_request_headers(custom)
        assert "X-Custom" in headers
        assert headers["X-Custom"] == "value"


class TestWebScraping:
    """Test web scraping functionality"""
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_scrape_webpage_success(self, mock_session):
        """Test successful webpage scraping"""
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="""
            <html>
                <head><title>Test Page</title></head>
                <body>
                    <p>Test content</p>
                    <a href="/link1">Link 1</a>
                    <img src="/image1.jpg" alt="Image 1">
                </body>
            </html>
        """)
        mock_response.raise_for_status = MagicMock()
        
        # Configure mock session
        mock_session_instance = AsyncMock()
        mock_session_instance.get = AsyncMock(return_value=mock_response)
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock()
        mock_session.return_value = mock_session_instance
        
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()
        
        # Test scraping
        result = await scrape_webpage("https://example.com")
        
        assert result["success"] is True
        assert result["url"] == "https://example.com"
        assert result["title"] == "Test Page"
        assert "Test content" in result["content"]
        assert len(result["links"]) == 1
        assert len(result["images"]) == 1
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_scrape_webpage_with_options(self, mock_session):
        """Test webpage scraping with custom options"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html><body>Content</body></html>")
        mock_response.raise_for_status = MagicMock()
        
        mock_session_instance = AsyncMock()
        mock_session_instance.get = AsyncMock(return_value=mock_response)
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock()
        mock_session.return_value = mock_session_instance
        
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()
        
        options = ScrapeOptions(
            simulate_human=False,
            max_content_length=100
        )
        
        result = await scrape_webpage("https://example.com", options)
        assert result["success"] is True
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_scrape_webpage_error(self, mock_session):
        """Test webpage scraping error handling"""
        mock_session_instance = AsyncMock()
        mock_session_instance.get = AsyncMock(side_effect=Exception("Network error"))
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock()
        mock_session.return_value = mock_session_instance
        
        result = await scrape_webpage("https://example.com")
        
        assert result["success"] is False
        assert "Network error" in result["error"]


class TestAPIConnections:
    """Test API connection management"""
    
    def setup_method(self):
        """Clear api_connections before each test"""
        api_connections.clear()
    
    @pytest.mark.asyncio
    async def test_create_api_connection(self):
        """Test creating an API connection"""
        config = APIConnectionConfig(
            name="test_api",
            base_url="https://api.test.com",
            default_headers={"Authorization": "Bearer token"}
        )
        
        result = await create_api_connection(config)
        
        assert "test_api" in api_connections
        assert api_connections["test_api"]["base_url"] == "https://api.test.com"
        assert api_connections["test_api"]["default_headers"]["Authorization"] == "Bearer token"
        assert "created successfully" in result
    
    @pytest.mark.asyncio
    async def test_add_api_method(self):
        """Test adding a method to an API connection"""
        # First create a connection
        config = APIConnectionConfig(
            name="test_api",
            base_url="https://api.test.com"
        )
        await create_api_connection(config)
        
        # Add a method
        method_config = APIMethodConfig(
            connection_name="test_api",
            method_name="get_data",
            http_method="GET",
            endpoint="/data",
            params={"limit": 10}
        )
        
        result = await add_api_method(method_config)
        
        assert "get_data" in api_connections["test_api"]["methods"]
        assert api_connections["test_api"]["methods"]["get_data"]["method"] == "GET"
        assert "added to API connection" in result
    
    @pytest.mark.asyncio
    async def test_add_api_method_nonexistent_connection(self):
        """Test adding a method to a non-existent connection"""
        method_config = APIMethodConfig(
            connection_name="nonexistent",
            method_name="test",
            http_method="GET",
            endpoint="/test"
        )
        
        result = await add_api_method(method_config)
        assert "not found" in result
    
    @pytest.mark.asyncio
    async def test_list_api_connections(self):
        """Test listing API connections"""
        # Create some connections
        await create_api_connection(APIConnectionConfig(
            name="api1",
            base_url="https://api1.com"
        ))
        await create_api_connection(APIConnectionConfig(
            name="api2",
            base_url="https://api2.com"
        ))
        
        connections = await list_api_connections()
        
        assert isinstance(connections, list)
        assert len(connections) == 2
        assert "api1" in connections
        assert "api2" in connections
    
    @pytest.mark.asyncio
    async def test_get_api_connection_details(self):
        """Test getting API connection details"""
        # Create a connection with a method
        await create_api_connection(APIConnectionConfig(
            name="test_api",
            base_url="https://api.test.com"
        ))
        await add_api_method(APIMethodConfig(
            connection_name="test_api",
            method_name="test_method",
            http_method="GET",
            endpoint="/test"
        ))
        
        details = await get_api_connection_details("test_api")
        
        assert details["name"] == "test_api"
        assert details["base_url"] == "https://api.test.com"
        assert "test_method" in details["methods"]
    
    @pytest.mark.asyncio
    async def test_get_api_connection_details_nonexistent(self):
        """Test getting details of non-existent connection"""
        details = await get_api_connection_details("nonexistent")
        assert "error" in details
        assert "not found" in details["error"]


class TestAPIExecution:
    """Test API call execution"""
    
    def setup_method(self):
        """Clear api_connections before each test"""
        api_connections.clear()
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_execute_api_call_get(self, mock_session):
        """Test executing a GET API call"""
        # Setup connection and method
        await create_api_connection(APIConnectionConfig(
            name="test_api",
            base_url="https://api.test.com"
        ))
        await add_api_method(APIMethodConfig(
            connection_name="test_api",
            method_name="get_data",
            http_method="GET",
            endpoint="/data"
        ))
        
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value={"result": "success"})
        mock_response.raise_for_status = MagicMock()
        
        mock_session_instance = AsyncMock()
        mock_session_instance.get = AsyncMock(return_value=mock_response)
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock()
        mock_session.return_value = mock_session_instance
        
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()
        
        # Execute call
        result = await execute_api_call(
            connection_name="test_api",
            method_name="get_data",
            simulate_human=False
        )
        
        assert result["success"] is True
        assert result["status_code"] == 200
        assert result["data"]["result"] == "success"
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession')
    async def test_execute_api_call_post(self, mock_session):
        """Test executing a POST API call"""
        # Setup connection and method
        await create_api_connection(APIConnectionConfig(
            name="test_api",
            base_url="https://api.test.com"
        ))
        await add_api_method(APIMethodConfig(
            connection_name="test_api",
            method_name="create_data",
            http_method="POST",
            endpoint="/data",
            body={"default": "value"}
        ))
        
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value={"id": 123})
        mock_response.raise_for_status = MagicMock()
        
        mock_session_instance = AsyncMock()
        mock_session_instance.post = AsyncMock(return_value=mock_response)
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock()
        mock_session.return_value = mock_session_instance
        
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()
        
        # Execute call with override body
        result = await execute_api_call(
            connection_name="test_api",
            method_name="create_data",
            body={"name": "test"},
            simulate_human=False
        )
        
        assert result["success"] is True
        assert result["status_code"] == 201
        assert result["data"]["id"] == 123
    
    @pytest.mark.asyncio
    async def test_execute_api_call_nonexistent_connection(self):
        """Test executing call with non-existent connection"""
        result = await execute_api_call(
            connection_name="nonexistent",
            method_name="test"
        )
        
        assert result["success"] is False
        assert "not found" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_api_call_nonexistent_method(self):
        """Test executing call with non-existent method"""
        await create_api_connection(APIConnectionConfig(
            name="test_api",
            base_url="https://api.test.com"
        ))
        
        result = await execute_api_call(
            connection_name="test_api",
            method_name="nonexistent"
        )
        
        assert result["success"] is False
        assert "not found" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])