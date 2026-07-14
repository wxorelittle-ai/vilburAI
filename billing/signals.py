from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LimitTracker


def register_signals():
    """Вызывается из billing.apps.BillingConfig.ready()."""
    from documents.models import Dokument
    from calculator.models import Raschet
    from smety.models import Smeta

    @receiver(post_save, sender=Dokument, weak=False, dispatch_uid='billing_increment_dokumenty')
    def on_dokument_created(sender, instance, created, **kwargs):
        if created:
            LimitTracker.increment(instance.brigada, 'dokumenty_ispolzovano')

    @receiver(post_save, sender=Raschet, weak=False, dispatch_uid='billing_increment_raschety')
    def on_raschet_created(sender, instance, created, **kwargs):
        if created:
            LimitTracker.increment(instance.brigada, 'raschety_ispolzovano')

    @receiver(post_save, sender=Smeta, weak=False, dispatch_uid='billing_increment_smety')
    def on_smeta_created(sender, instance, created, **kwargs):
        if created:
            LimitTracker.increment(instance.brigada, 'smety_ispolzovano')
