import io
import json
import re
import zipfile

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .models import (
    CHOICE_TYPES, FIELD_GROUPS, FIELD_TYPES, HEADING_TYPES, LENGTH_TYPES,
    RANGE_TYPES, Form, FormField, FormPage, Submission,
)

FIELD_TYPE_LABELS = dict(FIELD_TYPES)


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _field_attrs(f):
    return {
        'max_length': f.max_length,
        'min_length': f.min_length,
        'min_value': f.min_value,
        'max_value': f.max_value,
        'css_class': f.css_class,
    }


def _serialize_field(f):
    return {
        'id': f.id,
        'field_type': f.field_type,
        'label': f.label,
        'name': f.name,
        'placeholder': f.placeholder,
        'help_text': f.help_text,
        'default_value': f.default_value,
        'required': f.required,
        'choices': f.choices,
        **_field_attrs(f),
    }


def _ensure_pages(form):
    """Give legacy forms (fields without pages) a default page."""
    if form.pages.exists():
        return
    orphans = list(form.fields.filter(page__isnull=True))
    if not orphans:
        return
    page = FormPage.objects.create(form=form, title='Page 1', order=0)
    FormField.objects.filter(pk__in=[f.pk for f in orphans]).update(page=page)


def form_list(request):
    forms = Form.objects.all()
    return render(request, 'builder/form_list.html', {'forms': forms})


@require_http_methods(['GET', 'POST'])
def form_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            form = Form.objects.create(
                name=name,
                description=request.POST.get('description', ''),
            )
            return redirect('builder:builder', pk=form.pk)
    return render(request, 'builder/form_create.html')


def form_delete(request, pk):
    form = get_object_or_404(Form, pk=pk)
    if request.method == 'POST':
        form.delete()
        return redirect('builder:list')
    return render(request, 'builder/form_delete.html', {'form': form})


def builder(request, pk):
    form = get_object_or_404(Form, pk=pk)
    _ensure_pages(form)
    pages = form.pages.prefetch_related('fields').all()
    pages_json = [
        {
            'id': p.id,
            'title': p.title,
            'fields': [_serialize_field(f) for f in p.fields.all()],
        }
        for p in pages
    ]
    if not pages_json:
        pages_json = [{'id': None, 'title': 'Page 1', 'fields': []}]
    field_groups = [
        (header, [(v, FIELD_TYPE_LABELS[v]) for v in types if v in FIELD_TYPE_LABELS])
        for header, types in FIELD_GROUPS
    ]
    return render(request, 'builder/builder.html', {
        'form': form,
        'pages_json': json.dumps(pages_json),
        'field_groups': field_groups,
    })


@require_POST
def api_save_fields(request, pk):
    form = get_object_or_404(Form, pk=pk)
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    pages_payload = payload.get('pages')
    if pages_payload is None:
        # legacy single-page payload
        pages_payload = [{'title': 'Page 1', 'fields': payload.get('fields', [])}]

    form.fields.all().delete()  # orphans without a page
    form.pages.all().delete()  # cascades to paged fields
    count = 0
    for pi, p in enumerate(pages_payload):
        page = FormPage.objects.create(
            form=form,
            title=(p.get('title') or '').strip() or f'Page {pi + 1}',
            order=pi,
        )
        for i, f in enumerate(p.get('fields', [])):
            FormField.objects.create(
                form=form,
                page=page,
                field_type=f.get('field_type', 'text'),
                label=f.get('label', '') or f'Field {i + 1}',
                name=f.get('name', ''),
                placeholder=f.get('placeholder', ''),
                help_text=f.get('help_text', ''),
                default_value=f.get('default_value', ''),
                required=bool(f.get('required')),
                choices=f.get('choices', ''),
                max_length=_parse_int(f.get('max_length')),
                min_length=_parse_int(f.get('min_length')),
                min_value=_parse_float(f.get('min_value')),
                max_value=_parse_float(f.get('max_value')),
                css_class=f.get('css_class', ''),
                order=i,
            )
            count += 1
    return JsonResponse({'status': 'ok', 'count': count, 'pages': len(pages_payload)})


def preview(request, pk):
    form = get_object_or_404(Form, pk=pk)
    _ensure_pages(form)
    pages = form.pages.prefetch_related('fields').all()
    return render(request, 'builder/preview.html', {'form': form, 'pages': pages})


@require_POST
def submit(request, pk):
    form = get_object_or_404(Form, pk=pk)
    data = {}
    for field in form.fields.all():
        if field.field_type in HEADING_TYPES:
            continue
        name = field.name or field.label.lower().replace(' ', '_')
        if field.field_type == 'checkbox':
            data[name] = request.POST.getlist(name)
        elif field.field_type == 'file':
            uploaded = request.FILES.get(name)
            data[name] = uploaded.name if uploaded else ''
        else:
            data[name] = request.POST.get(name, '')
    Submission.objects.create(form=form, data=data)
    return render(request, 'builder/submitted.html', {'form': form})


def submissions(request, pk):
    form = get_object_or_404(Form, pk=pk)
    return render(request, 'builder/submissions.html', {
        'form': form,
        'submissions': form.submissions.all()[:100],
    })


# ---------------- Exports ----------------

def _field_name(field):
    return field.name or field.label.lower().replace(' ', '_')


def export_json(request, pk):
    form = get_object_or_404(Form, pk=pk)
    _ensure_pages(form)

    def field_json(f):
        return {
            'field_type': f.field_type,
            'label': f.label,
            'name': _field_name(f),
            'placeholder': f.placeholder,
            'help_text': f.help_text,
            'default_value': f.default_value,
            'required': f.required,
            'choices': f.choice_list,
            **_field_attrs(f),
        }

    data = {
        'name': form.name,
        'description': form.description,
        'pages': [
            {'title': p.title, 'fields': [field_json(f) for f in p.fields.all()]}
            for p in form.pages.prefetch_related('fields').all()
        ],
        'fields': [field_json(f) for f in form.fields.all()],
    }
    response = HttpResponse(
        json.dumps(data, indent=2),
        content_type='application/json',
    )
    response['Content-Disposition'] = f'attachment; filename="{form.name}.json"'
    return response


def generate_django_form_code(form):
    lines = [
        'from django import forms',
        '',
        '',
        f'class {form.name.title().replace(" ", "")}Form(forms.Form):',
    ]
    fields = [f for f in form.fields.all() if f.field_type not in HEADING_TYPES]
    if not fields:
        lines.append('    pass')
    FIELD_CLASS = {
        'text': 'forms.CharField', 'textarea': 'forms.CharField',
        'email': 'forms.EmailField', 'password': 'forms.CharField',
        'number': 'forms.FloatField', 'url': 'forms.URLField',
        'date': 'forms.DateField', 'select': 'forms.ChoiceField',
        'radio': 'forms.ChoiceField',
        'checkbox': 'forms.MultipleChoiceField',
        'file': 'forms.FileField', 'hidden': 'forms.CharField',
    }
    WIDGET_MAP = {
        'textarea': 'forms.Textarea', 'password': 'forms.PasswordInput',
        'date': 'forms.DateInput', 'hidden': 'forms.HiddenInput',
        'radio': 'forms.RadioSelect',
        'checkbox': 'forms.CheckboxSelectMultiple',
        'select': 'forms.Select', 'text': 'forms.TextInput',
        'email': 'forms.EmailInput', 'number': 'forms.NumberInput',
        'url': 'forms.URLInput',
    }
    ALWAYS_WIDGET = {'textarea', 'password', 'date', 'hidden', 'radio', 'checkbox'}

    for f in fields:
        name = _field_name(f)
        ft = f.field_type
        kwargs = ['required=True' if f.required else 'required=False']
        if f.help_text:
            kwargs.append(f"help_text={f.help_text!r}")
        if f.default_value:
            kwargs.append(f"initial={f.default_value!r}")
        if ft in LENGTH_TYPES:
            if f.max_length:
                kwargs.append(f"max_length={f.max_length}")
            if f.min_length:
                kwargs.append(f"min_length={f.min_length}")
        if ft in RANGE_TYPES:
            if f.min_value is not None:
                kwargs.append(f"min_value={f.min_value}")
            if f.max_value is not None:
                kwargs.append(f"max_value={f.max_value}")
        if ft in CHOICE_TYPES:
            choices = ', '.join(f'({c!r}, {c!r})' for c in f.choice_list)
            kwargs.append(f"choices=[{choices}]")

        attrs = {}
        if f.placeholder:
            attrs['placeholder'] = f.placeholder
        if f.css_class:
            attrs['class'] = f.css_class
        if ft == 'date':
            attrs['type'] = 'date'
        if ft in WIDGET_MAP and (attrs or ft in ALWAYS_WIDGET):
            widget = WIDGET_MAP[ft]
            if attrs:
                attr_str = ', '.join(f'{k!r}: {v!r}' for k, v in attrs.items())
                kwargs.append(f"widget={widget}(attrs={{{attr_str}}})")
            else:
                kwargs.append(f"widget={widget}")

        decl = f'{FIELD_CLASS.get(ft, "forms.CharField")}({", ".join(kwargs)})'
        label_arg = f', label={f.label!r}' if f.label != name.replace('_', ' ').title() else ''
        lines.append(f'    {name} = {decl}{label_arg}')

    return '\n'.join(lines) + '\n'


def export_django(request, pk):
    form = get_object_or_404(Form, pk=pk)
    content = generate_django_form_code(form)
    response = HttpResponse(content, content_type='text/x-python')
    response['Content-Disposition'] = f'attachment; filename="{form.name}_form.py"'
    return response


def _slug(text):
    slug = re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')
    return slug or 'myform'


def export_project(request, pk):
    """Download a ready-made Django project containing this form."""
    form = get_object_or_404(Form, pk=pk)
    _ensure_pages(form)
    slug = _slug(form.name)
    class_name = f'{form.name.title().replace(" ", "")}Form'
    forms_code = generate_django_form_code(form)

    settings_py = f'''from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-dev-key-change-me'
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = '{slug}.urls'

TEMPLATES = [
    {{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {{
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        }},
    }},
]

DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }}
}}

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
'''

    project_urls = f'''from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
]
'''

    core_views = f'''from django.views.generic import FormView, TemplateView
from django.urls import reverse_lazy

from .forms import {class_name}


class FormPageView(FormView):
    form_class = {class_name}
    template_name = 'core/form.html'
    success_url = reverse_lazy('core:success')


class SuccessView(TemplateView):
    template_name = 'core/success.html'
'''

    core_urls = '''from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.FormPageView.as_view(), name='form'),
    path('success/', views.SuccessView.as_view(), name='success'),
]
'''

    core_models = "from django.db import models\n"
    core_admin = "from django.contrib import admin\n"
    core_apps = "from django.apps import AppConfig\n\n\nclass CoreConfig(AppConfig):\n    default_auto_field = 'django.db.models.BigAutoField'\n    name = 'core'\n"

    form_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{form.name}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    .form-control, .form-select {{ width: 100%; padding: .375rem .75rem; border: 1px solid #ced4da; border-radius: .375rem; }}
    textarea.form-control {{ min-height: 100px; }}
    .form-check {{ margin-bottom: .25rem; }}
  </style>
</head>
<body class="bg-light">
  <div class="container py-5" style="max-width: 720px;">
    <h1 class="mb-2">{form.name}</h1>
    {'<p class="text-muted">' + form.description + '</p>' if form.description else ''}
    <form method="post" class="card p-4">
      {{% csrf_token %}}
      {{% for field in form %}}
      <div class="mb-3">
        <label class="form-label fw-semibold" for="{{{{ field.id_for_label }}}}">{{{{ field.label }}}}{{% if field.field.required %}} <span class="text-danger">*</span>{{% endif %}}</label>
        {{{{ field }}}}
        {{% if field.help_text %}}<div class="form-text">{{{{ field.help_text }}}}</div>{{% endif %}}
        {{% for error in field.errors %}}<div class="text-danger small">{{{{ error }}}}</div>{{% endfor %}}
      </div>
      {{% endfor %}}
      <button type="submit" class="btn btn-primary">Submit</button>
    </form>
  </div>
</body>
</html>
'''

    success_html = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Thank you</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
  <div class="container py-5" style="max-width: 720px;">
    <div class="alert alert-success"><h1 class="h5">Thank you!</h1><p class="mb-0">Your submission has been received.</p></div>
  </div>
</body>
</html>
'''

    project_readme = f'''# {form.name}

A Django project generated by Simple Form Builder.

## Run

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/ to view the form.

## Structure

- `{slug}/` — project settings & URLs
- `core/` — the app containing `forms.py` (edit fields here), views, URLs and templates
- `core/templates/core/form.html` — the Bootstrap 5 form template
'''

    manage_py = f'''#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{slug}.settings')
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
'''

    wsgi_py = f'''import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{slug}.settings')

application = get_wsgi_application()
'''

    asgi_py = f'''import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{slug}.settings')

application = get_asgi_application()
'''

    files = {
        f'{slug}/manage.py': manage_py,
        f'{slug}/requirements.txt': 'Django>=5.0\n',
        f'{slug}/README.md': project_readme,
        f'{slug}/{slug}/__init__.py': '',
        f'{slug}/{slug}/settings.py': settings_py,
        f'{slug}/{slug}/urls.py': project_urls,
        f'{slug}/{slug}/wsgi.py': wsgi_py,
        f'{slug}/{slug}/asgi.py': asgi_py,
        f'{slug}/core/__init__.py': '',
        f'{slug}/core/apps.py': core_apps,
        f'{slug}/core/admin.py': core_admin,
        f'{slug}/core/models.py': core_models,
        f'{slug}/core/forms.py': forms_code,
        f'{slug}/core/views.py': core_views,
        f'{slug}/core/urls.py': core_urls,
        f'{slug}/core/migrations/__init__.py': '',
        f'{slug}/core/templates/core/form.html': form_html,
        f'{slug}/core/templates/core/success.html': success_html,
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    buffer.seek(0)

    response = HttpResponse(buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{slug}_project.zip"'
    return response


def export_html(request, pk):
    form = get_object_or_404(Form, pk=pk)
    _ensure_pages(form)
    html = render_to_string_html(form)
    response = HttpResponse(html, content_type='text/html')
    response['Content-Disposition'] = f'attachment; filename="{form.name}.html"'
    return response


def render_to_string_html(form):
    parts = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '  <meta charset="UTF-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        '  <title>' + form.name + '</title>',
        '  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">',
        '</head>',
        '<body class="bg-light">',
        '  <div class="container py-5" style="max-width: 720px;">',
        f'    <h1 class="mb-2">{form.name}</h1>',
    ]
    if form.description:
        parts.append(f'    <p class="text-muted">{form.description}</p>')
    parts.append('    <form method="post" class="card p-4">')

    def html_attrs(f):
        attrs = ''
        if f.field_type in LENGTH_TYPES:
            if f.max_length:
                attrs += f' maxlength="{f.max_length}"'
            if f.min_length:
                attrs += f' minlength="{f.min_length}"'
        if f.field_type in RANGE_TYPES:
            if f.min_value is not None:
                attrs += f' min="{f.min_value}"'
            if f.max_value is not None:
                attrs += f' max="{f.max_value}"'
        if f.css_class:
            attrs += f' class="{f.css_class}"'
        return attrs

    pages = list(form.pages.prefetch_related('fields').all())
    show_page_titles = len(pages) > 1
    for page in pages:
        if show_page_titles:
            parts.append(f'      <h5 class="mt-4 mb-2 text-secondary">{page.title}</h5>')
        for f in page.fields.all():
            if f.field_type in HEADING_TYPES:
                hcls = f' class="{f.css_class}"' if f.css_class else ''
                parts.append(f'      <{f.field_type}{hcls}>{f.label}</{f.field_type}>')
                continue
            name = _field_name(f)
            req = ' required' if f.required else ''
            extra = html_attrs(f)
            parts.append('      <div class="mb-3">')
            parts.append(f'        <label class="form-label fw-semibold" for="id_{name}">{f.label}</label>')

            ft = f.field_type
            if ft == 'textarea':
                parts.append(f'        <textarea class="form-control" id="id_{name}" name="{name}" rows="4" placeholder="{f.placeholder}"{req}{extra}>{f.default_value}</textarea>')
            elif ft == 'select':
                parts.append(f'        <select class="form-select" id="id_{name}" name="{name}"{req}{extra}>')
                parts.append('          <option value="">---------</option>')
                for c in f.choice_list:
                    sel = ' selected' if c == f.default_value else ''
                    parts.append(f'          <option value="{c}"{sel}>{c}</option>')
                parts.append('        </select>')
            elif ft == 'radio':
                for c in f.choice_list:
                    checked = ' checked' if c == f.default_value else ''
                    parts.append(f'        <div class="form-check"><input class="form-check-input" type="radio" name="{name}" id="id_{name}_{c}" value="{c}"{checked}><label class="form-check-label" for="id_{name}_{c}">{c}</label></div>')
            elif ft == 'checkbox':
                for c in f.choice_list:
                    parts.append(f'        <div class="form-check"><input class="form-check-input" type="checkbox" name="{name}" id="id_{name}_{c}" value="{c}"><label class="form-check-label" for="id_{name}_{c}">{c}</label></div>')
            elif ft == 'file':
                parts.append(f'        <input type="file" class="form-control" id="id_{name}" name="{name}"{req}{extra}>')
            elif ft == 'hidden':
                parts.append(f'        <input type="hidden" name="{name}" value="{f.default_value}">')
            else:
                input_type = {'email': 'email', 'password': 'password', 'number': 'number', 'url': 'url', 'date': 'date'}.get(ft, 'text')
                parts.append(f'        <input type="{input_type}" class="form-control" id="id_{name}" name="{name}" placeholder="{f.placeholder}" value="{f.default_value}"{req}{extra}>')

            if f.help_text:
                parts.append(f'        <div class="form-text">{f.help_text}</div>')
            parts.append('      </div>')

    parts.append('      <button type="submit" class="btn btn-primary">Submit</button>')
    parts.append('    </form>')
    parts.append('  </div>')
    parts.append('  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>')
    parts.append('</body>')
    parts.append('</html>')
    return '\n'.join(parts)
