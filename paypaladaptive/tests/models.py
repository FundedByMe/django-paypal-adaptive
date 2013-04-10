from django.test import TestCase
from factories import PaymentFactory
from mock import patch


class TestPayment(TestCase):
    @patch('paypaladaptive.models.api')
    def testProcess(self, mockPay):
        payment = PaymentFactory.create()
        # test api.Pay is called with correct values
        payment.process()
        # test api.Pay().call() is called with correct values
        # test self.status is correctly saved
        # check returns correct bool val
        pass

    def testRefund(self):
        # make sure ValueError is triggered properly
        # make sure api is called with correct params
        # make sure status is 'refunded' after
        # test Refund object is saved
        pass

    def testUrlMethods(self):
        # check correct values returned
        pass