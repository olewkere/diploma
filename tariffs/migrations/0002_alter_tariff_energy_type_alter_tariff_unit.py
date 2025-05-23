# Generated by Django 5.1.6 on 2025-05-03 08:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariffs', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tariff',
            name='energy_type',
            field=models.CharField(choices=[('fuel', 'Паливо'), ('gas', 'Газ'), ('electricity', 'Електроенергія'), ('air', 'Стисле повітря')], max_length=20, unique=True, verbose_name='Тип енергоносія'),
        ),
        migrations.AlterField(
            model_name='tariff',
            name='unit',
            field=models.CharField(choices=[('literh', 'л/год'), ('cubic_meter_h', 'м³/год'), ('kwh', 'кВт/год'), ('kilosec', 'кг/с')], max_length=20, verbose_name='Одиниця виміру'),
        ),
    ]
