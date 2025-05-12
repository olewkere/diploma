from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('user', 'Користувач'),
        ('specialist', 'Спеціаліст'),
    ]
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='user'
    )


class LabWorker(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Ім'я лаборанта")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Лаборант"
        verbose_name_plural = "Лаборанти"
