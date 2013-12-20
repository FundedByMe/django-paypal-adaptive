from django.test import TestCase

from mock import patch
from money.Money import Money

from .. import settings
from ..models import Payment
from ..api.datatypes import Receiver, ReceiverList


class MockPaymentRequest(object):
    _response = None
    _code = None

    @property
    def response(self):
        return self._response

    @property
    def code(self):
        return self._code

    def call(self, *args, **kwargs):
        return self


class TestPaymentResponses(TestCase):
    def setUp(self):
        self.payment = Payment()
        self.payment.money = Money(100, "USD")
        self.payment.save()
        self.payment = Payment.objects.all()[0]

        george = Receiver(amount=10, email=settings.settings.PAYPAL_EMAIL,
                          primary=False)
        allen = Receiver(amount=90, email="mrbuyer@antonagestam.se",
                         primary=True)
        self.receivers = ReceiverList([george, allen])

    @patch("paypaladaptive.api.endpoints.UrlRequest", MockPaymentRequest)
    def testPaymentExecStatusError(self):
        MockPaymentRequest._response = (
            u'{"responseEnvelope":'
            u'{"timestamp":"2013-06-14T07:29:00.573-07:00",'
            u'"ack":"Success",'
            u'"correlationId":"0a2a453266f0c",'
            u'"build":"6133763"},'
            u'"payKey":"AP-7YC11928U7484393G",'
            u'"paymentExecStatus":"ERROR",'
            u'"payErrorList":'
            u'{"payError":[{'
            u'"receiver":{'
            u'"amount":"2000",'
            u'"email":"hi@example.com",'
            u'"primary":"true"},'
            u'"error":{'
            u'"errorId":"569059",'
            u'"domain":"PLATFORM",'
            u'"severity":"Error",'
            u'"category":"Application",'
            u'"message":"Instant payments can\'t be pending"}}]}}')

        res = self.payment.process(self.receivers)
        self.assertFalse(res)
        self.assertEqual(self.payment.status, 'error')
        self.assertEqual(
            self.payment.status_detail,
            u"Error 569059: Instant payments can\'t be pending")
