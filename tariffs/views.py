from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Tariff
from .forms import TariffForm


@login_required
def edit_tariffs(request):
    tariffs = Tariff.objects.all()
    if request.method == 'POST':
        forms = []
        for tariff in tariffs:
            form = TariffForm(request.POST, prefix=str(tariff.id), instance=tariff)
            if form.is_valid():
                form.save()
        return redirect('edit_tariffs')
    else:
        forms = [TariffForm(instance=tariff, prefix=str(tariff.id)) for tariff in tariffs]
    return render(request, 'tariffs/edit_tariffs.html', {'forms': forms})
