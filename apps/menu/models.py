from django.db import models


class MenuCategory(models.Model):
    name = models.CharField(max_length=100)
    kitchen_section = models.ForeignKey(
        "orders.KitchenSection",
        on_delete=models.PROTECT,
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Категория меню"
        verbose_name_plural = "Категории меню"

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    class Unit(models.TextChoices):
        KG = "kg", "кг"
        PCS = "pcs", "шт"

    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(
        max_length=10,
        choices=Unit.choices,
        default=Unit.PCS,
        verbose_name="Единица измерения",
    )
    description = models.TextField(blank=True)
    is_available = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Блюдо"
        verbose_name_plural = "Блюда"

    def __str__(self):
        return self.name
