"""Models to support Paypal Adaptive API"""
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db import models, transaction
from django.utils.translation import ugettext_lazy as _
from django.contrib.sites.models import Site
from django.utils import simplejson as json
from money.contrib.django.models.fields import MoneyField
import money

import api
import settings

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

    money = MoneyField()
    created_date = models.DateTimeField(_(u'created on'), auto_now_add=True)
    secret_uuid = UUIDField(_(u'secret UUID')) # to verify return_url
    debug_request = models.TextField(_(u'raw request'), blank=True, null=True)
    debug_response = models.TextField(_(u'raw response'), blank=True,
                                      null=True)

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
    
    class Meta:
        abstract = True


class Payment(PaypalAdaptive):
    """Models a payment made using Paypal"""

    STATUS_CHOICES = (
        ('new', _(u'New')), 
        ('created', _(u'Created')), 
        ('error', _(u'Error')), 
        ('canceled', _(u'Canceled')), 
        ('returned', _(u'Returned')),
        ('completed', _(u'Completed')),
        ('refunded', _(u'Refunded')),
    )
    
    purchaser = models.ForeignKey(User, related_name='payments_made')
    owner = models.ForeignKey(User, blank=True, null=True,
                              related_name='payments_received')
    pay_key = models.CharField(_(u'paykey'), max_length=255)
    transaction_id = models.CharField(_(u'paypal transaction ID'),
                                      max_length=128, blank=True, null=True)
    status = models.CharField(_(u'status'), max_length=10,
                              choices=STATUS_CHOICES, default='new')
    status_detail = models.CharField(_(u'detailed status'), max_length=2048)

    @property
    def ipn_url(self):
        current_site = Site.objects.get_current()
        kwargs = {'id': self.id, 'secret_uuid': self.secret_uuid}
        ipn_url = reverse('paypal-adaptive-ipn', kwargs=kwargs)
        return "http://%s%s" % (current_site, ipn_url)

    @property
    def return_url(self):
        current_site = Site.objects.get_current()
        kwargs = {'id': self.id, 'secret_uuid': self.secret_uuid}
        return_url = reverse('paypal-adaptive-payment-return', kwargs=kwargs)
        return "http://%s%s" % (current_site, return_url)

    @property
    def cancel_url(self):
        current_site = Site.objects.get_current()
        kwargs = {'id': self.id}
        cancel_url = reverse('paypal-adaptive-payment-cancel', kwargs=kwargs)
        return "http://%s%s" % (current_site, cancel_url)

    @transaction.autocommit
    def process(self, remote_addr=None, preapproval_key=None,
                secondary_receiver=None, seller_email=None):
        """Process the payment"""

        self.save()

        ipn_url = self.ipn_url if settings.USE_IPN else None
        seller_paypal_email = None
        return_url = self.return_url
        cancel_url = self.cancel_url
        current_site = Site.objects.get_current()

        if settings.USE_CHAIN and seller_email:
            seller_paypal_email = seller_email

        # CHECK IF A PREAPPROVAL EXISTS
        if preapproval_key:
            try:
                endpoint = api.Pay(self.amount, return_url, cancel_url,
                                   remote_addr, seller_paypal_email, ipn_url,
                                   preapproval_key, secondary_receiver)
            except:
                endpoint = api.Pay(self.amount, return_url, cancel_url,
                                   current_site, seller_paypal_email, ipn_url,
                                   preapproval_key, secondary_receiver)
        else:
            endpoint = api.Pay(self.amount, return_url, cancel_url,
                               remote_addr, seller_paypal_email, ipn_url)

        endpoint.call()

        self.debug_request = json.dumps(endpoint.data)
        self.debug_response = endpoint.raw_response
        self.pay_key = endpoint.paykey
        
        if endpoint.paykey:
            self.status = 'created'
        else:
            self.status = 'error'
            
        self.save()
        
        return self.status == 'created'

    @transaction.autocommit
    def refund(self):
        """Refund this payment"""

        self.save()
        
        if self.status != 'completed':
            raise ValueError('Cannot refund a Payment until it is completed.')
        
        refund_call = api.Refund(self.pay_key)

        self.status = 'refunded'
        self.save()
    
        refund = Refund(payment=self, debug_request=refund_call.raw_request,
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
        ('returned', _(u'Returned')),
        ('completed', _(u'Completed')),
        ('used', _(u'Used')),
    )
    
    purchaser = models.ForeignKey(User, related_name='preapprovals_made')
    valid_until_date = models.DateTimeField(_(u'valid until'),
                                            default=default_valid_date)
    preapproval_key = models.CharField(_(u'preapprovalkey'), max_length=255)
    status = models.CharField(_(u'status'), max_length=10,
                              choices=STATUS_CHOICES, default='new')
    status_detail = models.CharField(_(u'detailed status'), max_length=2048)

    @property
    def ipn_url(self):
        current_site = Site.objects.get_current()
        kwargs = {'id': self.id,
                  'secret_uuid': self.secret_uuid}
        ipn_url = reverse('paypal-adaptive-ipn', kwargs=kwargs)
        return "http://%s%s" % (current_site, ipn_url)

    @property
    def return_url(self):
        current_site = Site.objects.get_current()
        kwargs = {'id': self.id, 'secret_uuid': self.secret_uuid}
        return_url = reverse('paypal-adaptive-preapproval-return',
                             kwargs=kwargs)
        return "http://%s%s" % (current_site, return_url)

    @property
    def cancel_url(self):
        current_site = Site.objects.get_current()
        kwargs = {'id': self.id}
        cancel_url = reverse('paypal-adaptive-preapproval-cancel',
                             kwargs=kwargs)
        return "http://%s%s" % (current_site, cancel_url)

    @transaction.autocommit
    def process(self, remote_addr, ending_date, project_id, currency_code):
        """Process the preapproval"""

        self.save()
        
        ipn_url = self.ipn_url if settings.USE_IPN else None
        return_url = self.return_url
        cancel_url = self.cancel_url
                     
        preapprove = api.Preapprove(self.amount, return_url, cancel_url,
                                    remote_addr,  ipn_url=ipn_url,
                                    starting_date=self.created_date,
                                    ending_date=ending_date,
                                    project_id=project_id,
                                    currency_code=currency_code)
    
        self.debug_request = preapprove.raw_request
        self.debug_response = preapprove.raw_response
        self.preapproval_key = preapprove.preapprovalkey
        
        if preapprove.preapprovalkey:
            self.status = 'created'
        else:
            self.status = 'error'
            
        self.save()
        
        return self.status == 'created'
        
    @transaction.autocommit
    def cancel_preapproval(self):
        cancel = api.CancelPreapproval(preapproval_key=self.preapproval_key)
    
        self.debug_request = cancel.raw_request
        self.debug_response = cancel.raw_response
        
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
        return '%s?cmd=_ap-preapproval&preapprovalkey=%s' \
            % (settings.PAYPAL_PAYMENT_HOST, self.preapproval_key)
            
    def __unicode__(self):
        return self.preapproval_key


# South support for the custom fields
add_introspection_rules([], ["^paypaladaptive\.models\.UUIDField"])
add_introspection_rules([], ["^paypaladaptive\.models\.MoneyField"])
