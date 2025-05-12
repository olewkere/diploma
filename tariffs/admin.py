from django.contrib import admin
from .models import Tariff


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = ['energy_type', 'day_rate', 'night_rate', 'unit']
