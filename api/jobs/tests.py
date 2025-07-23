from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from django.core.cache import cache
from unittest.mock import patch, MagicMock
from urllib.parse import quote_plus
import os

# Build the path to the fixture file
FIXTURE_PATH = os.path.join(os.path.dirname(__file__), 'fixtures', 'sample_response.html')

# Load the fixture content
with open(FIXTURE_PATH, 'r', encoding='utf-8') as f:
    HTML_FIXTURE = f.read()

# Mocks will target the function that creates the selenium driver
TARGET_CREATE_DRIVER_FUNCTION = 'jobs.views.JobList._create_driver'

@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class JobApiAndCacheTests(TestCase):

    def setUp(self):
        # Clear cache before each test to ensure isolation
        cache.clear()
        self.url = reverse('job-list')

    def test_missing_parameters(self):
        """Test API returns 400 if parameters are missing."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    @patch(TARGET_CREATE_DRIVER_FUNCTION)
    def test_successful_scrape_populates_caches(self, mock_create_driver):
        """Test a successful live scrape populates both fresh and stale caches."""
        mock_driver = MagicMock()
        mock_driver.page_source = HTML_FIXTURE
        mock_create_driver.return_value = mock_driver
        
        keyword, location = 'dev', 'usa'
        response = self.client.get(self.url, {'keyword': keyword, 'location': location})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['source'], 'live')
        # Called once for the main page, and once for each of the 5 job details pages
        self.assertEqual(mock_create_driver.call_count, 6)

        # Verify that both caches are now populated
        cache_key = f"jobs_{quote_plus(keyword)}_{quote_plus(location)}"
        stale_cache_key = f"{cache_key}:stale"
        self.assertIsNotNone(cache.get(cache_key))
        self.assertIsNotNone(cache.get(stale_cache_key))

    @patch(TARGET_CREATE_DRIVER_FUNCTION)
    def test_second_request_serves_from_fresh_cache(self, mock_create_driver):
        """Test that a second identical request is served from the fresh cache."""
        mock_driver = MagicMock()
        mock_driver.page_source = HTML_FIXTURE
        mock_create_driver.return_value = mock_driver
        keyword, location = 'caching', 'test'
        
        # First request - should call the mock scraper and populate cache
        self.client.get(self.url, {'keyword': keyword, 'location': location})
        self.assertEqual(mock_create_driver.call_count, 6)

        # Second request - should NOT call the mock scraper again
        response = self.client.get(self.url, {'keyword': keyword, 'location': location})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['source'], 'cache')
        self.assertEqual(mock_create_driver.call_count, 6) # Assert it was not called again

    @patch(TARGET_CREATE_DRIVER_FUNCTION, side_effect=Exception("Scraping failed!"))
    def test_stale_cache_is_used_on_live_scrape_failure(self, mock_create_driver):
        """
        Test that stale cache is served if the fresh cache is empty and live scrape fails.
        """
        keyword, location = 'stale', 'test'
        cache_key = f"jobs_{quote_plus(keyword)}_{quote_plus(location)}"
        stale_cache_key = f"{cache_key}:stale"
        stale_data = [{'title': 'Old Job From Stale Cache', 'company': 'TestCorp'}]

        # Manually populate the stale cache to simulate a previous successful run
        cache.set(stale_cache_key, stale_data, timeout=3600)
        self.assertIsNone(cache.get(cache_key)) # Ensure fresh cache is empty

        # Make the request that will trigger a failed live scrape
        response = self.client.get(self.url, {'keyword': keyword, 'location': location})

        # Assert that the stale data was returned
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['source'], 'stale_cache_on_error')
        self.assertEqual(response.data['jobs'], stale_data)
        self.assertIn('error_message', response.data)
        mock_create_driver.assert_called_once() # Ensure a live scrape was attempted
