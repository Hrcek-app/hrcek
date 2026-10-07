from django.urls import path

from hrcek.entries import in_collections, labels, views

app_name = "entries"

urlpatterns = [
    path("", views.entry_list, name="list"),
    path("new/", views.entry_create, name="create"),
    path("<int:pk>/edit/", views.entry_edit, name="edit"),
    path("<int:pk>/delete/", views.entry_delete, name="delete"),
    path("<int:pk>/labels/add/", labels.label_add, name="label_add"),
    path("<int:pk>/labels/remove/", labels.label_remove, name="label_remove"),
    path(
        "<int:pk>/collections/add/",
        in_collections.collection_add,
        name="collection_add",
    ),
    path(
        "<int:pk>/collections/remove/",
        in_collections.collection_remove,
        name="collection_remove",
    ),
    path("<int:pk>/image/", views.entry_image, name="image"),
    path("fields/", views.field_list, name="fields"),
    path("fields/<int:pk>/edit/", views.field_edit, name="field_edit"),
    path("fields/<int:pk>/delete/", views.field_delete, name="field_delete"),
]
