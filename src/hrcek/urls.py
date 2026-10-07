from django.contrib import admin
from django.urls import include, path

from hrcek.accounts import views as account_views
from hrcek.api import api
from hrcek.core import views as core_views

urlpatterns = [
    path("", account_views.landing, name="landing"),
    # Django's set_language view: the footer's language switcher posts
    # here, and the choice lands in the language cookie.
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("accounts/", include("hrcek.accounts.urls")),
    path("entries/", include("hrcek.entries.urls")),
    path("collections/", include("hrcek.collections.urls")),
    # Shared collection pages sit at the root, not under
    # /collections/, so a shared link stays short.
    path("", include("hrcek.collections.shared_urls")),
    path("api/", api.urls),
    # A superuser's way to see the error pages; a 404 for anyone else.
    path("errors/<int:code>/", core_views.error_preview, name="error_preview"),
]
