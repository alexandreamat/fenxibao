# Generated by Django 3.1.2 on 2020-10-09 05:56

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_auto_20201009_0234'),
    ]

    operations = [
        migrations.CreateModel(
            name='Counterpart',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
            ],
        ),
        migrations.AlterField(
            model_name='rawtransaction',
            name='counterpart',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.counterpart'),
        ),
    ]
