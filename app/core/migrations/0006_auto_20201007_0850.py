# Generated by Django 3.1.2 on 2020-10-07 08:50

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_auto_20201007_0841'),
    ]

    operations = [
        migrations.RenameField(
            model_name='rawtransaction',
            old_name='type',
            new_name='category',
        ),
    ]