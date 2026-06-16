from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.ReportsDashboardView.as_view(), name="dashboard"),
    path("export/", views.ExportReportView.as_view(), name="export"),
]
