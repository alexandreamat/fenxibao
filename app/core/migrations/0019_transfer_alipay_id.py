# Generated by Django 3.1.2 on 2020-10-18 05:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_auto_20201017_1051'),
    ]

    operations = [
        migrations.AddField(
            model_name='transfer',
            name='alipay_id',
            field=models.CharField(default=0, max_length=100, unique=True),
            preserve_default=False,
        ),
    ]
