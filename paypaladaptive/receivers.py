from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Preapproval, Payment
from .settings import DELAYED_UPDATE_COUNTDOWN
from .tasks import update_preapproval, update_payment


@receiver(
    post_save,
    sender=Preapproval,
    dispatch_uid='django_paypal_adaptive_delay_preapproval_update_on_creation')
def delay_preapproval_update_on_creation(sender, instance, **kwargs):
    if instance.status != 'created':
        return

    update_preapproval.delay(
        preapproval_id=instance.id,
        countdown=int(DELAYED_UPDATE_COUNTDOWN.total_seconds()))


@receiver(
    post_save,
    sender=Payment,
    dispatch_uid='django_paypal_adaptive_delay_payment_update_on_creation')
def delay_payment_update_on_creation(sender, instance, **kwargs):
    if instance.status != 'created':
        return

    update_payment.delay(
        payment_id=instance.id,
        countdown=int(DELAYED_UPDATE_COUNTDOWN.total_seconds()))
