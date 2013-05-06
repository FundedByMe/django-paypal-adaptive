import django.test as test
from django.core.urlresolvers import reverse

#from paypaladaptive.models import Payment

from factories import PaymentFactory

class TestPaymentIpn(test.TestCase):
    def setUp(self):
        self.payment = PaymentFactory.create()

    def test(self):
        c = test.Client()
        url = self.payment.ipn_url
        response = c.post(url)
        print response
        # -> mock incoming call from PP
        # -> mock call to PP and respond with VERIFY or (INVALID?!)
        # -> the test should see that the payment model us updated according
        # -> to what PP says ...
        # -> try with different calls, like errors and so on
        # -> also cases for when VERIFY is missing
        # -> same for the preapproval and adjustment calls :))))
        pass