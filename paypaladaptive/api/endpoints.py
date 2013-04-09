"""Endpoints for (parts of) Paypal Adaptive API."""

from datetime import datetime, timedelta
import logging
import urllib
from ipn_constants import *
from errors import *
from dateutil.parser import parse
from django.utils import simplejson as json
from pytz import utc
import settings
from money import Money, Currency
from urllib2 import URLError
import urllib2

logger = logging.getLogger(__name__)


class UrlRequest(object):
    """Wrapper for urllib2"""

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
        request = UrlRequest(self.url, data=self.data, headers=self.headers)
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

    def prepare_data(self, amount, return_url, cancel_url, remote_address,
                     seller_paypal_email=None, ipn_url=None,
                     preapproval_key=None, secondary_receiver=None,
                     secondary_receiver_amount=None):
        if (not amount or not isinstance(amount, Money)
            or amount <= Money('0.00', amount.currency)):
            raise ValueError("amount must be a positive instance of Money")
        
        data = {'actionType': 'PAY',
                'currencyCode': amount.currency.code,
                'returnUrl': return_url,
                'cancelUrl': cancel_url}
        
        if not secondary_receiver or not secondary_receiver_amount:
            # simple payment
            receiverList = {'receiver': [{'email': seller_paypal_email,
                                          'amount': float(amount)}]}
        else:
            receiverList = {'receiver':[
                {'email': seller_paypal_email,
                 'amount': float(amount),
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


class IPN(object):
    """
    Models the IPN API response
    
    Note that this model is specific to the Paypal Adaptive API; it cannot
    handle IPNs from the standard Paypal checkout.

    """

    class Transaction(object):
        def __init__(self, **kwargs):
            self.id = kwargs.get('id', None)
            self.status = kwargs.get('status', None)
            self.id_for_sender = kwargs.get('id_for_sender', None)
            self.status_for_sender_txn = kwargs.get('status_for_sender_txn', None)
            self.refund_id = kwargs.get('refund_id', None)
            self.refund_amount = IPN.process_money(kwargs.get('refund_amount', None))
            self.refund_account_charged = kwargs.get('refund_account_charged', None)
            self.receiver = kwargs.get('receiver', None)
            self.invoiceId = kwargs.get('invoiceId', None)
            self.amount = IPN.process_money(kwargs.get('amount', None))
            self.is_primary_receiver = kwargs.get('is_primary_receiver', 'false') == 'true'

        @classmethod
        def slicedict(cls, d, s):
            return dict((str(k.replace(s, '', 1)), v) for k,v in d.iteritems() if k.startswith(s))

    def __init__(self, request):
        # verify that the request is paypal's
        verify_response = UrlRequest('%s?cmd=_notify-validate' % settings.PAYPAL_PAYMENT_HOST,
                                      data=urllib.urlencode(request.POST.copy()))

        # check code
        if verify_response.code != 200:
            raise IpnError('PayPal response code was %i' % verify_response.code)

        # check response
        raw_response = verify_response.content
        if raw_response != 'VERIFIED':
            raise IpnError('PayPal response was "%s"' % raw_response)

        # check transaction type
        raw_type = request.POST.get('transaction_type', '')
        if raw_type in [IPN_TYPE_PAYMENT, IPN_TYPE_ADJUSTMENT, IPN_TYPE_PREAPPROVAL]:
            self.type = raw_type
        else:
            raise IpnError('Unknown transaction_type received: %s' % raw_type)
        
        # check payment status
        if request.POST.get('status', '') != 'COMPLETED':
            raise IpnError('PayPal status was "%s"' % request.GET.get('status'))

        try:
            ''' payments and adjustments define these '''
            self.status = request.POST.get('status', None)
            self.sender_email = request.POST.get('sender_email', None)
            self.action_type = request.POST.get('action_type', None)
            self.payment_request_date = IPN.process_date(request.POST.get('payment_request_date', None))
            self.reverse_all_parallel_payments_on_error = request.POST.get('reverse_all_parallel_payments_on_error', 'false') == 'true'
            self.return_url = request.POST.get('return_url', None)
            self.cancel_url = request.POST.get('cancel_url', None)
            self.ipn_notification_url = request.POST.get('ipn_notification_url', None)
            self.pay_key = request.POST.get('pay_key', None)
            self.memo = request.POST.get('memo', None)
            self.fees_payer = request.POST.get('fees_payer', None) 
            self.trackingId = request.POST.get('trackingId', None)
            self.preapproval_key = request.POST.get('preapproval_key', None)
            self.reason_code = request.POST.get('reason_code', None)
            
            self.process_transactions(request)
                
            ''' preapprovals define these '''
            self.approved = request.POST.get('approved', 'false') == 'true'            
            self.current_number_of_payments = IPN.process_int(request.POST.get('current_number_of_payments', None))
            self.current_total_amount_of_all_payments = IPN.process_money(request.POST.get('current_total_amount_of_all_payments', None))
            self.current_period_attempts = IPN.process_int(request.POST.get('current_period_attempts', None))
            self.currencyCode = Currency(request.POST.get('currencyCode', None))
            self.date_of_month = IPN.process_int(request.POST.get('date_of_month', None))
            self.day_of_week = IPN.process_int(request.POST.get('day_of_week', None))
            self.starting_date = IPN.process_date(request.POST.get('starting_date', None))
            self.ending_date = IPN.process_date(request.POST.get('ending_date', None))
            self.max_total_amount_of_all_payments = IPN.process_money(request.POST.get('max_total_amount_of_all_payments', None))            
            self.max_amount_per_payment = IPN.process_money(request.POST.get('max_amount_per_payment', None))
            self.max_number_of_payments = IPN.process_int(request.POST.get('max_number_of_payments', None))
            self.payment_period = request.POST.get('payment_period', None)
            self.pin_type = request.POST.get('pin_type', None)
        except Exception, e:
            raise IpnError(e)
        
        # Verify enumerations
        if self.status and self.status not in [IPN_STATUS_CREATED,
                                               IPN_STATUS_COMPLETED,
                                               IPN_STATUS_INCOMPLETE,
                                               IPN_STATUS_ERROR,
                                               IPN_STATUS_REVERSALERROR,
                                               IPN_STATUS_PROCESSING,
                                               IPN_STATUS_PENDING]:
            raise IpnError("unknown status: %s" % self.status)
        
        if self.action_type and self.action_type not in [IPN_ACTION_TYPE_PAY, IPN_ACTION_TYPE_CREATE]:
            raise IpnError("unknown action type: %s" % self.action_type)

    @classmethod
    def process_int(cls, int_str):
        """
        Attempt to turn strings into integers (or longs if long enough).
        Doesn't trap the ValueError so bad values raise the exception.

        """

        if int_str:
            return int(int_str)
        
        return None
    
    @classmethod
    def process_money(cls, money_str):
        """
        Paypal sends money in the form "XXX 0.00" where XXX is the currency
        code and 0.00 is the amount.

        """

        if money_str:
            money_args = str(money_str).split(' ', 1)
            money_args.reverse()
            if money_args and len(money_args) == 2:
                return Money(*money_args)

        return None

    @classmethod
    def process_date(cls, date_str):
        """
        Paypal sends dates in the form "Thu Jun 09 07:23:38 PDT 2011", where
        the timezone appears to always be (US) Pacific.

        """

        if not date_str:
            return None
        
        return parse(date_str, tzinfos=IPN_TIMEZONES).astimezone(utc)
    
    def process_transactions(self, data):
        """
        Paypal sends transactions in the form transaction[n].[attribute],
        where n is 0 - 5 inclusive. We'll attempt to pull POST dictionary keys
        matching each transaction and build an IPN.Transaction object from
        them.

        """

        self.transactions = []
        
        transaction_nums = range(6)
        for transaction_num in transaction_nums:
            transdict = IPN.Transaction.slicedict(data, ('transaction[%s].'
                                                         % transaction_num))
            if len(transdict) > 0:
                self.transactions.append(IPN.Transaction(**transdict))