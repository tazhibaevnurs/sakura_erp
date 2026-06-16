from django.urls import path

from . import views

urlpatterns = [
    path("", views.StaffListView.as_view(), name="staff_list"),
    path("add/", views.AddEmployeeView.as_view(), name="staff_add"),
    path("<int:pk>/", views.EmployeeDetailView.as_view(), name="staff_detail"),
]
