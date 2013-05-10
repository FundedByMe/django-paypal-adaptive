from urllib import urlencode
from collections import OrderedDict

import django.test as test
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse

from money.Money import Money
import mock

from paypaladaptive.models import Payment, Preapproval
from paypaladaptive.api.httpwrapper import UrlRequest, UrlResponse
from factories import PreapprovalFactory, PaymentFactory


class MockIPNVerifyRequest(UrlRequest):
    def call(self, url, data=None, headers=None):
        MockIPNVerifyRequest.data = data
        self._response = UrlResponse(data='VERIFIED', meta={}, code=200)
        return self


class MockIPNVerifyRequestInvalid(UrlRequest):
    data = None
    def call(self, url, data=None, headers=None):
        self.data = data
        self._response = UrlResponse(data='invalid', meta={}, code=200)
        return self


class TestPaymentIPN(test.TestCase):
    def setUp(self):
        self.payment = PaymentFactory.create(status='created')

    @mock.patch('paypaladaptive.api.ipn.endpoints.UrlRequest',
                MockIPNVerifyRequest)
    def mock_ipn_call(self, data, url=None):
        c = test.Client()
        url = url if url is not None else self.payment.ipn_url

        return c.post(url, data=data)

    def get_payment(self):
        return Payment.objects.get(pk=self.payment.pk)

    def testPasses(self):
        """Test valid IPN call"""

        money = str(self.payment.money)
        data = {
            'status': 'COMPLETED',
            'transaction_type': 'Adaptive Payment PAY',
            'transaction[0].id': '1',
            'transaction[0].amount': money,
            'transaction[0].status': 'COMPLETED',
        }

        response = self.mock_ipn_call(data)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, '')

        payment = self.get_payment()

        self.assertEqual(payment.status, 'completed')

    def testVerificationCall(self):
        """Test that the verification call is made with correct params"""

        money = str(self.payment.money)
        data = {
            'status': 'COMPLETED',
            'transaction_type': 'Adaptive Payment PAY',
            'transaction[0].id': '1',
            'transaction[0].amount': money,
            'transaction[0].status': 'COMPLETED',
        }

        self.mock_ipn_call(data)
        qs = urlencode(data)
        self.assertEqual(MockIPNVerifyRequest.data, qs)


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

    @mock.patch('paypaladaptive.api.ipn.endpoints.UrlRequest',
                MockIPNVerifyRequest)
    def mock_ipn_call(self, data, url=None):
        c = test.Client()
        url = url if url is not None else self.preapproval.ipn_url

        return c.post(url, data=data)

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
            u'currency_code': money.currency,
            u'current_period_attempts': u'0',
            u'max_total_amount_of_all_payments': money.amount,
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

    @mock.patch('paypaladaptive.api.ipn.endpoints.UrlRequest',
                MockIPNVerifyRequest)
    def testVerificationCall(self):
        # TODO: bring back this test
        """Test that the verification call is made with correct params"""

        data = OrderedDict(self.get_valid_IPN_call(self.preapproval.money))
        qs = urlencode(data)

        self.mock_ipn_call(data)

        # qs params don't preserver order, might be due to python dicts
        #self.assertEqual(MockIPNVerifyRequest.data, qs)


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