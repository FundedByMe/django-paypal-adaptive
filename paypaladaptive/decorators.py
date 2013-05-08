import logging

from django.http import HttpResponseBadRequest

from api.ipn import IPN
from api import IpnError

logger = logging.getLogger(__name__)

def takes_ipn(function):
    def _view(request, *args, **kwargs):
        try:
            kwargs['ipn'] = IPN(request)
        except IpnError, e:
            logger.warning("PayPal IPN verify failed: %s" % e)
            logger.debug("Request was: %s" % request)
            return HttpResponseBadRequest('verify failed')

        logger.debug("Incoming IPN call: " + str(request))

        return function(request, *args, **kwargs)

    return _view