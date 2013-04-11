"""Endpoints for (parts of) Paypal Adaptive API."""

from datetime import datetime, timedelta
import logging
import urllib
from ipn_constants import *
from errors import *
from dateutil.parser import parse
from django.utils import simplejson as json
from pytz import utc
from paypaladaptive import settings
from money import Money, Currency
from urllib2 import URLError
import urllib2

logger = logging.getLogger(__name__)


class UrlRequest(object):
    """Wrapper for urllib2"""

    _response = None
    _code = None

    def __init__(self, url, data=None, headers=None):
        if headers is None:
            headers = {}

        # urllib - not validated
        request = urllib2.Request(url, data=data, headers=headers)

        try:
            self._response = urllib2.urlopen(request).read()
            self._code = 200
        except URLError, e:
            self._response = e.read()
            self._code = e.code

    @property
    def content(self):
        return self._response

    @property
    def code(self):
        return self._code


class PaypalAdaptiveEndpoint(object):
    """Base class for all Paypal endpoints"""

    headers = {}
    data = {'requestEnvelope': {'errorLanguage': 'en_US'}, }
    raw_response = None
    response = None
    error_class = Exception
    url = None

    def __init__(self, *args, **kwargs):
        self._build_headers()
        self.data.update(self.prepare_data(*args, **kwargs))

    def _build_headers(self, remote_address=None):
        headers = {'X-PAYPAL-SECURITY-USERID': settings.PAYPAL_USERID,
                   'X-PAYPAL-SECURITY-PASSWORD': settings.PAYPAL_PASSWORD,
                   'X-PAYPAL-SECURITY-SIGNATURE': settings.PAYPAL_SIGNATURE,
                   'X-PAYPAL-REQUEST-DATA-FORMAT': 'JSON',
                   'X-PAYPAL-RESPONSE-DATA-FORMAT': 'JSON',
                   'X-PAYPAL-APPLICATION-ID': settings.PAYPAL_APPLICATION_ID}

        if remote_address:
            headers['X-PAYPAL-DEVICE-IPADDRESS'] = remote_address

        self.headers.update(headers)

    def call(self):
        raw_data = json.dumps(self.data)
        request = UrlRequest(self.url, data=raw_data, headers=self.headers)
        self.raw_response = request.content
        self.response = json.loads(self.raw_response)

        logger.debug('headers are: %s' % str(self.headers))
        logger.debug('request is: %s' % str(self.data))
        logger.debug('response is: %s' % str(self.raw_response))

        if ('responseEnvelope' not in self.response
            or 'ack' not in self.response['responseEnvelope']
            or self.response['responseEnvelope']['ack']
            not in ['Success','SuccessWithWarning']):

            error_message = 'unknown'
            try:
                error_message = self.response['error'][0]['message']
            except Exception:
                pass

            raise self.error_class(error_message)

    def prepare_data(self, *args, **kwargs):
        """
        Override this to set the correct data for the Endpoint. Has to return
        a dict.

        """
        return {}



class Pay(PaypalAdaptiveEndpoint):
    """Models the Pay API operation"""

    url = '%s%s' % (settings.PAYPAL_ENDPOINT, 'Pay')
    error_class = PayError

    def prepare_data(self, money, return_url, cancel_url, seller_paypal_email,
                     ipn_url=None, preapproval_key=None,
                     secondary_receiver=None, secondary_receiver_amount=None):
        """Prepare data for Pay API call"""

        if (not money or not isinstance(money, Money)
            or money <= Money('0.00', money.currency)):
            raise ValueError("amount must be a positive instance of Money")
        
        data = {'actionType': 'PAY',
                'currencyCode': money.currency.code,
                'returnUrl': return_url,
                'cancelUrl': cancel_url}
        
        if not secondary_receiver or not secondary_receiver_amount:
            # simple payment
            receiverList = {'receiver': [{'email': seller_paypal_email,
                                          'amount': float(money.amount)}]}
        else:
            receiverList = {'receiver':[
                {'email': seller_paypal_email,
                 'amount': float(money.amount),
                 'primary': 'true'},
                {'email': secondary_receiver,
                 'amount': float(secondary_receiver_amount),
                 'primary': 'false'}
            ]}

        data.update({'receiverList': receiverList})

        if ipn_url:
            data.update({'ipnNotificationUrl': ipn_url})

        if preapproval_key:
            data.update({'preapprovalKey': preapproval_key})

        return data

    @property
    def status(self):
        return self.response.get('paymentExecStatus', None)

    @property
    def paykey(self):
        return self.response.get('payKey', None)


class Refund(PaypalAdaptiveEndpoint):
    """
    Models the Refund API operation
    
    Currently only a full refund is supported.

    """

    url = '%s%s' % (settings.PAYPAL_ENDPOINT, 'Refund')
    error_class = RefundError

    def prepare_data(self, pay_key):
        if not pay_key:
            raise ValueError("a payKey must be provided")
        
        return {'payKey': pay_key}


class CancelPreapproval(PaypalAdaptiveEndpoint):
    """
    Models the Cancel Preapproval API operation
    
    Currently only a full refund is supported.

    """

    url = '%s%s' % (settings.PAYPAL_ENDPOINT, 'CancelPreapproval')
    error_class = CancelPreapprovalError

    def prepare_data(self, preapproval_key):
        if not preapproval_key:
            raise ValueError("must provide a preapprovalKey")
        
        return {'preapprovalKey': preapproval_key}


class Preapprove(PaypalAdaptiveEndpoint):
    """
    Models the Preapproval API operation
    
    Currently only a single payment with a simple date range is supported

    """

    url = '%s%s' % (settings.PAYPAL_ENDPOINT, 'Preapproval')
    error_class = PreapproveError

    def prepare_data(self, amount, return_url, cancel_url, remote_address,
                     ipn_url=None, starting_date=datetime.utcnow(),
                     ending_date=(datetime.utcnow() + timedelta(days=90)),
                     currency_code=None):

        data = {'currencyCode': amount.currency.code,
                'returnUrl': return_url,
                'cancelUrl': cancel_url,
                'startingDate': starting_date.isoformat(),
                'endingDate': ending_date.isoformat(),
                'maxNumberOfPayments': 1,
                'maxNumberOfPaymentsPerPeriod': 1,
                'maxTotalAmountOfAllPayments': int(amount),
                'pinType': 'NOT_REQUIRED'}

        if ipn_url:
            data['ipnNotificationUrl'] = ipn_url
        
        return data

    @property
    def preapprovalkey(self):
        return self.response.get('preapprovalKey', None)


class ShippingAddress(PaypalAdaptiveEndpoint):
    url = '%s%s' % (settings.PAYPAL_ENDPOINT, 'GetShippingAddresses')

    def prepare_data(self, paykey):
        return {'key': paykey}