from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import JobViewSet, health

router = DefaultRouter(trailing_slash=True)
router.include_root_view = False
router.register("jobs", JobViewSet, basename="job")

urlpatterns = [path("health/", health, name="health"), *router.urls]
