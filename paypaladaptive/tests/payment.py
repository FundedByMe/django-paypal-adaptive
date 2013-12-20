from django.test import TestCase

from money.Money import Money

from ..models import Payment
from .factories import PaymentFactory


class PaymentDBTest(TestCase):

    def testSaveBigAmount(self):
        big_money = Money(2500000, "USD")
        payment = PaymentFactory.build(money=big_money,
                                       money_currency=big_money.currency)
        payment.save()

        self.assertEqual(big_money,
                         Payment.objects.get(pk=payment.pk).money)
