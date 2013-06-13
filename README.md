Django Paypal Adaptive
===

This is not a stable repository. The API and the modules will be subject to
heavy changes and not all Paypal Adaptive endpoints are covered. FundedByMe
will help make the covering of the Pay, Preapproval and IPN endpoints as good
as possible but we might not have the resources to perfect this project.

Making Preapprovals and using them to create Payments is fully supported and
tested as long as IPN is turned on. Creating Payments without Preapprovals
might not work in this version.

Please reach out to us if you're interested in helping maintaining this
package.

Installation
============

Install package from PyPI:

    pip install django-paypal-adaptive
    
Add to your project's `INSTALLED_APPS` setting:

    INSTALLED_APPS = (
        …
        'paypaladaptive',
    )

Sync the database:
    
    $ python manage.py syncdb
    
Or if you're using __South__ you might want to add an initial migration for future changes:
    
    $ python manage.py schemamigration paypaladaptive --initial
    $ python manage.py syncdb --migrate

Models
===

Payment
---

__Status__

Possible values are:

    'new'  # Payment only exists locally
    'created'  # Payment exists on Paypal
    'error'  # Something along the process has gone wrong. Check status_detail
             # for more info.
    'returned'  # User has returned via the Payment return_url
    'completed'  # The Payment is complete
    'refunded'  # The Payment is refunded
    'canceled'  # The Payment has been canceled

Preapproval
---

__Status__

Possible values are:

    'new'  # Preapproval only exists locally — not known to Paypal
    'created'  # Preapproval has been saved on Paypal
    'error'  # Something has gone wrong, check status_detail for more info
    'returned'  # User has returned via the Preapproval return_url
    'approved'  # Preapproval is completed — ready to be used in payment
    'canceled'  # Preapproval has been canceled
    'used'  # Preapproval has been used in payment

The status describes

Settings
===

TEST_WITH_MOCK
---

Set whether tests should be run with built-in mocking responses and requests
or if the testing should spawn requests that hits Paypal's APIs directly.
Defaults to True. Override in your settings file like this:

    PAYPAL_TEST_WITH_MOCK = False

<a rel="license" href="http://creativecommons.org/licenses/by/3.0/deed.sv"><img alt="Creative Commons-licens" style="border-width:0" src="http://i.creativecommons.org/l/by/3.0/80x15.png" /></a><br /><span xmlns:dct="http://purl.org/dc/terms/" property="dct:title">django-paypal-adaptive</span> av <a xmlns:cc="http://creativecommons.org/ns#" href="https://github.com/FundedByMe/django-paypal-adaptive" property="cc:attributionName" rel="cc:attributionURL">FundedByMe</a> är licensierad under en <a rel="license" href="http://creativecommons.org/licenses/by/3.0/deed.sv">Creative Commons Erkännande 3.0 Unported licens</a>.<br />Based on a work at <a xmlns:dct="http://purl.org/dc/terms/" href="https://github.com/gmcguire/django-paypal-adaptive" rel="dct:source">https://github.com/gmcguire/django-paypal-adaptive</a>.

WARNING!! Everything below is outdated!!
===

A trivial example for now:
---


urls.py:

    from buzzcar.accounting.views import view_that_asks_for_money
    from django.conf.urls.defaults import patterns, url, include
    
    urlpatterns = patterns('',
        url(r'^payment/$', view_that_asks_for_money, name="payment"),
        
        url(r'^paypal/', include('paypaladaptive.urls')),
    )


views.py:

    from django.contrib.auth.decorators import login_required
    from django.http import HttpResponseServerError, HttpResponseRedirect
    from django.shortcuts import render_to_response
    from django.template.context import RequestContext
    from django.views.decorators.http import require_GET
    from money.Money import Money
    from paypaladaptive import settings, forms
    from paypaladaptive.models import Payment
    import logging
    
    logger = logging.getLogger(__name__)
    
    @login_required
    @require_GET
    def view_that_asks_for_money(request):
        
        payment = Payment(amount=Money('5.00'), purchaser=request.user)
        if not payment.process(request):
            # TODO: unable to process payment
            logger.error('Payment returned error during processing: %s' % payment.status_detail)
            
            return HttpResponseServerError("Unexpected error")
        
        if not settings.USE_EMBEDDED:
            return HttpResponseRedirect(payment.next_url())
    
        form = forms.PayPalAdaptiveEmbeddedForm(payment.pay_key)
        context = RequestContext(request)
        template_vars = {"form": form}
        
        return render_to_response("payment.html", template_vars, context)


templates/payment.html (not showing inheritance):

    <h1>Show me the money!</h1>
    <!-- writes out the form tag automatically -->
    {{ form.render }}
