"""The addresses a collection is shared at.

Kept out of `urls.py` because these sit at the root — `/c/...` and
`/u/...` — rather than under `/collections/`, while still belonging to
the same URL namespace.
"""

from django.urls import path

from hrcek.collections import feeds, views

# Its own namespace: two includes cannot share one, and "shared"
# says what these addresses are for.
app_name = "shared"

urlpatterns = [
    path("c/<str:secret>/", views.unlisted_collection, name="unlisted"),
    path(
        "c/<str:secret>/feed/",
        feeds.UnlistedCollectionFeed(),
        name="unlisted_feed",
    ),
    path(
        "c/<str:secret>/got/<int:entry_pk>/",
        views.unlisted_got_it,
        name="unlisted_got_it",
    ),
    path(
        "c/<str:secret>/got/<int:entry_pk>/undo/",
        views.unlisted_got_it,
        {"undo": True},
        name="unlisted_undo",
    ),
    path(
        "u/<str:namespace>/<slug:slug>/",
        views.public_collection,
        name="public",
    ),
    path(
        "u/<str:namespace>/<slug:slug>/feed/",
        feeds.PublicCollectionFeed(),
        name="public_feed",
    ),
    path(
        "u/<str:namespace>/<slug:slug>/got/<int:entry_pk>/",
        views.public_got_it,
        name="public_got_it",
    ),
    path(
        "u/<str:namespace>/<slug:slug>/got/<int:entry_pk>/undo/",
        views.public_got_it,
        {"undo": True},
        name="public_undo",
    ),
]
