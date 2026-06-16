from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.OrderListView.as_view(), name="list"),
    path("new/<int:table_id>/", views.CreateOrderView.as_view(), name="create"),
    path("<int:pk>/", views.OrderDetailView.as_view(), name="detail"),
    path("<int:pk>/pay/", views.PayOrderView.as_view(), name="pay"),
    path("<int:pk>/cancel/", views.CancelOrderView.as_view(), name="cancel"),
    path("takeaway/", views.TakeawayOrderView.as_view(), name="takeaway"),
    path("delivery/", views.DeliveryOrderView.as_view(), name="delivery"),
    path("api/item/<int:pk>/cooking/", views.OrderItemCookingAPIView.as_view(), name="item_cooking"),
    path("api/item/<int:pk>/ready/", views.OrderItemReadyAPIView.as_view(), name="item_ready"),
]
