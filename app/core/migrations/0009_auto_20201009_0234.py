# Generated by Django 3.1.1 on 2020-10-09 02:34

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_auto_20201007_0907'),
    ]

    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alipay_id', models.CharField(max_length=100, unique=True)),
            ],
        ),
        migrations.RemoveField(
            model_name='rawtransaction',
            name='funds_state',
        ),
        migrations.RemoveField(
            model_name='rawtransaction',
            name='order_num',
        ),
        migrations.RemoveField(
            model_name='rawtransaction',
            name='sign',
        ),
        migrations.AlterField(
            model_name='rawtransaction',
            name='last_modified_date',
            field=models.DateTimeField(),
        ),
        migrations.AddField(
            model_name='rawtransaction',
            name='order',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.order'),
        ),
    ]
