# Generated by Django 3.1.1 on 2020-10-06 14:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_auto_20200919_0924'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='account',
            name='user_name',
        ),
        migrations.AddField(
            model_name='account',
            name='username',
            field=models.CharField(default='null', max_length=100, unique=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='transaction',
            name='account',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='core.account'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='account',
            name='user_full_name',
            field=models.CharField(blank=True, max_length=100),
        ),
    ]