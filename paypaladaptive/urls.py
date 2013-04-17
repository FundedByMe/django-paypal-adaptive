'''
Paypal Adaptive Payment callback URLs

Created on Jun 13, 2011

@author: greg
'''
from django.conf.urls.defaults import patterns, url
from views import payment_cancel, payment_return, payment_ipn, \
    preapproval_cancel, preapproval_return
import settings


urlpatterns = patterns('',
    url(r'^cancel/pay/(?P<id>\d+)/$', payment_cancel,
        name="paypal-adaptive-payment-cancel"),
    url(r'^return/pay/(?P<id>\d+)/(?P<secret_uuid>\w+)/$', payment_return,
        name="paypal-adaptive-payment-return"),

    url(r'^cancel/pre/(?P<id>\d+)/$', preapproval_cancel,
        name="paypal-adaptive-preapproval-cancel"),
    url(r'^return/pre/(?P<id>\d+)/(?P<secret_uuid>\w+)/$', preapproval_return,
        name="paypal-adaptive-preapproval-return"),
)

if settings.USE_IPN:
    urlpatterns += patterns('',
        url(r'^ipn/(?P<id>\d+)/(?P<secret_uuid>\w+)/$', payment_ipn,
            name="paypal-adaptive-ipn"),
    )
