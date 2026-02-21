import json
import sys

from django.core.management.base import BaseCommand, CommandError

from printing.services.template_io import TemplateImportError, import_template


class Command(BaseCommand):
    help = "Import a label template from a JSON file"

    def add_arguments(self, parser):
        parser.add_argument(
            "file",
            nargs="?",
            default="-",
            help="Path to JSON file (or - for stdin, which is the default)",
        )

    def handle(self, *args, **options):
        file_path = options["file"]

        if file_path == "-":
            raw = sys.stdin.read()
        else:
            try:
                with open(file_path) as f:
                    raw = f.read()
            except FileNotFoundError:
                raise CommandError(f"File not found: {file_path}")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON: {e}")

        # Handle both single template and list of templates
        if isinstance(data, list):
            templates = data
        else:
            templates = [data]

        for entry in templates:
            try:
                template = import_template(entry)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Imported "{template.name}" '
                        f"({template.width_mm}x{template.height_mm}mm, "
                        f"{template.elements.count()} elements)"
                    )
                )
            except TemplateImportError as e:
                raise CommandError(str(e))
