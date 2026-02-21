import logging

import docker

from printing.models import LabelTemplate, Printer, PrinterType

logger = logging.getLogger(__name__)


def discover_printers() -> list[dict]:
    """Discover CUPS printers from Docker containers with props.printer labels.

    Returns list of dicts with keys: name, cups_queue, cups_server, created.
    """
    try:
        client = docker.from_env()
    except docker.errors.DockerException:
        logger.warning("Docker not available for printer discovery", exc_info=True)
        return []

    containers = client.containers.list(
        filters={"label": "props.printer=true", "status": "running"}
    )

    results = []
    default_template = LabelTemplate.objects.filter(is_default=True).first()

    for container in containers:
        labels = container.labels
        env = _parse_env(container.attrs["Config"]["Env"])

        queue_name = env.get("PRINTER_NAME", "")
        if not queue_name:
            continue

        friendly_name = labels.get("props.printer.name", queue_name)
        cups_server = f"{container.name}:631"

        printer, created = Printer.objects.update_or_create(
            cups_queue=queue_name,
            printer_type=PrinterType.CUPS,
            defaults={
                "name": friendly_name,
                "cups_server": cups_server,
                "is_active": True,
            },
        )
        if created and default_template:
            printer.default_template = default_template
            printer.save(update_fields=["default_template"])

        results.append(
            {
                "name": friendly_name,
                "cups_queue": queue_name,
                "cups_server": cups_server,
                "created": created,
            }
        )

    return results


def _parse_env(env_list: list[str]) -> dict[str, str]:
    result = {}
    for item in env_list:
        if "=" in item:
            k, v = item.split("=", 1)
            result[k] = v
    return result
