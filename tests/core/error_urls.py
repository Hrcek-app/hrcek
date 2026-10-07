"""The project's addresses plus one that always fails, so the 500 page
can be reached the way a real fault reaches it."""

from django.urls import path

from hrcek.urls import urlpatterns as project_urlpatterns


def _boom(request):
    raise RuntimeError("a deliberate fault for the 500 page test")


urlpatterns = [*project_urlpatterns, path("boom/", _boom)]
