from django.contrib import admin

from .models import Form, FormField, Submission


class FormFieldInline(admin.TabularInline):
    model = FormField
    extra = 0
    ordering = ['order']


@admin.register(Form)
class FormAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    inlines = [FormFieldInline]


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('form', 'created_at')
    list_filter = ('form',)
