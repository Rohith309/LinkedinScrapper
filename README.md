# 🚀 Advanced LinkedIn Jobs API

**Production-ready LinkedIn job scraping API with intelligent filtering and error handling**

A powerful, enterprise-grade web scraping API that retrieves and filters LinkedIn job postings with precision and reliability. Built with Django REST Framework and enhanced with cutting-edge features including authenticated proxy support, intelligent error handling, and advanced filtering capabilities.

## 🌟 What Makes This Special

- **🧠 Intelligent Error Handling**: Automatically detects restrictive filter combinations and provides actionable suggestions
- **🔐 Authenticated Proxy Support**: Full proxy authentication with automatic Chrome extension generation
- **⚡ Advanced Filtering**: 8 specialized endpoints with LinkedIn URL parameter integration
- **🎯 Production Ready**: Comprehensive error handling, logging, and resource management

## ✨ Key Features

### 🎯 **Advanced Filtering System**
- **8 Specialized Endpoints**: Target specific job criteria with dedicated filtering endpoints
- **Combined Search**: Use `/jobs/advanced/` to combine multiple filters for laser-focused results
- **LinkedIn URL Integration**: Direct mapping to LinkedIn's native filter parameters (`f_TPR`, `f_JT`, `f_E`, `f_WT`)
- **Input Validation**: Comprehensive parameter validation with helpful error messages

### 🧠 **Intelligent Error Handling**
- **Restrictive Filter Detection**: Automatically detects when filter combinations are too restrictive
- **Smart Suggestions**: Provides actionable recommendations to improve search results
- **Filter Analysis**: Analyzes job results and suggests optimal filter combinations
- **Graceful Degradation**: Maintains functionality even when specific filters yield no results

### ⚡ **Enterprise Performance**
- **Authenticated Proxy Support**: Full support for proxy authentication with automatic extension generation
- **Parallel Processing**: Concurrent job detail scraping using ThreadPoolExecutor
- **Smart Caching**: 10-minute fresh cache with intelligent fallback mechanisms
- **Optimized WebDriver**: Headless Chrome with JavaScript-enabled filtering for accurate results

### 🔒 **Production Ready**
- **Robust Error Handling**: Comprehensive timeout management and graceful failure recovery
- **Detailed Logging**: Structured logging with request tracking and performance metrics
- **Resource Management**: Automatic cleanup of WebDriver instances and temporary files
- **Security**: Input sanitization and validation to prevent malicious requests

## API Endpoints Overview

The API provides specialized endpoints for targeted searches:

- `GET /api/jobs/` - Basic search
- `GET /api/jobs/date-posted/` - Filter by post date
- `GET /api/jobs/type/` - Filter by job type
- `GET /api/jobs/experience/` - Filter by experience level
- `GET /api/jobs/company/` - Filter by company
- `GET /api/jobs/remote/` - Filter by workplace type
- `GET /api/jobs/advanced/` - Combine any of the above filters

> For a complete list of parameters, request/response examples, and `curl` commands, please see the **[Full API Specification](docs/api-spec.md)**.

## 🧠 Intelligent Error Handling in Action

The API automatically detects when your filter combinations are too restrictive and provides helpful suggestions:

### Example: Restrictive Filter Combination
```bash
curl "http://localhost:8000/api/jobs/advanced/?keyword=Python%20Developer&location=India&date_posted=month&job_type=fulltime&experience=entry&workplace=remote"
```

**Response with Filter Warning:**
```json
{
  "success": true,
  "jobs": [...],
  "filter_warning": {
    "message": "Filter combination too restrictive: 3/4 results are internships despite requesting full-time jobs",
    "suggestions": [
      "Remove 'experience=entry' filter - entry-level full-time remote positions are rare",
      "Try 'workplace=hybrid' or remove workplace filter - remote positions are limited"
    ],
    "relaxed_filters_removed": ["experience", "workplace"],
    "suggested_query_params": "job_type=fulltime&date_posted=month"
  }
}
```

### Benefits
- **✅ Saves Time**: No need to manually adjust filters
- **💡 Educational**: Learn which filter combinations work best
- **🎯 Optimized Results**: Get actionable suggestions for better job matches
- **🚀 User-Friendly**: Clear explanations of why filters might be too restrictive

## Getting Started

### Prerequisites
- Python 3.8+
- Pip
- Git

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd linkedin-jobs-api
   ```

2. **Create a virtual environment and activate it:**
   ```bash
   python -m venv venv
   # On Windows
   .\venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Django development server:**
   ```bash
   cd api
   python manage.py runserver
   ```

The API will be available at `http://localhost:8000/api/`.

## Example Usage

Here's a quick example of how to find mid-level, full-time Python developer jobs posted in the last week in San Francisco:

```bash
curl "http://localhost:8000/api/jobs/advanced/?keyword=python%20developer&location=san%20francisco&date_posted=week&job_type=fulltime&experience=mid"
```

## Project Structure

```
linkedin-jobs-api/
├─ api/                     # Django project
│  └─ jobs/                 # Django app for the jobs API
├─ docs/
│  └─ api-spec.md           # Detailed API endpoint documentation
├─ tests/                   # Unit and integration tests
├─ .gitignore
├─ README.md
├─ requirements.txt
```
