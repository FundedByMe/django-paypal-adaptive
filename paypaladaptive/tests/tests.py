import json

from django.test import TestCase
from django.core.urlresolvers import reverse
from django.contrib.sites.models import Site

from money.Money import Money
from mock import patch

from paypaladaptive import settings
from paypaladaptive.models import Preapproval, Payment
from paypaladaptive.api import Receiver, ReceiverList
from paypaladaptive.api.httpwrapper import UrlResponse


if not settings.TEST_WITH_MOCK:
    class FakePatch:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, f):
            return f

    patch = FakePatch


class MockUrlRequest(object):
    def call(self, url, data=None, headers=None):
        self._assert_valid_url(url)
        self._assert_valid_data(json.loads(data))
        self._assert_valid_headers(headers)
        self._set_response()
        return self

    def _set_response(self):
        """Define JSON string returned by paypal"""
        raise NotImplementedError

    def _assert_valid_url(self, url):
        valid_url = "%s%s" % (settings.PAYPAL_ENDPOINT, self._endpoint_name())
        assert url == valid_url

    def _endpoint_name(self):
        """"Name of API call to paypal"""
        raise NotImplementedError

    def _assert_valid_return_url(self, url):
        raise NotImplementedError

    def _assert_valid_cancel_url(self, url):
        raise NotImplementedError

    def _assert_valid_data(self, data):
        self._assert_valid_return_url(data["returnUrl"])
        self._assert_valid_cancel_url(data["cancelUrl"])
        assert data["requestEnvelope"] == {"errorLanguage": "en_US"}

    def _assert_valid_headers(self, headers):
        self._assert_valid_header(headers, 'X-PAYPAL-SECURITY-SIGNATURE',
                                  settings.PAYPAL_SIGNATURE)
        self._assert_valid_header(headers, 'X-PAYPAL-REQUEST-DATA-FORMAT',
                                  'JSON')
        self._assert_valid_header(headers, 'X-PAYPAL-APPLICATION-ID',
                                  settings.PAYPAL_APPLICATION_ID)
        self._assert_valid_header(headers, 'X-PAYPAL-SECURITY-USERID',
                                  settings.PAYPAL_USERID)
        self._assert_valid_header(headers, 'X-PAYPAL-SECURITY-PASSWORD',
                                  settings.PAYPAL_PASSWORD)
        self._assert_valid_header(headers, 'X-PAYPAL-RESPONSE-DATA-FORMAT',
                                  'JSON')

    def _assert_valid_header(self, headers, name, value):
        assert headers[name] == value

    def _assert_valid_reversed_url(self, url, kwargs, template_name):
        """"Helper function for return and cancel urls"""
        current_site = Site.objects.get_current()
        return_url = reverse(template_name, kwargs=kwargs)
        assert url == "http://%s%s" % (current_site, return_url)

    @property
    def response(self):
        return self._response.data

    @property
    def code(self):
        return self._response.code


class MockUrlRequestPreapproval(MockUrlRequest):

    def _set_response(self):
        data = """{\"responseEnvelope\":
                   {\"timestamp\": \"2013-04-23T02:03:21.737-07:00\",
                    \"ack\": \"Success\",
                    \"correlationId\": \"877ca0ec3b8db\",
                    \"build\": \"5710487\"},
                   \"preapprovalKey\": \"PA-8X048594NU8990615\"}"""
        self._response = UrlResponse(data, {}, 200)
        return self

    def _endpoint_name(self):
        return "Preapproval"

    def _assert_valid_data(self, data):
        super(MockUrlRequestPreapproval, self)._assert_valid_data(data)
        assert data["currencyCode"] == str(self.preapproval().currency)
        assert data["maxNumberOfPayments"] == 1
        assert data["maxNumberOfPaymentsPerPeriod"] == 1
        assert data["endingDate"] is not None
        assert data["startingDate"] is not None
        assert data["pinType"] == "NOT_REQUIRED"
        assert data["maxTotalAmountOfAllPayments"] == self.preapproval().amount

    def _assert_valid_return_url(self, url):
        kwargs = {'preapproval_id': self.preapproval().id,
                  'secret_uuid': self.preapproval().secret_uuid}
        self._assert_valid_reversed_url(url, kwargs,
                                        'paypal-adaptive-preapproval-return')

    def _assert_valid_cancel_url(self, url):
        kwargs = {'preapproval_id': self.preapproval().id}
        self._assert_valid_reversed_url(url, kwargs,
                                        'paypal-adaptive-preapproval-cancel')


class MockUrlRequestPayment(MockUrlRequest):
    def _set_response(self):
        data = """{\"responseEnvelope\":
                   {\"timestamp\":\"2013-04-23T07:45:36.456-07:00\",
                    \"ack\":\"Success\",
                    \"correlationId\":\"0d9ee9c8aab09\",
                    \"build\":\"5710487\"},
                   \"payKey\":\"AP-7KL74713BP0955948\",
                   \"paymentExecStatus\":\"CREATED\"}"""
        self._response = UrlResponse(data, {}, 200)

    def _endpoint_name(self):
        return "Pay"

    def _assert_valid_return_url(self, url):
        kwargs = {'payment_id': self.payment().id,
                  'secret_uuid': self.payment().secret_uuid}
        self._assert_valid_reversed_url(url, kwargs,
                                        'paypal-adaptive-payment-return')

    def _assert_valid_cancel_url(self, url):
        self._assert_valid_reversed_url(url, {'payment_id': self.payment().id},
                                        'paypal-adaptive-payment-cancel')

    def _assert_valid_data(self, data):
        super(MockUrlRequestPayment, self)._assert_valid_data(data)
        assert data["currencyCode"] == str(self.payment().currency)
        assert data["actionType"] == "PAY"
        self._assert_valid_recievers_list(data["receiverList"]["receiver"])

    def _assert_valid_recievers_list(self, reciever_list):
        assert reciever_list == self.recievers().to_dict()


class AdaptiveTests(TestCase):

    def setUp(self):

        self.preapproval = Preapproval()
        self.preapproval.money = Money(100, "SEK")
        self.preapproval.save()
        self.preapproval = Preapproval.objects.all()[0]

        self.payment = Payment()
        self.payment.money = Money(100, "USD")
        self.payment.save()
        self.payment = Payment.objects.all()[0]

        george = Receiver(amount=10, email=settings.settings.PAYPAL_EMAIL,
                          primary=False)
        allen = Receiver(amount=90, email="mrbuyer@antonagestam.se",
                         primary=True)
        self.recievers = ReceiverList([george, allen])

    @patch("paypaladaptive.api.endpoints.UrlRequest",
           MockUrlRequestPreapproval)
    def test_preapproval(self):
        MockUrlRequestPreapproval.preapproval = (
            classmethod(lambda cls: self.preapproval))
        self.assertTrue(self.preapproval.process())
        self.preapproval = Preapproval.objects.get(pk=self.preapproval.pk)
        self.assertNotEqual(self.preapproval.preapproval_key, "")
        self.assertEqual(self.preapproval.status, "created")

    @patch("paypaladaptive.api.endpoints.UrlRequest",
           MockUrlRequestPayment)
    def test_payment(self):
        MockUrlRequestPayment.payment = classmethod(lambda cls: self.payment)
        MockUrlRequestPayment.recievers = classmethod(
            lambda cls: self.recievers)
        self.assertTrue(self.payment.process(self.recievers))
        self.payment = Payment.objects.get(pk=self.payment.id)
        self.assertTrue(self.payment.status, "created")
        self.assertNotEqual(self.payment.pay_key, "")

    # Doesn't work
    # def test_payment_from_preapproval(self):
    #     self.preapproval.process()
    #     self.assertTrue(self.payment.process(self.recievers,
    #                                          preapproval=self.preapproval))
