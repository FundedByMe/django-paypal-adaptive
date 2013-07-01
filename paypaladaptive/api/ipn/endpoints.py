import logging
import  urllib

from django.utils import simplejson

from dateutil.parser import parse
from money.Money import Money, Currency
from pytz import utc

from constants import *
from paypaladaptive import settings
from paypaladaptive.api.errors import IpnError
from paypaladaptive.api.httpwrapper import UrlRequest


logger = logging.getLogger(__name__)


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
            self.status_for_sender_txn = kwargs.get('status_for_sender_txn',
                                                    None)
            self.refund_id = kwargs.get('refund_id', None)
            self.refund_amount = IPN.process_money(kwargs.get('refund_amount',
                                                              None))
            self.refund_account_charged = kwargs.get('refund_account_charged',
                                                     None)
            self.receiver = kwargs.get('receiver', None)
            self.invoiceId = kwargs.get('invoiceId', None)            
            self.amount = IPN.process_money(kwargs.get('amount', None))
            self.is_primary_receiver = (kwargs.get('is_primary_receiver', '')
                                        == 'true')
            
        @classmethod
        def slicedict(cls, d, s):
            """
            Iterates over a dict d and filters out all values whose key starts
            with a string s and then removes that string s from the key and
            returns a new dict.

            """

            d = dict((str(k.replace(s, '', 1)), v) for k,v in d.iteritems() if k.startswith(s))
            return d

    def __init__(self, request):
        # verify that the request is paypal's
        url = '%s?cmd=_notify-validate' % settings.PAYPAL_PAYMENT_HOST
        post_data = {}
        for k, v in request.POST.copy().iteritems():
            post_data[k] = unicode(v).encode('utf-8')
        data = urllib.urlencode(post_data)
        verify_request = UrlRequest().call(url, data=data)

        # check code
        if verify_request.code != 200:
            raise IpnError('PayPal response code was %s' % verify_request.code)

        # check response
        raw_response = verify_request.response
        if raw_response != 'VERIFIED':
            raise IpnError('PayPal response was "%s"' % raw_response)

        # check transaction type
        raw_type = request.POST.get('transaction_type', '')
        allowed_types = [IPN_TYPE_PAYMENT, IPN_TYPE_ADJUSTMENT,
                         IPN_TYPE_PREAPPROVAL]

        if raw_type in allowed_types:
            self.type = raw_type
        else:
            raise IpnError('Unknown transaction_type received: %s' % raw_type)
        
        self.process_transactions(request)

        try:
            # payments and adjustments define these
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

            # preapprovals define these
            self.approved = request.POST.get('approved', 'false') == 'true'            
            self.current_number_of_payments = IPN.process_int(request.POST.get('current_number_of_payments', None))
            self.current_total_amount_of_all_payments = IPN.process_money(request.POST.get('current_total_amount_of_all_payments', None))
            self.current_period_attempts = IPN.process_int(request.POST.get('current_period_attempts', None))
            self.currency_code = Currency(request.POST.get('currency_code', None))
            self.date_of_month = IPN.process_int(request.POST.get('date_of_month', None))
            self.day_of_week = IPN.process_int(request.POST.get('day_of_week', None), None)
            self.starting_date = IPN.process_date(request.POST.get('starting_date', None))
            self.ending_date = IPN.process_date(request.POST.get('ending_date', None))
            self.max_total_amount_of_all_payments = Money(request.POST.get('max_total_amount_of_all_payments', None),
                                                          request.POST.get('currency_code', None))
            self.max_amount_per_payment = IPN.process_money(request.POST.get('max_amount_per_payment', None))
            self.max_number_of_payments = IPN.process_int(request.POST.get('max_number_of_payments', None))
            self.payment_period = request.POST.get('payment_period', None)
            self.pin_type = request.POST.get('pin_type', None)
        except Exception, e:
            logger.error('Could not parse request')
            raise e
        
        # Verify enumerations
        allowed_statuses = [IPN_STATUS_CREATED,
                            IPN_STATUS_COMPLETED,
                            IPN_STATUS_INCOMPLETE,
                            IPN_STATUS_ERROR,
                            IPN_STATUS_REVERSALERROR,
                            IPN_STATUS_PROCESSING,
                            IPN_STATUS_PENDING,
                            IPN_STATUS_ACTIVE,
                            IPN_STATUS_CANCELED]

        if self.status and self.status not in allowed_statuses:
            raise IpnError("unknown status: %s" % self.status)
        
        if (self.action_type
            and self.action_type not in [IPN_ACTION_TYPE_PAY,
                                         IPN_ACTION_TYPE_CREATE]):
            raise IpnError("unknown action type: %s" % self.action_type)

    @classmethod
    def process_int(cls, int_str, default='null'):
        """
        Attempt to turn strings into integers (or longs if long enough.)
        Doesn't trap the ValueError so bad values raise the exception.

        """

        val = default

        if int_str:
            try:
                val = int(int_str)
            except ValueError, e:
                if default == 'null':
                    raise e

        
        return val
    
    @classmethod
    def process_money(cls, money_str):
        """
        Paypal sends money in the form "XXX 0.00" where XXX is the currency
        code and 0.00 is the amount

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
    
    def process_transactions(self, request):
        """
        Paypal sends transactions in the form transaction[n].[attribute], where
        n is 0 - 5 inclusive. We'll attempt to pull POST dictionary keys
        matching each transaction and build an IPN. Transaction object from
        them.

        """

        self.transactions = []

        transaction_nums = range(6)
        for transaction_num in transaction_nums:
            transdict = IPN.Transaction.slicedict(request.POST, 'transaction[%s].' % transaction_num)
            if len(transdict) > 0:
                self.transactions.append(IPN.Transaction(**transdict))