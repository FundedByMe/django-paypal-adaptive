from celery.task import task

from .models import Preapproval, Payment


@task
def update_preapproval(preapproval_id):
    preapproval = Preapproval.objects.get(pk=preapproval_id)
    if preapproval.status != 'used':
        preapproval.update()


@task
def update_payment(payment_id):
    payment = Payment.objects.get(pk=payment_id)
    if payment.status != 'completed':
        payment.update()
