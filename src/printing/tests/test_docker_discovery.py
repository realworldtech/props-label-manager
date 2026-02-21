from unittest.mock import MagicMock, patch

import pytest

from printing.models import LabelTemplate, Printer, PrinterType


def _make_container(name, labels, env_list):
    container = MagicMock()
    container.name = name
    container.labels = labels
    container.attrs = {"Config": {"Env": env_list}}
    return container


@pytest.mark.django_db
class TestDockerDiscovery:
    @patch("printing.services.docker_discovery.docker")
    def test_discovers_container_creates_printer(self, mock_docker):
        container = _make_container(
            "dymo-5xl",
            {"props.printer": "true", "props.printer.name": "DYMO LabelWriter 5XL"},
            ["PRINTER_NAME=DYMO-5XL", "PRINTER_URI=socket://10.0.0.50:9100"],
        )
        mock_docker.from_env.return_value.containers.list.return_value = [container]

        from printing.services.docker_discovery import discover_printers

        results = discover_printers()

        assert len(results) == 1
        assert results[0]["name"] == "DYMO LabelWriter 5XL"
        assert results[0]["cups_queue"] == "DYMO-5XL"
        assert results[0]["cups_server"] == "dymo-5xl:631"
        assert results[0]["created"] is True

        printer = Printer.objects.get(cups_queue="DYMO-5XL")
        assert printer.printer_type == PrinterType.CUPS
        assert printer.cups_server == "dymo-5xl:631"
        assert printer.name == "DYMO LabelWriter 5XL"
        assert printer.is_active is True

    @patch("printing.services.docker_discovery.docker")
    def test_idempotent_second_run(self, mock_docker):
        container = _make_container(
            "dymo-5xl",
            {"props.printer": "true", "props.printer.name": "DYMO LabelWriter 5XL"},
            ["PRINTER_NAME=DYMO-5XL"],
        )
        mock_docker.from_env.return_value.containers.list.return_value = [container]

        from printing.services.docker_discovery import discover_printers

        results1 = discover_printers()
        results2 = discover_printers()

        assert results1[0]["created"] is True
        assert results2[0]["created"] is False
        assert Printer.objects.filter(cups_queue="DYMO-5XL").count() == 1

    @patch("printing.services.docker_discovery.docker")
    def test_updates_cups_server_on_container_name_change(self, mock_docker):
        container1 = _make_container(
            "dymo-old",
            {"props.printer": "true"},
            ["PRINTER_NAME=DYMO-5XL"],
        )
        mock_docker.from_env.return_value.containers.list.return_value = [container1]

        from printing.services.docker_discovery import discover_printers

        discover_printers()

        container2 = _make_container(
            "dymo-new",
            {"props.printer": "true"},
            ["PRINTER_NAME=DYMO-5XL"],
        )
        mock_docker.from_env.return_value.containers.list.return_value = [container2]

        discover_printers()

        printer = Printer.objects.get(cups_queue="DYMO-5XL")
        assert printer.cups_server == "dymo-new:631"

    @patch("printing.services.docker_discovery.docker")
    def test_assigns_default_template_on_creation_only(self, mock_docker):
        template = LabelTemplate.objects.create(
            name="Default", width_mm=62, height_mm=62, is_default=True
        )
        container = _make_container(
            "dymo-5xl",
            {"props.printer": "true"},
            ["PRINTER_NAME=DYMO-5XL"],
        )
        mock_docker.from_env.return_value.containers.list.return_value = [container]

        from printing.services.docker_discovery import discover_printers

        results = discover_printers()
        assert results[0]["created"] is True

        printer = Printer.objects.get(cups_queue="DYMO-5XL")
        assert printer.default_template == template

        # Second run should not overwrite template even if we clear it
        printer.default_template = None
        printer.save(update_fields=["default_template"])

        discover_printers()
        printer.refresh_from_db()
        assert printer.default_template is None

    @patch("printing.services.docker_discovery.docker")
    def test_skips_container_without_printer_name(self, mock_docker):
        container = _make_container(
            "some-service",
            {"props.printer": "true"},
            ["OTHER_VAR=value"],
        )
        mock_docker.from_env.return_value.containers.list.return_value = [container]

        from printing.services.docker_discovery import discover_printers

        results = discover_printers()

        assert len(results) == 0
        assert Printer.objects.count() == 0

    @patch("printing.services.docker_discovery.docker")
    def test_handles_docker_exception_gracefully(self, mock_docker):
        import docker as docker_lib

        mock_docker.errors.DockerException = docker_lib.errors.DockerException
        mock_docker.from_env.side_effect = docker_lib.errors.DockerException(
            "Cannot connect"
        )

        from printing.services.docker_discovery import discover_printers

        results = discover_printers()
        assert results == []

    @patch("printing.services.docker_discovery.docker")
    def test_uses_queue_name_as_friendly_name_when_label_missing(self, mock_docker):
        container = _make_container(
            "dymo-5xl",
            {"props.printer": "true"},
            ["PRINTER_NAME=DYMO-5XL"],
        )
        mock_docker.from_env.return_value.containers.list.return_value = [container]

        from printing.services.docker_discovery import discover_printers

        results = discover_printers()

        assert results[0]["name"] == "DYMO-5XL"
        printer = Printer.objects.get(cups_queue="DYMO-5XL")
        assert printer.name == "DYMO-5XL"
