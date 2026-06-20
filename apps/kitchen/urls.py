from django.urls import path

from . import views

app_name = "kitchen"

urlpatterns = [
    path("<slug:section_slug>/", views.KitchenDisplayView.as_view(), name="display"),
    path(
        "<slug:section_slug>/api/orders/",
        views.KitchenOrdersHistoryAPIView.as_view(),
        name="api_orders",
    ),
    path(
        "<slug:section_slug>/completed/",
        views.KitchenCompletedOrdersView.as_view(),
        name="completed_orders",
    ),
    path(
        "<slug:section_slug>/order/<int:pk>/",
        views.KitchenOrderDetailView.as_view(),
        name="order_detail",
    ),
]
