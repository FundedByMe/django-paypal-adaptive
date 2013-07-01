import django.test as test
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.http import HttpRequest

from money.Money import Money
import mock
import urlparse

from paypaladaptive.api.ipn import IPN
from paypaladaptive.models import Payment, Preapproval
from paypaladaptive.api.errors import IpnError

from factories import PreapprovalFactory, PaymentFactory
from helpers import (MockIPNVerifyRequest,
                     MockIPNVerifyRequestFail,
                     MockIPNVerifyRequestInvalid,
                     MockIPNVerifyRequestInvalidCode,
                     mock_ipn_call)




class TestPaymentIPN(test.TestCase):
    def setUp(self):
        self.payment = PaymentFactory.create(status='created')

    @mock.patch('paypaladaptive.api.ipn.endpoints.UrlRequest',
                MockIPNVerifyRequest)
    def mock_ipn_call(self, data, url=None):
        c = test.Client()
        url = url if url is not None else self.payment.ipn_url

        return c.post(url, data=data)

    def get_valid_IPN_data(self, money):
        money = str(money)
        return {
            'status': 'COMPLETED',
            'transaction_type': 'Adaptive Payment PAY',
            'transaction[0].id': '1',
            'transaction[0].amount': money,
            'transaction[0].status': 'COMPLETED',
        }

    def testVerificationCall(self):
        """Test that the verification call is made with correct params"""

        data = self.get_valid_IPN_data(self.payment.money)
        self.mock_ipn_call(data)

        verification_data = urlparse.parse_qs(MockIPNVerifyRequest.data)

        for k, v in data.iteritems():
            self.assertEqual([v], verification_data[k])

    def get_payment(self):
        return Payment.objects.get(pk=self.payment.pk)

    def testPasses(self):
        """Test valid IPN call"""

        data = self.get_valid_IPN_data(self.payment.money)
        response = self.mock_ipn_call(data)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, '')

        payment = self.get_payment()

        self.assertEqual(payment.status, 'completed')

    def testSequenceCalls(self):
        """Test two valid IPN calls being received in sequence"""

        self.testPasses()
        self.testPasses()

    def testMismatchedAmounts(self):
        """Test mismatching amounts"""

        wrong_amount = str(Money("1337.23", 'SEK'))

        data = {
            'status': 'COMPLETED',
            'transaction_type': 'Adaptive Payment PAY',
            'transaction[0].id': 1,
            'transaction[0].amount': wrong_amount,
            'transaction[0].status': 'COMPLETED',
            'transaction[1].id': 2,
            'transaction[1].amount': wrong_amount,
            'transaction[1].status': 'COMPLETED',
        }

        self.mock_ipn_call(data)

        payment = self.get_payment()

        self.assertEqual(payment.status, 'error')
        self.assertEqual(payment.status_detail,
                         "IPN amounts didn't match. Payment requested %s. "
                         "Payment made %s"
                         % (payment.money, wrong_amount))

    def testMismatchedUUID(self):
        """Test error response if invalid secret UUID"""

        current_site = Site.objects.get_current()
        incorrect_UUID = 'thisisnotthecorrectuuid'
        kwargs = {'object_id': self.payment.id,
                  'object_secret_uuid': incorrect_UUID}
        internal_url = reverse('paypal-adaptive-ipn', kwargs=kwargs)
        ipn_url = "http://%s%s" % (current_site, internal_url)

        money = str(self.payment.money)
        data = {
            'status': 'COMPLETED',
            'transaction_type': 'Adaptive Payment PAY',
            'transaction[0].id': '1',
            'transaction[0].amount': money,
            'transaction[0].status': 'COMPLETED',
        }

        response = self.mock_ipn_call(data, ipn_url)

        payment = self.get_payment()

        self.assertEqual(payment.status, 'error')
        self.assertEqual(payment.status_detail,
                         ('IPN secret "%s" did not match db'
                          % incorrect_UUID))

        self.assertEqual(response.status_code, 400)

    def test404MissingObject(self):
        """Test 404 if missing object"""

        current_site = Site.objects.get_current()
        incorrect_UUID = 'thisisnotthecorrectuuid'
        incorrect_object_id = 9000
        kwargs = {'object_id': incorrect_object_id,
                  'object_secret_uuid': incorrect_UUID}
        internal_url = reverse('paypal-adaptive-ipn', kwargs=kwargs)
        ipn_url = "http://%s%s" % (current_site, internal_url)

        money = str(self.payment.money)
        data = {
            'status': 'COMPLETED',
            'transaction_type': 'Adaptive Payment PAY',
            'transaction[0].id': '1',
            'transaction[0].amount': money,
            'transaction[0].status': 'COMPLETED',
        }

        response = self.mock_ipn_call(data, ipn_url)
        self.assertEqual(response.status_code, 404)


class TestPreapprovalIPN(test.TestCase):
    def setUp(self):
        self.preapproval = PreapprovalFactory.create(status='created')

    def mock_ipn_call(self, data, url=None):
        url = url if url is not None else self.preapproval.ipn_url
        return mock_ipn_call(data, url)

    def get_preapproval(self):
        return Preapproval.objects.get(pk=self.preapproval.pk)

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
            u'status': u'ACTIVE',
            u'date_of_month': u'0',
            u'day_of_week': u'NO_DAY_SPECIFIED',
            u'transaction_type': u'Adaptive Payment PREAPPROVAL',
            u'pin_type': u'NOT_REQUIRED',
            u'charset': u'windows-1252',
            u'test_ipn': u'1',
            u'currency_code': str(money.currency),
            u'current_period_attempts': u'0',
            u'max_total_amount_of_all_payments': str(money.amount),
            u'approved': u'true'
        }

    def testPasses(self):
        """Test valid IPN call"""

        money = self.preapproval.money
        data = self.get_valid_IPN_call(money)

        response = self.mock_ipn_call(data)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, '')

        preapproval = self.get_preapproval()

        self.assertEqual(preapproval.status, 'approved')

    def testSequenceCalls(self):
        """Test two valid IPN calls being received in sequence"""

        self.testPasses()
        self.testPasses()

    @mock.patch('paypaladaptive.api.ipn.endpoints.UrlRequest',
                MockIPNVerifyRequest)
    def testVerificationCall(self):
        """Test that the verification call is made with correct params"""

        data = self.get_valid_IPN_call(self.preapproval.money)

        self.mock_ipn_call(data)

        verification_data = urlparse.parse_qs(MockIPNVerifyRequest.data)

        for k, v in data.iteritems():
            self.assertEqual([v], verification_data[k])

    def testMismatchedAmounts(self):
        """Test mismatching amounts"""

        wrong_amount = Money("1337.23", 'SEK')
        data = self.get_valid_IPN_call(wrong_amount)

        self.mock_ipn_call(data)

        preapproval = self.get_preapproval()

        self.assertEqual(preapproval.status, 'error')
        self.assertEqual(preapproval.status_detail,
                         ("IPN amounts didn't match. Preapproval "
                          "requested %s. Preapproval made %s"
                          % (preapproval.money, wrong_amount)))

    def testNotApproved(self):
        """Test unapproved"""

        data = self.get_valid_IPN_call(self.preapproval.money)
        data.update({u'approved': u'false'})

        self.mock_ipn_call(data)

        preapproval = self.get_preapproval()

        self.assertEqual(preapproval.status, 'error')
        self.assertEqual(preapproval.status_detail,
                         "The preapproval is not approved")

    def testUnicodeInMemo(self):
        """Test with Unicode characters in the memo field."""

        data = self.get_valid_IPN_call(self.preapproval.money)
        data.update({u'memo': u"v\ufffdrldens b\ufffdsta app"})

        self.mock_ipn_call(data)


class TestIPNVerification(test.TestCase):
    def setUp(self):
        self.request = HttpRequest()

    @mock.patch('paypaladaptive.api.ipn.endpoints.UrlRequest',
                MockIPNVerifyRequestFail)
    def testVerificationNoneCode(self):
        with self.assertRaises(IpnError) as context:
            IPN(self.request)

        self.assertEqual(context.exception.message,
                         'PayPal response code was None')

    @mock.patch('paypaladaptive.api.ipn.endpoints.UrlRequest',
                MockIPNVerifyRequestInvalidCode)
    def testVerificationCodeInvalid(self):
        with self.assertRaises(IpnError) as context:
            IPN(self.request)

        self.assertEqual(context.exception.message,
                         'PayPal response code was 500')

    @mock.patch('paypaladaptive.api.ipn.endpoints.UrlRequest',
                MockIPNVerifyRequestInvalid)
    def testVerificationMessageInvalid(self):
        with self.assertRaises(IpnError) as context:
            IPN(self.request)

        self.assertEqual(context.exception.message,
                         'PayPal response was "invalid"')
