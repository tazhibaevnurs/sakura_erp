import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.assistant.models import AssistantChatLog

User = get_user_model()


@pytest.fixture
def owner_client(db, client):
    from django.contrib.auth.models import Group
    from apps.accounts.models import Employee, Role
    from apps.salary.models import SalarySchema

    group, _ = Group.objects.get_or_create(name="Владелец-dialogs")
    role, _ = Role.objects.get_or_create(
        slug="owner",
        defaults={"name": "Владелец", "group": group},
    )
    schema, _ = SalarySchema.objects.get_or_create(
        name="Тест dialogs",
        defaults={"percent_of_revenue": 0, "fixed_per_shift": 0, "fixed_monthly": 0},
    )
    user = User.objects.create_user("dialog_owner", password="x")
    Employee.objects.create(
        user=user,
        role=role,
        hired_date="2026-01-01",
        salary_schema=schema,
    )
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_dialog_list_page(owner_client):
    AssistantChatLog.objects.create(
        channel=AssistantChatLog.Channel.TELEGRAM,
        external_user_id="999",
        user_message="Привет",
        assistant_reply="Здравствуйте!",
    )
    url = reverse("assistant:dialogs")
    response = owner_client.get(url)
    assert response.status_code == 200
    assert "Привет" in response.content.decode()


@pytest.mark.django_db
def test_dialog_detail_page(owner_client):
    AssistantChatLog.objects.create(
        channel=AssistantChatLog.Channel.WHATSAPP,
        external_user_id="996500000000",
        user_message="Меню",
        assistant_reply="Вот меню",
    )
    AssistantChatLog.objects.create(
        channel=AssistantChatLog.Channel.WHATSAPP,
        external_user_id="996500000000",
        user_message="Плов",
        assistant_reply="Принято",
    )
    url = reverse(
        "assistant:dialog_detail",
        kwargs={"channel": "whatsapp", "external_user_id": "996500000000"},
    )
    response = owner_client.get(url)
    content = response.content.decode()
    assert response.status_code == 200
    assert "Меню" in content
    assert "Принято" in content
