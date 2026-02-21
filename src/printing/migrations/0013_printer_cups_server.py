from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("printing", "0012_printer_cups_queue_alter_printer_printer_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="printer",
            name="cups_server",
            field=models.CharField(
                blank=True,
                help_text="CUPS server address (e.g. dymo-5xl:631). "
                "Auto-populated by Docker discovery.",
                max_length=200,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="printer",
            name="cups_queue",
            field=models.CharField(
                blank=True,
                help_text="CUPS queue name \u2014 must match PRINTER_NAME in "
                "dymolp-docker (e.g. DYMO-5XL)",
                max_length=200,
                null=True,
            ),
        ),
    ]
