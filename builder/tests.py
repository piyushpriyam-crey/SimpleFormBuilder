import json

from django.test import TestCase
from django.urls import reverse

from .models import Form, FormField, Submission


class FormModelTests(TestCase):
    def test_form_str(self):
        form = Form.objects.create(name='Contact Us')
        self.assertEqual(str(form), 'Contact Us')

    def test_field_name_fallback_and_choices(self):
        form = Form.objects.create(name='F')
        field = FormField.objects.create(
            form=form, field_type='select', label='Pick One',
            choices='A\nB\n\nC', order=0,
        )
        self.assertEqual(field.clean_name(), 'pick_one')
        self.assertEqual(field.choice_list, ['A', 'B', 'C'])

    def test_field_ordering(self):
        form = Form.objects.create(name='F')
        FormField.objects.create(form=form, label='Second', order=2)
        FormField.objects.create(form=form, label='First', order=1)
        self.assertEqual([f.label for f in form.fields.all()], ['First', 'Second'])


class ViewTests(TestCase):
    def setUp(self):
        self.form = Form.objects.create(name='Contact Us', description='Say hi')

    def test_list_shows_form(self):
        self.assertContains(self.client.get(reverse('builder:list')), 'Contact Us')

    def test_list_empty(self):
        self.form.delete()
        self.assertContains(self.client.get(reverse('builder:list')), 'No forms yet')

    def test_create_form(self):
        resp = self.client.post(reverse('builder:create'), {
            'name': 'Survey', 'description': 'Quick survey',
        })
        self.assertRedirects(resp, reverse('builder:builder', args=[Form.objects.get(name='Survey').pk]))
        self.assertTrue(Form.objects.filter(name='Survey').exists())

    def test_create_requires_name(self):
        resp = self.client.post(reverse('builder:create'), {'name': '', 'description': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Form.objects.filter(name='').exists())

    def test_builder_page(self):
        resp = self.client.get(reverse('builder:builder', args=[self.form.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Contact Us')

    def test_builder_404(self):
        self.assertEqual(self.client.get(reverse('builder:builder', args=[999])).status_code, 404)

    def test_delete_form(self):
        pk = self.form.pk
        self.client.post(reverse('builder:delete', args=[pk]))
        self.assertFalse(Form.objects.filter(pk=pk).exists())


class SaveFieldsTests(TestCase):
    def setUp(self):
        self.form = Form.objects.create(name='F')
        self.url = reverse('builder:save', args=[self.form.pk])

    def test_save_fields(self):
        payload = {
            'fields': [
                {'field_type': 'text', 'label': 'Name', 'required': True},
                {'field_type': 'select', 'label': 'Color', 'choices': 'Red\nBlue'},
            ]
        }
        resp = self.client.post(
            self.url, data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.form.fields.count(), 2)
        first = self.form.fields.first()
        self.assertEqual(first.field_type, 'text')
        self.assertTrue(first.required)
        self.assertEqual(first.order, 0)

    def test_save_replaces_existing(self):
        FormField.objects.create(form=self.form, label='Old', order=0)
        self.client.post(
            self.url, data=json.dumps({'fields': []}),
            content_type='application/json',
        )
        self.assertEqual(self.form.fields.count(), 0)

    def test_save_invalid_json(self):
        resp = self.client.post(
            self.url, data='not json', content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_save_requires_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_save_multi_page(self):
        payload = {
            'pages': [
                {'title': 'Basics', 'fields': [
                    {'field_type': 'text', 'label': 'Name', 'required': True},
                ]},
                {'title': 'Details', 'fields': [
                    {'field_type': 'textarea', 'label': 'Bio'},
                    {'field_type': 'number', 'label': 'Age', 'min_value': 0},
                ]},
            ]
        }
        resp = self.client.post(
            self.url, data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.form.pages.count(), 2)
        self.assertEqual(self.form.fields.count(), 3)
        pages = list(self.form.pages.all())
        self.assertEqual(pages[0].title, 'Basics')
        self.assertEqual(pages[0].fields.count(), 1)
        self.assertEqual(pages[1].fields.count(), 2)
        age = self.form.fields.get(label='Age')
        self.assertEqual(age.min_value, 0.0)
        self.assertEqual(age.page.title, 'Details')

    def test_save_pages_replaces_old(self):
        FormField.objects.create(form=self.form, label='Old', order=0)
        payload = {'pages': [{'title': 'Only', 'fields': []}]}
        self.client.post(
            self.url, data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(self.form.pages.count(), 1)
        self.assertEqual(self.form.fields.count(), 0)


class PreviewAndSubmitTests(TestCase):
    def setUp(self):
        self.form = Form.objects.create(name='Contact Us')
        FormField.objects.create(form=self.form, field_type='text', label='Name', name='name', required=True, order=0)
        FormField.objects.create(form=self.form, field_type='checkbox', label='Tags', name='tags', choices='a\nb', order=1)

    def test_preview_renders_fields(self):
        resp = self.client.get(reverse('builder:preview', args=[self.form.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Name')
        self.assertContains(resp, 'value="a"')

    def test_submit_stores_submission(self):
        resp = self.client.post(reverse('builder:submit', args=[self.form.pk]), {
            'name': 'Jane', 'tags': ['a', 'b'],
        })
        self.assertEqual(resp.status_code, 200)
        sub = Submission.objects.get(form=self.form)
        self.assertEqual(sub.data['name'], 'Jane')
        self.assertEqual(sub.data['tags'], ['a', 'b'])

    def test_submissions_page(self):
        Submission.objects.create(form=self.form, data={'name': 'Jane'})
        resp = self.client.get(reverse('builder:submissions', args=[self.form.pk]))
        self.assertContains(resp, 'Jane')


class ExportTests(TestCase):
    def setUp(self):
        self.form = Form.objects.create(name='Contact Us')
        FormField.objects.create(
            form=self.form, field_type='select', label='Topic',
            name='topic', choices='Sales\nSupport', order=0,
        )
        FormField.objects.create(
            form=self.form, field_type='email', label='Email',
            name='email', required=True, order=1,
        )

    def test_export_json(self):
        resp = self.client.get(reverse('builder:export_json', args=[self.form.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/json')
        self.assertIn('attachment', resp['Content-Disposition'])
        data = json.loads(resp.content)
        self.assertEqual(data['name'], 'Contact Us')
        self.assertEqual(len(data['fields']), 2)
        self.assertEqual(data['fields'][0]['choices'], ['Sales', 'Support'])

    def test_export_django(self):
        resp = self.client.get(reverse('builder:export_django', args=[self.form.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('class ContactUsForm(forms.Form):', content)
        self.assertIn("forms.ChoiceField", content)
        self.assertIn("('Sales', 'Sales')", content)
        self.assertIn('forms.EmailField', content)

    def test_export_html(self):
        resp = self.client.get(reverse('builder:export_html', args=[self.form.pk]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('<!DOCTYPE html>', content)
        self.assertIn('bootstrap', content.lower())
        self.assertIn('Contact Us', content)
        self.assertIn('name="topic"', content)

    def test_export_project(self):
        import io
        import zipfile

        resp = self.client.get(reverse('builder:export_project', args=[self.form.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/zip')
        self.assertIn('attachment', resp['Content-Disposition'])

        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = zf.namelist()
        self.assertIn('contact_us/manage.py', names)
        self.assertIn('contact_us/contact_us/settings.py', names)
        self.assertIn('contact_us/core/forms.py', names)
        self.assertIn('contact_us/core/views.py', names)
        self.assertIn('contact_us/core/templates/core/form.html', names)

        forms_py = zf.read('contact_us/core/forms.py').decode()
        self.assertIn('class ContactUsForm(forms.Form):', forms_py)
        self.assertIn('topic = forms.ChoiceField', forms_py)

        settings_py = zf.read('contact_us/contact_us/settings.py').decode()
        self.assertIn("ROOT_URLCONF = 'contact_us.urls'", settings_py)
        self.assertIn('BASE_DIR', settings_py)
