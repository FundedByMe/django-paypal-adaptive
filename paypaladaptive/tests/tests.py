from django.test import TestCase

from money.Money import Money
from mock import patch

from paypaladaptive import settings
from paypaladaptive.models import Preapproval, Payment
from paypaladaptive.api import Receiver, ReceiverList
from paypaladaptive.api.httpwrapper import UrlResponse

from mock_url_request import MockUrlRequest
from factories import PreapprovalFactory


if not settings.TEST_WITH_MOCK:
    class FakePatch:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, f):
            return f

    patch = FakePatch


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
        self._assert_valid_reversed_url(url, {'payment_id': self.payment().id,
                                        'secret_uuid': self.payment().secret_uuid},
                                        'paypal-adaptive-payment-cancel')

    def _assert_valid_data(self, data):
        super(MockUrlRequestPayment, self)._assert_valid_data(data)
        assert data["currencyCode"] == str(self.payment().currency)
        assert data["actionType"] == "PAY"
        self._assert_valid_recievers_list(data["receiverList"]["receiver"])

    def _assert_valid_recievers_list(self, reciever_list):
        assert reciever_list == self.recievers().to_dict()


class FakePay:
    status = 'COMPLETED'
    paykey = 'PA-123'


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

    @patch("paypaladaptive.models.Payment.call")
    def test_payment_from_preapproval(self, mock_api_caller):
        """Make sure we can create payments from Preapprovals"""

        preapproval = PreapprovalFactory.create(status='approved')
        mock_api_caller.return_value = (True, FakePay())

        self.assertTrue(self.payment.process(self.recievers,
                                             preapproval=self.preapproval))
        self.assertEqual(self.payment.status, 'completed')
