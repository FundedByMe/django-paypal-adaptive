import django.dispatch


preapproval_approved = django.dispatch.Signal()
preapproval_canceled = django.dispatch.Signal()
preapproval_error = django.dispatch.Signal()

payment_completed = django.dispatch.Signal()
payment_error = django.dispatch.Signal()
