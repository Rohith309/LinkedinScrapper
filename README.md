# LinkedIn Jobs API

This project is a web scraping API designed to retrieve job postings from LinkedIn based on specified criteria. It is built with Django and Django Rest Framework.

## Features

- Scrape LinkedIn for job postings.
- Filter jobs by keyword, location, and other parameters.
- Caching mechanism to improve performance and reduce redundant scrapes.

## Project Structure

```
linkedin-jobs-api/
├─ api/                     # Django app or serverless function code
│  └─ jobs/                 # “jobs” endpoint module
├─ tests/                   # Unit and integration tests
├─ docs/
│  └─ api-spec.md           # API specification (endpoints, schemas)
├─ .gitignore
├─ README.md
├─ requirements.txt
```
