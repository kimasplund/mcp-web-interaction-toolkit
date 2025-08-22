# MCP Web Interaction Toolkit

A powerful MCP (Model Context Protocol) server for web scraping, API interaction, and authentication detection with human behavior simulation. Built for LLMs to interact with websites intelligently and efficiently.

## 🌟 Features

### Core Capabilities
- **🔍 Intelligent Web Scraping** - Extract content, links, images with smart parsing
- **🤖 Human Behavior Simulation** - Random delays, user-agent rotation, browser-like headers
- **🔐 Authentication Detection** - Automatically identifies login mechanisms (Spring Security, forms, OAuth)
- **🧠 Persistent API Discovery** - Learns and caches API endpoints for each domain
- **📦 JavaScript Data Extraction** - Captures `__NEXT_DATA__`, window objects, and embedded JSON
- **🍪 Session Management** - Maintains cookies and sessions across requests
- **⚡ Lightweight & Fast** - No browser overhead, pure HTTP requests (~0.5s response time)
- **🔌 API Connection Management** - Create and manage multiple API connections with custom methods

### Authentication Support
- **Spring Security** - JSON-based authentication with JSESSIONID handling
- **Form-based Login** - Traditional HTML form detection and submission
- **Hybrid Authentication** - Supports sites using multiple auth methods
- **CSRF Token Handling** - Automatic token extraction and inclusion
- **Event ID Support** - For complex authentication flows (ClickBank-style)

### Smart Features
- **API Endpoint Discovery** - Finds hidden APIs in HTML/JavaScript
- **Persistent Knowledge Base** - Saves discoveries to `.api_discovery/` directory
- **Automatic Auth Detection** - Identifies authentication type without configuration
- **Cookie Jar Management** - Per-domain session persistence
- **Redirect Handling** - Follows or captures redirects as needed

## 📦 Installation

### From GitHub
```bash
# Clone the repository
git clone https://github.com/kimasplund/mcp-web-interaction-toolkit.git
cd mcp-web-interaction-toolkit

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .
```

### From pip (direct from GitHub)
```bash
pip install git+https://github.com/kimasplund/mcp-web-interaction-toolkit.git
```

## 🚀 Available Versions

The toolkit comes in three versions, each with increasing capabilities:

### 1. **Basic Server** (`mcp-web-interaction-toolkit`)
Simple web scraping with human simulation
```bash
mcp-web-interaction-toolkit
```

### 2. **Enhanced Server** (`mcp-web-interaction-toolkit-enhanced`)
Adds security improvements and better error handling
```bash
mcp-web-interaction-toolkit-enhanced
```

### 3. **Integrated Server** (`mcp-web-interaction-toolkit-integrated`) ⭐ Recommended
Full feature set with API discovery, authentication detection, and persistent caching
```bash
mcp-web-interaction-toolkit-integrated
```

## 🛠️ MCP Tools

### 1. `scrape_webpage`
Scrapes a webpage with full discovery and circumvention features.

**Parameters:**
- `url` (string, required): The URL to scrape
- `options` (object, optional):
  - `simulate_human` (boolean): Simulate human behavior (default: true)
  - `min_delay` (float): Minimum delay in seconds (default: 0.5)
  - `max_delay` (float): Maximum delay in seconds (default: 2.0)
  - `max_content_length` (integer): Max content to return (default: 5000)
  - `max_links` (integer): Max links to extract (default: 50)
  - `max_images` (integer): Max images to extract (default: 20)
  - `use_cache` (boolean): Use cached responses (default: true)
  - `follow_redirects` (boolean): Follow HTTP redirects (default: true)
  - `extract_js` (boolean): Extract JavaScript data (default: true)

**Example:**
```json
{
  "tool": "scrape_webpage",
  "arguments": {
    "url": "https://example.com",
    "options": {
      "simulate_human": true,
      "extract_js": true,
      "max_content_length": 10000
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "url": "https://example.com",
  "title": "Example Domain",
  "content": "Page text content...",
  "links": [{"text": "Link text", "url": "https://..."}],
  "images": [{"alt": "Alt text", "url": "https://..."}],
  "status_code": 200,
  "headers": {...},
  "cookies": {"session": "..."},
  "discovery": {
    "endpoints": [...],
    "authentication": {...},
    "javascript_data": {...}
  }
}
```

### 2. `smart_login` (Integrated version only)
Performs intelligent login with automatic authentication detection.

**Parameters:**
- `login_url` (string, required): URL of the login page
- `username` (string, required): Username or email
- `password` (string, required): Password
- `use_discovery` (boolean): Use cached discovery data (default: true)
- `use_spring_security` (boolean): Force Spring Security mode (default: false)

**Example:**
```json
{
  "tool": "smart_login",
  "arguments": {
    "login_url": "https://example.com/login",
    "username": "user@example.com",
    "password": "password123",
    "use_discovery": true
  }
}
```

### 3. `discover_api_endpoints` (Integrated version only)
Discovers and caches API endpoints from a webpage.

**Parameters:**
- `url` (string, required): URL to analyze
- `html_content` (string, optional): Pre-fetched HTML content
- `save_to_cache` (boolean): Save to persistent cache (default: true)

**Example:**
```json
{
  "tool": "discover_api_endpoints",
  "arguments": {
    "url": "https://api.example.com",
    "save_to_cache": true
  }
}
```

### 4. `get_cached_discovery` (Integrated version only)
Retrieves cached API discovery for a domain.

**Parameters:**
- `url` (string, required): URL to get discovery for

**Example:**
```json
{
  "tool": "get_cached_discovery",
  "arguments": {
    "url": "https://example.com"
  }
}
```

### 5. `extract_javascript_data` (Integrated version only)
Extracts JavaScript data from a webpage.

**Parameters:**
- `url` (string, required): URL to extract JavaScript from

**Returns:**
- `__NEXT_DATA__`: Next.js application data
- `eventId`: Authentication event IDs
- `buildId`: Build identifiers
- Window objects and other embedded JavaScript data

### 6. `create_api_connection` (All versions)
Create a new API connection configuration.

**Parameters:**
- `config` (object, required):
  - `name` (string): Name for this API connection
  - `base_url` (string): Base URL for the API
  - `default_headers` (object): Default headers for all requests

### 7. `add_api_method` (All versions)
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

### 8. `execute_api_call` (All versions)
Execute an API call using a configured connection and method.

**Parameters:**
- `connection_name` (string, required): Name of the API connection
- `method_name` (string, required): Name of the method to execute
- `params` (object, optional): Override parameters for this call
- `body` (object, optional): Override body for this call
- `simulate_human` (boolean, optional): Whether to simulate human-like behavior

### 9. `list_api_connections` (All versions)
List all configured API connections.

### 10. `get_api_connection_details` (All versions)
Get details of a specific API connection.

## 📁 API Discovery Cache

The integrated version maintains a persistent knowledge base in the `.api_discovery/` directory:

```
.api_discovery/
├── github.com.json
├── example.com.json
└── api.service.com.json
```

Each file contains:
- Discovered API endpoints
- Authentication mechanisms
- JavaScript data structures
- Last update timestamp
- Discovery count

### Cache File Structure:
```json
{
  "domain": "example.com",
  "last_updated": "2025-08-22T10:30:00",
  "discovery_count": 5,
  "endpoints": [
    {
      "url": "https://example.com/api/login",
      "method": "POST",
      "discovered_at": "2025-08-22T10:30:00"
    }
  ],
  "authentication": {
    "type": "spring_security",
    "details": {
      "login_endpoint": "/api/login",
      "csrf_token": "token_value"
    }
  },
  "javascript_data": {
    "__NEXT_DATA__": {},
    "eventId": "uuid-here",
    "buildId": "build-123"
  }
}
```

## 🎯 Use Cases

### Basic Web Scraping
```python
# Scrape a webpage with human simulation
result = await scrape_webpage(
    "https://example.com",
    options={"simulate_human": True}
)
```

### API Authentication
```python
# Login to a Spring Security protected API
login_result = await smart_login(
    "https://api.example.com/login",
    "username",
    "password"
)
session_id = login_result["session_id"]
```

### Discovering Hidden APIs
```python
# Find API endpoints in a webpage
discovery = await discover_api_endpoints("https://app.example.com")
for endpoint in discovery["endpoints"]:
    print(f"Found: {endpoint['method']} {endpoint['url']}")
```

### Session-based Scraping
```python
# Login and scrape protected content
login = await smart_login(login_url, username, password)
if login["success"]:
    cookies = login["cookies"]
    # Use cookies for subsequent requests
```

### API Connection Management
```python
# Create API connection
await create_api_connection({
    "name": "github_api",
    "base_url": "https://api.github.com",
    "default_headers": {"Accept": "application/vnd.github.v3+json"}
})

# Add method
await add_api_method({
    "connection_name": "github_api",
    "method_name": "get_user",
    "http_method": "GET",
    "endpoint": "/users/{username}"
})

# Execute
result = await execute_api_call(
    "github_api",
    "get_user",
    params={"username": "octocat"}
)
```

## ⚡ Performance

- **Response Time**: ~0.5s without simulation, 1.5-2.5s with human simulation
- **Memory Usage**: Minimal, no browser instances
- **Concurrent Requests**: Supports connection pooling (10 connections per domain)
- **Cache Performance**: Instant retrieval of discovered APIs
- **User Agents**: 3 rotating browser identities

## 🆚 Comparison with Browser Automation

| Feature | Web Interaction Toolkit | Browser Automation (Playwright/Selenium) |
|---------|-------------------------|------------------------------------------|
| Speed | ⚡ 0.5-2s | 🐢 5-10s |
| Resource Usage | ✅ Minimal | ❌ Heavy (full browser) |
| JavaScript Execution | ❌ No | ✅ Yes |
| API Discovery | ✅ Automatic | ❌ Manual |
| Session Persistence | ✅ Built-in | 🟨 Requires setup |
| Learning/Caching | ✅ Persistent | ❌ No |
| Best For | APIs, server-rendered sites | SPAs, complex interactions |

## 🔧 Configuration

### Claude Desktop Integration

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "web-toolkit": {
      "command": "mcp-web-interaction-toolkit-integrated",
      "args": [],
      "env": {}
    }
  }
}
```

Or if using virtual environment:

```json
{
  "mcpServers": {
    "web-toolkit": {
      "command": "/path/to/venv/bin/mcp-web-interaction-toolkit-integrated",
      "args": [],
      "env": {}
    }
  }
}
```

Claude Code
```
#claude mcp add mcp-web-interaction-toolkit-integrated mcp-web-interaction-toolkit-integrated
```

### Environment Variables (Optional)

```bash
# Set custom cache directory
API_DISCOVERY_DIR=/path/to/cache

# Set default timeouts
REQUEST_TIMEOUT=30
SESSION_TIMEOUT=1800

# Debug mode
LOG_LEVEL=DEBUG
```

## 🐛 Troubleshooting

### Common Issues

1. **"Authentication type unknown"**
   - The site likely uses JavaScript-rendered forms
   - Try forcing Spring Security: `use_spring_security=true`
   - Consider using a browser automation MCP for this site

2. **Empty JavaScript extraction**
   - Site may load data dynamically after initial HTML
   - Check if the site is a SPA (React/Vue/Angular)
   - Look for API calls in browser network tab

3. **Session expires quickly**
   - Some sites require periodic activity
   - Use the session cookies promptly after login
   - Check if site requires specific headers

4. **Rate limiting**
   - Enable human simulation: `simulate_human=true`
   - Increase delay parameters: `min_delay=2, max_delay=5`
   - Respect site's robots.txt

5. **Import errors**
   ```bash
   # Ensure all dependencies are installed
   pip install -e .
   # Or reinstall
   pip uninstall mcp-web-interaction-toolkit
   pip install -e .
   ```

6. **MCP connection fails**
   - Check if server runs standalone: `mcp-web-interaction-toolkit-integrated`
   - Verify Python path in MCP config
   - Check for port conflicts

### Debug Mode

Run with verbose logging:
```bash
LOG_LEVEL=DEBUG mcp-web-interaction-toolkit-integrated
```

Or test specific functionality:
```python
# Test script
from server_integrated import EnhancedWebScraper, ScrapeOptions
import asyncio

async def test():
    scraper = EnhancedWebScraper()
    result = await scraper.scrape_with_discovery(
        "https://example.com",
        ScrapeOptions(simulate_human=True)
    )
    print(result)
    await scraper.cleanup()

asyncio.run(test())
```

## 🏗️ Project Structure

```
mcp-web-interaction-toolkit/
├── server.py                 # Basic MCP server
├── server_enhanced.py        # Enhanced server with security improvements
├── server_integrated.py      # Full-featured integrated server
├── pyproject.toml           # Package configuration
├── README.md                # This file
├── LICENSE                  # MIT license
├── examples.md              # Detailed usage examples
├── .api_discovery/          # Cached API discoveries (created at runtime)
│   ├── github.com.json
│   └── example.com.json
└── .gitignore              # Git ignore rules
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

Built with:
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP framework
- [aiohttp](https://github.com/aio-libs/aiohttp) - Async HTTP client
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation

## 📚 Related Projects

For JavaScript-heavy sites requiring browser automation, consider:
- Browser debugging MCP servers
- Playwright-based MCP servers
- Selenium automation tools

## 🔗 Links

- [GitHub Repository](https://github.com/kimasplund/mcp-web-interaction-toolkit)
- [MCP Documentation](https://modelcontextprotocol.io/)
- [Report Issues](https://github.com/kimasplund/mcp-web-interaction-toolkit/issues)

## Author

Kim Asplund - [GitHub](https://github.com/kimasplund/)