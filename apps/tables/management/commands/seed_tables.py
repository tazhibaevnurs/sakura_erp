from django.core.management.base import BaseCommand

from apps.tables.models import Table


class Command(BaseCommand):
    help = "Создать 20 столиков на карте зала"

    def handle(self, *args, **options):
        positions = [
            (40, 40), (160, 40), (280, 40), (400, 40), (520, 40),
            (40, 160), (160, 160), (280, 160), (400, 160), (520, 160),
            (40, 280), (160, 280), (280, 280), (400, 280), (520, 280),
            (100, 400), (220, 400), (340, 400), (460, 400), (580, 400),
        ]
        for i, (x, y) in enumerate(positions, start=1):
            Table.objects.update_or_create(
                number=i,
                defaults={
                    "position_x": x,
                    "position_y": y,
                    "capacity": 4 if i <= 15 else 6,
                    "type": Table.TableType.BOOTH if i % 5 == 0 else Table.TableType.TABLE,
                    "status": Table.Status.FREE,
                },
            )
        self.stdout.write(self.style.SUCCESS("20 tables created"))
