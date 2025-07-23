from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from django.core.cache import cache

class JobAPITests(TestCase):

    def setUp(self):
        # Clear the cache before each test to ensure isolation
        cache.clear()

    def test_api_endpoint_success_and_parses_data(self):
        """
        Ensure the API returns a 200 OK and contains a list of jobs.
        """
        url = reverse('job-list') + '?keyword=test&location=test'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('jobs', response.data)
        self.assertIsInstance(response.data['jobs'], list)

    def test_api_endpoint_missing_params(self):
        """
        Ensure the API endpoint returns a 400 Bad Request with missing parameters.
        """
        url = reverse('job-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_caching_is_used_on_second_request(self):
        """
        Ensure that a second identical request is served from the cache.
        """
        url = reverse('job-list') + '?keyword=caching&location=test'
        
        # First request - should be a live scrape
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data.get('source'), 'live')

        # Second request - should be served from cache
        response2 = self.client.get(url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.data.get('source'), 'cache')
