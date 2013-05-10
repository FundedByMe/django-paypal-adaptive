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
from api.ipn import constants
from models import Payment, Preapproval
from decorators import takes_ipn


logger = logging.getLogger(__name__)


def render(request, template, template_vars=None):
    if template_vars is None:
        template_vars = {}

    if request.GET.get('next'):
        return HttpResponseRedirect(request.GET.get('next'))

    context = RequestContext(request)
    d = {"is_embedded": settings.USE_EMBEDDED}.update(template_vars)

    return render_to_response(template, d, context)


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

    template_vars = {"is_embedded": settings.USE_EMBEDDED}
    return render(request, template, template_vars)


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
        
    template_vars = {"is_embedded": settings.USE_EMBEDDED}
    return render(request, template, template_vars)


@transaction.autocommit
def preapproval_cancel(request, preapproval_id,
                       template="paypaladaptive/cancel.html"):
    """Incoming preapproval cancellation from paypal"""

    logger.debug("Cancellation received for Preapproval %s" % preapproval_id)

    preapproval = get_object_or_404(Preapproval, id=preapproval_id)

    api.CancelPreapproval(preapproval.preapproval_key)
    preapproval.status = 'canceled'
    preapproval.save()

    template_vars = {"is_embedded": settings.USE_EMBEDDED}
    return render(request, template, template_vars)


@transaction.autocommit
def preapproval_return(request, preapproval_id, secret_uuid,
                       template="paypaladaptive/return.html"):
    """
    Incoming return from paypal process (note this is a return to the site,
    not a returned payment)

    """

    preapproval = get_object_or_404(Preapproval, id=preapproval_id)

    logger.info("Return received for Preapproval %s" % preapproval_id)

    if preapproval.status not in ['created', 'approved']:
        preapproval.status_detail = _(
            u"Expected status to be created or approved not %s - duplicate "
            u"transaction?") % preapproval.status
        preapproval.status = 'error'
        preapproval.save()
        return HttpResponseServerError('Unexpected error')

    elif secret_uuid != preapproval.secret_uuid:
        preapproval.status_detail = _(u"BuyReturn secret \"%s\" did not"
                                      u" match") % secret_uuid
        preapproval.status = 'error'
        preapproval.save()
        return HttpResponseServerError('Unexpected error')

    if preapproval.status != 'approved':
        preapproval.status = 'returned'
        preapproval.save()

    if not settings.USE_IPN:
        # TODO: make PreapprovalDetails call here if not using IPN
        logger.warning("Using PreapprovalDetails is not implemented and IPN is"
                       "turned off.")

    if request.GET.get('next', False):
        next_url = request.GET.get('next')
        return HttpResponseRedirect(next_url)

    template_vars = {"is_embedded": settings.USE_EMBEDDED,
                     "preapproval": preapproval, }
    return render(request, template, template_vars)


@csrf_exempt
@require_POST
@transaction.autocommit
@takes_ipn
def ipn(request, object_id, object_secret_uuid, ipn):
    """
    Incoming IPN POST request from Paypal

    """

    logger.debug("Incoming IPN call: " + str(request))

    object_class = {
        constants.IPN_TYPE_PAYMENT: Payment,
        constants.IPN_TYPE_PREAPPROVAL: Preapproval,
        constants.IPN_TYPE_ADJUSTMENT: Payment
    }[ipn.type]

    try:
        obj = object_class.objects.get(pk=object_id)
    except object_class.DoesNotExist:
        logger.warning('Could not find %s ID %s, replying to IPN with '
                       '404.' % (object_class.__name__, object_id))
        raise Http404

    if obj.secret_uuid != object_secret_uuid:
        obj.status = 'error'
        obj.status_detail = ('IPN secret "%s" did not match db'
                             % object_secret_uuid)
        obj.save()
        return HttpResponseBadRequest('secret uuid mismatch')

    # IPN type-specific operations
    if ipn.type == constants.IPN_TYPE_PAYMENT:
        obj.transaction_id = ipn.transactions[0].id

        if obj.money != ipn.transactions[0].amount:
            obj.status = 'error'
            obj.status_detail = ("IPN amounts didn't match. Payment requested "
                                 "%s. Payment made %s"
                                 % (obj.money, ipn.transactions[0].amount))

        # check payment status
        elif request.POST.get('status', '') != 'COMPLETED':
            obj.status = 'error'
            obj.status_detail = ('PayPal status was "%s"'
                                 % request.POST.get('status'))
        else:
            obj.status = 'completed'

            # TODO: mark preapproval 'used'
    elif ipn.type == constants.IPN_TYPE_PREAPPROVAL:
        if obj.money != ipn.max_total_amount_of_all_payments:
            obj.status = 'error'
            obj.status_detail = (
                "IPN amounts didn't match. Preapproval requested %s. "
                "Preapproval made %s"
                % (obj.money, ipn.max_total_amount_of_all_payments))
        elif not ipn.approved:
            obj.status = 'error'
            obj.status_detail = "The preapproval is not approved"
        else:
            obj.status = 'approved'

    obj.save()

    # Ok, no content
    return HttpResponse(status=204)
