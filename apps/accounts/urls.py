from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.ChaihanaLoginView.as_view(), name="login"),
    path("logout/", views.ChaihanaLogoutView.as_view(), name="logout"),
]
