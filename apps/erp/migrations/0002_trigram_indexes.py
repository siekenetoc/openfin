from django.contrib.postgres.indexes import GinIndex
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("erp", "0001_initial"),
        ("core", "0002_pg_trgm"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="expectedpayment",
            index=GinIndex(
                fields=["invoice_id"],
                name="erp_expected_invoice_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ),
        migrations.AddIndex(
            model_name="expectedpayment",
            index=GinIndex(
                fields=["customer_name"],
                name="erp_expected_customer_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
