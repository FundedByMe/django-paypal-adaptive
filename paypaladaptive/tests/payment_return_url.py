from django.test import TestCase
from django.test import Client

from paypaladaptive.models import Payment
from .factories import PaymentFactory


class TestPaymentReturnURL(TestCase):
    def setUp(self):
        self.payment = PaymentFactory.create(status='created')
        self.client = Client()

    def get_payment(self):
        return Payment.objects.get(pk=self.payment.pk)

    def hitReturnUrl(self, url=None):
        data = {'next': '/'}
        url = self.payment.return_url if url is None else url
        return self.client.get(url, data=data, follow=False)

    def testPassing(self):
        """Test that during normal circumstances, everything is OK"""

        response = self.hitReturnUrl()
        payment = self.get_payment()

        self.assertEqual(payment.status_detail, '')
        self.assertEqual(payment.status, 'returned')
        self.assertIn(response.status_code, [200, 302])

    def testAlreadyCompleted(self):
        """Test that 'completed' status is not overridden"""

        self.payment.status = 'completed'
        self.payment.save()

        response = self.hitReturnUrl()
        payment = self.get_payment()

        self.assertEqual(payment.status_detail, '')
        self.assertEqual(payment.status, 'completed')
        self.assertIn(response.status_code, [200, 302])

    def testUnexpectedStatus(self):
        """
        Test that receiving IPN for anything else than completed/created
        saves an error on the Payment.

        """

        self.payment.status = 'new'
        self.payment.save()

        response = self.hitReturnUrl()
        payment = self.get_payment()

        self.assertEqual(response.status_code, 500)
        self.assertEqual(payment.status, 'error')
        self.assertEqual(payment.status_detail,
                         u"Expected status to be created or completed, not "
                         u"new - duplicate transaction?")
