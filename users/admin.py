from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, LabWorker


class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Роль', {'fields': ('role',)}),
    )
    list_display = ['username', 'email', 'role']


admin.site.register(CustomUser, CustomUserAdmin)


@admin.register(LabWorker)
class LabWorkerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)