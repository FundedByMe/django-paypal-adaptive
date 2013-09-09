from django.conf import settings
from money import set_default_currency


DEBUG = getattr(settings, "DEBUG", False)

if DEBUG:
    # use sandboxes while in debug mode
    PAYPAL_ENDPOINT = 'https://svcs.sandbox.paypal.com/AdaptivePayments/'
    PAYPAL_PAYMENT_HOST = 'https://www.sandbox.paypal.com/au/cgi-bin/webscr'
    EMBEDDED_ENDPOINT = 'https://www.sandbox.paypal.com/webapps/adaptivepayment/flow/pay'

    PAYPAL_APPLICATION_ID = 'APP-80W284485P519543T' # sandbox only
else:
    PAYPAL_ENDPOINT = 'https://svcs.paypal.com/AdaptivePayments/' # production
    PAYPAL_PAYMENT_HOST = 'https://www.paypal.com/webscr' # production
    EMBEDDED_ENDPOINT = 'https://paypal.com/webapps/adaptivepayment/flow/pay'

    PAYPAL_APPLICATION_ID = settings.PAYPAL_APPLICATION_ID

# These settings are required
PAYPAL_USERID = settings.PAYPAL_USERID
PAYPAL_PASSWORD = settings.PAYPAL_PASSWORD
PAYPAL_SIGNATURE = settings.PAYPAL_SIGNATURE
PAYPAL_EMAIL = settings.PAYPAL_EMAIL

USE_IPN = getattr(settings, 'PAYPAL_USE_IPN', True)
USE_CHAIN = getattr(settings, 'PAYPAL_USE_CHAIN', True)
USE_EMBEDDED = getattr(settings, 'PAYPAL_USE_EMBEDDED', True)
SHIPPING = getattr(settings, 'PAYPAL_USE_SHIPPING', False)

DEFAULT_CURRENCY = getattr(settings, 'DEFAULT_CURRENCY', 'USD')
set_default_currency(code=DEFAULT_CURRENCY)

DECIMAL_PLACES = getattr(settings, 'PAYPAL_DECIMAL_PLACES', 2)
MAX_DIGITS = getattr(settings, 'PAYPAL_MAX_DIGITS', 10)

# Should tests hit Paypaladaptive or not? Defaults to using mock responses
TEST_WITH_MOCK = getattr(settings, 'PAYPAL_TEST_WITH_MOCK', True)
