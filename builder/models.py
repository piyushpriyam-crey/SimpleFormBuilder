from django.db import models


FIELD_TYPES = [
    ('text', 'Text'),
    ('textarea', 'Textarea'),
    ('email', 'Email'),
    ('password', 'Password'),
    ('number', 'Number'),
    ('url', 'URL'),
    ('date', 'Date'),
    ('select', 'Select'),
    ('radio', 'Radio'),
    ('checkbox', 'Checkbox'),
    ('file', 'File'),
    ('hidden', 'Hidden'),
    ('h1', 'Heading 1'),
    ('h2', 'Heading 2'),
    ('h3', 'Heading 3'),
    ('h4', 'Heading 4'),
    ('h5', 'Heading 5'),
    ('h6', 'Heading 6'),
]

CHOICE_TYPES = {'select', 'radio', 'checkbox'}
LENGTH_TYPES = {'text', 'textarea', 'email', 'password', 'url', 'hidden'}
RANGE_TYPES = {'number'}
HEADING_TYPES = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}

FIELD_GROUPS = [
    ('Text Inputs', ['text', 'textarea', 'email', 'password', 'number', 'url', 'date']),
    ('Choice Inputs', ['select', 'radio', 'checkbox']),
    ('Layout', ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']),
    ('Advanced', ['file', 'hidden']),
]


class Form(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class FormPage(models.Model):
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='pages')
    title = models.CharField(max_length=200, default='Page 1')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.form.name} — {self.title}'


class FormField(models.Model):
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='fields')
    page = models.ForeignKey(FormPage, on_delete=models.CASCADE, null=True, blank=True, related_name='fields')
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, default='text')
    label = models.CharField(max_length=200)
    name = models.CharField(max_length=100, blank=True)
    placeholder = models.CharField(max_length=200, blank=True)
    help_text = models.CharField(max_length=300, blank=True)
    default_value = models.CharField(max_length=300, blank=True)
    required = models.BooleanField(default=False)
    choices = models.TextField(blank=True)  # one option per line
    max_length = models.PositiveIntegerField(null=True, blank=True)
    min_length = models.PositiveIntegerField(null=True, blank=True)
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    css_class = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.label} ({self.field_type})'

    def clean_name(self):
        name = self.name.strip()
        if not name:
            name = self.label.lower().replace(' ', '_')
        return name

    @property
    def is_heading(self):
        return self.field_type in HEADING_TYPES

    @property
    def choice_list(self):
        return [c.strip() for c in self.choices.splitlines() if c.strip()]


class Submission(models.Model):
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='submissions')
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Submission #{self.pk} for {self.form.name}'
