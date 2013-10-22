"""Endpoints for (parts of) Paypal Adaptive API."""

from datetime import datetime, timedelta
import logging

from django.utils import simplejson as json

from money.Money import Money

from paypaladaptive import settings

from errors import *
from datatypes import ReceiverList
from httpwrapper import UrlRequest

logger = logging.getLogger(__name__)


class PaypalAdaptiveEndpoint(object):
    """Base class for all Paypal endpoints"""

    headers = {}
    data = {'requestEnvelope': {'errorLanguage': 'en_US'}, }
    raw_response = None
    response = None
    error_class = Exception
    url = None

    def __init__(self, *args, **kwargs):
        remote_address = kwargs.pop('remote_address', None)
        self._build_headers(remote_address=remote_address)
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
        request = UrlRequest().call(self.url, data=json.dumps(self.data),
                                    headers=self.headers)
        self.raw_response = request.response
        self.response = json.loads(request.response)

        logger.debug('headers are: %s' % str(self.headers))
        logger.debug('request is: %s' % str(self.data))
        logger.debug('response is: %s' % str(self.raw_response))

        if ('responseEnvelope' not in self.response
                or 'ack' not in self.response['responseEnvelope']
                or self.response['responseEnvelope']['ack']
                not in ['Success', 'SuccessWithWarning']):
            error_message = 'unknown'
            try:
                error_message = self.response['error'][0]['message']
            except KeyError:
                pass

            raise self.error_class(error_message)

    def prepare_data(self, *args, **kwargs):
        """
        Override this to set the correct data for the Endpoint. Has to return
        a dict.

        """

        raise NotImplementedError("Endpoint class needs to override the "
                                  "prepare_data method.")

    def pretty_response(self):
        print json.dumps(json.loads(self.raw_response), indent=4)

    def pretty_request(self):
        print json.dumps(self.data, indent=4)


class Pay(PaypalAdaptiveEndpoint):
    """Models the Pay API operation"""

    url = '%s%s' % (settings.PAYPAL_ENDPOINT, 'Pay')
    error_class = PayError

    def prepare_data(self, money, return_url, cancel_url, receivers,
                     ipn_url=None, **kwargs):
        """Prepare data for Pay API call"""

        if (not money or not isinstance(money, Money)
                or money <= Money('0.00', money.currency)):
            raise ValueError("amount must be a positive instance of Money")

        if (not isinstance(receivers, ReceiverList) or len(receivers) < 1):
            raise ValueError("receivers must be an instance of ReceiverList")
        
        data = {'actionType': 'PAY',
                'currencyCode': money.currency.code,
                'returnUrl': return_url,
                'cancelUrl': cancel_url}
        
        receiverList = {'receiver': receivers.to_dict()}
        data.update({'receiverList': receiverList})

        if ipn_url:
            data.update({'ipnNotificationUrl': ipn_url})

        if kwargs:
            data.update(**kwargs)

        return data

    @property
    def status(self):
        return self.response.get('paymentExecStatus', None)

    @property
    def paykey(self):
        return self.response.get('payKey', None)


class PaymentDetails(PaypalAdaptiveEndpoint):
    """
    Models the PaymentDetails API operation.
    Use this to retrieve data about a Payment from Paypal

    """

    url = '%s%s' % (settings.PAYPAL_ENDPOINT, 'PaymentDetails')
    error_class = PaypalAdaptiveApiError

    def prepare_data(self, payKey=None, transactionId=None, trackingId=None):
        """Prepare data for PaymentDetails API call"""

        if not any([payKey, transactionId, trackingId]):
            raise self.error_class("You need to supply one of payKey, "
                                   "transactionId or trackingId for Paypal to "
                                   "identify the payment")

        data = {}

        if payKey is not None:
            data.update({'payKey': payKey})

        if transactionId is not None:
            data.update({'transactionId': transactionId})

        if trackingId is not None:
            data.update({'trackingId': trackingId})

        return data


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

    def prepare_data(self, money, return_url, cancel_url, ipn_url=None,
                     starting_date=datetime.utcnow(),
                     ending_date=(datetime.utcnow() + timedelta(days=90)),
                     pin_type='NOT_REQUIRED', max_payments=1,
                     max_payments_per_period=1, **kwargs):

        data = {'currencyCode': money.currency.code,
                'returnUrl': return_url,
                'cancelUrl': cancel_url,
                'startingDate': starting_date.isoformat(),
                'endingDate': ending_date.isoformat(),
                'maxNumberOfPayments': max_payments,
                'maxNumberOfPaymentsPerPeriod': max_payments_per_period,
                'maxTotalAmountOfAllPayments': float(money.amount),
                'pinType': pin_type}

        if kwargs:
            data.update(**kwargs)

        if ipn_url:
            data['ipnNotificationUrl'] = ipn_url
        
        return data

    @property
    def preapprovalkey(self):
        return self.response.get('preapprovalKey', None)


class PreapprovalDetails(PaypalAdaptiveEndpoint):
    """
    Models the PreapprovalDetails API operation.
    Use this to retrieve data about a Preapproval from Paypal

    """

    url = '%s%s' % (settings.PAYPAL_ENDPOINT, 'PreapprovalDetails')
    error_class = PaypalAdaptiveApiError

    def prepare_data(self, preapprovalKey):
        """Prepare data for PreapprovalDetails API call"""
        return {'preapprovalKey': preapprovalKey}


class ShippingAddress(PaypalAdaptiveEndpoint):
    url = '%s%s' % (settings.PAYPAL_ENDPOINT, 'GetShippingAddresses')

    def prepare_data(self, paykey):
        return {'key': paykey}
