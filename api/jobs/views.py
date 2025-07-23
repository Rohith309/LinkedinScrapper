from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.core.cache import cache
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time

class JobList(APIView):
    """
    API endpoint that scrapes and returns a list of jobs from LinkedIn.
    """
    def scrape_linkedin(self, url):
        """
        Launches a headless Chrome browser to scrape the given URL.
        Returns the page's HTML content.
        """
        # Setup Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # Add proxy support
        if settings.PROXY_HOST and settings.PROXY_PORT:
            proxy_url = f"{settings.PROXY_HOST}:{settings.PROXY_PORT}"
            chrome_options.add_argument(f'--proxy-server={proxy_url}')

        # Initialize WebDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        driver.get(url)
        time.sleep(5)  # Wait for dynamic content to load

        html = driver.page_source
        driver.quit()
        return html

    def get(self, request, format=None):
        """
        Scrape LinkedIn for job listings based on query parameters.
        """
        keyword = request.query_params.get('keyword')
        location = request.query_params.get('location')

        if not keyword or not location:
            return Response(
                {"error": "Missing required parameters: keyword and location"},
                status=status.HTTP_400_BAD_REQUEST
            )

        cache_key = f"jobs_search_{keyword.lower()}_{location.lower()}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response({"jobs": cached_data, "source": "cache"})

        try:
            url = f"https://www.linkedin.com/jobs/search/?keywords={keyword}&location={location}"
            html = self.scrape_linkedin(url)

            soup = BeautifulSoup(html, 'html.parser')
            job_cards = soup.find_all('div', class_='base-card')

            jobs_list = []
            for card in job_cards:
                try:
                    title_elem = card.find('h3', class_='base-search-card__title')
                    company_elem = card.find('h4', class_='base-search-card__subtitle')
                    location_elem = card.find('span', class_='job-search-card__location')
                    url_elem = card.find('a', class_='base-card__full-link')
                    
                    # Skip if essential elements are not found
                    if not all([title_elem, company_elem, location_elem, url_elem]):
                        continue

                    job_data = {
                        'title': title_elem.get_text(strip=True),
                        'company': company_elem.get_text(strip=True),
                        'location': location_elem.get_text(strip=True),
                        'url': url_elem['href'],
                        'date_posted': '', # LinkedIn often hides this behind interactions
                        'snippet': '' # Snippet is also often loaded on interaction
                    }
                    jobs_list.append(job_data)
                except Exception:
                    # Ignore cards that fail to parse to avoid a single bad card failing the whole request
                    continue
            
            # Cache the results before returning
            cache.set(cache_key, jobs_list)
            
            return Response({"jobs": jobs_list, "source": "live"})

        except Exception as e:
            return Response(
                {"error": f"An error occurred during scraping or parsing: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY
            )
