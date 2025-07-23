from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from django.conf import settings
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import logging
import os
import zipfile
import re
from urllib.parse import quote_plus

# Configure logging
logger = logging.getLogger(__name__)

# LinkedIn filter mappings
LINKEDIN_FILTERS = {
    'date_posted': {
        'day': 'r86400',
        'week': 'r604800', 
        'month': 'r2592000'
    },
    'job_type': {
        'fulltime': 'F',
        'parttime': 'P',
        'contract': 'C',
        'internship': 'I'
    },
    'experience': {
        'entry': '1',
        'associate': '2',
        'mid': '3',
        'senior': '4',
        'director': '5'
    },
    'workplace': {
        'all': '0',
        'onsite': '1',
        'remote': '2',
        'hybrid': '3'
    }
}

class BaseJobScraper(APIView):
    """
    Base class for LinkedIn job scraping with shared functionality.
    Supports parallel scraping of job details with robust error handling.
    """
    
    MAX_JOBS_PER_REQUEST = 25  # Limit to prevent abuse
    DETAIL_PAGE_TIMEOUT = 10   # Seconds to wait for detail pages
    SEARCH_PAGE_TIMEOUT = 15   # Seconds to wait for search page



    def _create_driver(self):
        """Create a Chrome driver with optimized settings for scraping."""
        chrome_options = Options()
        # Essential for running in a server environment
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")

        # Standard practices to avoid detection and ensure consistency
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
        
        # Suppress verbose console output from Chrome
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # --- CRITICAL FIX ---
        # JavaScript is required for LinkedIn's filters to apply. The previous, more aggressive
        # flags (--disable-javascript, --disable-images, etc.) have been removed as they were
        # breaking the site's functionality.

        if settings.PROXY_HOST and settings.PROXY_PORT:
            if settings.PROXY_USER and settings.PROXY_PASS:
                # Authenticated proxy: create a temporary extension
                plugin_file = 'proxy_auth_plugin.zip'

                manifest_json = """
                {
                    "version": "1.0.0",
                    "manifest_version": 2,
                    "name": "Chrome Proxy",
                    "permissions": [
                        "proxy",
                        "tabs",
                        "unlimitedStorage",
                        "storage",
                        "<all_urls>",
                        "webRequest",
                        "webRequestBlocking"
                    ],
                    "background": {
                        "scripts": ["background.js"]
                    }
                }
                """

                background_js = """
                var config = {
                    mode: "fixed_servers",
                    rules: {
                        singleProxy: {
                            scheme: "http",
                            host: \"%(host)s\",
                            port: parseInt(%(port)s)
                        },
                        bypassList: ["localhost"]
                    }
                };

                chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});

                function callbackFn(details) {
                    return {
                        authCredentials: {
                            username: \"%(user)s\",
                            password: \"%(pass)s\"
                        }
                    };
                }

                chrome.webRequest.onAuthRequired.addListener(
                    callbackFn,
                    {urls: ["<all_urls>"]},
                    ['blocking']
                );
                """ % {
                    "host": settings.PROXY_HOST,
                    "port": settings.PROXY_PORT,
                    "user": settings.PROXY_USER,
                    "pass": settings.PROXY_PASS,
                }

                with zipfile.ZipFile(plugin_file, 'w') as zp:
                    zp.writestr("manifest.json", manifest_json)
                    zp.writestr("background.js", background_js)
                chrome_options.add_extension(plugin_file)
            else:
                # Unauthenticated proxy
                proxy_url = f"{settings.PROXY_HOST}:{settings.PROXY_PORT}"
                chrome_options.add_argument(f'--proxy-server={proxy_url}')

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

        if 'plugin_file' in locals() and os.path.exists(plugin_file):
            os.remove(plugin_file)

        return driver
    
    def _validate_inputs(self, keyword, location):
        """Validate and sanitize input parameters."""
        if not keyword or not location:
            return False, "Missing required parameters: keyword and location"
        
        if len(keyword) > 100 or len(location) > 100:
            return False, "Parameters too long (max 100 characters each)"
            
        # Basic sanitization
        keyword = re.sub(r'[^\w\s+-]', '', keyword.strip())
        location = re.sub(r'[^\w\s,.-]', '', location.strip())
        
        if not keyword or not location:
            return False, "Invalid characters in parameters"
            
        return True, (keyword, location)
    
    def _validate_filter_param(self, filter_type, value):
        """Validate filter parameters against allowed values."""
        if not value:
            return True, value  # Optional parameters
            
        if filter_type not in LINKEDIN_FILTERS:
            return False, f"Unknown filter type: {filter_type}"
            
        allowed_values = LINKEDIN_FILTERS[filter_type].keys()
        if value not in allowed_values:
            return False, f"Invalid {filter_type}. Allowed values: {', '.join(allowed_values)}"
            
        return True, value
    
    def _validate_company_param(self, companies):
        """Validate and sanitize company parameter."""
        if not companies:
            return True, companies
            
        # Split by comma and clean each company name
        company_list = [re.sub(r'[^\w\s&.-]', '', company.strip()) for company in companies.split(',')]
        company_list = [c for c in company_list if c]  # Remove empty strings
        
        if not company_list:
            return False, "Invalid company names"
            
        if len(company_list) > 10:  # Reasonable limit
            return False, "Too many companies specified (max 10)"
            
        return True, ','.join(company_list)
    
    def _build_search_url(self, keyword, location, filters=None):
        """Build LinkedIn search URL with filters."""
        base_url = f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(keyword)}&location={quote_plus(location)}"

        if not filters:
            return base_url

        # Mapping from our API filter keys to LinkedIn's URL parameter names
        PARAM_MAPPING = {
            'date_posted': 'f_TPR',
            'job_type': 'f_JT',
            'experience': 'f_E',
            'company': 'f_C',  # Note: LinkedIn expects company IDs, not names.
            'workplace': 'f_WT',
        }

        filter_parts = []
        for key, value in filters.items():
            if not value:
                continue

            param_name = PARAM_MAPPING.get(key)
            if not param_name:
                continue

            # For company, we pass the raw value. This is a known limitation as LinkedIn
            # prefers company IDs for its 'f_C' parameter.
            if key == 'company':
                filter_parts.append(f"{param_name}={quote_plus(value)}")
            else:
                # For other filters, we look up the corresponding code from our mappings.
                filter_code = LINKEDIN_FILTERS.get(key, {}).get(value)
                if filter_code:
                    filter_parts.append(f"{param_name}={filter_code}")

        if filter_parts:
            final_url = f"{base_url}&{'&'.join(filter_parts)}"
            logger.info(f"Generated LinkedIn URL with filters: {final_url}")
            return final_url

        logger.info(f"Generated LinkedIn URL without filters: {base_url}")
        return base_url
    
    def _analyze_filter_effectiveness(self, jobs, filters):
        """
        Analyze job results to detect if filters are too restrictive.
        Returns suggestions if issues are detected.
        """
        if not jobs or not filters:
            return None
        
        # Keywords that indicate filter mismatch
        internship_keywords = ['intern', 'internship', 'trainee', 'apprentice']
        
        # Count jobs that don't match requested filters
        internship_count = 0
        total_jobs = len(jobs)
        
        for job in jobs:
            title = job.get('title', '').lower()
            if any(keyword in title for keyword in internship_keywords):
                internship_count += 1
        
        # If more than 50% of results are internships but user requested full-time
        if (filters.get('job_type') == 'fulltime' and 
            internship_count > total_jobs * 0.5 and 
            total_jobs > 0):
            
            suggestions = []
            relaxed_filters = []
            
            # Suggest removing restrictive filters
            if filters.get('experience') == 'entry':
                suggestions.append("Remove 'experience=entry' filter - entry-level full-time remote positions are rare")
                relaxed_filters.append('experience')
            
            if filters.get('workplace') == 'remote':
                suggestions.append("Try 'workplace=hybrid' or remove workplace filter - remote positions are limited")
                relaxed_filters.append('workplace')
            
            if filters.get('date_posted') == 'month':
                suggestions.append("Expand to 'date_posted=week' or remove date filter for more results")
                relaxed_filters.append('date_posted')
            
            # Build suggested URL with relaxed filters
            suggested_params = []
            for key, value in filters.items():
                if key not in relaxed_filters:
                    suggested_params.append(f"{key}={value}")
            
            return {
                "filter_warning": {
                    "message": f"Filter combination too restrictive: {internship_count}/{total_jobs} results are internships despite requesting full-time jobs",
                    "suggestions": suggestions,
                    "relaxed_filters_removed": relaxed_filters,
                    "suggested_query_params": "&".join(suggested_params) if suggested_params else "No additional filters"
                }
            }
        
        return None
    
    def scrape_job_details(self, job_data):
        """
        Scrapes the detail page for a single job to get date_posted and snippet.
        This method is designed to be run in a separate thread with robust error handling.
        """
        job_url = job_data['url']
        driver = None
        
        try:
            driver = self._create_driver()
            driver.set_page_load_timeout(self.DETAIL_PAGE_TIMEOUT)
            
            # Navigate to job detail page
            driver.get(job_url)
            
            # Wait for key elements to load
            wait = WebDriverWait(driver, 5)
            
            try:
                # Try to find date posted with multiple selectors
                date_selectors = [
                    'span.posted-time-ago__text',
                    'span[data-test="job-post-date"]',
                    '.job-details-jobs-unified-top-card__primary-description-container time'
                ]
                
                for selector in date_selectors:
                    try:
                        date_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                        job_data['date_posted'] = date_elem.text.strip()
                        break
                    except TimeoutException:
                        continue
                        
            except Exception as e:
                logger.debug(f"Could not find date for job {job_url}: {e}")
            
            try:
                # Try to find job description with multiple selectors
                desc_selectors = [
                    'div.show-more-less-html__markup',
                    'div[data-test="job-description"]',
                    '.job-details-jobs-unified-top-card__job-description'
                ]
                
                for selector in desc_selectors:
                    try:
                        desc_elem = driver.find_element(By.CSS_SELECTOR, selector)
                        full_text = desc_elem.get_attribute('textContent') or desc_elem.text
                        if full_text:
                            # Clean and truncate
                            clean_text = re.sub(r'\s+', ' ', full_text.strip())
                            job_data['snippet'] = clean_text[:200] + ('...' if len(clean_text) > 200 else '')
                            break
                    except Exception:
                        continue
                        
            except Exception as e:
                logger.debug(f"Could not find description for job {job_url}: {e}")
                
        except TimeoutException:
            logger.warning(f"Timeout loading job detail page: {job_url}")
        except WebDriverException as e:
            logger.error(f"WebDriver error for job {job_url}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error scraping job details {job_url}: {e}")
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
        
        # Ensure only basic data types in the returned object (no mock objects)
        clean_job_data = {
            'title': str(job_data.get('title', '')),
            'company': str(job_data.get('company', '')),
            'location': str(job_data.get('location', '')),
            'url': str(job_data.get('url', '')),
            'date_posted': str(job_data.get('date_posted', '')),
            'snippet': str(job_data.get('snippet', ''))
        }
        return clean_job_data

    def get(self, request, format=None):
        """Handle GET requests for job listings with enhanced validation and error handling."""
        start_time = time.time()
        
        # Input validation
        keyword = request.query_params.get('keyword', '').strip()
        location = request.query_params.get('location', '').strip()
        
        is_valid, result = self._validate_inputs(keyword, location)
        if not is_valid:
            return Response(
                {"error": result, "success": False},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        keyword, location = result
        
        # Check cache first - include filters in cache key
        filters = getattr(self, 'filters', None)
        filter_str = ''
        if filters:
            filter_parts = [f"{k}:{v}" for k, v in sorted(filters.items()) if v]
            filter_str = '_'.join(filter_parts)
        
        cache_key = f"jobs_{quote_plus(keyword)}_{quote_plus(location)}"
        if filter_str:
            cache_key += f"_{filter_str}"
        stale_cache_key = f"{cache_key}:stale"
        
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response({
                "success": True,
                "jobs": cached_data,
                "source": "cache",
                "count": len(cached_data),
                "processing_time": round(time.time() - start_time, 2)
            })

        # Start scraping process
        driver = None
        try:
            logger.info(f"Starting job search for keyword='{keyword}', location='{location}'")
            
            # Create main driver for search page
            driver = self._create_driver()
            driver.set_page_load_timeout(self.SEARCH_PAGE_TIMEOUT)
            
            # Build search URL with filters
            search_url = self._build_search_url(keyword, location, getattr(self, 'filters', None))
            logger.info(f"Fetching search URL: {search_url}")
            
            driver.get(search_url)
            
            # Wait for job cards to load
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.jobs-search__results-list')))

            # --- CRITICAL FIX: Add a delay for client-side filtering ---
            # Give LinkedIn's JavaScript time to apply the filters and update the DOM.
            logger.info("Waiting 5 seconds for filters to apply...")
            time.sleep(5)
            
            # Parse job cards
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            job_cards = soup.find_all('div', class_='base-card')
            
            # Close main driver early to free resources
            driver.quit()
            driver = None
            
            if not job_cards:
                logger.warning(f"No jobs found for keyword='{keyword}', location='{location}'")
                return Response({
                    "success": True,
                    "jobs": [],
                    "source": "live",
                    "count": 0,
                    "message": "No jobs found for the given criteria",
                    "processing_time": round(time.time() - start_time, 2)
                })
            
            # Extract initial job data
            initial_jobs = []
            for card in job_cards[:self.MAX_JOBS_PER_REQUEST]:  # Limit results
                try:
                    url_elem = card.find('a', class_='base-card__full-link')
                    title_elem = card.find('h3', class_='base-search-card__title')
                    company_elem = card.find('h4', class_='base-search-card__subtitle')
                    location_elem = card.find('span', class_='job-search-card__location')
                    
                    if all([url_elem, title_elem, company_elem, location_elem]):
                        initial_jobs.append({
                            'title': title_elem.get_text(strip=True),
                            'company': company_elem.get_text(strip=True),
                            'location': location_elem.get_text(strip=True),
                            'url': url_elem.get('href', ''),
                            'date_posted': '',
                            'snippet': ''
                        })
                except Exception as e:
                    logger.debug(f"Error parsing job card: {e}")
                    continue
            
            if not initial_jobs:
                return Response({
                    "success": True,
                    "jobs": [],
                    "source": "live",
                    "count": 0,
                    "message": "No valid jobs could be parsed",
                    "processing_time": round(time.time() - start_time, 2)
                })
            
            logger.info(f"Found {len(initial_jobs)} jobs, starting detail scraping")
            
            # Scrape detail pages in parallel
            enriched_jobs = []
            if initial_jobs:
                with ThreadPoolExecutor(max_workers=5) as executor:
                    future_to_job = {executor.submit(self.scrape_job_details, job): job for job in initial_jobs}
                    
                    for future in as_completed(future_to_job):
                        job = future_to_job[future]
                        try:
                            updated_job = future.result()
                            if updated_job:
                                # Replace the job in the list with updated version
                                index = initial_jobs.index(job)
                                initial_jobs[index] = updated_job
                        except Exception as e:
                            logger.error(f"Error processing job details for {job.get('title', 'Unknown')}: {e}")
                            # Keep the original job data if detail scraping fails
            
            # --- INTELLIGENT FILTER ANALYSIS ---
            filter_analysis = self._analyze_filter_effectiveness(initial_jobs, filters if hasattr(self, 'filters') else {})
            
            # Cache the results
            cache.set(cache_key, initial_jobs, 600)  # Cache for 10 minutes
            
            processing_time = round(time.time() - start_time, 2)
            logger.info(f"Successfully scraped {len(initial_jobs)} jobs in {processing_time} seconds")
            
            response_data = {
                "success": True,
                "jobs": initial_jobs,
                "source": "live",
                "count": len(initial_jobs),
                "processing_time": processing_time
            }
            
            # Add filter analysis if issues detected
            if filter_analysis:
                response_data.update(filter_analysis)
            
            return Response(response_data)
            
        except TimeoutException:
            logger.error(f"Timeout during job search for '{keyword}' in '{location}'")
            return Response({
                "success": False,
                "error": "Request timed out. Please try again.",
                "processing_time": round(time.time() - start_time, 2)
            }, status=status.HTTP_504_GATEWAY_TIMEOUT)
            
        except WebDriverException as e:
            logger.error(f"WebDriver error during job search: {e}")
            return Response({
                "success": False,
                "error": "Browser automation failed. Please try again.",
                "processing_time": round(time.time() - start_time, 2)
            }, status=status.HTTP_502_BAD_GATEWAY)
            
        except Exception as e:
            logger.error(f"Unexpected error during job search: {e}")
            
            # Attempt to serve from stale cache as a last resort
            stale_data = cache.get(stale_cache_key)
            if stale_data:
                logger.warning("Live scrape failed, serving stale data.")
                return Response({
                    "success": True,
                    "jobs": stale_data,
                    "source": "stale_cache_on_error",
                    "count": len(stale_data),
                    "error_message": "Live data could not be fetched. Serving older data.",
                    "processing_time": round(time.time() - start_time, 2)
                })
            
            return Response({
                "success": False,
                "error": "An unexpected error occurred and no cached data is available.",
                "processing_time": round(time.time() - start_time, 2)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass


class JobList(BaseJobScraper):
    """
    Original jobs endpoint - basic keyword and location search.
    """
    pass


class JobsByDatePosted(BaseJobScraper):
    """
    Filter jobs by date posted (day/week/month).
    """
    
    def get(self, request, format=None):
        # Validate date_posted parameter
        date_posted = request.query_params.get('date_posted', '').strip().lower()
        is_valid, result = self._validate_filter_param('date_posted', date_posted)
        if not is_valid:
            return Response(
                {"error": result, "success": False},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set filters for the base class
        self.filters = {'date_posted': date_posted} if date_posted else {}
        
        # Call parent get method
        return super().get(request, format)


class JobsByType(BaseJobScraper):
    """
    Filter jobs by type (fulltime/parttime/contract/internship).
    """
    
    def get(self, request, format=None):
        # Validate job_type parameter
        job_type = request.query_params.get('job_type', '').strip().lower()
        is_valid, result = self._validate_filter_param('job_type', job_type)
        if not is_valid:
            return Response(
                {"error": result, "success": False},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set filters for the base class
        self.filters = {'job_type': job_type} if job_type else {}
        
        # Call parent get method
        return super().get(request, format)


class JobsByExperience(BaseJobScraper):
    """
    Filter jobs by experience level (entry/associate/mid/senior/director).
    """
    
    def get(self, request, format=None):
        # Validate experience parameter
        experience = request.query_params.get('experience', '').strip().lower()
        is_valid, result = self._validate_filter_param('experience', experience)
        if not is_valid:
            return Response(
                {"error": result, "success": False},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set filters for the base class
        self.filters = {'experience': experience} if experience else {}
        
        # Call parent get method
        return super().get(request, format)


class JobsByCompany(BaseJobScraper):
    """
    Filter jobs by company name(s).
    """
    
    def get(self, request, format=None):
        # Validate company parameter
        company = request.query_params.get('company', '').strip()
        is_valid, result = self._validate_company_param(company)
        if not is_valid:
            return Response(
                {"error": result, "success": False},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set filters for the base class
        self.filters = {'company': result} if result else {}
        
        # Call parent get method
        return super().get(request, format)


class JobsByRemote(BaseJobScraper):
    """
    Filter jobs by workplace type (all/onsite/remote/hybrid).
    """
    
    def get(self, request, format=None):
        # Validate workplace parameter
        workplace = request.query_params.get('workplace', '').strip().lower()
        is_valid, result = self._validate_filter_param('workplace', workplace)
        if not is_valid:
            return Response(
                {"error": result, "success": False},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set filters for the base class
        self.filters = {'workplace': workplace} if workplace else {}
        
        # Call parent get method
        return super().get(request, format)


class JobsAdvanced(BaseJobScraper):
    """
    Advanced search with combined filters.
    """
    
    def get(self, request, format=None):
        filters = {}
        errors = []
        
        # Validate all filter parameters
        filter_params = {
            'date_posted': request.query_params.get('date_posted', '').strip().lower(),
            'job_type': request.query_params.get('job_type', '').strip().lower(),
            'experience': request.query_params.get('experience', '').strip().lower(),
            'workplace': request.query_params.get('workplace', '').strip().lower(),
        }
        
        # Validate standard filters
        for filter_name, value in filter_params.items():
            if value:
                is_valid, result = self._validate_filter_param(filter_name, value)
                if not is_valid:
                    errors.append(result)
                else:
                    filters[filter_name] = value
        
        # Validate company filter separately
        company = request.query_params.get('company', '').strip()
        if company:
            is_valid, result = self._validate_company_param(company)
            if not is_valid:
                errors.append(result)
            else:
                filters['company'] = result
        
        # Return validation errors if any
        if errors:
            return Response(
                {"error": "; ".join(errors), "success": False},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set filters for the base class
        self.filters = filters
        
        # Call parent get method
        return super().get(request, format)
