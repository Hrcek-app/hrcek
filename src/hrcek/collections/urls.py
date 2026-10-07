from django.urls import path

from hrcek.collections import feeds, views

app_name = "collections"

urlpatterns = [
    path("", views.collection_list, name="list"),
    path("new/", views.collection_create, name="create"),
    path("<int:pk>/", views.collection_detail, name="detail"),
    path(
        "<int:pk>/feed/",
        feeds.PrivateCollectionFeed(),
        name="feed",
    ),
    path("<int:pk>/edit/", views.collection_edit, name="edit"),
    path("<int:pk>/delete/", views.collection_delete, name="delete"),
    path(
        "<int:pk>/remove/<int:entry_pk>/",
        views.collection_remove_entry,
        name="remove_entry",
    ),
    path(
        "<int:pk>/got/<int:entry_pk>/put-back/",
        views.collection_put_back,
        name="put_back",
    ),
]
