from django.urls import path

from . import views

app_name = "cash"

urlpatterns = [
    path("", views.CashTodayView.as_view(), name="today"),
    path("closed/", views.CashClosedListView.as_view(), name="closed_list"),
    path("expenses/", views.ExpenseListView.as_view(), name="expenses"),
    path("expenses/add/", views.AddExpenseView.as_view(), name="expense_add"),
    path("debts/", views.DebtListView.as_view(), name="debts"),
    path("debts/add/", views.AddDebtView.as_view(), name="debt_add"),
    path("<str:date>/", views.CashDayView.as_view(), name="day"),
]
