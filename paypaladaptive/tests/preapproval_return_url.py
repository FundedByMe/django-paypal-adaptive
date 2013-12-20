from django.test import TestCase
from django.test import Client

from paypaladaptive.models import Preapproval

from factories import PreapprovalFactory


class TestPreapprovalReturnURL(TestCase):
    def setUp(self):
        self.preapproval = PreapprovalFactory.create(status='created')

    def get_preapproval(self):
        return Preapproval.objects.get(pk=self.preapproval.pk)

    def hitReturnUrl(self):
        data = {'next': '/'}
        client = Client()
        return client.get(self.preapproval.return_url, data=data, follow=False)

    def testPassing(self):
        """Test a normal call does what it should"""

        self.preapproval.status = 'created'
        self.preapproval.save()

        response = self.hitReturnUrl()
        # accept normal response or redirect
        self.assertIn(response.status_code, [200, 302])

        preapproval = self.get_preapproval()

        self.assertEqual(preapproval.status_detail, '')
        self.assertEqual(preapproval.status, 'returned')

    def testStatusAlreadyApproved(self):
        """
        Test for the case the IPN is received before the return url is accessed
        by the user. That is, the status is approved.

        """

        self.preapproval.status = 'approved'
        self.preapproval.save()

        response = self.hitReturnUrl()
        # accept normal response or redirect
        self.assertIn(response.status_code, [200, 302])

        preapproval = self.get_preapproval()
        self.assertEqual(preapproval.status_detail, '')
        self.assertEqual(preapproval.status, 'approved')

    def testBadStatus(self):
        """Test with bad saved Preapproval status"""

        self.preapproval.status = 'canceled'
        self.preapproval.save()

        response = self.hitReturnUrl()

        self.assertEqual(response.status_code, 500)

        p = self.get_preapproval()
        self.assertEqual(p.status, 'error')
        self.assertEqual(p.status_detail,
                        "Expected status to be created or approved not %s - "
                        "duplicate transaction?" % 'canceled')
