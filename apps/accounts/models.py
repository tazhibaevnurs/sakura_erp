from django.contrib.auth.models import Group, User
from django.db import models


class Role(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    group = models.OneToOneField(Group, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Роль"
        verbose_name_plural = "Роли"

    def __str__(self):
        return self.name


class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    kitchen_section = models.ForeignKey(
        "orders.KitchenSection",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    phone = models.CharField(max_length=20, blank=True)
    hired_date = models.DateField()
    salary_schema = models.ForeignKey(
        "salary.SalarySchema",
        on_delete=models.PROTECT,
    )
    advance_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"

    def __str__(self):
        return self.user.get_full_name() or self.user.username
