"""
Paypal Adaptive Payment callback and IPN URLs

"""

from django.conf.urls import patterns, url

import views
import settings


urlpatterns = patterns(
    '',

    url(r'^pay/cancel/(?P<payment_id>\d+)/(?P<secret_uuid>\w+)/$',
        views.payment_cancel, name="paypal-adaptive-payment-cancel"),

    url(r'^pay/return/(?P<payment_id>\d+)/(?P<secret_uuid>\w+)/$',
        views.payment_return, name="paypal-adaptive-payment-return"),

    url(r'^pre/cancel/(?P<preapproval_id>\d+)/$', views.preapproval_cancel,
        name="paypal-adaptive-preapproval-cancel"),

    url(r'^pre/return/(?P<preapproval_id>\d+)/(?P<secret_uuid>\w+)/$',
        views.preapproval_return, name="paypal-adaptive-preapproval-return"),
)

if settings.USE_IPN:
    urlpatterns += patterns(
        '',

        url(r'^ipn/(?P<object_id>\d+)/(?P<object_secret_uuid>\w+)/$',
            views.ipn, name="paypal-adaptive-ipn"),
    )
