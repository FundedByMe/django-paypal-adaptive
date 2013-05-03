"""
Paypal Adaptive Payments supporting views

Created on Jun 13, 2011

@author: greg
"""

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import (HttpResponseServerError, HttpResponseRedirect)
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from models import Payment, Preapproval
from django.shortcuts import get_object_or_404
import api
import logging
import settings
from django.utils.translation import ugettext_lazy as _

logger = logging.getLogger(__name__)


def render(request, template, template_vars={}):
    if request.GET.get('next'):
        return HttpResponseRedirect(request.GET.get('next'))

    context = RequestContext(request)
    d = {"is_embedded": settings.USE_EMBEDDED}.update(template_vars)

    return render_to_response(template, d, context)


@login_required
@transaction.autocommit
def payment_cancel(request, payment_id, template="paypaladaptive/cancel.html"):
    """Handle incoming cancellation from paypal"""

    logger.debug("Cancellation received for Payment %s" % payment_id)

    payment = get_object_or_404(Payment, id=payment_id)
    payment.status = 'canceled'
    payment.save()
    return render(request, template)


@login_required
@transaction.autocommit
def payment_return(request, payment_id, secret_uuid,
                   template="paypaladaptive/return.html"):
    """
    Incoming return from paypal process (note this is a return to the site, not
    a returned payment)
    """

    logger.debug("Return received for Payment %s" % payment_id)

    payment = get_object_or_404(Payment, id=payment_id)

    if secret_uuid != payment.secret_uuid:
        payment.status_detail = (_(u"BuyReturn secret \"%s\" did not match")
                                 % secret_uuid)
        payment.status = 'error'
        payment.save()
        return HttpResponseServerError('Unexpected error')

    if payment.status != 'completed':
        payment.status = 'returned'
        payment.save()

    return render(request, template)


@login_required
@transaction.autocommit
def preapproval_cancel(request, preapproval_id,
                       template="paypaladaptive/cancel.html"):
    """Incoming preapproval cancellation from paypal"""

    logger.debug("Cancellation received for Preapproval %s" % preapproval_id)

    preapproval = get_object_or_404(Preapproval, id=preapproval_id)

    api.CancelPreapproval(preapproval.preapproval_key)
    preapproval.status = 'canceled'
    preapproval.save()

    return render(request, template)


@login_required
@transaction.autocommit
def preapproval_return(request, preapproval_id, secret_uuid,
                       template="paypaladaptive/return.html"):
    """
    Incoming return from paypal process (note this is a return to the site,
    not a returned payment)

    """

    logger.debug("Return received for Payment %s" % preapproval_id)

    preapproval = get_object_or_404(Preapproval, id=preapproval_id)

    if preapproval.status not in ['created', 'completed']:
        preapproval.status_detail = _(u"Expected status to be created or"
                                      u" completed, not %s - duplicate"
                                      u" transaction?") % preapproval.status
        preapproval.status = 'error'
        preapproval.save()
        return HttpResponseServerError('Unexpected error')

    elif secret_uuid != preapproval.secret_uuid:
        preapproval.status_detail = _(u"BuyReturn secret \"%s\" did not"
                                      u" match") % secret_uuid
        preapproval.status = 'error'
        preapproval.save()
        return HttpResponseServerError('Unexpected error')

    if preapproval.status != 'completed':
        preapproval.status = 'returned'
        preapproval.save()

    return render(request, template,
                  template_vars={"preapproval": preapproval})
