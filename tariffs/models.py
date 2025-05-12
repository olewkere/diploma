from django.db import models


class Tariff(models.Model):
    ENERGY_TYPE_CHOICES = [
        ('fuel', 'Паливо'),
        ('gas', 'Газ'),
        ('electricity', 'Електроенергія'),
        ('air', 'Стисле повітря'),
        ('solution', 'Водно-мелясовий розчин'),
    ]
    UNIT_CHOICES = [
        ('literh', 'л/год'),
        ('cubic_meter_h', 'м³/год'),
        ('kwh', 'кВт/год'),
        ('kilosec', 'кг/с'),
    ]

    energy_type = models.CharField(
        max_length=20,
        choices=ENERGY_TYPE_CHOICES,
        unique=True,
        verbose_name="Тип енергоносія"
    )
    day_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Денний тариф"
    )
    night_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Нічний тариф"
    )
    unit = models.CharField(
        max_length=20,
        choices=UNIT_CHOICES,
        verbose_name="Одиниця виміру"
    )

    def __str__(self):
        return self.get_energy_type_display()