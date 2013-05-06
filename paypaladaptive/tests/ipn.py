import django.test as test

import mock

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
        self.payment = PaymentFactory.create()

    @mock.patch('paypaladaptive.api.ipn.endpoints.UrlRequest',
                MockIPNVerifyRequest)
    def test(self):
        c = test.Client()
        url = self.payment.ipn_url

        data = {
            'status': 'COMPLETED',
            'transaction_type': 'Adaptive Payment PAY',
            'transactions': [
                {'id': 1}
            ]
        }

        response = c.post(url, data=data)
        print response

        self.assertEqual(response.code, 204)
        # -> mock incoming call from PP
        # -> mock call to PP and respond with VERIFY or (INVALID?!)
        # -> the test should see that the payment model us updated according
        # -> to what PP says ...
        # -> try with different calls, like errors and so on
        # -> also cases for when VERIFY is missing
        # -> same for the preapproval and adjustment calls :))))
        # -> test 404 if missing object
        # -> test exception if mismatched uuid
        pass