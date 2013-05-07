from urllib import urlencode

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
                         % (payment.amount, wrong_amount))

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

    def testPasses(self):
        """Test valid IPN call"""

        money = str(self.preapproval.money)
        data = {
            'status': 'COMPLETED',
            'transaction_type': 'Adaptive Payment Preapproval',
            'transaction[0].id': '1',
            'transaction[0].amount': money,
            'transaction[0].status': 'PREAPPROVED',
        }

        response = self.mock_ipn_call(data)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, '')

        preapproval = self.get_preapproval()

        self.assertEqual(preapproval.status, 'completed')

    def testVerificationCall(self):
        """Test that the verification call is made with correct params"""

        money = str(self.preapproval.money)
        data = {
            'status': 'COMPLETED',
            'transaction_type': 'Adaptive Payment Preapproval',
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
            'transaction_type': 'Adaptive Payment Preapproval',
            'transaction[0].id': 1,
            'transaction[0].amount': wrong_amount,
            'transaction[0].status': 'COMPLETED',
            'transaction[1].id': 2,
            'transaction[1].amount': wrong_amount,
            'transaction[1].status': 'COMPLETED',
        }

        self.mock_ipn_call(data)

        preapproval = self.get_preapproval()

        self.assertEqual(preapproval.status, 'error')
        self.assertEqual(preapproval.status_detail,
                         ("IPN amounts didn't match. Preapproval "
                          "requested %s. Preapproval made %s"
                          % (preapproval.money, wrong_amount)))