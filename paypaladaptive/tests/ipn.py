from decimal import Decimal
import urllib

import django.test as test

from money.Money import Money
import mock

from paypaladaptive.models import Payment
from paypaladaptive.api.httpwrapper import UrlRequest, UrlResponse

from factories import PaymentFactory


class MockIPNVerifyRequest(UrlRequest):
    def call(self, url, data=None, headers=None):
        self._response = UrlResponse(data='VERIFIED', meta={}, code=200)
        return self


class MockIPNVerifyRequestInvalid(UrlRequest):
    def call(self, url, data=None, headers=None):
        self._response = UrlResponse(data='invalid', meta={}, code=200)
        return self


class TestPaymentIPN(test.TestCase):
    def setUp(self):
        self.payment = PaymentFactory.create(status='created')

    @mock.patch('paypaladaptive.api.ipn.endpoints.UrlRequest',
                MockIPNVerifyRequest)
    def mock_ipn_call(self, data):
        c = test.Client()
        url = self.payment.ipn_url

        return c.post(url, data=data)

    def get_payment(self):
        return Payment.objects.get(pk=self.payment.pk)

    def testPasses(self):
        money = str(self.payment.money)
        query_string = ("status=COMPLETED"
                        "&transaction_type=Adaptive+Payment+PAY"
                        "&transaction[0][id]=1"
                        "&transaction[0][amount]=100.00+SEK"
                        "&transaction[0][status]=COMPLETED")
        data = {
            'status': 'COMPLETED',
            'transaction_type': 'Adaptive Payment PAY',
            'transaction': [
                {
                    'id': 1,
                    'amount': money,
                    'status': 'COMPLETED',
                },
            ]
        }

        response = self.mock_ipn_call(data)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, '')

        payment = self.get_payment()

        self.assertEqual(payment.status, 'COMPLETED')

        #self.assertEqual(response.code, 204)
        # -X mock incoming call from PP
        # -X mock call to PP and respond with VERIFY or (INVALID?!)

        # -> the test should see that the payment model us updated according
        # -> to what PP says ...

        # -> try with different calls, like errors and so on
        # -> also cases for when VERIFY is missing
        # -> same for the preapproval and adjustment calls :))))
        # -> test 404 if missing object
        # -> test exception if mismatched uuid
        # -> test mismatching amounts

    def testMismatchedAmounts(self):
        wrong_amount = str(Money("1337.23", 'SEK'))

        data = {
            'status': 'COMPLETED',
            'transaction_type': 'Adaptive Payment PAY',
            'transaction': [
                {
                    'id': 1,
                    'amount': wrong_amount,
                    'status': 'COMPLETED',
                },
                {
                    'id': 2,
                    'amount': wrong_amount,
                    'status': 'COMPLETED',
                },
            ]
        }

        self.mock_ipn_call(data)

        payment = self.get_payment()

        self.assertEqual(payment.status, 'error')
        self.assertEqual(payment.status_detail,
                         "IPN amounts didn't match. Payment requested %s. "
                         "Payment made %s"
                         % (payment.amount, wrong_amount))