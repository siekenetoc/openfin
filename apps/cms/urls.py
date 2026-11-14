from django.urls import path

from . import views

app_name = "cms"

urlpatterns = [
    path("page/<slug:slug>/", views.page_detail, name="page_detail"),
    path("cms/", views.editor_list, name="editor_list"),
    path("cms/new/", views.editor_edit, name="editor_new"),
    path("cms/<int:pk>/edit/", views.editor_edit, name="editor_edit"),
    path("cms/upload-image/", views.upload_image, name="upload_image"),
]
