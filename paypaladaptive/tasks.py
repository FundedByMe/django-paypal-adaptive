from celery.task import task
from celery.utils.log import get_task_logger

from .models import Preapproval, Payment

logger = get_task_logger(__name__)


@task
def update_preapproval(preapproval_id):
    preapproval = Preapproval.objects.get(pk=preapproval_id)
    if preapproval.status != 'used':
        logger.info('Updating Preapproval %i' % preapproval.id)
        preapproval.update()


@task
def update_payment(payment_id):
    payment = Payment.objects.get(pk=payment_id)
    if payment.status != 'completed':
        logger.info('Updating Payment %i' % payment.id)
        payment.update()
