# Generated by Django 5.0.2 on 2024-02-28 17:21

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(max_length=200)),
                ('is_completed', models.BooleanField(default=False)),
                ('result', models.CharField(blank=True, default='', max_length=200, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
            ],
        ),
    ]
