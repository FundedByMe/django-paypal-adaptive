from django.contrib.auth.models import User
from paypaladaptive.models import Payment
import factory
import uuid

class UserFactory(factory.DjangoModelFactory):
    FACTORY_FOR = User

    username = factory.Sequence(lambda n: 'user{0}'.format(n))
    first_name = "Bill"
    last_name = "Murray"
    is_active = True
    is_superuser = False
    is_staff = False
    email = "bill@themurrayfoundation.com"

class PaymentFactory(factory.DjangoModelFactory):
    FACTORY_FOR = Payment

    amount = 1400
    purchaser = factory.SubFactory(UserFactory)
    owner = factory.SubFactory(UserFactory)
    transaction_id = str(uuid.uuid4())[0:17]