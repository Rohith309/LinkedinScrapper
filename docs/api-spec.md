# API Specification

This document outlines the design of the LinkedIn Jobs API.

## Endpoints

### Get Jobs

- **Endpoint:** `GET /jobs`
- **Description:** Retrieves a list of jobs from LinkedIn based on search criteria.

#### Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `keyword` | string | Yes | The job title, skill, or keyword to search for. |
| `location` | string | Yes | The geographical location to search within. |
| `remote` | boolean | No | If `true`, only remote jobs will be returned. |
| `experience_level` | string | No | The desired experience level (e.g., `entry_level`, `mid_senior_level`). |

#### Responses

- **200 OK:** Successful response.
  ```json
  {
    "jobs": [
      {
        "title": "Software Engineer",
        "company": "Tech Corp",
        "location": "San Francisco, CA",
        "date_posted": "2024-07-23",
        "snippet": "Exciting opportunity for a skilled software engineer...",
        "url": "https://www.linkedin.com/jobs/view/..."
      }
    ]
  }
  ```

- **400 Bad Request:** Missing or invalid parameters.
  ```json
  {
    "error": "Missing required parameter: keyword"
  }
  ```

- **500 Internal Server Error:** Scraper failure or other server-side issue.
  ```json
  {
    "error": "Failed to retrieve job listings."
  }
  ```
