import json

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from printing.models import ElementType, LabelElement, LabelTemplate, TextAlign


@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", password="testpass")


@pytest.fixture
def template(db):
    t = LabelTemplate.objects.create(name="Test Label", width_mm=62, height_mm=29)
    LabelElement.objects.create(
        template=t,
        element_type=ElementType.ASSET_NAME,
        x_mm=5,
        y_mm=2,
        width_mm=20,
        height_mm=5,
        font_size_pt=10,
        text_align=TextAlign.LEFT,
        sort_order=0,
    )
    return t


@pytest.fixture
def auth_client(user):
    client = Client()
    client.login(username="testuser", password="testpass")
    return client


@pytest.mark.django_db
class TestDesignerView:
    def test_requires_login(self, template):
        client = Client()
        url = reverse("label-designer", kwargs={"pk": template.pk})
        response = client.get(url)
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_returns_200(self, auth_client, template):
        url = reverse("label-designer", kwargs={"pk": template.pk})
        response = auth_client.get(url)
        assert response.status_code == 200
        assert b"fabric" in response.content.lower()

    def test_contains_template_data(self, auth_client, template):
        url = reverse("label-designer", kwargs={"pk": template.pk})
        response = auth_client.get(url)
        assert template.name.encode() in response.content

    def test_404_for_missing_template(self, auth_client):
        url = reverse("label-designer", kwargs={"pk": 9999})
        response = auth_client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestDesignerSave:
    def test_requires_login(self, template):
        client = Client()
        url = reverse("label-designer-save", kwargs={"pk": template.pk})
        response = client.post(
            url,
            data=json.dumps({"template": {}, "elements": []}),
            content_type="application/json",
        )
        assert response.status_code == 302

    def test_requires_post(self, auth_client, template):
        url = reverse("label-designer-save", kwargs={"pk": template.pk})
        response = auth_client.get(url)
        assert response.status_code == 405

    def test_save_updates_elements(self, auth_client, template):
        url = reverse("label-designer-save", kwargs={"pk": template.pk})
        payload = {
            "template": {
                "name": "Updated Label",
            },
            "elements": [
                {
                    "element_type": "barcode_128",
                    "x_mm": 1,
                    "y_mm": 2,
                    "width_mm": 30,
                    "height_mm": 8,
                    "rotation": 0,
                    "sort_order": 0,
                },
                {
                    "element_type": "asset_name",
                    "x_mm": 5,
                    "y_mm": 12,
                    "width_mm": 20,
                    "height_mm": 4,
                    "rotation": 0,
                    "font_name": "helvetica",
                    "font_size_pt": 12,
                    "font_bold": True,
                    "text_align": "center",
                    "sort_order": 1,
                },
            ],
        }
        response = auth_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

        template.refresh_from_db()
        assert template.name == "Updated Label"
        assert template.elements.count() == 2

        el = template.elements.order_by("sort_order").first()
        assert el.element_type == "barcode_128"
        assert float(el.x_mm) == 1.0

    def test_save_invalid_json(self, auth_client, template):
        url = reverse("label-designer-save", kwargs={"pk": template.pk})
        response = auth_client.post(
            url,
            data="not json",
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "error" in response.json()

    def test_save_empty_elements(self, auth_client, template):
        url = reverse("label-designer-save", kwargs={"pk": template.pk})
        payload = {"template": {}, "elements": []}
        response = auth_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 200
        template.refresh_from_db()
        assert template.elements.count() == 0


@pytest.mark.django_db
class TestDesignerPreview:
    def test_requires_login(self, template):
        client = Client()
        url = reverse("label-designer-preview", kwargs={"pk": template.pk})
        response = client.get(url)
        assert response.status_code == 302

    def test_returns_pdf(self, auth_client, template):
        url = reverse("label-designer-preview", kwargs={"pk": template.pk})
        response = auth_client.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert response.content[:5] == b"%PDF-"

    def test_404_for_missing_template(self, auth_client):
        url = reverse("label-designer-preview", kwargs={"pk": 9999})
        response = auth_client.get(url)
        assert response.status_code == 404
