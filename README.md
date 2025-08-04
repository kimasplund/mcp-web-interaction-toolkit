# Web Interaction Toolkit MCP Server

A modern MCP (Model Context Protocol) server for web scraping and API interaction with human behavior simulation to avoid bot detection.

## Features

- 🌐 **Web Scraping with Human Simulation**: Scrape webpages while simulating human-like behavior (delays, user agents, headers)
- 🔌 **API Connection Management**: Create and manage multiple API connections with custom methods
- 🔄 **Session Management**: Maintains session state across requests
- 📊 **Resource Exposure**: Access API connections as MCP resources
- ⚡ **Async Support**: Built with async/await for efficient concurrent operations
- 🛡️ **Anti-Bot Detection**: Rotating user agents, realistic headers, and configurable delays

## Requirements

- Python 3.8+
- pip

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/kimasplund/mcp-web-interaction-toolkit.git
cd mcp-web-interaction-toolkit

# Create and activate virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .

# Or install normally
pip install .
```

### Dependencies

The package uses modern Python libraries:
- `fastmcp>=2.11.0` - FastMCP framework for MCP servers
- `aiohttp>=3.12.15` - Async HTTP client/server
- `beautifulsoup4>=4.13.4` - HTML/XML parsing
- `lxml>=6.0.0` - XML/HTML processing
- `pydantic>=2.11.7` - Data validation

## Usage

### Running the Server

```bash
# After installation, run using the command:
mcp-web-interaction-toolkit

# Or run directly with Python:
python server.py

# Or if using virtual environment:
.venv/bin/mcp-web-interaction-toolkit
```

### MCP Client Configuration

Add to your MCP client's configuration file:

```json
{
  "mcpServers": {
    "web-interaction-toolkit": {
      "command": "mcp-web-interaction-toolkit"
    }
  }
}
```

Or if not installed globally:

```json
{
  "mcpServers": {
    "web-interaction-toolkit": {
      "command": "python",
      "args": ["/path/to/server.py"]
    }
  }
}
```

## Quick Example

Here's a simple example of scraping a webpage:

```python
# Using the MCP tool
result = await scrape_webpage(
    url="https://example.com",
    options={
        "simulate_human": True,
        "max_content_length": 10000
    }
)

# Result includes:
# - title: Page title
# - content: Cleaned text content
# - links: List of links found
# - images: List of images found
# - status_code: HTTP status code
```

## Available Tools

### 1. `scrape_webpage`
Scrape a webpage and extract content while simulating human behavior.

**Parameters:**
- `url` (string, required): The URL to scrape
- `options` (object, optional):
  - `simulate_human` (boolean): Simulate human-like behavior (default: true)
  - `max_content_length` (integer): Maximum content length to return (default: 5000)
  - `max_links` (integer): Maximum number of links to extract (default: 50)
  - `max_images` (integer): Maximum number of images to extract (default: 20)
  - `min_delay` (float): Minimum delay between requests in seconds (default: 0.5)
  - `max_delay` (float): Maximum delay between requests in seconds (default: 2.0)

**Example:**
```json
{
  "tool": "scrape_webpage",
  "arguments": {
    "url": "https://example.com",
    "options": {
      "simulate_human": true,
      "max_content_length": 10000
    }
  }
}
```

#### 2. `create_api_connection`
Create a new API connection configuration.

**Parameters:**
- `config` (object, required):
  - `name` (string): Name for this API connection
  - `base_url` (string): Base URL for the API
  - `default_headers` (object): Default headers for all requests

**Example:**
```json
{
  "tool": "create_api_connection",
  "arguments": {
    "config": {
      "name": "github_api",
      "base_url": "https://api.github.com",
      "default_headers": {
        "Accept": "application/vnd.github.v3+json"
      }
    }
  }
}
```

#### 3. `add_api_method`
Add a method to an existing API connection.

**Parameters:**
- `config` (object, required):
  - `connection_name` (string): Name of the API connection
  - `method_name` (string): Name for this method
  - `http_method` (string): HTTP method (GET or POST)
  - `endpoint` (string): API endpoint (relative to base URL)
  - `headers` (object): Headers for this specific method
  - `params` (object): Query parameters
  - `body` (object): Request body (for POST requests)

**Example:**
```json
{
  "tool": "add_api_method",
  "arguments": {
    "config": {
      "connection_name": "github_api",
      "method_name": "get_user",
      "http_method": "GET",
      "endpoint": "/users/{username}",
      "headers": {},
      "params": {},
      "body": {}
    }
  }
}
```

#### 4. `execute_api_call`
Execute an API call using a configured connection and method.

**Parameters:**
- `connection_name` (string, required): Name of the API connection
- `method_name` (string, required): Name of the method to execute
- `params` (object, optional): Override parameters for this call
- `body` (object, optional): Override body for this call
- `simulate_human` (boolean, optional): Whether to simulate human-like behavior

**Example:**
```json
{
  "tool": "execute_api_call",
  "arguments": {
    "connection_name": "github_api",
    "method_name": "get_user",
    "params": {"username": "octocat"},
    "simulate_human": true
  }
}
```

#### 5. `list_api_connections`
List all configured API connections.

**Example:**
```json
{
  "tool": "list_api_connections",
  "arguments": {}
}
```

#### 6. `get_api_connection_details`
Get details of a specific API connection.

**Parameters:**
- `connection_name` (string, required): Name of the API connection

**Example:**
```json
{
  "tool": "get_api_connection_details",
  "arguments": {
    "connection_name": "github_api"
  }
}
```

### Available Resources

#### 1. `api://connections`
List all API connections as a resource.

#### 2. `api://connections/{name}`
Get detailed information about a specific API connection.

## Human Behavior Simulation

The server includes several features to simulate human-like browsing behavior:

1. **Random User Agents**: Rotates through a variety of browser user agents
2. **Variable Delays**: Adds random delays between requests (configurable)
3. **Realistic Headers**: Includes standard browser headers
4. **Referer Simulation**: Randomly adds Google as referer to appear more natural
5. **Session Management**: Maintains cookies and session state

## Error Handling

All tools return structured responses with `success` field:
- On success: `{"success": true, ...data}`
- On failure: `{"success": false, "error": "error message"}`

## Testing

Run the test suite:

```bash
# Using pytest
pytest tests.py

# Or with Python
python -m pytest tests.py

# With coverage
pytest tests.py --cov=server --cov-report=html
```

## Development

### Project Structure

```
mcp-web-interaction-toolkit/
├── server.py           # Main MCP server implementation
├── tests.py            # Test suite
├── examples.md         # Detailed usage examples
├── pyproject.toml      # Package configuration
├── README.md           # This file
├── LICENSE             # MIT license
└── .gitignore          # Git ignore rules
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Advanced Usage

For more detailed examples including API connection management, chaining requests, and advanced scraping scenarios, see [examples.md](examples.md).

## Troubleshooting

### Common Issues

1. **Import errors**: Make sure all dependencies are installed: `pip install -e .`
2. **Connection timeouts**: Increase timeout values or check network connectivity
3. **Bot detection**: Enable human simulation and increase delays between requests
4. **SSL errors**: The server disables SSL verification by default; ensure you understand the security implications

### Debug Mode

Set environment variables for debugging:

```bash
export LOG_LEVEL=DEBUG
mcp-web-interaction-toolkit
```

## Security Considerations

- ⚠️ SSL verification is disabled by default for broader compatibility
- 🔒 Consider enabling SSL verification in production environments
- 🔑 API credentials should be handled securely (use environment variables)
- ⏱️ Be mindful of rate limits when scraping websites
- 🤖 Respect robots.txt and website terms of service

## License

MIT License - See [LICENSE](LICENSE) file for details

## Author

Kim Asplund - [GitHub](https://github.com/kimasplund/)

## Acknowledgments

- Built with [FastMCP](https://github.com/jlowin/fastmcp) framework
- Uses [aiohttp](https://github.com/aio-libs/aiohttp) for async HTTP
- HTML parsing by [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/)
- Powered by the [Model Context Protocol](https://modelcontextprotocol.io/)