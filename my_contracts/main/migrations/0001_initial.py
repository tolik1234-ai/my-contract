from __future__ import annotations

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('display_name', models.CharField(blank=True, max_length=150)),
                ('wallet_address', models.CharField(blank=True, max_length=128)),
                ('bio', models.TextField(blank=True)),
                ('preferred_network', models.CharField(blank=True, max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['user__username'],
            },
        ),
        migrations.CreateModel(
            name='ContractDeployment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('template_id', models.CharField(max_length=128)),
                ('template_name', models.CharField(max_length=255)),
                ('network', models.CharField(max_length=64)),
                ('funding_wallet', models.CharField(max_length=128)),
                ('constructor_arguments', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('simulated', 'Simulated'), ('running', 'Running'), ('succeeded', 'Succeeded'), ('failed', 'Failed')], default='queued', max_length=16)),
                ('status_message', models.TextField(blank=True)),
                ('transaction_hash', models.CharField(blank=True, max_length=120)),
                ('raw_output', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deployments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
