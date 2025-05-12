from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect

from users import views as user_views
from tasks import views as task_views
from tariffs import views as tariff_views

urlpatterns = [
    path('', lambda request: redirect('login/'), name='root_redirect'),
    path('admin/', admin.site.urls),

    # Автентифікація
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('admin/login/', auth_views.LoginView.as_view(template_name='admin/login.html'), name='admin_login'),

    path('dashboard/', user_views.dashboard, name='dashboard'),

    # Завдання
    path('tasks/', task_views.view_tasks, name='view_tasks'),
    path('tasks/manage/', task_views.manage_tasks, name='manage_tasks'),
    path('tasks/create/', task_views.create_task, name='create_task'),
    path('tasks/<int:task_id>/', task_views.task_detail, name='task_detail'),
    path('tasks/<int:task_id>/edit/', task_views.edit_task, name='edit_task'),
    path('tasks/<int:task_id>/delete/', task_views.delete_task, name='delete_task'),
    path('tasks/<int:task_id>/update_status/', task_views.update_task_status, name='update_task_status'),

    path('tasks/full/<int:task_id>/', task_views.task_full_details, name='task_full_details'),

    # Контроль якості
    path('quality/', task_views.quality_control_list, name='quality_control_list'),
    path('quality/<int:task_id>/', task_views.quality_control_detail, name='quality_control_detail'),

    # Аналіз
    path('analysis/', task_views.analysis_view, name='analysis'),

    # Тарифи
    path('tariffs/edit/', tariff_views.edit_tariffs, name='edit_tariffs'),

    # Створення користувачів
    path('users/create/', user_views.create_user, name='create_user'),
]
