from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from datetime import time

from users.models import CustomUser, LabWorker


class Task(models.Model):
    title = models.CharField(max_length=200, verbose_name="Назва")
    description = models.TextField(verbose_name="Опис")
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='tasks_created',
        verbose_name="Створено користувачем"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    BRAND_CHOICES = [
        ('N772', 'Марка N772'),
        ('N326', 'Марка N326'),
        ('N220', 'Марка N220'),
    ]
    LINE_CHOICES = [
        ('1', 'Лінія 1'),
        ('2', 'Лінія 2'),
    ]
    STATUS_CHOICES = [
        ('new', 'Нове'),
        ('in_progress', 'В процесі'),
        ('done', 'Виконано'),
        ('done_late', 'Виконано з запізненням'),
        ('failed', 'Не виконано'),
    ]

    brand = models.CharField(
        max_length=20,
        choices=BRAND_CHOICES,
        default='N772',
        verbose_name="Марка продукту"
    )
    line = models.CharField(
        max_length=10,
        choices=LINE_CHOICES,
        default='1',
        verbose_name="Лінія сушіння"
    )
    quantity = models.PositiveIntegerField(
        default=100,
        verbose_name="Кількість продукції (кг)"
    )
    moisture = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0.2), MaxValueValidator(0.9)],
        verbose_name="Потрібна вологість (%)",
        help_text="Діапазон: 0.2 - 0.9"
    )
    deadline = models.DateTimeField(
        verbose_name="Кінцевий термін",
        default=timezone.now
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new',
        verbose_name="Статус"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Час початку виконання"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Час завершення виконання"
    )

    def __str__(self):
        return self.title

    def update_status(self):
        now = timezone.now()
        if self.deadline < now and self.status == 'new':
            self.status = 'failed'
            self.save()
        elif self.status == 'in_progress' and self.deadline < now:
            self.status = 'done_late'
            self.save()

    def get_shift(self):
        if not self.created_at:
            return "-"
        creation_time = self.created_at.time()

        if time(8, 0) <= creation_time < time(16, 0):
            return "Зміна 1"
        elif time(16, 0) <= creation_time:
            return "Зміна 2"
        else:
            return "Зміна 3"

    def get_duration_seconds(self):
        if self.started_at and self.completed_at:
            duration = self.completed_at - self.started_at
            if duration.total_seconds() >= 0:
                return int(duration.total_seconds())
        return None


class QualityIndicator(models.Model):
    BRAND_CHOICES = Task.BRAND_CHOICES

    brand = models.CharField(
        max_length=20,
        choices=BRAND_CHOICES,
        unique=True,
        verbose_name="Марка продукту"
    )
    min_moisture = models.FloatField(
        default=0.2,
        validators=[MinValueValidator(0.0)],
        verbose_name="Мін. Вологість (%)"
    )
    max_moisture = models.FloatField(
        default=0.9,
        validators=[MinValueValidator(0.0)],
        verbose_name="Макс. Вологість (%)"
    )
    max_ash = models.FloatField(
        default=0.45,
        validators=[MinValueValidator(0.0)],
        verbose_name="Макс. Зольність (%)"
    )
    min_hardness = models.FloatField(
        default=10.0,
        validators=[MinValueValidator(0.0)],
        verbose_name="Мін. Твердість (г)"
    )
    max_hardness = models.FloatField(
        default=50.0,
        validators=[MinValueValidator(0.0)],
        verbose_name="Макс. Твердість (г)"
    )

    def __str__(self):
        return f"Показники якості для {self.get_brand_display()}"

    class Meta:
        verbose_name = "Показник якості"
        verbose_name_plural = "Показники якості"


class LabMeasurement(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='lab_measurements',
        verbose_name="Виробниче завдання"
    )
    measurement_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Час вимірювання"
    )
    measured_moisture = models.FloatField(
        validators=[MinValueValidator(0.0)],
        verbose_name="Виміряна вологість (%)",
        null=True, blank=True
    )
    measured_ash = models.FloatField(
        validators=[MinValueValidator(0.0)],
        verbose_name="Виміряна зольність (%)",
         null=True, blank=True
    )
    measured_hardness = models.FloatField(
        validators=[MinValueValidator(0.0)],
        verbose_name="Виміряна твердість (г)",
         null=True, blank=True
    )
    measured_by = models.ForeignKey(
        LabWorker,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lab_measurements_taken',
        verbose_name="Виміряв(ла)"
    )

    def __str__(self):
        return f"Вимірювання для {self.task.title} від {self.measurement_time.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        verbose_name = "Лабораторне вимірювання"
        verbose_name_plural = "Лабораторні вимірювання"
        ordering = ['-measurement_time']


class TaskProcessParameters(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='process_parameters_history',
        verbose_name="Виробниче завдання"
    )
    timestamp = models.DateTimeField(
        auto_now=True,
        verbose_name="Час останнього оновлення"
    )

    initial_moisture = models.FloatField(null=True, blank=True, verbose_name="Поч. вологість (%)")
    initial_temp = models.FloatField(null=True, blank=True, verbose_name="Поч. температура (°C)")
    axial_burner_temp = models.FloatField(null=True, blank=True, verbose_name="Темп. осьового пальника (°C)")
    zone1_drum_temp = models.FloatField(null=True, blank=True, verbose_name="Зона 1: Темп. барабану (°C)")
    zone1_burner_temp = models.FloatField(null=True, blank=True, verbose_name="Зона 1: Темп. пальника (°C)")
    zone1_1_carbon_temp = models.FloatField(null=True, blank=True, verbose_name="Зона 1.1: Темп. вуглецю (°C)")
    zone1_1_carbon_moisture = models.FloatField(null=True, blank=True, verbose_name="Зона 1.1: Вологість вуглецю (%)")
    zone1_2_carbon_temp = models.FloatField(null=True, blank=True, verbose_name="Зона 1.2: Темп. вуглецю (°C)")
    zone1_2_carbon_moisture = models.FloatField(null=True, blank=True, verbose_name="Зона 1.2: Вологість вуглецю (%)")
    zone2_drum_temp = models.FloatField(null=True, blank=True, verbose_name="Зона 2: Темп. барабану (°C)")
    zone2_burner_temp = models.FloatField(null=True, blank=True, verbose_name="Зона 2: Темп. пальника (°C)")
    zone2_1_carbon_temp = models.FloatField(null=True, blank=True, verbose_name="Зона 2.1: Темп. вуглецю (°C)")
    zone2_1_carbon_moisture = models.FloatField(null=True, blank=True, verbose_name="Зона 2.1: Вологість вуглецю (%)")
    zone2_2_carbon_temp = models.FloatField(null=True, blank=True, verbose_name="Зона 2.2: Темп. вуглецю (°C)")
    zone2_2_carbon_moisture = models.FloatField(null=True, blank=True, verbose_name="Зона 2.2: Вологість вуглецю (%)")
    zone3_drum_temp = models.FloatField(null=True, blank=True, verbose_name="Зона 3: Темп. барабану (°C)")
    zone3_burner_temp = models.FloatField(null=True, blank=True, verbose_name="Зона 3: Темп. пальника (°C)")
    zone3_1_carbon_temp = models.FloatField(null=True, blank=True, verbose_name="Зона 3.1: Темп. вуглецю (°C)")
    zone3_1_carbon_moisture = models.FloatField(null=True, blank=True, verbose_name="Зона 3.1: Вологість вуглецю (%)")
    zone3_2_carbon_temp = models.FloatField(null=True, blank=True, verbose_name="Зона 3.2: Темп. вуглецю (°C)")
    zone3_2_carbon_moisture = models.FloatField(null=True, blank=True, verbose_name="Зона 3.2: Вологість вуглецю (%)")
    final_temp = models.FloatField(null=True, blank=True, verbose_name="Кінц. температура (°C)")
    final_moisture = models.FloatField(null=True, blank=True, verbose_name="Кінц. вологість (%)")

    def __str__(self):
        return f"Параметри процесу для завдання {self.task.title} (ID: {self.task.id}) від {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        verbose_name = "Параметр процесу завдання"
        verbose_name_plural = "Параметри процесу завдань"
        ordering = ['-timestamp']


class EnergyType(models.Model):
    id = models.IntegerField(primary_key=True, verbose_name="ID Типу енергії")
    name = models.CharField(max_length=100, unique=True, verbose_name="Назва типу енергії")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Тип енергії"
        verbose_name_plural = "Типи енергії"


class RawMaterialFlow(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='raw_material_flows',
        verbose_name="Виробниче завдання"
    )
    brand = models.CharField(
        max_length=20,
        null=True, blank=True,
        verbose_name="Марка продукту (на момент запису)"
    )
    carbon_flow_rate = models.FloatField(null=True, blank=True, verbose_name="Витрата вуглецю (кг/с)")
    solution_flow_rate = models.FloatField(null=True, blank=True, verbose_name="Витрата розчину (кг/с)")
    timestamp = models.DateTimeField(auto_now=True, verbose_name="Час запису")

    def __str__(self):
        return f"Потік сировини для {self.task.title} від {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        verbose_name = "Потік сировини"
        verbose_name_plural = "Потоки сировини"
        ordering = ['-timestamp']


class EnergyFlow(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='energy_flows',
        verbose_name="Виробниче завдання"
    )
    process_params = models.ForeignKey(
        TaskProcessParameters,
        on_delete=models.CASCADE,
        related_name='energy_flows',
        verbose_name="Параметри процесу (запис)"
    )
    energy_type = models.ForeignKey(
        EnergyType,
        on_delete=models.CASCADE,
        verbose_name="Тип енергії"
    )
    value = models.FloatField(null=True, blank=True, verbose_name="Витрата енергії (од.)")
    timestamp = models.DateTimeField(auto_now=True, verbose_name="Час запису")

    def __str__(self):
        return f"{self.energy_type.name} для {self.task.title} ({self.process_params.timestamp.strftime('%H:%M:%S')}) - {self.value}"

    class Meta:
        verbose_name = "Потік енергії"
        verbose_name_plural = "Потоки енергії"
        ordering = ['-timestamp', 'energy_type']
