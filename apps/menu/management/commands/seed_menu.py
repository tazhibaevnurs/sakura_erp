from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.menu.models import MenuCategory, MenuItem
from apps.orders.models import KitchenSection

MENU = {
    "hot": ("Горячий цех", [
        ("Супы", [("Шурпа", 35), ("Лагман", 40)]),
        ("Горячее", [("Плов", 45), ("Манты", 38), ("Гуляш", 42)]),
    ]),
    "bbq": ("Мангал", [
        ("Шашлык", [("Баранина", 55), ("Курица", 35), ("Люля-кебаб", 30)]),
    ]),
    "salad": ("Салаты", [
        ("Салаты", [("Оливье", 25), ("Греческий", 28), ("Ачичук", 15)]),
    ]),
    "baker": ("Выпечка", [
        ("Выпечка", [("Самса", 12), ("Лепёшка", 8), ("Хачапури", 22)]),
    ]),
    "drinks": ("Напитки", [
        ("Чай", [("Зелёный чай", 10), ("Чёрный чай", 10), ("Сабза", 15)]),
        ("Напитки", [("Компот", 12), ("Айран", 14)]),
    ]),
}


class Command(BaseCommand):
    help = "Загрузить тестовое меню"

    def handle(self, *args, **options):
        order = 0
        for slug, (section_name, categories) in MENU.items():
            section, _ = KitchenSection.objects.get_or_create(
                slug=slug,
                defaults={"name": section_name},
            )
            for cat_name, items in categories:
                order += 1
                cat, _ = MenuCategory.objects.get_or_create(
                    name=cat_name,
                    kitchen_section=section,
                    defaults={"order": order},
                )
                for idx, (item_name, price) in enumerate(items):
                    MenuItem.objects.update_or_create(
                        category=cat,
                        name=item_name,
                        defaults={
                            "price": Decimal(str(price)),
                            "order": idx,
                            "is_available": True,
                        },
                    )
        self.stdout.write(self.style.SUCCESS("Menu seeded"))
