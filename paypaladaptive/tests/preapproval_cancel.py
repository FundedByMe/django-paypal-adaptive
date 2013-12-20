from django.test import TestCase
from django.test import Client

from ..models import Preapproval

from .factories import PreapprovalFactory
from .helpers import mock_ipn_call


class TestPreapprovalCancel(TestCase):
    def setUp(self):
        self.preapproval = PreapprovalFactory.create(status='created')

    def get_preapproval(self):
        return Preapproval.objects.get(pk=self.preapproval.pk)

    def hitCancelUrl(self):
        data = {'next': '/'}
        client = Client()
        return client.get(self.preapproval.cancel_url, data=data, follow=False)

    def get_valid_IPN_call(self, money):
        return {
            u'verify_sign': u'AFcWxV21C7fd0v3bYYYRCpSSRl31AzHvdpOG25tWUY92LjYc'
                            u'NpDPvi76',
            u'ending_date': u'2013-07-06T11:34:05.000-07:00',
            u'max_number_of_payments': u'1',
            u'payment_period': u'0',
            u'current_number_of_payments': u'0',
            u'sender_email': u'mrbuyer@antonagestam.se',
            u'current_total_amount_of_all_payments': u'0.00',
            u'starting_date': u'2013-05-08T16:04:24.000-07:00',
            u'notify_version': u'UNVERSIONED',
            u'preapproval_key': u'PA-94D908252K3063112',
            u'status': u'CANCELED',
            u'date_of_month': u'0',
            u'day_of_week': u'NO_DAY_SPECIFIED',
            u'transaction_type': u'Adaptive Payment PREAPPROVAL',
            u'pin_type': u'NOT_REQUIRED',
            u'charset': u'windows-1252',
            u'test_ipn': u'1',
            u'currency_code': str(money.currency),
            u'current_period_attempts': u'0',
            u'max_total_amount_of_all_payments': str(money.amount),
            u'approved': u'false'
        }

    def testPassing(self):
        """Test cancel URL does what it should"""

        self.preapproval.status = 'created'
        self.preapproval.preapproval_key = 'PA-9HW83863H61516232'
        self.preapproval.save()

        response = self.hitCancelUrl()
        # Accept normal response or redirect
        self.assertIn(response.status_code, [200, 302])

        preapproval = self.get_preapproval()

        self.assertEqual(preapproval.status_detail, '')
        self.assertEqual(preapproval.status, 'created')

    def testIPN(self):
        """Test IPN call does what it should"""
        response = mock_ipn_call(
            data = self.get_valid_IPN_call(self.preapproval.money),
            url = self.preapproval.ipn_url)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, '')

        preapproval = self.get_preapproval()
        self.assertEqual(preapproval.status_detail,
                         'Cancellation received via IPN')
        self.assertEqual(preapproval.status, 'canceled')
