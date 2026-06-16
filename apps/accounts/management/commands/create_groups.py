from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from apps.accounts.models import Role

ROLE_PERMISSIONS = {
    "owner": ["*"],
    "admin": [
        "view_order",
        "change_order",
        "delete_order",
        "view_dailycash",
        "change_dailycash",
        "add_expense",
        "change_expense",
        "view_expense",
        "view_debt",
        "change_debt",
        "add_debt",
        "view_employee",
        "change_employee",
        "view_shift",
        "change_shift",
        "add_shift",
        "view_salaryschema",
        "view_menuitem",
        "change_menuitem",
        "view_table",
        "change_table",
    ],
    "waiter": [
        "add_order",
        "change_order",
        "view_order",
        "view_menuitem",
        "view_table",
        "change_table",
    ],
    "cook": ["view_orderitem", "change_orderitem"],
    "baker": ["view_orderitem", "change_orderitem"],
    "salad": ["view_orderitem", "change_orderitem"],
    "bbq": ["view_orderitem", "change_orderitem"],
}

ROLES = [
    ("owner", "Владелец"),
    ("admin", "Администратор"),
    ("waiter", "Официант"),
    ("cook", "Повар"),
    ("baker", "Выпечка"),
    ("salad", "Салаты"),
    ("bbq", "Мангал"),
]


class Command(BaseCommand):
    help = "Создать роли, группы и права доступа"

    def handle(self, *args, **options):
        all_perms = Permission.objects.all()
        for slug, name in ROLES:
            group, _ = Group.objects.get_or_create(name=name)
            role, _ = Role.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "group": group},
            )
            if role.group_id != group.pk:
                role.group = group
                role.save()
            perms = ROLE_PERMISSIONS.get(slug, [])
            if "*" in perms:
                group.permissions.set(all_perms)
            else:
                group.permissions.set(Permission.objects.filter(codename__in=perms))
            self.stdout.write(self.style.SUCCESS(f"Role {slug} configured"))
