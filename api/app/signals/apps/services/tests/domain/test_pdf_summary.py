# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2018 - 2022 Gemeente Amsterdam, Vereniging van Nederlandse Gemeenten
"""
These tests check the contents of PDFs generated byt the PDFSummaryService.
We do not want to parse PDFs, instead we look at the content of the intermediate
HTML.
"""
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.utils import timezone

from signals.apps.services.domain.pdf_summary import PDFSummaryService
from signals.apps.signals import workflow
from signals.apps.signals.factories import (
    CategoryFactory,
    LocationFactory,
    ParentCategoryFactory,
    SignalFactoryWithImage,
    StatusFactory,
    ValidLocationFactory
)
from signals.apps.users.factories import SuperUserFactory, UserFactory


class TestPDFSummaryService(TestCase):
    def setUp(self):
        self.parent_category = ParentCategoryFactory.create(name='PARENT-CATEGORY')
        self.child_category = CategoryFactory.create(name='CHILD-CATEGORY', parent=self.parent_category)

        self.signal = SignalFactoryWithImage.create(
            text='BLAH BLAH BLAH',
            incident_date_start=timezone.now(),
            category_assignment__category=self.child_category,
            reporter__email='foo@bar.com',
            reporter__phone='0612345678')
        StatusFactory.create(_signal=self.signal, state=workflow.AFWACHTING, text='waiting')
        StatusFactory.create(_signal=self.signal, state=workflow.ON_HOLD, text='please hold')
        status = StatusFactory.create(_signal=self.signal,
                                      state=workflow.AFGEHANDELD,
                                      text='Consider it done')
        self.signal.status = status
        self.signal.save()

        self.user = SuperUserFactory.create()

    def test_get_html(self):
        html = PDFSummaryService._get_html(self.signal, self.user, False)

        # General information about the `Signal` object.
        current_tz = timezone.get_current_timezone()
        self.assertIn(self.signal.get_id_display(), html)
        self.assertIn(self.signal.created_at.astimezone(current_tz).strftime('%d-%m-%Y'), html)
        self.assertIn(self.signal.created_at.astimezone(current_tz).strftime('%H:%M:%S'), html)
        self.assertIn(self.signal.incident_date_start.astimezone(current_tz).strftime('%d-%m-%Y'), html)
        self.assertIn(self.signal.incident_date_start.astimezone(current_tz).strftime('%H:%M:%S'), html)
        self.assertIn(self.signal.get_id_display(), html)
        self.assertIn(self.signal.category_assignment.category.parent.name, html)
        self.assertIn(self.signal.category_assignment.category.name, html)
        self.assertIn(self.signal.priority.get_priority_display(), html)
        self.assertIn(self.signal.text, html)
        self.assertIn(self.signal.location.get_stadsdeel_display(), html)
        self.assertIn(self.signal.location.address_text, html)
        self.assertIn(self.signal.source, html)

        # All status transitions.
        for status in self.signal.statuses.all():
            self.assertIn(status.state, html)
            self.assertIn(status.text, html)
            self.assertIn(status.user, html)

    def test_get_contact_details(self):
        """
        Users without "signals.sia_can_view_contact_details" permission cannot
        see contact details of the reporter. PDFs generated for use with
        CityControl always contain the contact details.

        This test checks the PDFSummaryService._get_contact_details method.
        """
        # No "signals.sia_can_view_contact_details" and no CityControl/Sigmax
        # override mean no contact details.
        user = UserFactory.create()
        email, phone = PDFSummaryService._get_contact_details(self.signal, user, False)
        self.assertFalse(user.has_perm('signals.sia_can_view_contact_details'))
        self.assertEqual(email, '*****')
        self.assertEqual(phone, '*****')

        # Check CityControl/Sigmax override
        email, phone = PDFSummaryService._get_contact_details(self.signal, None, True)
        self.assertEqual(email, 'foo@bar.com')
        self.assertEqual(phone, '0612345678')

        # Check user has "signals.sia_can_view_contact_details"
        sia_can_view_contact_details = Permission.objects.get(codename='sia_can_view_contact_details')
        user.user_permissions.add(sia_can_view_contact_details)
        user = User.objects.get(pk=user.id)

        self.assertTrue(user.has_perm('signals.sia_can_view_contact_details'))
        email, phone = PDFSummaryService._get_contact_details(self.signal, user, False)
        self.assertEqual(email, 'foo@bar.com')
        self.assertEqual(phone, '0612345678')

    def test_get_contact_details_no_contact_details_and_no_permissions(self):
        """
        Check that missing contact details are not turned into '*****' when not
        allowed to view reporter contact details.
        """
        self.signal.reporter.email = None
        self.signal.reporter.phone = None
        self.signal.reporter.save()
        self.signal.refresh_from_db()

        user = UserFactory.create()
        self.assertFalse(user.has_perm('signals.sia_can_view_contact_details'))
        email, phone = PDFSummaryService._get_contact_details(self.signal, user, False)
        self.assertEqual(email, None)
        self.assertEqual(phone, None)

    def test_show_contact_details(self):
        """
        Users without "signals.sia_can_view_contact_details" permission cannot
        see contact details of the reporter. PDFs generated for use with
        CityControl always contain the contact details.

        This test checks the intermediate HTML does or does not contain the
        contact details as appropriate.
        """
        # No "signals.sia_can_view_contact_details" and no CityControl/Sigmax
        # override mean no contact details in intermediate HTML.
        user = UserFactory.create()
        html = PDFSummaryService._get_html(self.signal, user, False)
        self.assertFalse(user.has_perm('signals.sia_can_view_contact_details'))
        self.assertNotIn('foo@bar.com', html)
        self.assertNotIn('0612345678', html)

        # Check CityControl/Sigmax override
        html = PDFSummaryService._get_html(self.signal, None, True)
        self.assertIn('foo@bar.com', html)
        self.assertIn('0612345678', html)

        # Check user has "signals.sia_can_view_contact_details"
        sia_can_view_contact_details = Permission.objects.get(codename='sia_can_view_contact_details')
        user.user_permissions.add(sia_can_view_contact_details)
        user = User.objects.get(pk=user.id)

        self.assertTrue(user.has_perm('signals.sia_can_view_contact_details'))
        html = PDFSummaryService._get_html(self.signal, user, False)
        self.assertIn('foo@bar.com', html)
        self.assertIn('0612345678', html)

    def test_location_has_stadsdeel(self):
        # test stadsdeel present
        location = ValidLocationFactory.create(_signal=self.signal)
        self.signal.location = location
        self.signal.save()
        self.signal.refresh_from_db()

        html = PDFSummaryService._get_html(self.signal, None, False)
        self.assertIn(self.signal.location.get_stadsdeel_display(), html)

    def test_location_has_area_code_and_area_name(self):
        # test area_name and area_code present
        location = LocationFactory.create(
            _signal=self.signal, area_name='AREA-NAME', area_code='AREA-CODE', stadsdeel=None)
        self.signal.location = location
        self.signal.save()
        self.signal.refresh_from_db()

        html = PDFSummaryService._get_html(self.signal, None, False)
        self.assertIn(self.signal.location.area_name, html)
        self.assertNotIn(self.signal.location.area_code, html)

    def test_location_has_no_area_name_and_area_code(self):
        # test only area_code present
        location = LocationFactory.create(_signal=self.signal, area_name=None, area_code='AREA-CODE', stadsdeel=None)
        self.signal.location = location
        self.signal.save()
        self.signal.refresh_from_db()

        html = PDFSummaryService._get_html(self.signal, None, False)
        self.assertIn(self.signal.location.area_code, html)


class TestPDFSummaryServiceWithExtraProperties(TestCase):
    def setUp(self):
        # Note: this test assumes Amsterdam categories being present, hence it being isolated.
        self.extra_properties_data = [
            {
                "id": "extra_straatverlichting",
                "label": "Is de situatie gevaarlijk?",
                "answer": {
                    "id": "niet_gevaarlijk",
                    "label": "Niet gevaarlijk"
                },
                "category_url": "/signals/v1/public/terms/categories/wegen-verkeer-straatmeubilair/sub_categories/lantaarnpaal-straatverlichting"  # noqa
            },
        ]

        self.signal = SignalFactoryWithImage.create(
            extra_properties=self.extra_properties_data,
            category_assignment__category__parent__name='Wegen, verkeer, straatmeubilair',
            category_assignment__category__name='lantaarnpaal straatverlichting'
        )

    def test_extra_properties(self):
        html = PDFSummaryService._get_html(self.signal, None, False)

        self.assertIn('Is de situatie gevaarlijk?', html)
        self.assertIn('Niet gevaarlijk', html)
