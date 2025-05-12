from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .forms import CustomUserCreationForm
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy


@login_required
def dashboard(request):
    context = {
        'body_class': 'dashboard-page'
    }
    if request.user.role == 'specialist':
        return render(request, 'dashboards/specialist_dashboard.html', context)
    else:
        return render(request, 'dashboards/user_dashboard.html', context)


class CustomLoginView(LoginView):
    def get_success_url(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return reverse_lazy('admin:index')
        else:
            return reverse_lazy('dashboard')


@login_required
def create_user(request):
    if request.user.role != 'specialist':
        return redirect('dashboard')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Користувач успішно створений!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Виправте помилки у формі.')
    else:
        form = CustomUserCreationForm()

    context = {
        'form': form,
        'body_class': 'dashboard-page'
    }
    return render(request, 'users/create_user.html', context)
