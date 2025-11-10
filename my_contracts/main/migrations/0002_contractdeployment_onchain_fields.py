from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="contractdeployment",
            name="chain_id",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="contractdeployment",
            name="contract_address",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="contractdeployment",
            name="deployment_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="contractdeployment",
            name="deployer_wallet",
            field=models.CharField(
                blank=True,
                help_text="Адрес кошелька, который инициировал транзакцию.",
                max_length=128,
            ),
        ),
        migrations.AddField(
            model_name="contractdeployment",
            name="manager_address",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
