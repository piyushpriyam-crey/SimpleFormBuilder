from django.urls import path

from . import views

app_name = 'builder'

urlpatterns = [
    path('', views.form_list, name='list'),
    path('create/', views.form_create, name='create'),
    path('<int:pk>/', views.builder, name='builder'),
    path('<int:pk>/save/', views.api_save_fields, name='save'),
    path('<int:pk>/preview/', views.preview, name='preview'),
    path('<int:pk>/submit/', views.submit, name='submit'),
    path('<int:pk>/submissions/', views.submissions, name='submissions'),
    path('<int:pk>/delete/', views.form_delete, name='delete'),
    path('<int:pk>/export/json/', views.export_json, name='export_json'),
    path('<int:pk>/export/django/', views.export_django, name='export_django'),
    path('<int:pk>/export/html/', views.export_html, name='export_html'),
    path('<int:pk>/export/project/', views.export_project, name='export_project'),
]
