from datetime import datetime, timedelta

from django import forms
from django.utils import timezone

from .models import Table, TableReservation
from .reservation_time import DEFAULT_DURATION, conflicting_reservations


class TableReservationForm(forms.ModelForm):
    reserved_date = forms.DateField(
        label="Дата",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    reserved_time_start = forms.TimeField(
        label="Время начала",
        widget=forms.TimeInput(
            attrs={"type": "time", "class": "form-control", "step": "900"}
        ),
    )
    reserved_time_end = forms.TimeField(
        label="Время окончания",
        required=False,
        widget=forms.TimeInput(
            attrs={"type": "time", "class": "form-control", "step": "900"}
        ),
    )

    class Meta:
        model = TableReservation
        fields = ["guest_name", "guest_phone", "guest_count", "comment"]
        labels = {
            "guest_name": "Имя гостя",
            "guest_phone": "Телефон",
            "guest_count": "Количество гостей",
            "comment": "Комментарий",
        }
        widgets = {
            "guest_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Иванов Иван"}
            ),
            "guest_phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "+996 …"}
            ),
            "guest_count": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "comment": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "День рождения, предзаказ…",
                }
            ),
        }

    def __init__(self, *args, table=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.table = table
        now = timezone.localtime()
        if not self.is_bound:
            start = now.replace(minute=0, second=0, microsecond=0)
            end = start + DEFAULT_DURATION
            self.fields["reserved_date"].initial = start.date()
            self.fields["reserved_time_start"].initial = start.time()
            self.fields["reserved_time_end"].initial = end.time()

    def clean_guest_count(self):
        count = self.cleaned_data["guest_count"]
        if self.table and count > self.table.capacity:
            raise forms.ValidationError(
                f"В кабинке только {self.table.capacity} мест. Укажите меньшее число гостей."
            )
        return count

    def _combine(self, date, time):
        return timezone.make_aware(
            datetime.combine(date, time),
            timezone.get_current_timezone(),
        )

    def clean(self):
        cleaned = super().clean()
        date = cleaned.get("reserved_date")
        t_start = cleaned.get("reserved_time_start")
        t_end = cleaned.get("reserved_time_end")
        if not (date and t_start and self.table):
            return cleaned

        start = self._combine(date, t_start)
        if t_end:
            end = self._combine(date, t_end)
            if t_end <= t_start:
                end = self._combine(date, t_end) + timedelta(days=1)
        else:
            end = start + DEFAULT_DURATION

        if end <= start:
            self.add_error("reserved_time_end", "Окончание должно быть позже начала.")
            return cleaned

        if start < timezone.now() - timedelta(minutes=5):
            self.add_error("reserved_date", "Нельзя забронировать на прошедшее время.")

        conflicts = conflicting_reservations(self.table, start, end)
        if conflicts.exists():
            c = conflicts.first()
            self.add_error(
                None,
                f"На это время уже есть бронь: {c.guest_name} "
                f"({timezone.localtime(c.reserved_for).strftime('%H:%M')}–"
                f"{timezone.localtime(c.reserved_until).strftime('%H:%M')}).",
            )

        now = timezone.now()
        if start <= now < end and self.table.active_order:
            self.add_error(
                None,
                "Сейчас по кабинке открыт заказ. Выберите другое время или закройте заказ.",
            )

        cleaned["reserved_for"] = start
        cleaned["reserved_until"] = end
        return cleaned


class QuickReserveTableForm(forms.Form):
    table = forms.ModelChoiceField(
        queryset=Table.objects.order_by("number"),
        label="Кабинка",
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class CalendarOrderForm(forms.ModelForm):
    """Финальный шаг календарного приёма: гость + скрытые дата, время, стол."""

    table_id = forms.IntegerField(widget=forms.HiddenInput)
    reserved_date = forms.DateField(widget=forms.HiddenInput)
    reserved_time_start = forms.TimeField(widget=forms.HiddenInput)
    reserved_time_end = forms.TimeField(
        required=False,
        widget=forms.HiddenInput,
    )

    class Meta:
        model = TableReservation
        fields = ["guest_name", "guest_phone", "guest_count", "comment"]
        labels = {
            "guest_name": "Имя гостя",
            "guest_phone": "Телефон",
            "guest_count": "Количество гостей",
            "comment": "Комментарий",
        }
        widgets = {
            "guest_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Иванов Иван"}
            ),
            "guest_phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "+996 …"}
            ),
            "guest_count": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "comment": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Пожелания, предзаказ…",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table = None

    def clean_table_id(self):
        table_id = self.cleaned_data["table_id"]
        try:
            self.table = Table.objects.get(pk=table_id)
        except Table.DoesNotExist as exc:
            raise forms.ValidationError("Кабинка не найдена.") from exc
        return table_id

    def clean_guest_count(self):
        count = self.cleaned_data["guest_count"]
        if self.table and count > self.table.capacity:
            raise forms.ValidationError(
                f"В кабинке только {self.table.capacity} мест."
            )
        return count

    def clean(self):
        cleaned = super().clean()
        day = cleaned.get("reserved_date")
        t_start = cleaned.get("reserved_time_start")
        t_end = cleaned.get("reserved_time_end")
        if not (day and t_start and self.table):
            return cleaned

        start = timezone.make_aware(
            datetime.combine(day, t_start),
            timezone.get_current_timezone(),
        )
        if t_end:
            end = timezone.make_aware(
                datetime.combine(day, t_end),
                timezone.get_current_timezone(),
            )
            if t_end <= t_start:
                end += timedelta(days=1)
        else:
            end = start + DEFAULT_DURATION

        if end <= start:
            self.add_error(None, "Время окончания должно быть позже начала.")

        if start < timezone.now() - timedelta(minutes=5):
            self.add_error(None, "Нельзя оформить заказ на прошедшее время.")

        conflicts = conflicting_reservations(self.table, start, end)
        if conflicts.exists():
            c = conflicts.first()
            self.add_error(
                None,
                f"На это время уже есть бронь: {c.guest_name} "
                f"({timezone.localtime(c.reserved_for).strftime('%H:%M')}–"
                f"{timezone.localtime(c.reserved_until).strftime('%H:%M')}).",
            )

        now = timezone.now()
        if start <= now < end and self.table.active_order:
            self.add_error(
                None,
                "Сейчас по кабинке открыт заказ. Выберите другое время или стол.",
            )

        cleaned["reserved_for"] = start
        cleaned["reserved_until"] = end
        return cleaned
