from django.urls import path

from . import views

app_name = "menu"

urlpatterns = [
    path("", views.MenuManageView.as_view(), name="manage"),
    path("item/add/", views.MenuItemCreateView.as_view(), name="item_add"),
    path("item/<int:pk>/edit/", views.MenuItemUpdateView.as_view(), name="item_edit"),
    path("item/<int:pk>/stop/", views.ToggleStopListView.as_view(), name="item_stop"),
]
