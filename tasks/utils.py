from django.utils import timezone
from .models import Task


def auto_update_task_statuses():
    now = timezone.now()
    tasks_to_fail = Task.objects.filter(
        status='new',
        deadline__lt=now
    )
    tasks_to_fail.update(status='failed')