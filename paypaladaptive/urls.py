"""
Paypal Adaptive Payment callback URLs

"""

from django.conf.urls import patterns, url

import views
import settings


urlpatterns = patterns(
    '',

    url(r'^cancel/pay/(?P<payment_id>\d+)/$', views.payment_cancel,
        name="paypal-adaptive-payment-cancel"),

    url(r'^return/pay/(?P<payment_id>\d+)/(?P<secret_uuid>\w+)/$',
        views.payment_return, name="paypal-adaptive-payment-return"),

    url(r'^cancel/pre/(?P<preapproval_id>\d+)/$', views.preapproval_cancel,
        name="paypal-adaptive-preapproval-cancel"),

    url(r'^return/pre/(?P<preapproval_id>\d+)/(?P<secret_uuid>\w+)/$',
        views.preapproval_return, name="paypal-adaptive-preapproval-return"),
)

if settings.USE_IPN:
    urlpatterns += patterns(
        '',

        url(r'^ipn/(?P<payment_id>\d+)/(?P<payment_secret_uuid>\w+)/$',
            views.payment_ipn, name="paypal-adaptive-payment-ipn"),

        url(r'^ipn/(?P<preapproval_id>\d+)/(?P<preapproval_secret_uuid>\w+)/$',
            views.preapproval_ipn, name="paypal-adaptive-preapproval-ipn"),

        url(r'^ipn/(?P<payment_id>\d+)/(?P<payment_secret_uuid>\w+)/$',
            views.adjustment_ipn, name="paypal-adaptive-adjustment-ipn"),
    )