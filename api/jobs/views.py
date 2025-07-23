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
import re
from urllib.parse import quote_plus

# Configure logging
logger = logging.getLogger(__name__)

class JobList(APIView):
    """
    API endpoint that scrapes and returns a list of jobs from LinkedIn.
    Supports parallel scraping of job details with robust error handling.
    """
    
    MAX_JOBS_PER_REQUEST = 25  # Limit to prevent abuse
    DETAIL_PAGE_TIMEOUT = 10   # Seconds to wait for detail pages
    SEARCH_PAGE_TIMEOUT = 15   # Seconds to wait for search page



    def _create_driver(self):
        """Create a Chrome driver with optimized settings."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        if settings.PROXY_HOST and settings.PROXY_PORT:
            proxy_url = f"{settings.PROXY_HOST}:{settings.PROXY_PORT}"
            chrome_options.add_argument(f'--proxy-server={proxy_url}')
            
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
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
        
        # Check cache first
        cache_key = f"jobs_{quote_plus(keyword)}_{quote_plus(location)}"
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
            
            # Build search URL with proper encoding
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(keyword)}&location={quote_plus(location)}"
            logger.debug(f"Fetching search URL: {search_url}")
            
            driver.get(search_url)
            
            # Wait for job cards to load
            wait = WebDriverWait(driver, 10)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.base-card')))
            except TimeoutException:
                logger.warning("No job cards found or page took too long to load")
            
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
            failed_details = 0
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_job = {executor.submit(self.scrape_job_details, job): job for job in initial_jobs}
                
                for future in as_completed(future_to_job):
                    try:
                        result = future.result(timeout=self.DETAIL_PAGE_TIMEOUT + 5)
                        enriched_jobs.append(result)
                    except Exception as e:
                        failed_details += 1
                        logger.warning(f"Failed to get job details: {e}")
                        # Add the original job data without enrichment
                        original_job = future_to_job[future]
                        enriched_jobs.append(original_job)
            
            # Cache results with two different TTLs
            cache.set(cache_key, enriched_jobs, timeout=600)  # 10 minutes for fresh data
            cache.set(stale_cache_key, enriched_jobs, timeout=86400) # 24 hours for stale fallback
            
            processing_time = round(time.time() - start_time, 2)
            logger.info(f"Completed job search in {processing_time}s. Found {len(enriched_jobs)} jobs, {failed_details} detail failures")
            
            return Response({
                "success": True,
                "jobs": enriched_jobs,
                "source": "live",
                "count": len(enriched_jobs),
                "processing_time": processing_time,
                "detail_failures": failed_details
            })
            
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
