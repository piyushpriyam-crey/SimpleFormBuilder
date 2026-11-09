# Simple Form Builder

A multi-form Django application with a drag-and-drop form builder, field
configuration, live preview, submission storage, and one-click exports.

## Features

- **Multiple forms** — create, list, preview, and delete as many forms as you need.
- **Drag & drop builder** — drag field types from a palette onto a sortable canvas
  (SortableJS), reorder fields, and configure each field in a side panel.
- **12 field types** — text, textarea, email, password, number, URL, date,
  select, radio, checkbox, file, hidden.
- **Per-field config** — label, name, placeholder, help text, default value,
  required flag, and choices (one per line) for choice fields.
- **Live preview & submissions** — preview renders the real Bootstrap form;
  submissions are stored as JSON and viewable in the admin UI.
- **One-click downloads** — export any form as:
  - **JSON** — portable form definition
  - **Django `forms.py`** — ready-to-use `forms.Form` class
  - **Standalone HTML** — a self-contained Bootstrap 5 page

## Setup

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/ and click **+ New Form**.

## Project layout

```
config/          Django project settings & URLs
builder/         The form-builder app (models, views, URLs, admin)
templates/builder/  Bootstrap 5 templates
static/builder/  Drag-and-drop builder JS
```

## Models

- `Form` — name, description, timestamps
- `FormField` — type, label, name, placeholder, help text, default, required,
  choices (newline-separated), ordering
- `Submission` — JSON payload per submission
