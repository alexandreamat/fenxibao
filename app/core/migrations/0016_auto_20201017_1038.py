# Generated by Django 3.1.2 on 2020-10-17 10:38

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_auto_20201017_0538'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='transaction',
            name='category',
        ),
        migrations.RemoveField(
            model_name='transaction',
            name='origin',
        ),
        migrations.RemoveField(
            model_name='transaction',
            name='state',
        ),
        migrations.AlterField(
            model_name='transaction',
            name='transfer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.transfer'),
        ),
    ]
