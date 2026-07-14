from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'billing'
    verbose_name = 'Тарифы и оплата'

    def ready(self):
        from .signals import register_signals
        register_signals()
