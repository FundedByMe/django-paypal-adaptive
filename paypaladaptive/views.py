"""
Paypal Adaptive Payments supporting views

"""

import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import (HttpResponseServerError, HttpResponseRedirect,
                         HttpResponseBadRequest, HttpResponse, Http404)
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

import settings
import api
from api.ipn import constants, IPN
from models import Payment, Preapproval
from decorators import takes_ipn


logger = logging.getLogger(__name__)


@login_required
@transaction.autocommit
def payment_cancel(request, payment_id, payment_secret_uuid,
                   template="paypaladaptive/cancel.html"):
    """Handle incoming cancellation from paypal"""

    logger.debug("Cancellation received for Payment %s" % payment_id)

    payment = get_object_or_404(Payment, id=payment_id,
                                secret_uuid=payment_secret_uuid)
    
    payment.status = 'canceled'
    payment.save()

    context = RequestContext(request)
    template_vars = {"is_embedded": settings.USE_EMBEDDED}
        
    return render_to_response(template, template_vars, context)


@login_required
@transaction.autocommit
def payment_return(request, payment_id, payment_secret_uuid,
                   template="paypaladaptive/return.html"):
    """
    Incoming return from paypal process (note this is a return to the site, not
    a returned payment)
    """

    logger.debug("Return received for Payment %s" % payment_id)

    payment = get_object_or_404(Payment, id=payment_id,
                                secret_uuid=payment_secret_uuid)

    if payment.status not in ['created', 'completed']:
        payment.status_detail = _(u"Expected status to be created or "
                                  u"completed, not %s - duplicate "
                                  u"transaction?") % payment.status
        payment.status = 'error'
        payment.save()
        return HttpResponseServerError('Unexpected error')

    elif payment_secret_uuid != payment.secret_uuid:
        payment.status_detail = (_(u"BuyReturn secret \"%s\" did not match")
                                 % payment_secret_uuid)
        payment.status = 'error'
        payment.save()
        return HttpResponseServerError('Unexpected error')

    if payment.status != 'completed':
        payment.status = 'returned'
        payment.save()

    if not settings.USE_IPN:
        logger.warning("Using PaymentDetails is not implemented and IPN is"
                       "turned off.")
        # TODO: make PaymentDetails call here if not using IPN
        pass
        
    context = RequestContext(request)
    template_vars = {"is_embedded": settings.USE_EMBEDDED}
        
    return render_to_response(template, template_vars, context)


@login_required
@transaction.autocommit
def preapproval_cancel(request, preapproval_id,
                       template="paypaladaptive/cancel.html"):
    """Incoming preapproval cancellation from paypal"""

    logger.debug("Cancellation received for Preapproval %s" % preapproval_id)

    preapproval = get_object_or_404(Preapproval, id=preapproval_id)

    # if request.user != preapproval.purchaser:
    #     return HttpResponseForbidden("Unauthorized")
    
    api.CancelPreapproval(preapproval.preapproval_key)
    preapproval.status = 'canceled'
    preapproval.save()

    if request.GET.get('next'):
        next_url = request.GET.get('next')
        return HttpResponseRedirect(next_url)

    context = RequestContext(request)
    template_vars = {"is_embedded": settings.USE_EMBEDDED}
        
    return render_to_response(template, template_vars, context)


@login_required
@transaction.autocommit
def preapproval_return(request, preapproval_id, secret_uuid,
                       template="paypaladaptive/return.html"):
    """
    Incoming return from paypal process (note this is a return to the site,
    not a returned payment)

    """

    preapproval = get_object_or_404(Preapproval, id=preapproval_id)

    logger.debug("Return received for Preapproval %s" % preapproval_id)

    if preapproval.status != 'created':
        preapproval.status_detail = _(u"Expected status to be created"
                                      u" not %s - duplicate"
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

    if request.GET.get('next'):
        next_url = request.GET.get('next')
        return HttpResponseRedirect(next_url)

    if not settings.USE_IPN:
        # TODO: make PreapprovalDetails call here if not using IPN
        logger.warning("Using PreapprovalDetails is not implemented and IPN is"
                       "turned off.")
        pass

    context = RequestContext(request)
    template_vars = {"is_embedded": settings.USE_EMBEDDED,
                     "preapproval": preapproval, }

    return render_to_response(template, template_vars, context)


@takes_ipn
@require_POST
@csrf_exempt
@transaction.autocommit
def payment_ipn(request, payment_id, payment_secret_uuid, ipn):
    """
    Incoming IPN POST request from Paypal

    """

    try:
        payment = Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        logger.warning('Could not find Payment ID %s, replying to IPN with '
                       '404.' % payment_id)
        raise Http404

    if payment.secret_uuid != payment_secret_uuid:
        payment.status = 'error'
        payment.status_detail = ('IPN secret "%s" did not match'
                                 % payment_secret_uuid)
        payment.save()
        return HttpResponseBadRequest('secret uuid mismatch')

    # Type of IPN?
    if ipn.type == constants.IPN_TYPE_PAYMENT:
        payment.transaction_id = ipn.transactions[0].id

        if payment.amount != ipn.transactions[0].amount:
            payment.status = 'error'
            payment.status_detail = ("IPN amounts didn't match. Payment "
                                     "requested %s. Payment made %s"
                                     % (payment.amount,
                                        ipn.transactions[0].amount))
        else:
            payment.status = 'completed'

    payment.save()

    # Ok, no content
    return HttpResponse(status=204)


@takes_ipn
@require_POST
@csrf_exempt
@transaction.autocommit
def preapproval_ipn(request, preapproval_id, preapproval_secret_uuid, ipn):
    """
    Incoming IPN POST request from Paypal

    """

    if ipn.type != constants.IPN_TYPE_PREAPPROVAL:
        return HttpResponseBadRequest('invalid ipn type')

    # TODO:
    logger.error('IPN preapproval request is not implemented!')
    raise NotImplementedError


@takes_ipn
@require_POST
@csrf_exempt
@transaction.autocommit
def adjustment_ipn(request, ipn):
    """
    Incoming IPN POST request from Paypal

    """

    if ipn.type != constants.IPN_TYPE_ADJUSTMENT:
        return HttpResponseBadRequest('invalid ipn type')

    # TODO:
    logger.error('IPN adjustment request is not implemented!')
    raise NotImplementedError