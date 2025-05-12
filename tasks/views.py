from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden, Http404
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta, time, datetime
from django.db.models import Q, Sum, Avg
from collections import defaultdict
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import math

from .models import Task, QualityIndicator, LabMeasurement, TaskProcessParameters, EnergyType, RawMaterialFlow
from .forms import TaskForm
from .utils import auto_update_task_statuses
from tariffs.models import Tariff


def is_specialist(user):
    return user.is_authenticated and user.role == 'specialist'


def is_user(user):
    return user.is_authenticated and user.role == 'user'


@login_required
@user_passes_test(is_user, login_url='/login/')
def view_tasks(request):
    auto_update_task_statuses()
    tasks = Task.objects.exclude(status__in=['failed', 'done', 'done_late']).order_by('deadline')
    return render(request, 'tasks/view_tasks.html', {'tasks': tasks})


@login_required
@user_passes_test(is_specialist, login_url='/dashboard/')
def manage_tasks(request):
    auto_update_task_statuses()
    tasks = Task.objects.all().order_by('-created_at')
    return render(request, 'tasks/manage_tasks.html', {'tasks': tasks})


@login_required
def task_detail(request, task_id):
    auto_update_task_statuses()
    task = get_object_or_404(Task, id=task_id)

    can_start_task = False
    can_complete_task = False
    if request.user.role == 'user':
        time_until_deadline = task.deadline - timezone.now()
        can_start_task = task.status == 'new' and time_until_deadline >= timedelta(hours=1)
        can_complete_task = task.status == 'in_progress'

    context = {
        'task': task,
        'is_specialist': is_specialist(request.user),
        'is_user': is_user(request.user),
        'can_start_task': can_start_task,
        'can_complete_task': can_complete_task,
        'specialist_can_edit_delete': task.status == 'new' and is_specialist(request.user)
    }
    return render(request, 'tasks/task_detail.html', context)


@login_required
@user_passes_test(is_specialist, login_url='/dashboard/')
def create_task(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.status = 'new'
            task.save()
            messages.success(request, 'Нове завдання успішно створено.')
            return redirect('manage_tasks')
    else:
        default_deadline = timezone.now() + timedelta(days=1)
        form = TaskForm(initial={'deadline': default_deadline.strftime('%Y-%m-%dT%H:%M')})

    return render(request, 'tasks/create_task.html', {'form': form})


@login_required
@user_passes_test(is_specialist, login_url='/dashboard/')
def edit_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    if task.status != 'new':
        messages.error(request, f'Завдання "{task.title}" не може бути відредаговане, оскільки його статус не "Нове".')
        return redirect('manage_tasks')

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, f'Завдання "{task.title}" успішно оновлено.')
            return redirect('manage_tasks')
    else:
        form = TaskForm(instance=task, initial={'deadline': task.deadline.strftime('%Y-%m-%dT%H:%M')})

    return render(request, 'tasks/edit_task.html', {'form': form, 'task': task})


@login_required
@user_passes_test(is_specialist, login_url='/dashboard/')
@require_POST
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    if task.status != 'new':
        messages.error(request, f'Завдання "{task.title}" не може бути видалене, оскільки його статус не "Нове".')
        return redirect('manage_tasks')

    task_title = task.title
    task.delete()
    messages.success(request, f'Завдання "{task_title}" успішно видалено.')
    return redirect('manage_tasks')


@login_required
@user_passes_test(is_user, login_url='/dashboard/')
@require_POST
def update_task_status(request, task_id):
    auto_update_task_statuses()
    task = get_object_or_404(Task, id=task_id)
    action = request.POST.get('action')
    now = timezone.now()

    if action == 'start' and task.status == 'new':
        time_until_deadline = task.deadline - now
        if time_until_deadline < timedelta(hours=1):
            messages.error(request, 'Неможливо розпочати виконання: до дедлайну менше години.')
        else:
            task.status = 'in_progress'
            task.started_at = now
            task.save()
            messages.success(request, 'Статус завдання оновлено на "В процесі".')

    elif action == 'complete' and task.status == 'in_progress':
        if now > task.deadline:
            task.status = 'done_late'
            messages.warning(request, 'Завдання виконано із запізненням.')
        else:
            task.status = 'done'
            messages.success(request, 'Завдання успішно виконано.')
        task.completed_at = now
        task.save()

    else:
        messages.error(request, 'Неприпустима дія або статус завдання не дозволяє цю операцію.')

    return redirect('task_detail', task_id=task.id)


@login_required
@user_passes_test(is_specialist, login_url='/dashboard/')
def quality_control_list(request):
    auto_update_task_statuses()
    sort_by = request.GET.get('sort', '-created_at')
    filter_brand = request.GET.get('brand', '')
    filter_line = request.GET.get('line', '')
    filter_shift = request.GET.get('shift', '')
    tasks_query = Task.objects.all()

    if filter_brand:
        tasks_query = tasks_query.filter(brand=filter_brand)
    if filter_line:
        tasks_query = tasks_query.filter(line=filter_line)
    if filter_shift == '1':
        tasks_query = tasks_query.filter(created_at__time__gte=time(8, 0), created_at__time__lt=time(16, 0))
    elif filter_shift == '2':
        tasks_query = tasks_query.filter(created_at__time__gte=time(16, 0))
    elif filter_shift == '3':
        tasks_query = tasks_query.filter(created_at__time__lt=time(8, 0))

    allowed_sort_fields = {
        'created_at': 'created_at',
        '-created_at': '-created_at',
        'id': 'id',
        '-id': '-id'
    }
    sort_field = allowed_sort_fields.get(sort_by, '-created_at')
    tasks = tasks_query.order_by(sort_field)

    context = {
        'tasks': tasks,
        'brand_choices': Task.BRAND_CHOICES,
        'line_choices': Task.LINE_CHOICES,
        'shift_choices': [('1', 'Зміна 1'), ('2', 'Зміна 2'), ('3', 'Зміна 3')],
        'current_sort': sort_by,
        'current_brand': filter_brand,
        'current_line': filter_line,
        'current_shift': filter_shift,
    }
    return render(request, 'tasks/quality_control_list.html', context)


@login_required
@user_passes_test(is_specialist, login_url='/dashboard/')
def quality_control_detail(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    quality_norms = QualityIndicator.objects.filter(brand=task.brand).first()
    measurements = task.lab_measurements.all()

    context = {
        'task': task,
        'quality_norms': quality_norms,
        'measurements': measurements,
    }
    return render(request, 'tasks/quality_control_detail.html', context)


def calculate_task_totals(task):
    totals = {
        'duration_sec': None,
        'total_carbon': None,
        'total_solution': None,
        'energy_consumption': defaultdict(Decimal),
        'costs': defaultdict(Decimal),
        'total_cost': Decimal('0.00'),
        'final_measurement': None,
    }
    duration_sec = task.get_duration_seconds()
    totals['duration_sec'] = duration_sec

    if task.completed_at is None or duration_sec is None or duration_sec <= 0:
        return totals

    completion_hour = task.completed_at.hour
    is_night = (completion_hour >= 22 or completion_hour < 4)
    duration_hr = Decimal(duration_sec) / Decimal(3600.0)

    latest_raw_flow = task.raw_material_flows.order_by('-timestamp').first()
    if latest_raw_flow:
        if latest_raw_flow.carbon_flow_rate is not None:
            totals['total_carbon'] = Decimal(latest_raw_flow.carbon_flow_rate) * Decimal(duration_sec)
        if latest_raw_flow.solution_flow_rate is not None:
            total_sol = Decimal(latest_raw_flow.solution_flow_rate) * Decimal(duration_sec)
            totals['total_solution'] = total_sol
            try:
                tariff = Tariff.objects.get(energy_type='solution')
                rate = tariff.night_rate if is_night else tariff.day_rate
                cost = total_sol * rate
                totals['costs']['solution'] = cost.quantize(Decimal('0.01'))
                totals['total_cost'] += cost
            except Tariff.DoesNotExist:
                pass

    latest_params = task.process_parameters_history.order_by('-timestamp').first()
    if latest_params:
        energy_flows = latest_params.energy_flows.select_related('energy_type').order_by('energy_type', '-timestamp')
        processed_types = set()
        tariffs_cache = {t.energy_type: t for t in Tariff.objects.all()}

        for flow in energy_flows:
            tariff_key = None
            energy_type_name_lower = flow.energy_type.name.lower()
            if 'газ' in energy_type_name_lower:
                tariff_key = 'gas'
            elif 'рідке паливо' in energy_type_name_lower:
                tariff_key = 'fuel'
            elif 'електроенергія' in energy_type_name_lower:
                tariff_key = 'electricity'
            elif 'стисле повітря' in energy_type_name_lower:
                tariff_key = 'air'

            if tariff_key and flow.energy_type_id not in processed_types and flow.value is not None:
                consumption = Decimal(flow.value) * duration_hr
                totals['energy_consumption'][tariff_key] += consumption

                tariff = tariffs_cache.get(tariff_key)
                if tariff:
                    rate = tariff.night_rate if is_night else tariff.day_rate
                    cost = consumption * rate
                    totals['costs'][tariff_key] += cost
                    totals['total_cost'] += cost

                processed_types.add(flow.energy_type_id)

    totals['total_cost'] = totals['total_cost'].quantize(Decimal('0.01'))
    totals['final_measurement'] = task.lab_measurements.order_by('-measurement_time').first()

    return totals


def calculate_quality(measurement):
    if not measurement:
        return None

    quality = {
        'moisture': None, 'ash': None, 'hardness': None, 'total': None,
        'messages': []
    }
    valid_calc = True

    if measurement.measured_moisture is not None:
        moisture_val = Decimal(measurement.measured_moisture)
        q_m = Decimal(1.0) - (abs(moisture_val - Decimal(0.55)) / Decimal(0.35))
        quality['moisture'] = max(Decimal(0), q_m.quantize(Decimal('0.001')))
    else:
        quality['messages'].append("Вимірювання вологості відсутнє.")
        valid_calc = False

    if measurement.measured_ash is not None:
        ash_val = Decimal(measurement.measured_ash)
        if ash_val < 0: ash_val = Decimal(0)
        q_a = Decimal(1.0) - (ash_val / Decimal(0.45))
        quality['ash'] = max(Decimal(0), q_a.quantize(Decimal('0.001')))
    else:
        quality['messages'].append("Вимірювання зольності відсутнє.")
        valid_calc = False

    if measurement.measured_hardness is not None:
        hardness_val = Decimal(measurement.measured_hardness)
        q_h = Decimal(1.0) - (abs(hardness_val - Decimal(30.0)) / Decimal(20.0))
        quality['hardness'] = max(Decimal(0), q_h.quantize(Decimal('0.001')))
    else:
        quality['messages'].append("Вимірювання твердості відсутнє.")
        valid_calc = False

    if quality['moisture'] is not None:
        quality['total'] = quality['moisture']
    else:
        quality['total'] = None

    return quality


def calculate_value_assessment(task, total_quality):
    if total_quality is None or total_quality <= 0:
        return None

    prices = {
        'N220': Decimal('89.6'),
        'N326': Decimal('113.4'),
        'N772': Decimal('131.2'),
    }

    price_per_kg = prices.get(task.brand)
    if not price_per_kg:
        return None

    value = (Decimal(task.quantity) * price_per_kg * total_quality).quantize(Decimal('0.01'))
    return value


@login_required
@user_passes_test(is_specialist, login_url='/dashboard/')
def task_full_details(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    measurements = task.lab_measurements.all()
    process_params_history = task.process_parameters_history.all()
    quality_norms = QualityIndicator.objects.filter(brand=task.brand).first()
    task_totals = calculate_task_totals(task)
    quality_assessment = calculate_quality(task_totals['final_measurement'])
    value_assessment = None
    if quality_assessment and quality_assessment['total'] is not None:
        value_assessment = calculate_value_assessment(task, quality_assessment['total'])

    energy_consumption_dict = dict(task_totals['energy_consumption'])
    costs_dict = dict(task_totals['costs'])
    context = {
        'task': task,
        'measurements': measurements,
        'process_params_history': process_params_history,
        'quality_norms': quality_norms,
        'duration_seconds': task_totals['duration_sec'],
        'total_carbon': task_totals['total_carbon'],
        'total_solution': task_totals['total_solution'],
        'energy_consumption': energy_consumption_dict,
        'costs': costs_dict,
        'total_cost': task_totals['total_cost'],
        'final_measurement': task_totals['final_measurement'],
        'quality': quality_assessment,
        'value_assessment': value_assessment,
    }
    return render(request, 'tasks/task_full_details.html', context)


def calculate_efficiency_score(value_assessment, total_cost):
    if value_assessment is None or total_cost is None:
        return None
    profit_or_loss = Decimal(value_assessment) - Decimal(total_cost)
    if value_assessment == Decimal(0) or total_cost == Decimal(0):
        return None
    try:
        sign_val = Decimal('1') if profit_or_loss >= 0 else Decimal('-1')
        numerator = (profit_or_loss ** 2) * (Decimal('40') ** 2)
        denominator_part1 = Decimal(value_assessment) ** 2
        denominator_part2 = Decimal(total_cost) ** 2
        denominator_part3 = Decimal('3.5') ** 2
        denominator = denominator_part1 * denominator_part2 * denominator_part3
        if denominator == Decimal(0):
            return None
        efficiency = sign_val * (numerator / denominator)
        return efficiency.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    except Exception as e:
        return None


def analysis_view(request):
    today = timezone.localdate()
    start_date_str = request.GET.get('start_date', today.strftime('%Y-%m-%d'))
    end_date_str = request.GET.get('end_date', start_date_str)
    selected_shift = request.GET.get('shift', 'all')
    selected_task_id = request.GET.get('task_id', None)

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        end_datetime = timezone.make_aware(datetime.combine(end_date, time.max))
        start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
    except ValueError:
        messages.error(request, "Неправильний формат дати. Використовуйте РРРР-ММ-ДД.")
        start_date = today
        end_date = today
        end_datetime = timezone.make_aware(datetime.combine(end_date, time.max))
        start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))

    tasks_for_sidebar_query = Task.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).order_by('-created_at')

    if selected_shift == '1':
        tasks_for_sidebar_query = tasks_for_sidebar_query.filter(created_at__time__gte=time(8, 0),
                                                                 created_at__time__lt=time(16, 0))
    elif selected_shift == '2':
        tasks_for_sidebar_query = tasks_for_sidebar_query.filter(created_at__time__gte=time(16, 0))
    elif selected_shift == '3':
        tasks_for_sidebar_query = tasks_for_sidebar_query.filter(created_at__time__lt=time(8, 0))

    tasks_for_sidebar = list(tasks_for_sidebar_query)

    print(f"[VIEW_DEBUG] Кількість завдань у tasks_for_sidebar: {len(tasks_for_sidebar)}")

    selected_task_object = None
    task_specific_chart_data = None
    annotation_data = None
    no_data_for_selected_task = False
    detailed_task_table_data = []
    time_points_for_html = []
    main_zone_names_for_html = []
    task_totals_info = None
    quality_assessment_info = None
    value_assessment_info = None
    energy_consumption_info = None

    if selected_task_id:
        try:
            selected_task_object = get_object_or_404(Task, id=selected_task_id)
            selected_task_params = selected_task_object.process_parameters_history.order_by('-timestamp').first()

            if selected_task_params:
                print(f"[DEBUG] Використовуються параметри з timestamp: {selected_task_params.timestamp}")

                main_zone_names = ["Зона входу", "Зона 1", "Зона 2", "Зона 3", "Зона виходу"]

                point_definitions = {
                    'initial_temp': {'dataset': 'temp_carbon', 'x_center': 0, 'offset': -0.15},
                    'initial_moisture': {'dataset': 'moisture_carbon', 'x_center': 0, 'offset': -0.15},
                    'axial_burner_temp': {'dataset': 'axial_burner', 'x_center': 0, 'offset': +0.15},

                    'zone1_1_carbon_temp': {'dataset': 'temp_carbon', 'x_center': 1, 'offset': -0.3},
                    'zone1_1_carbon_moisture': {'dataset': 'moisture_carbon', 'x_center': 1, 'offset': -0.3},
                    'zone1_burner_temp': {'dataset': 'zone1_burner', 'x_center': 1, 'offset': -0.1},
                    'zone1_drum_temp': {'dataset': 'zone1_drum', 'x_center': 1, 'offset': +0.1},
                    'zone1_2_carbon_temp': {'dataset': 'temp_carbon', 'x_center': 1, 'offset': +0.3},
                    'zone1_2_carbon_moisture': {'dataset': 'moisture_carbon', 'x_center': 1, 'offset': +0.3},

                    'zone2_1_carbon_temp': {'dataset': 'temp_carbon', 'x_center': 2, 'offset': -0.3},
                    'zone2_1_carbon_moisture': {'dataset': 'moisture_carbon', 'x_center': 2, 'offset': -0.3},
                    'zone2_burner_temp': {'dataset': 'zone2_burner', 'x_center': 2, 'offset': -0.1},
                    'zone2_drum_temp': {'dataset': 'zone2_drum', 'x_center': 2, 'offset': +0.1},
                    'zone2_2_carbon_temp': {'dataset': 'temp_carbon', 'x_center': 2, 'offset': +0.3},
                    'zone2_2_carbon_moisture': {'dataset': 'moisture_carbon', 'x_center': 2, 'offset': +0.3},

                    'zone3_1_carbon_temp': {'dataset': 'temp_carbon', 'x_center': 3, 'offset': -0.3},
                    'zone3_1_carbon_moisture': {'dataset': 'moisture_carbon', 'x_center': 3, 'offset': -0.3},
                    'zone3_burner_temp': {'dataset': 'zone3_burner', 'x_center': 3, 'offset': -0.1},
                    'zone3_drum_temp': {'dataset': 'zone3_drum', 'x_center': 3, 'offset': +0.1},
                    'zone3_2_carbon_temp': {'dataset': 'temp_carbon', 'x_center': 3, 'offset': +0.3},
                    'zone3_2_carbon_moisture': {'dataset': 'moisture_carbon', 'x_center': 3, 'offset': +0.3},

                    'final_temp': {'dataset': 'temp_carbon', 'x_center': 4, 'offset': 0.0},
                    'final_moisture': {'dataset': 'moisture_carbon', 'x_center': 4, 'offset': 0.0},
                }

                def get_float_or_none(value):
                    if value is None: return None
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return None

                datasets_data = {
                    'temp_carbon': [], 'moisture_carbon': [], 'axial_burner': [],
                    'zone1_burner': [], 'zone1_drum': [],
                    'zone2_burner': [], 'zone2_drum': [],
                    'zone3_burner': [], 'zone3_drum': []
                }

                for field_name, definition in point_definitions.items():
                    value = getattr(selected_task_params, field_name, None)
                    y_val = get_float_or_none(value)
                    if y_val is not None:
                        x_val = definition['x_center'] + definition['offset']
                        datasets_data[definition['dataset']].append({'x': x_val, 'y': y_val})

                for ds_name in datasets_data:
                    datasets_data[ds_name].sort(key=lambda p: p['x'])

                temp_carbon_color = 'rgba(255, 99, 132, 1)'
                moisture_color = 'rgba(54, 162, 235, 1)'
                axial_burner_color = 'rgba(255, 159, 64, 1)'
                zone_burner_color_1 = 'rgba(255, 205, 86, 1)'
                zone_burner_color_2 = 'rgba(240, 180, 86, 0.9)'
                zone_burner_color_3 = 'rgba(220, 150, 86, 0.8)'
                drum_temp_color_1 = 'rgba(75, 192, 192, 1)'
                drum_temp_color_2 = 'rgba(70, 170, 170, 0.9)'
                drum_temp_color_3 = 'rgba(60, 150, 150, 0.8)'

                task_specific_chart_data = {
                    'datasets': [
                        {'label': 'Температура Вуглецю (°C)', 'data': datasets_data['temp_carbon'],
                         'borderColor': temp_carbon_color, 'backgroundColor': temp_carbon_color,
                         'yAxisID': 'yTemperature', 'showLine': True, 'tension': 0.1, 'pointRadius': 5,
                         'pointHoverRadius': 7},
                        {'label': 'Вологість Вуглецю (%)', 'data': datasets_data['moisture_carbon'],
                         'borderColor': moisture_color, 'backgroundColor': moisture_color, 'borderDash': [5, 5],
                         'yAxisID': 'yMoisture', 'showLine': True, 'tension': 0.1, 'pointRadius': 5,
                         'pointHoverRadius': 7},
                        {'label': 'Темп. осьового пальника (°C)', 'data': datasets_data['axial_burner'],
                         'borderColor': axial_burner_color, 'backgroundColor': axial_burner_color,
                         'yAxisID': 'yTemperature', 'showLine': True, 'tension': 0.1, 'pointRadius': 5,
                         'pointHoverRadius': 7},
                        {'label': 'Темп. пальника зони 1 (°C)', 'data': datasets_data['zone1_burner'],
                         'borderColor': zone_burner_color_1, 'backgroundColor': zone_burner_color_1,
                         'yAxisID': 'yTemperature', 'showLine': True, 'tension': 0.1, 'pointRadius': 5,
                         'pointHoverRadius': 7},
                        {'label': 'Темп. пальника зони 2 (°C)', 'data': datasets_data['zone2_burner'],
                         'borderColor': zone_burner_color_2, 'backgroundColor': zone_burner_color_2,
                         'yAxisID': 'yTemperature', 'showLine': True, 'tension': 0.1, 'pointRadius': 5,
                         'pointHoverRadius': 7},
                        {'label': 'Темп. пальника зони 3 (°C)', 'data': datasets_data['zone3_burner'],
                         'borderColor': zone_burner_color_3, 'backgroundColor': zone_burner_color_3,
                         'yAxisID': 'yTemperature', 'showLine': True, 'tension': 0.1, 'pointRadius': 5,
                         'pointHoverRadius': 7},
                        {'label': 'Темп. барабану зони 1 (°C)', 'data': datasets_data['zone1_drum'],
                         'borderColor': drum_temp_color_1, 'backgroundColor': drum_temp_color_1,
                         'yAxisID': 'yTemperature', 'showLine': True, 'tension': 0.1, 'pointRadius': 5,
                         'pointHoverRadius': 7},
                        {'label': 'Темп. барабану зони 2 (°C)', 'data': datasets_data['zone2_drum'],
                         'borderColor': drum_temp_color_2, 'backgroundColor': drum_temp_color_2,
                         'yAxisID': 'yTemperature', 'showLine': True, 'tension': 0.1, 'pointRadius': 5,
                         'pointHoverRadius': 7},
                        {'label': 'Темп. барабану зони 3 (°C)', 'data': datasets_data['zone3_drum'],
                         'borderColor': drum_temp_color_3, 'backgroundColor': drum_temp_color_3,
                         'yAxisID': 'yTemperature', 'showLine': True, 'tension': 0.1, 'pointRadius': 5,
                         'pointHoverRadius': 7},
                    ]
                }

                annotation_data = {
                    'dividers_x_values': [0.5, 1.5, 2.5, 3.5]
                }

                time_points_for_html = []
                time_axis_label_for_html = ""
                main_zone_names_for_html = main_zone_names

                if selected_task_object.started_at and selected_task_object.completed_at and \
                        selected_task_object.completed_at > selected_task_object.started_at:

                    start_time = selected_task_object.started_at
                    end_time = selected_task_object.completed_at
                    total_duration_seconds = (end_time - start_time).total_seconds()

                    time_axis_label_for_html = ""
                    time_points_for_html = []
                    time_x_coords = [
                        point_definitions['initial_temp']['x_center'] + point_definitions['initial_temp']['offset'],
                        point_definitions['zone1_1_carbon_temp']['x_center'] + point_definitions['zone1_1_carbon_temp'][
                            'offset'],
                        point_definitions['zone1_2_carbon_temp']['x_center'] + point_definitions['zone1_2_carbon_temp'][
                            'offset'],
                        point_definitions['zone2_1_carbon_temp']['x_center'] + point_definitions['zone2_1_carbon_temp'][
                            'offset'],
                        point_definitions['zone2_2_carbon_temp']['x_center'] + point_definitions['zone2_2_carbon_temp'][
                            'offset'],
                        point_definitions['zone3_1_carbon_temp']['x_center'] + point_definitions['zone3_1_carbon_temp'][
                            'offset'],
                        point_definitions['zone3_2_carbon_temp']['x_center'] + point_definitions['zone3_2_carbon_temp'][
                            'offset'],
                        point_definitions['final_temp']['x_center'] + point_definitions['final_temp']['offset']
                    ]

                    time_points_for_html.append({
                        'time_str': start_time.strftime('%H:%M'),
                        'id': 'time-start',
                        'x_coord': time_x_coords[0]
                    })

                    if total_duration_seconds > 0:
                        num_intervals_for_calc = 6
                        single_interval_duration_sec = total_duration_seconds / num_intervals_for_calc
                        current_calc_time = start_time

                        for i in range(num_intervals_for_calc):
                            current_calc_time += timedelta(seconds=single_interval_duration_sec)
                            time_to_display_for_interval = current_calc_time
                            if i == num_intervals_for_calc - 1:
                                time_to_display_for_interval = end_time

                            time_points_for_html.append({
                                'time_str': time_to_display_for_interval.strftime('%H:%M'),
                                'id': f'time-interval-{i + 1}',
                                'x_coord': time_x_coords[i + 1]
                            })
                    else:
                        for i in range(num_intervals_for_calc):
                            time_points_for_html.append({
                                'time_str': start_time.strftime('%H:%M'),
                                'id': f'time-interval-{i + 1}',
                                'x_coord': time_x_coords[i + 1]
                            })

                    time_points_for_html = [time_points_for_html[0]]

                    current_calc_time = start_time
                    if total_duration_seconds > 0:
                        single_interval_duration_sec = total_duration_seconds / 7
                        for i in range(6):
                            current_calc_time += timedelta(seconds=single_interval_duration_sec)
                            time_points_for_html.append({
                                'time_str': current_calc_time.strftime('%H:%M'),
                                'id': f'time-subzone-{(i // 2) + 1}.{(i % 2) + 1}',
                                'x_coord': time_x_coords[i + 1]
                            })

                        time_points_for_html.append({
                            'time_str': end_time.strftime('%H:%M'),
                            'id': 'time-end',
                            'x_coord': time_x_coords[7]
                        })
                    else:
                        for i in range(7):
                            time_points_for_html.append({
                                'time_str': start_time.strftime('%H:%M'),
                                'id': f'time-point-{i + 2}',
                                'x_coord': time_x_coords[i + 1]
                            })

                    print(f"[DEBUG] Фінальні time_points_for_html (8 міток): {time_points_for_html}")

                new_detailed_task_table_data = []
                if selected_task_params:
                    table_structure = [
                        {
                            "row_label": "Температура вуглецю, °C",
                            "data_fields": [
                                "initial_temp",
                                ("zone1_1_carbon_temp", "zone1_2_carbon_temp"),
                                ("zone2_1_carbon_temp", "zone2_2_carbon_temp"),
                                ("zone3_1_carbon_temp", "zone3_2_carbon_temp"),
                                "final_temp"
                            ]
                        },
                        {
                            "row_label": "Вологість вуглецю, %",
                            "data_fields": [
                                "initial_moisture",
                                ("zone1_1_carbon_moisture", "zone1_2_carbon_moisture"),
                                ("zone2_1_carbon_moisture", "zone2_2_carbon_moisture"),
                                ("zone3_1_carbon_moisture", "zone3_2_carbon_moisture"),
                                "final_moisture"
                            ]
                        },
                        {
                            "row_label": "Температура пальників, °C",
                            "data_fields": [
                                "axial_burner_temp",
                                "zone1_burner_temp",
                                "zone2_burner_temp",
                                "zone3_burner_temp",
                                None
                            ]
                        },
                        {
                            "row_label": "Температура барабану, °C",
                            "data_fields": [
                                None,
                                "zone1_drum_temp",
                                "zone2_drum_temp",
                                "zone3_drum_temp",
                                None
                            ]
                        }
                    ]

                    column_keys_map = ["col_zona_vkhodu", "col_zona_1", "col_zona_2", "col_zona_3", "col_zona_vykhodu"]

                    for row_spec in table_structure:
                        table_row = {"parameter_name": row_spec["row_label"]}

                        for i, field_spec in enumerate(row_spec["data_fields"]):
                            key_for_column = column_keys_map[i]
                            cell_display_value = "-"

                            if isinstance(field_spec, str):
                                raw_value = getattr(selected_task_params, field_spec, None)
                                if raw_value is not None:
                                    try:
                                        cell_display_value = f"{float(raw_value):.1f}"
                                    except (ValueError, TypeError):
                                        pass
                            elif isinstance(field_spec, tuple) and len(field_spec) == 2:
                                val1_str, val2_str = "-", "-"
                                raw_val1 = getattr(selected_task_params, field_spec[0], None)
                                raw_val2 = getattr(selected_task_params, field_spec[1], None)
                                if raw_val1 is not None:
                                    try:
                                        val1_str = f"{float(raw_val1):.1f}"
                                    except (ValueError, TypeError):
                                        pass
                                if raw_val2 is not None:
                                    try:
                                        val2_str = f"{float(raw_val2):.1f}"
                                    except (ValueError, TypeError):
                                        pass

                                if val1_str != "-" or val2_str != "-":
                                    cell_display_value = f"{val1_str} / {val2_str}"

                            table_row[key_for_column] = cell_display_value
                        new_detailed_task_table_data.append(table_row)

                detailed_task_table_data = new_detailed_task_table_data
            else:
                detailed_task_table_data = []

            if selected_task_object.status in ['done', 'done_late']:
                calculated_totals = calculate_task_totals(selected_task_object)
                if calculated_totals:
                    resource_key_translations = {
                        'fuel': 'Рідке паливо',
                        'gas': 'Газ',
                        'electricity': 'Електроенергія',
                        'air': 'Стиснене повітря',
                        'solution': 'Розчин CaCl2'
                    }

                    translated_costs = {}
                    if calculated_totals.get('costs'):
                        for key, value in calculated_totals['costs'].items():
                            translated_costs[resource_key_translations.get(key, key)] = value

                    task_totals_info = calculated_totals.copy()
                    task_totals_info['costs'] = translated_costs

                    translated_energy_consumption = {}
                    if calculated_totals.get('energy_consumption'):
                        for key, value in calculated_totals['energy_consumption'].items():
                            translated_energy_consumption[resource_key_translations.get(key, key)] = value
                    energy_consumption_info = translated_energy_consumption

                    final_measurement_for_quality = calculated_totals.get('final_measurement')
                    if final_measurement_for_quality:
                        quality_assessment_info = calculate_quality(final_measurement_for_quality)
                        if quality_assessment_info and quality_assessment_info.get(
                                'total') is not None and selected_task_object.quantity is not None:
                            try:
                                quantity_decimal = Decimal(selected_task_object.quantity)
                                value_assessment_info = calculate_value_assessment(selected_task_object,
                                                                                   quality_assessment_info['total'])
                            except InvalidOperation:
                                print(
                                    f"[ERROR Analysis] Некоректне значення quantity для завдання ID {selected_task_object.id}: {selected_task_object.quantity}")
                                value_assessment_info = None
        except Http404:
            messages.error(request, "Обране завдання не знайдено.")
            selected_task_id = None
            no_data_for_selected_task = True
        except Exception as e:
            messages.error(request, f"Помилка при отриманні даних для завдання: {e}")
            selected_task_id = None
            no_data_for_selected_task = True

    if selected_task_id and not task_specific_chart_data:
        no_data_for_selected_task = True
    elif not selected_task_id:
        no_data_for_selected_task = False
    else:
        no_data_for_selected_task = False

    tariffs = Tariff.objects.all().order_by('id')
    planned_tasks = Task.objects.filter(status='new').order_by('deadline')

    time_points_list_for_context = time_points_for_html if selected_task_id and not no_data_for_selected_task else []
    main_zone_names_list_for_context = main_zone_names_for_html if selected_task_id and not no_data_for_selected_task else []
    time_axis_label_for_context = ""

    aggregated_tasks_chart_data = None
    task_ids_for_chart2 = []
    total_costs_for_chart2 = []
    qualities_for_chart2 = []
    efficiency_scores_for_chart2 = []

    for task_in_list in tasks_for_sidebar:
        actual_status_repr = repr(task_in_list.status)
        display_status = task_in_list.get_status_display()
        print(
            f"[AGG_DEBUG] Обробка завдання ID: {task_in_list.id}, Фактичний статус з БД (repr): {actual_status_repr}, Відображуваний статус: {display_status}")

        valid_done_statuses = ['done', 'done_late', 'Виконано', 'Виконано із запізненням']
        is_done_or_late = task_in_list.status in valid_done_statuses
        print(
            f"[AGG_DEBUG {task_in_list.id}] Перевірка (task_in_list.status in {valid_done_statuses}): {is_done_or_late}")

        if is_done_or_late:
            agg_task_totals = calculate_task_totals(task_in_list)
            print(f"[AGG_DEBUG {task_in_list.id}] agg_task_totals: {agg_task_totals}")

            agg_quality_assessment = None
            agg_value_assessment = None
            agg_efficiency_score = None

            if agg_task_totals and agg_task_totals.get('total_cost') is not None:
                current_total_cost = agg_task_totals['total_cost']
                print(f"[AGG_DEBUG {task_in_list.id}] current_total_cost: {current_total_cost}")
                final_meas = agg_task_totals.get('final_measurement')
                print(f"[AGG_DEBUG {task_in_list.id}] final_measurement: {final_meas}")

                if final_meas:
                    agg_quality_assessment = calculate_quality(final_meas)
                    print(f"[AGG_DEBUG {task_in_list.id}] agg_quality_assessment: {agg_quality_assessment}")

                if agg_quality_assessment and agg_quality_assessment.get(
                        'total') is not None and task_in_list.quantity is not None:
                    try:
                        quantity_dec = Decimal(task_in_list.quantity)
                        agg_value_assessment = calculate_value_assessment(task_in_list, agg_quality_assessment['total'])
                        print(f"[AGG_DEBUG {task_in_list.id}] agg_value_assessment: {agg_value_assessment}")
                    except InvalidOperation:
                        agg_value_assessment = None
                        print(
                            f"[AGG_ERROR {task_in_list.id}] Invalid quantity for value assessment: {task_in_list.quantity}")

                if agg_value_assessment is not None:
                    agg_efficiency_score = calculate_efficiency_score(agg_value_assessment, current_total_cost)
                    print(f"[AGG_DEBUG {task_in_list.id}] agg_efficiency_score: {agg_efficiency_score}")

                cost_to_add = float(current_total_cost) if current_total_cost is not None else None
                quality_to_add = float(agg_quality_assessment['total']) if agg_quality_assessment and \
                                                                           agg_quality_assessment[
                                                                               'total'] is not None else None
                efficiency_to_add = float(agg_efficiency_score) if agg_efficiency_score is not None else None

                task_ids_for_chart2.append(f"ID {task_in_list.id}")
                total_costs_for_chart2.append(cost_to_add)
                qualities_for_chart2.append(quality_to_add)
                efficiency_scores_for_chart2.append(efficiency_to_add)
                print(
                    f"[AGG_DEBUG {task_in_list.id}] Додано до списків: ID={task_in_list.id}, Cost={cost_to_add}, Q={quality_to_add}, E={efficiency_to_add}")
            else:
                print(
                    f"[AGG_DEBUG {task_in_list.id}] Пропуск додавання до графіку: немає total_cost або agg_task_totals is None.")
        else:
            print(
                f"[AGG_DEBUG {task_in_list.id}] Пропуск: завдання не має одного зі статусів {valid_done_statuses}. Фактичний статус (repr): {actual_status_repr}")

    print(f"[AGG_DEBUG FINAL] task_ids_for_chart2: {task_ids_for_chart2}")
    if not task_ids_for_chart2:
        print(
            "[AGG_DEBUG FINAL] Список ID для другого графіка порожній. aggregated_tasks_chart_data не буде сформовано.")

    if task_ids_for_chart2:
        aggregated_tasks_chart_data = {
            'labels': task_ids_for_chart2,
            'datasets': [
                {
                    'label': 'Загальні витрати (грн)',
                    'data': total_costs_for_chart2,
                    'borderColor': 'rgba(255, 99, 132, 1)',
                    'backgroundColor': 'rgba(255, 99, 132, 0.5)',
                    'yAxisID': 'yCosts',
                    'type': 'bar',
                },
                {
                    'label': 'Коефіцієнт якості',
                    'data': qualities_for_chart2,
                    'borderColor': 'rgba(54, 162, 235, 1)',
                    'backgroundColor': 'rgba(54, 162, 235, 0.5)',
                    'yAxisID': 'yQualityEfficiency',
                    'type': 'line',
                    'tension': 0.1,
                },
                {
                    'label': 'Показник ефективності',
                    'data': efficiency_scores_for_chart2,
                    'borderColor': 'rgba(75, 192, 192, 1)',
                    'backgroundColor': 'rgba(75, 192, 192, 0.5)',
                    'yAxisID': 'yQualityEfficiency',
                    'type': 'line',
                    'tension': 0.1,
                }
            ]
        }
        print(f"[AGG_DEBUG FINAL] aggregated_tasks_chart_data СФОРМОВАНО.")
    else:
        aggregated_tasks_chart_data = None
        print(f"[AGG_DEBUG FINAL] aggregated_tasks_chart_data ВСТАНОВЛЕНО В None.")

    aggregated_tasks_table_data = []
    if task_ids_for_chart2:
        for i in range(len(task_ids_for_chart2)):
            aggregated_tasks_table_data.append({
                'task_id_display': task_ids_for_chart2[i],
                'total_cost': total_costs_for_chart2[i],
                'quality': qualities_for_chart2[i],
                'efficiency': efficiency_scores_for_chart2[i],
            })

    context = {
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'selected_shift': selected_shift,
        'tasks_for_sidebar': tasks_for_sidebar,
        'selected_task_id': selected_task_id,
        'selected_task_object': selected_task_object,
        'task_specific_chart_data_json': json.dumps(task_specific_chart_data) if task_specific_chart_data else None,
        'annotation_data_json': json.dumps(annotation_data) if annotation_data else None,
        'no_data_for_selected_task': no_data_for_selected_task,
        'time_axis_label_html': time_axis_label_for_context,
        'time_points_for_html_loop': time_points_list_for_context,
        'time_points_for_js_json': json.dumps(time_points_list_for_context),
        'main_zone_names_html': main_zone_names_list_for_context,
        'main_zone_names_for_js_json': json.dumps(main_zone_names_list_for_context),
        'task_totals_info': task_totals_info,
        'quality_assessment_info': quality_assessment_info,
        'value_assessment_info': value_assessment_info,
        'energy_consumption_info': energy_consumption_info,
        'aggregated_tasks_chart_data_json': json.dumps(
            aggregated_tasks_chart_data) if aggregated_tasks_chart_data else None,
        'aggregated_tasks_table_data': aggregated_tasks_table_data,
        'tariffs': tariffs,
        'planned_tasks': planned_tasks,
        'detailed_task_table_data': detailed_task_table_data,
    }
    print(
        f"[VIEW_DEBUG] aggregated_tasks_chart_data_json передається в контекст: {context['aggregated_tasks_chart_data_json']}")
    return render(request, 'tasks/analysis.html', context)
