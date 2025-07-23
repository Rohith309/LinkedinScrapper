# LinkedIn Jobs API Specification

This document outlines the comprehensive LinkedIn Jobs API with advanced filtering capabilities.

## Base URL

```
http://localhost:8000/api/
```

## Common Response Format

All endpoints return a consistent JSON structure:

```json
{
  "success": true,
  "jobs": [...],
  "source": "live|cache|stale_cache_on_error",
  "count": 15,
  "processing_time": 2.34,
  "detail_failures": 0
}
```

## Endpoints

### 1. Basic Job Search

**Endpoint:** `GET /jobs/`

**Description:** Retrieves jobs based on keyword and location.

**Parameters:**
- `keyword` (string, required): Job title, skill, or keyword
- `location` (string, required): Geographic location

**Example:**
```bash
curl "http://localhost:8000/api/jobs/?keyword=python%20developer&location=san%20francisco"
```

### 2. Filter by Date Posted

**Endpoint:** `GET /jobs/date-posted/`

**Description:** Filter jobs by how recently they were posted.

**Parameters:**
- `keyword` (string, required)
- `location` (string, required) 
- `date_posted` (enum): `day`, `week`, `month`

**Example:**
```bash
curl "http://localhost:8000/api/jobs/date-posted/?keyword=software%20engineer&location=new%20york&date_posted=week"
```

### 3. Filter by Job Type

**Endpoint:** `GET /jobs/type/`

**Description:** Filter jobs by employment type.

**Parameters:**
- `keyword` (string, required)
- `location` (string, required)
- `job_type` (enum): `fulltime`, `parttime`, `contract`, `internship`

**Example:**
```bash
curl "http://localhost:8000/api/jobs/type/?keyword=data%20analyst&location=chicago&job_type=fulltime"
```

### 4. Filter by Experience Level

**Endpoint:** `GET /jobs/experience/`

**Description:** Filter jobs by required experience level.

**Parameters:**
- `keyword` (string, required)
- `location` (string, required)
- `experience` (enum): `entry`, `associate`, `mid`, `senior`, `director`

**Example:**
```bash
curl "http://localhost:8000/api/jobs/experience/?keyword=product%20manager&location=seattle&experience=senior"
```

### 5. Filter by Company

**Endpoint:** `GET /jobs/company/`

**Description:** Filter jobs by specific company names.

**Parameters:**
- `keyword` (string, required)
- `location` (string, required)
- `company` (string): Single company or comma-separated list (max 10)

**Example:**
```bash
curl "http://localhost:8000/api/jobs/company/?keyword=engineer&location=austin&company=Google,Microsoft,Apple"
```

### 6. Filter by Remote/Workplace Type

**Endpoint:** `GET /jobs/remote/`

**Description:** Filter jobs by workplace arrangement.

**Parameters:**
- `keyword` (string, required)
- `location` (string, required)
- `workplace` (enum): `all`, `onsite`, `remote`, `hybrid`

**Example:**
```bash
curl "http://localhost:8000/api/jobs/remote/?keyword=frontend%20developer&location=boston&workplace=remote"
```

### 7. Advanced Combined Filters

**Endpoint:** `GET /jobs/advanced/`

**Description:** Combine multiple filters for precise job searches.

**Parameters:**
- `keyword` (string, required)
- `location` (string, required)
- `date_posted` (enum, optional): `day`, `week`, `month`
- `job_type` (enum, optional): `fulltime`, `parttime`, `contract`, `internship`
- `experience` (enum, optional): `entry`, `associate`, `mid`, `senior`, `director`
- `company` (string, optional): Company name(s)
- `workplace` (enum, optional): `all`, `onsite`, `remote`, `hybrid`

**Example:**
```bash
curl "http://localhost:8000/api/jobs/advanced/?keyword=machine%20learning&location=san%20francisco&date_posted=week&job_type=fulltime&experience=mid&workplace=remote"
```

## Response Format

All endpoints return JSON responses with the following structure:

### Standard Response
```json
{
  "success": true,
  "jobs": [
    {
      "title": "Software Engineer",
      "company": "Tech Corp",
      "location": "San Francisco, CA",
      "url": "https://linkedin.com/jobs/view/123456789",
      "date_posted": "2 days ago",
      "snippet": "Job description preview..."
    }
  ],
  "source": "live",
  "count": 25,
  "processing_time": 3.45
}
```

### Response with Filter Warning
When filter combinations are too restrictive, the API includes intelligent suggestions:

```json
{
  "success": true,
  "jobs": [
    {
      "title": "Python Developer Intern",
      "company": "Tech Startup",
      "location": "India",
      "url": "https://linkedin.com/jobs/view/123456789"
    }
  ],
  "source": "live",
  "count": 3,
  "processing_time": 8.12,
  "filter_warning": {
    "message": "Filter combination too restrictive: 2/3 results are internships despite requesting full-time jobs",
    "suggestions": [
      "Remove 'experience=entry' filter - entry-level full-time remote positions are rare",
      "Try 'workplace=hybrid' or remove workplace filter - remote positions are limited",
      "Expand to 'date_posted=week' or remove date filter for more results"
    ],
    "relaxed_filters_removed": ["experience", "workplace", "date_posted"],
    "suggested_query_params": "job_type=fulltime"
  },
  "detail_failures": 0
}
```

### Error Response
```json
{
  "success": false,
  "error": "Invalid job_type. Allowed values: fulltime, parttime, contract, internship"
}

## Intelligent Error Handling

The API includes smart detection of restrictive filter combinations that may not yield the desired results. When the system detects that your filters are too restrictive, it provides helpful suggestions.

### When Filter Warnings Trigger

A `filter_warning` is included in the response when:
- More than 50% of results are internships despite requesting full-time jobs
- The filter combination is statistically rare in the job market
- LinkedIn falls back to showing unrelated positions

### Filter Warning Structure

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | Human-readable explanation of the issue |
| `suggestions` | array | List of specific recommendations to improve results |
| `relaxed_filters_removed` | array | Filters that should be removed for better results |
| `suggested_query_params` | string | Recommended query parameters for a new request |

### Common Restrictive Filter Scenarios

#### Scenario 1: Entry-Level + Full-Time + Remote
```bash
# This combination often yields few results
curl "http://localhost:8000/api/jobs/advanced/?keyword=Python%20Developer&location=India&experience=entry&job_type=fulltime&workplace=remote"
```

**Typical Response:**
```json
{
  "filter_warning": {
    "message": "Filter combination too restrictive: 3/4 results are internships despite requesting full-time jobs",
    "suggestions": [
      "Remove 'experience=entry' filter - entry-level full-time remote positions are rare"
    ],
    "suggested_query_params": "job_type=fulltime&workplace=remote"
  }
}
```

#### Scenario 2: Recent + Senior + Remote + Specific Location
```bash
# Very specific requirements may limit results
curl "http://localhost:8000/api/jobs/advanced/?keyword=Machine%20Learning&location=San%20Francisco&date_posted=day&experience=senior&workplace=remote"
```

#### Scenario 3: Multiple Restrictive Filters
```bash
# Combining many filters reduces available positions
curl "http://localhost:8000/api/jobs/advanced/?keyword=DevOps&location=New%20York&date_posted=week&job_type=contract&experience=mid&workplace=hybrid"
```

### Best Practices for Filter Usage

1. **Start Broad, Then Narrow**: Begin with fewer filters and add more as needed
2. **Test Filter Combinations**: Use the API to understand which combinations work well
3. **Consider Market Reality**: Some combinations (entry-level + remote + recent) are naturally rare
4. **Use Suggestions**: When you receive filter warnings, try the suggested parameters

## Error Codes

- **400 Bad Request:** Invalid or missing parameters
- **500 Internal Server Error:** Scraping failure
- **502 Bad Gateway:** Browser automation failed
- **504 Gateway Timeout:** Request timed out

## Rate Limiting

- Maximum 25 jobs per request
- Caching implemented with 10-minute TTL for fresh data
- Stale cache fallback available for 24 hours

## Implementation Notes

- All endpoints support parallel detail page scraping
- Graceful degradation when detail pages fail
- Comprehensive input validation and sanitization

## Proxy Configuration

The API supports authenticated proxy connections for enhanced scraping reliability and geographic targeting.

### Environment Variables

Set these variables in your `.env` file:

```bash
# Proxy Configuration
PROXY_HOST=your_proxy_host
PROXY_PORT=your_proxy_port
PROXY_USER=your_username
PROXY_PASS=your_password
```

### Proxy Types Supported

1. **Unauthenticated Proxy**: Only `PROXY_HOST` and `PROXY_PORT` required
2. **Authenticated Proxy**: All four variables required (recommended for production)

### How It Works

- **Automatic Detection**: API automatically detects if proxy credentials are provided
- **Chrome Extension**: For authenticated proxies, a temporary Chrome extension is generated
- **Seamless Integration**: Proxy configuration is transparent to API users
- **Cleanup**: Temporary files are automatically removed after use

### Example Configuration

```bash
# Example .env file
PROXY_HOST=premium-proxy.example.com
PROXY_PORT=8080
PROXY_USER=api_user_123
PROXY_PASS=secure_password_456
```

### Benefits

- **Reliability**: Reduces blocking and rate limiting from LinkedIn
- **Geographic Targeting**: Access region-specific job listings
- **Scalability**: Support for high-volume scraping operations
- **Security**: Encrypted proxy connections with authentication

## Performance Metrics

### Response Times

| Scenario | Expected Time | Notes |
|----------|---------------|-------|
| **Cached Response** | 0.1-0.5s | Instant return from cache |
| **Fresh Scrape (Basic)** | 8-15s | Includes 5s filter delay |
| **Fresh Scrape (Advanced)** | 10-20s | Multiple filters + detail scraping |
| **Detail Page Enrichment** | +3-8s | Parallel processing of job details |

### Caching Strategy

- **Fresh Cache**: 10 minutes TTL for live data
- **Stale Fallback**: 24 hours for reliability
- **Cache Keys**: Unique per filter combination
- **Intelligent Invalidation**: Automatic cleanup of expired entries

### Optimization Features

1. **Parallel Processing**: Up to 5 concurrent detail page scrapes
2. **Smart Delays**: 5-second JavaScript execution wait for accurate filtering
3. **Resource Management**: Automatic WebDriver cleanup and memory optimization
4. **Request Limiting**: Maximum 25 jobs per request to balance speed and completeness

### Scalability Considerations

- **Proxy Rotation**: Use authenticated proxies for high-volume operations
- **Rate Limiting**: Built-in request throttling to prevent blocking
- **Error Recovery**: Graceful degradation with stale cache fallback
- **Memory Efficiency**: Optimized Chrome options for minimal resource usage

- Filter combinations are cached separately for optimal performance
