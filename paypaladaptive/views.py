"""
Paypal Adaptive Payments supporting views

Created on Jun 13, 2011

@author: greg
"""

from api import IpnError
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import (HttpResponseForbidden, HttpResponseServerError,
                         Http404, HttpResponse, HttpResponseBadRequest,
                         HttpResponseRedirect)
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from models import Payment, Preapproval
from django.shortcuts import get_object_or_404
import api
import logging
import settings
from django.utils.translation import ugettext_lazy as _
from signals import received_preapproval
from django.core.urlresolvers import reverse

logger = logging.getLogger(__name__)

@login_required
@transaction.autocommit
def payment_cancel(request, id, payment_secret_uuid,
                   template="paypaladaptive/cancel.html"):
    """Handle incoming cancellation from paypal"""

    logger.debug( "Cancellation received for Payment %s" % id)

    payment = get_object_or_404(Payment, id=id,
                                secret_uuid=payment_secret_uuid)
    
    if request.user != payment.purchaser:
        return HttpResponseForbidden("Unauthorized")
    
    payment.status = 'canceled'
    payment.save()

    context = RequestContext(request)
    template_vars = {"is_embedded": settings.USE_EMBEDDED}
        
    return render_to_response(template, template_vars, context)


@login_required
@transaction.autocommit
def payment_return(request, id, payment_secret_uuid,
                   template="paypaladaptive/return.html"):
    """
    Incoming return from paypal process (note this is a return to the site, not
    a returned payment)
    """

    logger.debug("Return received for Payment %s" % id)

    payment = get_object_or_404(Payment, id=id,
                                secret_uuid=payment_secret_uuid)

    if request.user != payment.purchaser:
        return HttpResponseForbidden("Unauthorized")
    
    if payment.status not in ['created', 'completed']:
        payment.status_detail = _(u"Expected status to be created or "
                                  u"completed, not %s - duplicate "
                                  u"transaction?") % payment.status
        payment.status = 'error'
        payment.save()
        return HttpResponseServerError('Unexpected error')

    elif payment_secret_uuid != payment.secret_uuid:
        payment.status_detail = _(u"BuyReturn secret \"%s\" did not match")\
                                % payment_secret_uuid
        payment.status = 'error'
        payment.save()
        return HttpResponseServerError('Unexpected error')

    if payment.status != 'completed':
        payment.status = 'returned'
        payment.save()
        
    if not settings.USE_IPN:
        # TODO: make PaymentDetails call here if not using IPN
        pass
    
    context = RequestContext(request)
    template_vars = {"is_embedded": settings.USE_EMBEDDED}
        
    return render_to_response(template, template_vars, context)


@login_required
@transaction.autocommit
def preapproval_cancel(request, id,
                       template="paypaladaptive/cancel.html"):
    """Incoming preapproval cancellation from paypal"""

    logger.debug("Cancellation received for Preapproval %s" % id)

    preapproval = get_object_or_404(Preapproval, id=id)

    if request.user != preapproval.purchaser:
        return HttpResponseForbidden("Unauthorized")
    
    api.CancelPreapproval(preapproval.preapproval_key)
    preapproval.status = 'canceled'
    preapproval.save()

    context = RequestContext(request)
    template_vars = {"is_embedded": settings.USE_EMBEDDED}
        
    return render_to_response(template, template_vars, context)

@login_required
@transaction.autocommit
def preapproval_return(request, id, secret_uuid,
                       template="paypaladaptive/return.html"):
    """
    Incoming return from paypal process (note this is a return to the site,
    not a returned payment)
    """

    logger.debug("Return received for Payment %s" % id)

    preapproval = get_object_or_404(Preapproval, id=id)

    # if request.user != preapproval.purchaser:
    #     return HttpResponseForbidden("Unauthorized")
    
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

    if not settings.USE_IPN:
        # TODO: make PaymentDetails call here if not using IPN
        pass

    received_preapproval.send_robust(sender=None, preapproval=preapproval)

    if request.GET.get('next'):
        next = request.GET.get('next')
        return HttpResponseRedirect(next)

    context = RequestContext(request)
    template_vars = {"is_embedded": settings.USE_EMBEDDED,
                     "preapproval": preapproval, }

    return render_to_response(template, template_vars, context)


@require_POST
@csrf_exempt
@transaction.autocommit
def payment_ipn(request, id, secret_uuid):
    """Incoming IPN POST request from Paypal"""

    logger.debug("IPN received for Payment %s" % id)
    
    try:
        ipn = api.IPN(request)
    except IpnError, e:
        logger.warning("PayPal IPN verify failed: %s" % e)
        logger.debug("Request was: %s" % request)
        return HttpResponseBadRequest('verify failed')
         
    try:
        payment = Payment.objects.get(id=id)
    except ObjectDoesNotExist:
        logger.warning("Could not find Payment ID %s, replying to IPN with"
                       " 404." % id)
        raise Http404
    
    if payment.secret_uuid != secret_uuid:
        payment.status = 'error'
        payment.status_detail = _(u"IPN secret \"%s\" did not match")\
                                % secret_uuid
        payment.save()
        return HttpResponseBadRequest('secret mismatch')
    
    # Type of IPN?
    if ipn.type == api.IPN_TYPE_PAYMENT:
        payment.transaction_id = ipn.transactions[0].id
        
        if payment.amount != ipn.transactions[0].amount:
            payment.status = 'error'
            payment.status_detail = _(u"IPN amounts didn't match. Payment "
                                      u"requested %s. Payment made %s") %\
                                    (payment.amount,
                                     ipn.transactions[0].amount)
        else:
            payment.status = 'completed'

    elif ipn.type == api.IPN_TYPE_ADJUSTMENT:
        # TODO:
        logger.error('IPN adjustment request is not implemented!')
        raise NotImplementedError
    elif ipn.type == api.IPN_TYPE_PREAPPROVAL:
        # TODO:
        logger.error('IPN preapproval request is not implemented!')
        raise NotImplementedError        

    payment.save()
    
    # Ok, no content
    return HttpResponse(status=204)
