'''
Classes and helper functions that implement (a portion of) the Paypal Adaptive API.

'''
from datetime import datetime, timedelta
from dateutil.parser import parse
from django.utils import simplejson as json
# from money.Money import Money, Currency
from pytz import timezone, utc
from urllib2 import URLError
import logging
import settings
import urllib
import urllib2

logger = logging.getLogger(__name__)

'''
IPN constants
'''
IPN_TYPE_PAYMENT = 'Adaptive Payment PAY'
IPN_TYPE_ADJUSTMENT = 'Adjustment'
IPN_TYPE_PREAPPROVAL = 'Adaptive Payment Preapproval'

IPN_STATUS_CREATED = 'CREATED'
IPN_STATUS_COMPLETED = 'COMPLETED'
IPN_STATUS_INCOMPLETE = 'INCOMPLETE'
IPN_STATUS_ERROR = 'ERROR' 
IPN_STATUS_REVERSALERROR = 'REVERSALERROR'
IPN_STATUS_PROCESSING = 'PROCESSING'
IPN_STATUS_PENDING = 'PENDING'

IPN_ACTION_TYPE_PAY = 'PAY'
IPN_ACTION_TYPE_CREATE = 'CREATE'

IPN_TXN_STATUS_COMPLETED = 'Completed'
IPN_TXN_STATUS_PENDING = 'Pending'
IPN_TXN_STATUS_REFUNDED = 'Refunded'

IPN_TXN_SENDER_STATUS_SUCCESS = 'SUCCESS' 
IPN_TXN_SENDER_STATUS_PENDING = 'PENDING'
IPN_TXN_SENDER_STATUS_CREATED = 'CREATED' 
IPN_TXN_SENDER_STATUS_PARTIALLY_REFUNDED = 'PARTIALLY_REFUNDED' 
IPN_TXN_SENDER_STATUS_DENIED = 'DENIED' 
IPN_TXN_SENDER_STATUS_PROCESSING = 'PROCESSING' 
IPN_TXN_SENDER_STATUS_REVERSED = 'REVERSED' 
IPN_TXN_SENDER_STATUS_REFUNDED = 'REFUNDED' 
IPN_TXN_SENDER_STATUS_FAILED = 'FAILED'

IPN_FEES_PAYER_SENDER = 'SENDER'
IPN_FEES_PAYER_PRIMARYRECEIVER = 'PRIMARYRECEIVER'
IPN_FEES_PAYER_EACHRECEIVER = 'EACHRECEIVER'
IPN_FEES_PAYER_SECONDARYONLY = 'SECONDARYONLY'

IPN_REASON_CODE_CHARGEBACK = 'Chargeback' 
IPN_REASON_CODE_SETTLEMENT = 'Settlement'
IPN_REASON_CODE_ADMIN_REVERSAL = 'Admin reversal'
IPN_REASON_CODE_REFUND = 'Refund'

IPN_PAYMENT_PERIOD_NO_PERIOD_SPECIFIED = 'NO_PERIOD_SPECIFIED'
IPN_PAYMENT_PERIOD_DAILY = 'DAILY'
IPN_PAYMENT_PERIOD_WEEKLY = 'WEEKLY'
IPN_PAYMENT_PERIOD_BIWEEKLY = 'BIWEEKLY'
IPN_PAYMENT_PERIOD_SEMIMONTHLY = 'SEMIMONTHLY'
IPN_PAYMENT_PERIOD_MONTHLY = 'MONTHLY'
IPN_PAYMENT_PERIOD_ANNUALLY = 'ANNUALLY'

IPN_PIN_TYPE_NOT_REQUIRED = 'NOT_REQUIRED'
IPN_PIN_TYPE_REQUIRED = 'REQUIRED'

IPN_TIMEZONES = {'PDT': timezone('US/Pacific'),
                 'PST': timezone('US/Pacific')}


'''
Functions
'''
def _build_headers(remote_address=None):
    headers = {
        'X-PAYPAL-SECURITY-USERID': settings.PAYPAL_USERID,
        'X-PAYPAL-SECURITY-PASSWORD': settings.PAYPAL_PASSWORD,
        'X-PAYPAL-SECURITY-SIGNATURE': settings.PAYPAL_SIGNATURE,
        'X-PAYPAL-REQUEST-DATA-FORMAT': 'JSON',
        'X-PAYPAL-RESPONSE-DATA-FORMAT': 'JSON',
        'X-PAYPAL-APPLICATION-ID': settings.PAYPAL_APPLICATION_ID,
    }
    if remote_address:
        headers['X-PAYPAL-DEVICE-IPADDRESS'] = remote_address
        
    return headers


'''
Classes
'''
class PaypalAdaptiveApiError(RuntimeError):
    pass


class PayError(PaypalAdaptiveApiError):
    pass


class RefundError(PaypalAdaptiveApiError):
    pass
    
class CancelPreapprovalError(PaypalAdaptiveApiError):
    pass

class PreapproveError(PaypalAdaptiveApiError):
    pass


class IpnError(PaypalAdaptiveApiError):
    pass


class Pay(object):
    '''
    Models the Pay API operation
    '''
    
    def __init__(self, amount, return_url, cancel_url, remote_address, 
                 seller_paypal_email=None, ipn_url=None, preapproval_key=None, secondary_receiver=None, currency_code=None):
        
#         if not amount or not isinstance(amount, Money) or amount <= Money('0.00', amount.currency):
        # if not amount or amount <= '0.00':
#             raise ValueError("amount must be a positive instance of Money")
        
        self._amount = amount
        
        headers = _build_headers(remote_address)
        data = {
            'actionType': 'PAY',
#             'currencyCode': amount.currency.code,
            'currencyCode': "SEK",
            'returnUrl': return_url,
            'cancelUrl': cancel_url,
            'requestEnvelope': {'errorLanguage': 'en_US'}, # It appears no other languages are supported
        }
        
        if not secondary_receiver:
            # simple payment
            data['receiverList'] = {'receiver': [{'email': seller_paypal_email, 
#                                                   'amount': unicode(amount.amount)}]}
                                                    'amount': amount}]}
        else:
            #### CUSTOM SECONDARY RECEIVER
            commission = (float(amount) * float(0.94))
            his = (float(amount) - float(commission))
            #### CUSTOM ENDS
            
            # chained TODO: don't hardcode this
            # commission = 16 % amount
            data['receiverList'] = {'receiver': [{'email': seller_paypal_email, 
                                                  # 'amount': unicode(amount.amount),
                                                  # 'amount': amount, 
                                                  'amount': float(amount),
                                                  'primary': 'true'}, 
                                                 {'email': secondary_receiver, 
                                                  # 'amount': unicode((amount - commission)),
                                                  'amount': float(his),
                                                  'primary': 'false'}]}

        if ipn_url:
            data['ipnNotificationUrl'] = ipn_url

        if preapproval_key:
            data['preapprovalKey'] = preapproval_key
 
        self.raw_request = json.dumps(data)
        self.raw_response = url_request('%s%s' % (settings.PAYPAL_ENDPOINT, 'Pay'),
                                        data=self.raw_request, headers=headers).content
        self.response = json.loads(self.raw_response)

        logger.debug('headers are: %s' % headers)
        logger.debug('request is: %s' % data)
        logger.debug('response is: %s' % self.raw_response)

        if 'responseEnvelope' not in self.response or 'ack' not in self.response['responseEnvelope'] \
            or self.response['responseEnvelope']['ack'] not in ['Success', 'SuccessWithWarning']:

            error_message = 'unknown'
            try:
                error_message = self.response['error'][0]['message']
            except Exception:
                pass
            
            raise PayError(error_message)

    @property
    def status(self):
        return self.response.get('paymentExecStatus', None)

    @property
    def amount(self):
        return self._amount

    @property
    def paykey(self):
        return self.response.get('payKey', None)


class Refund(object):
    '''
    Models the Refund API operation
    
    Currently only a full refund is supported.
    '''
    def __init__(self, pay_key):
        
        if not pay_key:
            raise ValueError("must provide a payKey")
        
        headers = _build_headers()
        data = {
            'payKey': pay_key,
            'requestEnvelope': {'errorLanguage': 'en_US'}, # It appears no other languages are supported
        }

        self.raw_request = json.dumps(data)
        self.raw_response = url_request('%s%s' % (settings.PAYPAL_ENDPOINT, 'Refund'),
                                        data=self.raw_request, headers=headers).content
        self.response = json.loads(self.raw_response)

        logger.debug('headers are: %s' % headers)
        logger.debug('request is: %s' % data)
        logger.debug('response is: %s' % self.raw_response)

        if 'responseEnvelope' not in self.response or 'ack' not in self.response['responseEnvelope'] \
            or self.response['responseEnvelope']['ack'] not in ['Success', 'SuccessWithWarning']:

            error_message = 'unknown'
            try:
                error_message = self.response['error'][0]['message']
            except Exception:
                pass
            
            raise RefundError(error_message)

class CancelPreapproval(object):
    '''
    Models the Cancel Preapproval API operation
    
    Currently only a full refund is supported.
    '''
    def __init__(self, preapproval_key):
        
        if not preapproval_key:
            raise ValueError("must provide a preapprovalKey")
        
        headers = _build_headers()
        data = {
            'preapprovalKey': preapproval_key,
            'requestEnvelope': {'errorLanguage': 'en_US'}, # It appears no other languages are supported
        }

        self.raw_request = json.dumps(data)
        self.raw_response = url_request('%s%s' % (settings.PAYPAL_ENDPOINT, 'CancelPreapproval'),
                                        data=self.raw_request, headers=headers).content
        self.response = json.loads(self.raw_response)

        logger.debug('headers are: %s' % headers)
        logger.debug('request is: %s' % data)
        logger.debug('response is: %s' % self.raw_response)

        if 'responseEnvelope' not in self.response or 'ack' not in self.response['responseEnvelope'] \
            or self.response['responseEnvelope']['ack'] not in ['Success', 'SuccessWithWarning']:

            error_message = 'unknown'
            try:
                error_message = self.response['error'][0]['message']
            except Exception:
                pass
            
            raise CancelPreapprovalError(error_message)

class Preapprove(object):
    '''
    Models the Preapproval API operation
    
    Currently only a single payment with a simple date range is supported
    '''
    # project_id added
    def __init__(self, amount, return_url, cancel_url, remote_address, ipn_url=None,
                 starting_date=datetime.utcnow(), ending_date=(datetime.utcnow() + timedelta(days=90)), project_id=None, currency_code=None):
        
        self._amount = amount
        
        headers = _build_headers(remote_address)
        data = {
#             'currencyCode': amount.currency.code,
            'currencyCode': currency_code,
            'returnUrl': return_url,
            'cancelUrl': cancel_url,
            'startingDate': starting_date.isoformat(),
            'endingDate': ending_date.isoformat(),
            'maxNumberOfPayments': 1,
            'maxNumberOfPaymentsPerPeriod': 1,
            'maxTotalAmountOfAllPayments': int(amount),
            'pinType': 'NOT_REQUIRED',
            'project': int(project_id),
            'requestEnvelope': {'errorLanguage': 'en_US'}, # It appears no other languages are supported
        }

        if ipn_url:
            data['ipnNotificationUrl'] = ipn_url
        
        self.raw_request = json.dumps(data)
        self.raw_response = url_request('%s%s' % (settings.PAYPAL_ENDPOINT, 'Preapproval'),
                                        data=self.raw_request, headers=headers).content
        self.response = json.loads(self.raw_response)

        logger.debug('headers are: %s' % headers)
        logger.debug('request is: %s' % data)
        logger.debug('response is: %s' % self.raw_response)

        if 'responseEnvelope' not in self.response or 'ack' not in self.response['responseEnvelope'] \
            or self.response['responseEnvelope']['ack'] not in ['Success', 'SuccessWithWarning']:

            error_message = 'unknown'
            try:
                error_message = self.response['error'][0]['message']
            except Exception:
                pass
            
            raise PreapproveError(error_message)

    @property
    def amount(self):
        return self._amount

    @property
    def preapprovalkey(self):
        return self.response.get('preapprovalKey', None)

        
class IPN(object):
    '''
    Models the IPN API response
    
    Note that this model is specific to the Paypal Adaptive API; it cannot handle IPNs from
    the standard Paypal checkout.
    '''
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
        verify_response = url_request('%s?cmd=_notify-validate' % settings.PAYPAL_PAYMENT_HOST,
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
        '''
        Attempt to turn strings into integers (or longs if long enough.)  Doesn't trap the ValueError
        so bad values raise the exception.
        '''
        if int_str:
            return int(int_str)
        
        return None
    
    @classmethod
    def process_money(cls, money_str):
        '''
        Paypal sends money in the form "XXX 0.00" where XXX is the currency code 
        and 0.00 is the amount
        '''
        if money_str:
            money_args = str(money_str).split(' ', 1)
            money_args.reverse()
            if money_args and len(money_args) == 2:
#                 return Money(*money_args)
                return money_args
        
        return None

    @classmethod
    def process_date(cls, date_str):
        '''
        Paypal sends dates in the form "Thu Jun 09 07:23:38 PDT 2011", where the timezone
        appears to always be (US) Pacific.
        '''
        if not date_str:
            return None
        
        return parse(date_str, tzinfos=IPN_TIMEZONES).astimezone(utc)
    
    def process_transactions(self, request):
        '''
        Paypal sends transactions in the form transaction[n].[attribute], where n is 0 - 5 inclusive.
        We'll attempt to pull POST dictionary keys matching each transaction and build an IPN.Transaction
        object from them.
        '''
        self.transactions = []
        
        transaction_nums = range(6)
        for transaction_num in transaction_nums:
            transdict = IPN.Transaction.slicedict(request.POST, 'transaction[%s].' % transaction_num)
            if len(transdict) > 0:
                self.transactions.append(IPN.Transaction(**transdict))
        

class ShippingAddress(object):
    def __init__(self, paykey, remote_address):
        headers = _build_headers(remote_address)
        data = {'key': paykey,
                'requestEnvelope': {'errorLanguage': 'en_US'}}

        self.raw_request = json.dumps(data)
        self.raw_response = url_request('%s%s'
                % (settings.PAYPAL_ENDPOINT, 'GetShippingAddresses'),
                data=self.raw_request, headers=headers).content
        logging.debug('response was: %s' % self.raw_response)
        self.response = json.loads(self.raw_response)


class url_request(object):
    '''
    wrapper for urllib2
    '''
    def __init__(self, url, data=None, headers={}):
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
