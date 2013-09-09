"""Models to support Paypal Adaptive API"""
from datetime import datetime, timedelta

from django.core.urlresolvers import reverse
from django.db import models, transaction
from django.utils.translation import ugettext_lazy as _
from django.contrib.sites.models import Site
from django.utils import simplejson as json

from money.contrib.django.models.fields import MoneyField

import settings
import api


try:
    import uuid
except ImportError:
    from django.utils import uuid


class UUIDField(models.CharField) :
    """Django db field using python's uuid4 library"""

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = kwargs.get('max_length', 32)
        models.CharField.__init__(self, *args, **kwargs)
    
    def pre_save(self, model_instance, add):
        if add:
            value = getattr(model_instance, self.attname)
            if not value:
                value = unicode(uuid.uuid4().hex)
            setattr(model_instance, self.attname, value)
        else:
            value = super(models.CharField, self).pre_save(model_instance, add)

        return value


class PaypalAdaptive(models.Model):
    """Base fields used by all PaypalAdaptive models"""
    money = MoneyField(_(u'money'), max_digits=settings.MAX_DIGITS,
                       decimal_places=settings.DECIMAL_PLACES)
    created_date = models.DateTimeField(_(u'created on'), auto_now_add=True)
    secret_uuid = UUIDField(_(u'secret UUID'))  # to verify return_url
    debug_request = models.TextField(_(u'raw request'), blank=True, null=True)
    debug_response = models.TextField(_(u'raw response'), blank=True,
                                      null=True)

    def call(self, endpoint_class, *args, **kwargs):
        endpoint = endpoint_class(*args, **kwargs)

        try:
            res = endpoint.call()
        finally:
            self.debug_request = json.dumps(endpoint.data)
            self.debug_response = endpoint.raw_response
            self.save()

        return res, endpoint

    def get_amount(self):
        return self.money.amount

    def set_amount(self, value):
        self.money.amount = value

    amount = property(get_amount, set_amount)

    def get_currency(self):
        return self.money.currency

    def set_currency(self, value):
        self.money.currency = value

    currency = property(get_currency, set_currency)

    @property
    def ipn_url(self):
        current_site = Site.objects.get_current()
        kwargs = {'object_id': self.id,
                  'object_secret_uuid': self.secret_uuid}
        ipn_url = reverse('paypal-adaptive-ipn', kwargs=kwargs)
        return "http://%s%s" % (current_site, ipn_url)
    
    class Meta:
        abstract = True


class Payment(PaypalAdaptive):
    """Models a payment made using Paypal"""

    STATUS_CHOICES = (
        ('new', _(u'New')),  # just saved locally
        ('created', _(u'Created')),  # payment created
        ('error', _(u'Error')),  # error occurred somewhere in the process
        ('canceled', _(u'Canceled')),  # the payment has been canceled
        ('returned', _(u'Returned')),  # user has returned via return_url
        ('completed', _(u'Completed')),  # the payment has been completed
        ('refunded', _(u'Refunded')),  # payment has been refunded
    )

    pay_key = models.CharField(_(u'paykey'), max_length=255)
    transaction_id = models.CharField(_(u'paypal transaction ID'),
                                      max_length=128, blank=True, null=True)
    status = models.CharField(_(u'status'), max_length=10,
                              choices=STATUS_CHOICES, default='new')
    status_detail = models.CharField(_(u'detailed status'), max_length=2048)

    @property
    def return_url(self):
        current_site = Site.objects.get_current()
        kwargs = {'payment_id': self.id, 'secret_uuid': self.secret_uuid}
        return_url = reverse('paypal-adaptive-payment-return', kwargs=kwargs)
        return "http://%s%s" % (current_site, return_url)

    @property
    def cancel_url(self):
        current_site = Site.objects.get_current()
        kwargs = {'payment_id': self.id, 'secret_uuid': self.secret_uuid}
        cancel_url = reverse('paypal-adaptive-payment-cancel', kwargs=kwargs)
        return "http://%s%s" % (current_site, cancel_url)

    @transaction.autocommit
    def process(self, receivers, preapproval=None, **kwargs):
        """Process the payment
        >>>from paypaladaptive.models import Payment
        >>>from paypaladaptive.api import ReceiverList, Receiver
        >>>from money.Money import Money
        >>>r = Receiver(amount=100, email="msn-facilitator@antonagestam.se", primary=False)
        >>>entrep = Receiver(amount=1900, email="mrbuyer@antonagestam.se", primary=True)
        >>>receivers = ReceiverList([r, entrep])
        >>>p = Payment()
        >>>p.money=Money(2000, 'usd')
        >>>p.save()
        >>>p.process(receivers, preapproval_key='PA-2MT146200X905683P')
        """

        endpoint_kwargs = {'money': self.money,
                           'return_url': self.return_url,
                           'cancel_url': self.cancel_url}

        # Update return_url with ?next param
        if 'next' in kwargs:
            return_next = "%s?next=%s" % (self.return_url, kwargs.pop('next'))
            endpoint_kwargs.update({'return_url': return_next})

        # Update cancel_url
        if 'cancel' in kwargs:
            return_cancel = "%s?next=%s" % (self.cancel_url,
                                            kwargs.pop('cancel'))
            endpoint_kwargs.update({'cancel_url': return_cancel})

        # Set ipn_url
        if settings.USE_IPN:
            endpoint_kwargs.update({'ipn_url': self.ipn_url})

        # Append extra arguments
        endpoint_kwargs.update(**kwargs)

        # Validate type of receivers and check ReceiverList has primary,
        # otherwise assign first
        if not isinstance(receivers, api.ReceiverList):
            raise ValueError("receivers must be an instance of "
                             "ReceiverList")
        elif not receivers.has_primary() and settings.USE_CHAIN:
            receivers.receivers[0].primary = True

        endpoint_kwargs.update({'receivers': receivers})

        # Use preapproval
        if preapproval is not None:
            if not isinstance(preapproval, Preapproval):
                raise ValueError("preapproval must be an instance of "
                                 "Preapproval")

            key = preapproval.preapproval_key
            endpoint_kwargs.update({'preapprovalKey': key})

        # Append extra arguments
        endpoint_kwargs.update(kwargs)

        # Call endpoint
        res, endpoint = self.call(api.Pay, **endpoint_kwargs)

        self.pay_key = endpoint.paykey

        if endpoint.status == 'ERROR':
            self.status = 'error'
            if 'payErrorList' in endpoint.response:
                if 'payError' in endpoint.response['payErrorList']:
                    payError = endpoint.response[
                        'payErrorList']['payError'][0]['error']
                    self.status_detail = "%s %s: %s" % (
                        payError['severity'],
                        payError['errorId'],
                        payError['message'])
                else:
                    self.status_detail = json.dumps(
                        endpoint.response.payErrorList)

        elif endpoint.status == 'COMPLETED':
            self.status = 'completed'
        elif endpoint.paykey or endpoint.status == 'CREATED':
            self.status = 'created'
        else:
            self.status = 'error'
            
        self.save()
        
        return self.status in ['created', 'completed']

    @transaction.autocommit
    def refund(self):
        """Refund this payment"""

        # TODO: flow should create a Refund object and call Refund.process()

        self.save()
        
        if self.status != 'completed':
            raise ValueError('Cannot refund a Payment until it is completed.')

        res, refund_call = self.call(api.Refund, self.pay_key)

        self.status = 'refunded'
        self.save()
    
        refund = Refund(payment=self,
                        debug_request=json.dumps(refund_call.data),
                        debug_response=refund_call.raw_response)
        refund.save()

    def next_url(self):
        return ('%s?cmd=_ap-payment&paykey=%s'
                % (settings.PAYPAL_PAYMENT_HOST, self.pay_key))
            
    def __unicode__(self):
        return self.pay_key


class Refund(PaypalAdaptive):
    """Models a refund make using Paypal"""

    STATUS_CHOICES = (
        ('new', _(u'New')), 
        ('created', _(u'Created')), 
        ('error', _(u'Error')), 
        ('canceled', _(u'Canceled')), 
        ('returned', _(u'Returned')),
        ('completed', _(u'Completed')),
    )

    payment = models.OneToOneField(Payment)
    status = models.CharField(_(u'status'), max_length=10,
                              choices=STATUS_CHOICES, default='new')
    status_detail = models.CharField(_(u'detailed status'), max_length=2048)
    
    # TODO: finish model


class Preapproval(PaypalAdaptive):
    """Models a preapproval made using Paypal"""

    default_valid_range = timedelta(days=90)
    default_valid_date = lambda: (datetime.now() +
                                  Preapproval.default_valid_range)

    STATUS_CHOICES = (
        ('new', _(u'New')),
        ('created', _(u'Created')),
        ('error', _(u'Error')),
        ('canceled', _(u'Canceled')),
        ('approved', _(u'Approved')),
        ('used', _(u'Used')),
        ('returned', _(u'Returned')),
    )
    
    valid_until_date = models.DateTimeField(_(u'valid until'),
                                            default=default_valid_date)
    preapproval_key = models.CharField(_(u'preapprovalkey'), max_length=255)
    status = models.CharField(_(u'status'), max_length=10,
                              choices=STATUS_CHOICES, default='new')
    status_detail = models.CharField(_(u'detailed status'), max_length=2048)

    @property
    def return_url(self):
        current_site = Site.objects.get_current()
        kwargs = {'preapproval_id': self.id, 'secret_uuid': self.secret_uuid}
        return_url = reverse('paypal-adaptive-preapproval-return',
                             kwargs=kwargs)
        return "http://%s%s" % (current_site, return_url)

    @property
    def cancel_url(self):
        current_site = Site.objects.get_current()
        kwargs = {'preapproval_id': self.id}
        cancel_url = reverse('paypal-adaptive-preapproval-cancel',
                             kwargs=kwargs)
        return "http://%s%s" % (current_site, cancel_url)

    @transaction.autocommit
    def process(self, **kwargs):
        """Process the preapproval
        >>>from paypaladaptive.models import Preapproval
        >>>p = Preapproval()
        >>>from money.Money import Money
        >>>p.money = Money(2000, 'usd')
        >>>p.save()
        >>>extra = {'requireInstantFundingSource': True, 'displayMaxTotalAmount': True, 'next': '123'}
        >>>p.process(**extra)
        """

        endpoint_kwargs = {'money': self.money,
                           'return_url': self.return_url,
                           'cancel_url': self.cancel_url,
                           'starting_date': self.created_date,
                           'ending_date': self.valid_until_date}

        if 'next' in kwargs:
            return_next = "%s?next=%s" % (self.return_url, kwargs.pop('next'))
            endpoint_kwargs.update({'return_url': return_next})

        if 'cancel' in kwargs:
            return_cancel = "%s?next=%s" % (self.cancel_url,
                                            kwargs.pop('cancel'))
            endpoint_kwargs.update({'cancel_url': return_cancel})

        if settings.USE_IPN:
            endpoint_kwargs.update({'ipn_url': self.ipn_url})

        # Append extra arguments
        endpoint_kwargs.update(**kwargs)

        res, preapprove = self.call(api.Preapprove, **endpoint_kwargs)
    
        if preapprove.preapprovalkey:
            self.preapproval_key = preapprove.preapprovalkey
            self.status = 'created'
        else:
            self.status = 'error'
            
        self.save()
        
        return self.status == 'created'
        
    @transaction.autocommit
    def cancel_preapproval(self):
        res, cancel = self.call(api.CancelPreapproval,
                                preapproval_key=self.preapproval_key)

        # TODO: validate response

        self.status = 'canceled'
        self.save()
        return self.status == 'canceled'
        
    @transaction.autocommit
    def mark_as_used(self):
        self.status = 'used'
        self.save()
        
        return self.status == 'used'
    
    def next_url(self):
        """Custom next URL"""
        return ('%s?cmd=_ap-preapproval&preapprovalkey=%s'
                % (settings.PAYPAL_PAYMENT_HOST, self.preapproval_key))
            
    def __unicode__(self):
        return self.preapproval_key


try:
    from south.modelsinspector import add_introspection_rules
    # South support for the custom fields
    add_introspection_rules([], ["^paypaladaptive\.models\.UUIDField"])
    add_introspection_rules([], ["^paypaladaptive\.models\.MoneyField"])
except ImportError:
    # South is not installed
    pass
