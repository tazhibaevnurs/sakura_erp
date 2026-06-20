from django.db.models import Prefetch

from .models import MenuCategory, MenuItem


def orderable_items_queryset():
    return MenuItem.objects.filter(is_available=True, is_stopped=False).order_by(
        "order", "name"
    )


def get_menu_categories():
    return (
        MenuCategory.objects.prefetch_related(
            Prefetch("items", queryset=orderable_items_queryset())
        )
        .order_by("order", "name")
    )


def menu_categories_json():
    data = []
    for cat in get_menu_categories():
        items = [
            {
                "id": item.pk,
                "name": item.name,
                "price": str(item.price),
                "unit": item.get_unit_display(),
                "unit_code": item.unit,
                "description": item.description,
            }
            for item in cat.items.all()
        ]
        if items:
            data.append(
                {
                    "id": cat.pk,
                    "name": cat.name,
                    "kitchen_section": cat.kitchen_section.name,
                    "items": items,
                }
            )
    return data
