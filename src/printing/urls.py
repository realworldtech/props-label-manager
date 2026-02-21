from django.urls import path

from printing import views

urlpatterns = [
    path("designer/<int:pk>/", views.designer, name="label-designer"),
    path("designer/<int:pk>/save/", views.designer_save, name="label-designer-save"),
    path(
        "designer/<int:pk>/preview/",
        views.designer_preview,
        name="label-designer-preview",
    ),
]
