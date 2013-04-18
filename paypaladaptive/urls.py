"""
Paypal Adaptive Payment callback URLs

"""

from django.conf.urls import patterns, url
from views import (payment_cancel, payment_return, preapproval_cancel,
                   preapproval_return)


urlpatterns = patterns('',
    url(r'^cancel/pay/(?P<payment_id>\d+)/$', payment_cancel,
        name="paypal-adaptive-payment-cancel"),
    url(r'^return/pay/(?P<payment_id>\d+)/(?P<secret_uuid>\w+)/$',
        payment_return, name="paypal-adaptive-payment-return"),
    url(r'^cancel/pre/(?P<preapproval_id>\d+)/$', preapproval_cancel,
        name="paypal-adaptive-preapproval-cancel"),
    url(r'^return/pre/(?P<preapproval_id>\d+)/(?P<secret_uuid>\w+)/$',
        preapproval_return, name="paypal-adaptive-preapproval-return"),
)