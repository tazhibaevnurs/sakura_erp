from django.urls import path

from . import views

app_name = "salary"

urlpatterns = [
    path("", views.SalaryListView.as_view(), name="list"),
    path("timesheet/", views.TimesheetView.as_view(), name="timesheet"),
    path("<str:period>/", views.SalaryPeriodView.as_view(), name="period"),
]
