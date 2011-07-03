'''
Models to support Paypal Adaptive API

'''
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db import models, transaction
from django.db.models.fields import CharField
from django.utils.translation import ugettext_lazy as _
from money.contrib.django.models.fields import MoneyField
from south.modelsinspector import add_introspection_rules
import api
import settings

try:
    import uuid
except ImportError:
    from django.utils import uuid


class UUIDField(models.CharField) :
    '''
    Django db field using python's uuid4 library
    '''    
    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = kwargs.get('max_length', 32)
        CharField.__init__(self, *args, **kwargs)
    
    def pre_save(self, model_instance, add):
        if add:
            value = getattr(model_instance,self.attname)
            if not value:
                value = unicode(uuid.uuid4().hex)
            setattr(model_instance, self.attname, value)
            return value
        else:
            return super(CharField, self).pre_save(model_instance, add)


class PaypalAdaptive(models.Model):
    '''
    Base fields used by all PaypalAdaptive models
    '''
    amount = MoneyField(_(u'amount'), max_digits=6, decimal_places=2)
    created_date = models.DateTimeField(_(u'created on'), auto_now_add=True)
    secret_uuid = UUIDField(_(u'secret UUID')) # to verify return_url
    debug_request = models.TextField(_(u'raw request'), blank=True, null=True)
    debug_response = models.TextField(_(u'raw response'), blank=True, null=True)
    
    class Meta:
        abstract = True


class Payment(PaypalAdaptive):
    '''
    Models a payment made using Paypal 
    '''
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
    owner = models.ForeignKey(User, blank=True, null=True, related_name='payments_received')
    pay_key = models.CharField(_(u'paykey'), max_length=255)
    transaction_id = models.CharField(_(u'paypal transaction ID'), max_length=128, blank=True, null=True)
    status = models.CharField(_(u'status'), max_length=10, choices=STATUS_CHOICES, default='new')
    status_detail = models.CharField(_(u'detailed status'), max_length=2048)

    @transaction.autocommit
    def process(self, request):
        self.save()
        
        ipn_url = None
        if settings.USE_IPN:
            ipn_url = request.build_absolute_uri(reverse('paypal-adaptive-ipn',
                                                         kwargs={'payment_id': self.id, 
                                                                 'payment_secret_uuid': self.secret_uuid}))

        seller_paypal_email = None
        if settings.USE_CHAIN:
            seller_paypal_email = self.owner.email if self.owner else None

        return_url = request.build_absolute_uri(reverse('paypal-adaptive-return', 
                                                         kwargs={'payment_id': self.id,
                                                                 'payment_secret_uuid': self.secret_uuid}))
        cancel_url = request.build_absolute_uri(reverse('paypal-adaptive-cancel', 
                                                         kwargs={'payment_id': self.id}))
                     
        pay = api.Pay(self.amount, return_url, cancel_url, request.META['REMOTE_ADDR'],
                      seller_paypal_email, ipn_url)
    
        self.debug_request = pay.raw_request
        self.debug_response = pay.raw_response
        self.pay_key = pay.paykey
        
        if pay.status == 'CREATED':
            self.status = 'created'
        else:
            self.status = 'error'
            
        self.save()
        
        return self.status == 'created'

    @transaction.autocommit
    def refund(self, request):
        self.save()
        
        if self.status != 'completed':
            raise ValueError('Cannot refund a Payment until it is completed.')
        
        ref = api.Refund(self.pay_key)

        self.status = 'refunded'
        self.save()
    
        refund = Refund(payment=self, debug_request=ref.raw_request, debug_response=ref.raw_response)
        refund.save()

    def next_url(self):
        return '%s?cmd=_ap-payment&paykey=%s' \
            % (settings.PAYPAL_PAYMENT_HOST, self.pay_key)


class Refund(PaypalAdaptive):
    '''
    Models a refund make using Paypal
    '''
    STATUS_CHOICES = (
        ('new', _(u'New')), 
        ('created', _(u'Created')), 
        ('error', _(u'Error')), 
        ('canceled', _(u'Canceled')), 
        ('returned', _(u'Returned')),
        ('completed', _(u'Completed')),
    )

    payment = models.OneToOneField(Payment)
    status = models.CharField(_(u'status'), max_length=10, choices=STATUS_CHOICES, default='new')
    status_detail = models.CharField(_(u'detailed status'), max_length=2048)
    
    # TODO: finish model
    

class Preapproval(PaypalAdaptive):
    '''
    Models a preapproval made using Paypal 
    '''
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
    valid_until_date = models.DateTimeField(_(u'valid until'), default=lambda: datetime.now() + timedelta(days=90))
    preapproval_key = models.CharField(_(u'preapprovalkey'), max_length=255)
    status = models.CharField(_(u'status'), max_length=10, choices=STATUS_CHOICES, default='new')
    status_detail = models.CharField(_(u'detailed status'), max_length=2048)

    @transaction.autocommit
    def process(self, request):
        self.save()
        
        ipn_url = None
        if settings.USE_IPN:
            ipn_url = request.build_absolute_uri(reverse('paypal-adaptive-ipn',
                                                         kwargs={'id': self.id, 
                                                                 'secret_uuid': self.secret_uuid}))

        return_url = request.build_absolute_uri(reverse('paypal-adaptive-preapproval-return', 
                                                         kwargs={'id': self.id,
                                                                 'secret_uuid': self.secret_uuid}))
        cancel_url = request.build_absolute_uri(reverse('paypal-adaptive-preapproval-cancel', 
                                                         kwargs={'id': self.id}))
                     
        preapprove = api.Preapprove(self.amount, return_url, cancel_url, request.META['REMOTE_ADDR'], 
                                    ipn_url=ipn_url, starting_date=self.created_date, ending_date=self.valid_until_date)
    
        self.debug_request = preapprove.raw_request
        self.debug_response = preapprove.raw_response
        self.preapproval_key = preapprove.preapprovalkey
        
        if preapprove.status == 'CREATED':
            self.status = 'created'
        else:
            self.status = 'error'
            
        self.save()
        
        return self.status == 'created'


'''
South support for the custom fields
'''
add_introspection_rules([], [ 
    "^paypaladaptive\.models\.UUIDField"
])
