from django.contrib import admin
from .models import Task, QualityIndicator, LabMeasurement, TaskProcessParameters, EnergyType, RawMaterialFlow, EnergyFlow


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'brand', 'line', 'status', 'started_at', 'deadline', 'created_by']
    list_filter = ('status', 'brand', 'line', 'created_by')
    search_fields = ('title', 'description')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at', 'started_at')


@admin.register(QualityIndicator)
class QualityIndicatorAdmin(admin.ModelAdmin):
    list_display = ('brand', 'min_moisture', 'max_moisture', 'max_ash', 'min_hardness', 'max_hardness')
    list_editable = ('min_moisture', 'max_moisture', 'max_ash', 'min_hardness', 'max_hardness')


@admin.register(LabMeasurement)
class LabMeasurementAdmin(admin.ModelAdmin):
    list_display = ('task', 'measurement_time', 'measured_moisture', 'measured_ash', 'measured_hardness', 'measured_by')
    list_filter = ('task__brand', 'measured_by', 'measurement_time')
    search_fields = ('task__title',)
    date_hierarchy = 'measurement_time'
    autocomplete_fields = ['task', 'measured_by']


@admin.register(TaskProcessParameters)
class TaskProcessParametersAdmin(admin.ModelAdmin):
    list_display = ('task', 'timestamp', 'initial_moisture', 'final_moisture', 'final_temp')
    list_filter = ('task__brand', 'task__line', 'timestamp')
    search_fields = ('task__title',)
    date_hierarchy = 'timestamp'
    readonly_fields = ('task', 'timestamp')


@admin.register(EnergyType)
class EnergyTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(RawMaterialFlow)
class RawMaterialFlowAdmin(admin.ModelAdmin):
    list_display = ('task', 'brand', 'carbon_flow_rate', 'solution_flow_rate', 'timestamp')
    list_filter = ('task__brand', 'timestamp')
    search_fields = ('task__title', 'brand')
    date_hierarchy = 'timestamp'
    autocomplete_fields = ['task']


@admin.register(EnergyFlow)
class EnergyFlowAdmin(admin.ModelAdmin):
    list_display = ('task', 'energy_type', 'value', 'timestamp', 'process_params')
    list_filter = ('energy_type', 'task__brand', 'timestamp')
    search_fields = ('task__title', 'energy_type__name')
    date_hierarchy = 'timestamp'
    autocomplete_fields = ['task', 'process_params', 'energy_type']