# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2021 Gemeente Amsterdam
from django.contrib.auth.models import Permission

from signals.apps.signals.factories import (
    CategoryFactory,
    DepartmentFactory,
    ImageAttachmentFactory,
    SignalFactory
)
from signals.apps.signals.models import Attachment
from signals.test.utils import SIAReadWriteUserMixin, SignalsBaseApiTestCase


class TestAttachmentPermissions(SIAReadWriteUserMixin, SignalsBaseApiTestCase):
    # Accessing Attachments must follow the same access rules as the signals.
    # Specifically: rules around categories and departments must be followed.
    # This test also checks that the special permissions around deletion of
    # attachments are followed.
    detail_endpoint = '/signals/v1/private/signals/{}'
    attachments_endpoint = '/signals/v1/private/signals/{}/attachments/'
    attachments_endpoint_detail = '/signals/v1/private/signals/{}/attachments/{}'

    def setUp(self):
        self.department = DepartmentFactory.create()
        self.category = CategoryFactory.create(departments=[self.department])
        self.signal = SignalFactory.create(category_assignment__category=self.category)
        self.attachment = ImageAttachmentFactory.create(_signal=self.signal, created_by='ambtenaar@example.com')

        # Various Attachment delete permissions
        self.permission_delete_other = Permission.objects.get(codename='delete_attachment_of_other_user')
        self.permission_delete_normal = Permission.objects.get(codename='delete_attachment_of_normal_signal')
        self.permission_delete_parent = Permission.objects.get(codename='delete_attachment_of_parent_signal')
        self.permission_delete_child = Permission.objects.get(codename='delete_attachment_of_child_signal')

    def test_cannot_access_without_proper_department_detail(self):
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 1)
        self.client.force_authenticate(user=self.sia_read_write_user)

        url = self.detail_endpoint.format(self.signal.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        url = self.attachments_endpoint.format(self.signal.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        url = self.attachments_endpoint_detail.format(self.signal.pk, self.attachment.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_can_access_with_proper_department(self):
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 1)
        self.client.force_authenticate(user=self.sia_read_write_user)
        self.sia_read_write_user.profile.departments.add(self.department)

        url = self.detail_endpoint.format(self.signal.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        url = self.attachments_endpoint.format(self.signal.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        url = self.attachments_endpoint_detail.format(self.signal.pk, self.attachment.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # Rules for deletion of attachments
    # 1: you need correct department to delete attachments as above
    # 2: you need correct permission to delete attachments. One or more of:
    #    - permission to delete a normal signal's attachments
    #    - permission to delete a parent signal's attachments
    #    - permission to delete a child signal's attachments
    # 3: you need extra permissions to delete attachments not uploaded
    #    by yourself

    def test_delete_own_attachments_with_proper_department_i(self):
        """
        Test that user without "delete_attachment_of_other_user" permission
        cannot delete somebody else's attachments.
        """
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 1)
        self.client.force_authenticate(user=self.sia_read_write_user)
        self.sia_read_write_user.profile.departments.add(self.department)

        # hand out all of normal, parent, child signal's attachment delete permissions
        self.sia_read_write_user.user_permissions.set([
            self.permission_delete_normal,
            self.permission_delete_parent,
            self.permission_delete_child,
        ])
        self.sia_read_write_user.save()
        self.sia_read_write_user.refresh_from_db()
        self.client.force_authenticate(user=self.sia_read_write_user)

        # should not be able to delete other's attachment
        url = self.attachments_endpoint_detail.format(self.signal.pk, self.attachment.pk)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 1)

    def test_delete_own_attachments_with_proper_department_ii(self):
        """
        Test that user without "delete_attachment_of_other_user" permission
        can delete their own attachments.
        """
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 1)
        self.client.force_authenticate(user=self.sia_read_write_user)
        self.sia_read_write_user.profile.departments.add(self.department)

        # hand out all of normal, parent, child signal's attachment delete permissions
        self.sia_read_write_user.user_permissions.set([
            self.permission_delete_normal,
            self.permission_delete_parent,
            self.permission_delete_child,
        ])
        self.sia_read_write_user.save()
        self.sia_read_write_user.refresh_from_db()
        self.client.force_authenticate(user=self.sia_read_write_user)

        # let's pretend our test user uploaded the attachment
        self.attachment.created_by = self.sia_read_write_user.email
        self.attachment.save()

        url = self.attachments_endpoint_detail.format(self.signal.pk, self.attachment.pk)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 0)

    def test_delete_others_attachments_with_proper_department_i(self):
        """
        Test that user with "delete_attachment_of_other_user" permission
        can delete somebody else's attachments.
        """
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 1)
        self.client.force_authenticate(user=self.sia_read_write_user)
        self.sia_read_write_user.profile.departments.add(self.department)

        # hand out all of normal, parent, child signal's attachment delete permissions
        # and permission to delete other's attachments
        self.sia_read_write_user.user_permissions.set([
            self.permission_delete_other,
            self.permission_delete_normal,
            self.permission_delete_parent,
            self.permission_delete_child,
        ])
        self.sia_read_write_user.save()
        self.sia_read_write_user.refresh_from_db()
        self.client.force_authenticate(user=self.sia_read_write_user)

        # should be able to delete other's attachment
        url = self.attachments_endpoint_detail.format(self.signal.pk, self.attachment.pk)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 0)

    def test_delete_others_attachments_with_proper_department_ii(self):
        """
        Test that user with "delete_attachment_of_other_user" permission
        can delete a reporter's attachments.
        """
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 1)
        self.client.force_authenticate(user=self.sia_read_write_user)
        self.sia_read_write_user.profile.departments.add(self.department)

        # hand out all of normal, parent, child signal's attachment delete permissions
        # and permission to delete other's attachments
        self.sia_read_write_user.user_permissions.set([
            self.permission_delete_other,
            self.permission_delete_normal,
            self.permission_delete_parent,
            self.permission_delete_child,
        ])
        self.sia_read_write_user.save()
        self.sia_read_write_user.refresh_from_db()
        self.client.force_authenticate(user=self.sia_read_write_user)

        # let's pretend a reporter (i.e. never logged-in) uploaded the attachment
        self.attachment.created_by = None
        self.attachment.save()

        # should be able to delete a reporter's attachment
        url = self.attachments_endpoint_detail.format(self.signal.pk, self.attachment.pk)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 0)

    def test_delete_others_attachments_with_proper_department_iii(self):
        """
        Test that user with "delete_attachment_of_other_user" permission
        can delete a their own attachments.
        """
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 1)
        self.client.force_authenticate(user=self.sia_read_write_user)
        self.sia_read_write_user.profile.departments.add(self.department)

        # hand out all of normal, parent, child signal's attachment delete permissions
        # and permission to delete other's attachments
        self.sia_read_write_user.user_permissions.set([
            self.permission_delete_other,
            self.permission_delete_normal,
            self.permission_delete_parent,
            self.permission_delete_child,
        ])
        self.sia_read_write_user.save()
        self.sia_read_write_user.refresh_from_db()
        self.client.force_authenticate(user=self.sia_read_write_user)

        # let's pretend our test user uploaded the attachment
        self.attachment.created_by = self.sia_read_write_user.email
        self.attachment.save()

        # should be able to delete a reporter's attachment
        url = self.attachments_endpoint_detail.format(self.signal.pk, self.attachment.pk)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 0)

    def test_delete_normal_signals_attachments(self):
        """
        Check that "delete_attachment_of_normal_signal" is needed to delete a
        normal signal's attachments.
        """
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 1)
        self.client.force_authenticate(user=self.sia_read_write_user)
        self.sia_read_write_user.profile.departments.add(self.department)

        # let's pretend our test user uploaded the attachment (no "delete_attachment_of_other_user" needed)
        self.attachment.created_by = self.sia_read_write_user.email
        self.attachment.save()

        # Try to delete without "delete_attachment_of_normal_signal"
        url = self.attachments_endpoint_detail.format(self.signal.pk, self.attachment.pk)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 1)

        # Try to delete with "delete_attachment_of_normal_signal"
        self.sia_read_write_user.user_permissions.set([self.permission_delete_normal])
        self.sia_read_write_user.save()
        self.sia_read_write_user.refresh_from_db()
        self.client.force_authenticate(user=self.sia_read_write_user)

        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 0)

    def test_delete_parent_signal_attachments(self):
        """
        Check that "delete_attachment_of_parent_signal" is needed to delete a
        parent signal's attachments.
        """
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 1)
        self.client.force_authenticate(user=self.sia_read_write_user)
        self.sia_read_write_user.profile.departments.add(self.department)

        # Create a child signal and create an attachment, let's pretend our test
        # user uploaded the attachment (no "delete_attachment_of_parent_signal" needed)
        child_signal = SignalFactory.create(parent=self.signal, category_assignment__category=self.category)
        ImageAttachmentFactory.create(_signal=child_signal)
        self.attachment.created_by = self.sia_read_write_user.email
        self.attachment.save()

        # Try to delete without "delete_attachment_of_parent_signal"
        parent_signal = self.signal
        parent_attachment = self.attachment
        parent_attachment_url = self.attachments_endpoint_detail.format(parent_signal.pk, parent_attachment.pk)

        response = self.client.delete(parent_attachment_url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Attachment.objects.filter(_signal=parent_signal).count(), 1)
        self.assertIn('delete_attachment_of_parent_signal', response.json()['detail'])

        # Try to delete with "delete_attachment_of_parent_signal"
        self.sia_read_write_user.user_permissions.set([self.permission_delete_parent])
        self.sia_read_write_user.save()
        self.sia_read_write_user.refresh_from_db()
        self.client.force_authenticate(user=self.sia_read_write_user)

        response = self.client.delete(parent_attachment_url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Attachment.objects.filter(_signal=parent_signal).count(), 0)

    def test_delete_child_signal_attachments(self):
        """
        Check that "delete_attachment_of_child_signal" is needed to delete a
        child signal's attachments.
        """
        self.assertEqual(Attachment.objects.filter(_signal=self.signal).count(), 1)
        self.client.force_authenticate(user=self.sia_read_write_user)
        self.sia_read_write_user.profile.departments.add(self.department)

        # let's pretend our test user uploaded the attachment (no "delete_attachment_of_parent_signal" needed)
        child_signal = SignalFactory.create(parent=self.signal, category_assignment__category=self.category)
        child_attachment = ImageAttachmentFactory.create(
            _signal=child_signal, created_by=self.sia_read_write_user.email)
        child_attachment_url = self.attachments_endpoint_detail.format(child_signal.pk, child_attachment.pk)

        # Try to delete without "delete_attachment_of_child_signal"
        response = self.client.get(child_attachment_url)
        self.assertEqual(response.status_code, 200)

        response = self.client.delete(child_attachment_url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Attachment.objects.filter(_signal=child_signal).count(), 1)
        self.assertIn('delete_attachment_of_child_signal', response.json()['detail'])

        # Try to delete with "delete_attachment_of_child_signal"
        self.sia_read_write_user.user_permissions.set([self.permission_delete_child])
        self.sia_read_write_user.save()
        self.sia_read_write_user.refresh_from_db()
        self.client.force_authenticate(user=self.sia_read_write_user)  # <---!!! is needed!!!

        self.assertTrue(self.sia_read_write_user.has_perm('signals.delete_attachment_of_child_signal'))

        response = self.client.delete(child_attachment_url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Attachment.objects.filter(_signal=child_signal).count(), 0)
