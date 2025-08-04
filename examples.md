# Web Interaction Toolkit MCP Server - Examples

## Basic Web Scraping

### 1. Simple Web Page Scraping

```python
# Scrape a webpage with default settings
result = await scrape_webpage(
    url="https://example.com"
)
```

### 2. Scraping with Custom Options

```python
# Scrape with custom settings and without human simulation
result = await scrape_webpage(
    url="https://example.com",
    options={
        "simulate_human": False,
        "max_content_length": 10000,
        "max_links": 100,
        "max_images": 50
    }
)
```

### 3. Scraping with Human Behavior Simulation

```python
# Scrape with longer delays to avoid rate limiting
result = await scrape_webpage(
    url="https://example.com/api/data",
    options={
        "simulate_human": True,
        "min_delay": 2.0,
        "max_delay": 5.0
    }
)
```

## API Connection Management

### 1. Setting Up a GitHub API Connection

```python
# Create the connection
await create_api_connection(
    config={
        "name": "github_api",
        "base_url": "https://api.github.com",
        "default_headers": {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": "Bearer YOUR_GITHUB_TOKEN"
        }
    }
)

# Add a method to get user info
await add_api_method(
    config={
        "connection_name": "github_api",
        "method_name": "get_user",
        "http_method": "GET",
        "endpoint": "/users/{username}"
    }
)

# Execute the API call
result = await execute_api_call(
    connection_name="github_api",
    method_name="get_user",
    params={"username": "octocat"}
)
```

### 2. Setting Up a REST API with POST Methods

```python
# Create a connection to a hypothetical blog API
await create_api_connection(
    config={
        "name": "blog_api",
        "base_url": "https://api.myblog.com/v1",
        "default_headers": {
            "Content-Type": "application/json",
            "API-Key": "YOUR_API_KEY"
        }
    }
)

# Add a method to create a blog post
await add_api_method(
    config={
        "connection_name": "blog_api",
        "method_name": "create_post",
        "http_method": "POST",
        "endpoint": "/posts",
        "headers": {
            "X-Request-ID": "unique-request-id"
        }
    }
)

# Create a new blog post
result = await execute_api_call(
    connection_name="blog_api",
    method_name="create_post",
    body={
        "title": "My New Post",
        "content": "This is the content of my blog post.",
        "tags": ["mcp", "web-scraping", "api"]
    }
)
```

### 3. Working with Query Parameters

```python
# Create a search API connection
await create_api_connection(
    config={
        "name": "search_api",
        "base_url": "https://api.search-engine.com",
        "default_headers": {
            "Accept": "application/json"
        }
    }
)

# Add a search method with default parameters
await add_api_method(
    config={
        "connection_name": "search_api",
        "method_name": "search",
        "http_method": "GET",
        "endpoint": "/search",
        "params": {
            "limit": 10,
            "sort": "relevance"
        }
    }
)

# Execute search with custom parameters
result = await execute_api_call(
    connection_name="search_api",
    method_name="search",
    params={
        "q": "model context protocol",
        "limit": 20,  # Override default limit
        "filter": "recent"  # Add new parameter
    }
)
```

## Managing Multiple API Connections

```python
# List all configured connections
connections = await list_api_connections()
print(f"Available connections: {connections}")

# Get details about a specific connection
details = await get_api_connection_details(
    connection_name="github_api"
)
print(f"GitHub API details: {details}")
```

## Using MCP Resources

### Accessing API Connections as Resources

```python
# Get all connections via resource URL
all_connections = await mcp.get_resource("api://connections")

# Get specific connection details via resource URL
github_details = await mcp.get_resource("api://connections/github_api")
```

## Error Handling Examples

### 1. Handling Scraping Errors

```python
result = await scrape_webpage(url="https://invalid-url-example")

if not result["success"]:
    print(f"Error scraping page: {result['error']}")
else:
    print(f"Page title: {result['title']}")
```

### 2. Handling API Connection Errors

```python
# Try to use a non-existent connection
result = await execute_api_call(
    connection_name="non_existent_api",
    method_name="some_method"
)

if not result["success"]:
    print(f"API Error: {result['error']}")
```

## Advanced Use Cases

### 1. Sequential Web Scraping with Rate Limiting

```python
urls = [
    "https://example.com/page1",
    "https://example.com/page2",
    "https://example.com/page3"
]

results = []
for url in urls:
    # Scrape with human simulation to respect rate limits
    result = await scrape_webpage(
        url=url,
        options={
            "simulate_human": True,
            "min_delay": 3.0,
            "max_delay": 6.0
        }
    )
    results.append(result)
    
    # Process results as needed
    if result["success"]:
        print(f"Scraped {url}: {result['title']}")
```

### 2. Chaining API Calls

```python
# First, get user information
user_result = await execute_api_call(
    connection_name="github_api",
    method_name="get_user",
    params={"username": "octocat"}
)

if user_result["success"]:
    # Then, get user's repositories
    await add_api_method(
        config={
            "connection_name": "github_api",
            "method_name": "get_user_repos",
            "http_method": "GET",
            "endpoint": "/users/{username}/repos"
        }
    )
    
    repos_result = await execute_api_call(
        connection_name="github_api",
        method_name="get_user_repos",
        params={"username": "octocat", "per_page": 100}
    )
```

### 3. Combining Web Scraping and API Calls

```python
# Scrape a webpage to find API endpoints
webpage = await scrape_webpage(url="https://api-docs.example.com")

# Extract API information from the scraped content
api_endpoints = []
for link in webpage.get("links", []):
    if "/api/" in link["url"]:
        api_endpoints.append(link)

# Create API connection based on scraped information
if api_endpoints:
    base_url = "https://api.example.com"
    await create_api_connection(
        config={
            "name": "discovered_api",
            "base_url": base_url,
            "default_headers": {"Accept": "application/json"}
        }
    )
```

## Best Practices

1. **Always use human simulation** when scraping websites to avoid being blocked
2. **Store API credentials securely** - never hardcode them in your scripts
3. **Implement retry logic** for failed requests
4. **Respect rate limits** by adjusting delay parameters
5. **Cache API connections** to avoid recreating them repeatedly
6. **Use appropriate timeouts** for different types of requests
7. **Handle errors gracefully** and provide meaningful error messages