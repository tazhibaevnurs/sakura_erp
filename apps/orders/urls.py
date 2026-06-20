from django.urls import path

from . import api_views, views

app_name = "orders"

urlpatterns = [
    path("", views.OrderListView.as_view(), name="list"),
    path("new/<int:table_id>/", views.CreateOrderView.as_view(), name="create"),
    path("<int:pk>/", views.OrderDetailView.as_view(), name="detail"),
    path("<int:pk>/pay/", views.PayOrderView.as_view(), name="pay"),
    path("<int:pk>/cancel/", views.CancelOrderView.as_view(), name="cancel"),
    path("takeaway/", views.TakeawayOrderView.as_view(), name="takeaway"),
    path("delivery/", views.DeliveryOrderView.as_view(), name="delivery"),
    path("api/menu/", api_views.MenuAPIView.as_view(), name="api_menu"),
    path("api/takeaway/", api_views.TakeawayOrderAPIView.as_view(), name="api_takeaway"),
    path("api/takeaway/list/", api_views.TakeawayOrdersAPIView.as_view(), name="api_takeaway_list"),
    path("api/delivery/", api_views.DeliveryOrderAPIView.as_view(), name="api_delivery"),
    path("api/delivery/list/", api_views.DeliveryOrdersAPIView.as_view(), name="api_delivery_list"),
    path("api/item/<int:pk>/cooking/", views.OrderItemCookingAPIView.as_view(), name="item_cooking"),
    path("api/item/<int:pk>/ready/", views.OrderItemReadyAPIView.as_view(), name="item_ready"),
]
