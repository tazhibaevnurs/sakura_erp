from django.urls import path

from . import views

app_name = "tables"

urlpatterns = [
    path("", views.FloorPlanView.as_view(), name="floor"),
    path("calendar-order/", views.CalendarOrderView.as_view(), name="calendar_order"),
    path("reservations/", views.ReservationListView.as_view(), name="reservation_list"),
    path("reservation/<int:pk>/", views.ReservationDetailView.as_view(), name="reservation_detail"),
    path(
        "reservation/<int:pk>/cancel/",
        views.CancelReservationView.as_view(),
        name="reservation_cancel",
    ),
    path(
        "reservation/<int:pk>/arrive/",
        views.ArriveReservationView.as_view(),
        name="reservation_arrive",
    ),
    path(
        "reservation/<int:pk>/preorder/",
        views.PreorderReservationView.as_view(),
        name="reservation_preorder",
    ),
    path("<int:pk>/", views.TableHubView.as_view(), name="booth"),
    path("<int:pk>/reserve/", views.ReserveTableView.as_view(), name="reserve"),
    path("api/status/", views.TableStatusAPIView.as_view(), name="api_status"),
]
