# Generated by Django 3.1.2 on 2020-10-17 10:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_auto_20201017_1038'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='account',
            name='kind',
        ),
    ]
