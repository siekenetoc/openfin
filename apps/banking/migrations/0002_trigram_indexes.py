from django.contrib.postgres.indexes import GinIndex
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("banking", "0001_initial"),
        ("core", "0002_pg_trgm"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="banktransaction",
            index=GinIndex(
                fields=["purpose"],
                name="bank_tx_purpose_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
