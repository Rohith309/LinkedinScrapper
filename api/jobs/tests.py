from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from django.core.cache import cache
from unittest.mock import patch
import os

# Build the path to the fixture file
FIXTURE_PATH = os.path.join(os.path.dirname(__file__), 'fixtures', 'sample_response.html')

# Load the fixture content
with open(FIXTURE_PATH, 'r', encoding='utf-8') as f:
    HTML_FIXTURE = f.read()

# This is the function we will mock in our tests
TARGET_SCRAPE_FUNCTION = 'jobs.views.JobList.scrape_linkedin'

@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}}) # Disable cache for most tests
class JobAPITests(TestCase):

    @patch(TARGET_SCRAPE_FUNCTION, return_value=HTML_FIXTURE)
    def test_api_parses_data_correctly(self, mock_scrape):
        """
        Ensure the API correctly parses the HTML fixture.
        """
        url = reverse('job-list') + '?keyword=test&location=test'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('jobs', response.data)
        self.assertEqual(len(response.data['jobs']), 2)
        self.assertEqual(response.data['jobs'][0]['title'], 'Software Engineer')
        self.assertEqual(response.data['jobs'][1]['company'], 'Facebook')

    def test_api_endpoint_missing_params(self):
        """
        Ensure the API returns a 400 Bad Request if params are missing.
        """
        url = reverse('job-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}) # Enable cache for this specific test class
class CachingTests(TestCase):

    def setUp(self):
        cache.clear()

    @patch(TARGET_SCRAPE_FUNCTION, return_value=HTML_FIXTURE)
    def test_caching_is_used_on_second_request(self, mock_scrape):
        """
        Ensure a second identical request is served from the cache.
        """
        url = reverse('job-list') + '?keyword=caching&location=test'
        
        # First request - should call the mock scraper
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        mock_scrape.assert_called_once()

        # Second request - should NOT call the mock scraper again
        response2 = self.client.get(url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        mock_scrape.assert_called_once() # Assert it was not called a second time
