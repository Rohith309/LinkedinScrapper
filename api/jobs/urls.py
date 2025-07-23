from django.urls import path
from . import views

urlpatterns = [
    # Original endpoint
    path('jobs/', views.JobList.as_view(), name='job-list'),
    
    # Specialized filter endpoints
    path('jobs/date-posted/', views.JobsByDatePosted.as_view(), name='jobs-by-date'),
    path('jobs/type/', views.JobsByType.as_view(), name='jobs-by-type'),
    path('jobs/experience/', views.JobsByExperience.as_view(), name='jobs-by-experience'),
    path('jobs/company/', views.JobsByCompany.as_view(), name='jobs-by-company'),
    path('jobs/remote/', views.JobsByRemote.as_view(), name='jobs-by-remote'),
    
    # Advanced combined filters endpoint
    path('jobs/advanced/', views.JobsAdvanced.as_view(), name='jobs-advanced'),
]
