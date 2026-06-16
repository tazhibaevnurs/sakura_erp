from datetime import date, timedelta

from django.http import FileResponse
from django.views.generic import FormView, TemplateView

from apps.core.mixins import RoleRequiredMixin

from .exporters import export_period_excel
from .forms import ExportReportForm, ReportFilterForm
from .services import get_daily_summary, get_period_report


class ReportsDashboardView(RoleRequiredMixin, TemplateView):
    template_name = "reports/dashboard.html"
    allowed_roles = ["owner", "admin"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        week_ago = today - timedelta(days=6)
        ctx["today"] = get_daily_summary(today)
        ctx["period"] = get_period_report(week_ago, today)
        ctx["filter_form"] = ReportFilterForm(initial={"date_from": week_ago, "date_to": today})
        return ctx

    def post(self, request, *args, **kwargs):
        form = ReportFilterForm(request.POST)
        if form.is_valid():
            return self.render_to_response(
                self.get_context_data(
                    period=get_period_report(
                        form.cleaned_data["date_from"],
                        form.cleaned_data["date_to"],
                    ),
                    filter_form=form,
                )
            )
        return self.get(request, *args, **kwargs)


class ExportReportView(RoleRequiredMixin, FormView):
    template_name = "reports/export.html"
    form_class = ExportReportForm
    allowed_roles = ["owner", "admin"]

    def form_valid(self, form):
        output = export_period_excel(
            form.cleaned_data["date_from"],
            form.cleaned_data["date_to"],
        )
        filename = f"report_{form.cleaned_data['date_from']}_{form.cleaned_data['date_to']}.xlsx"
        return FileResponse(
            output,
            as_attachment=True,
            filename=filename,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
