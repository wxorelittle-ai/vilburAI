from django.contrib import admin

from .models import WhatsAppOtpravka, TelegramUser


@admin.register(WhatsAppOtpravka)
class WhatsAppOtpravkaAdmin(admin.ModelAdmin):
    list_display = ('telefon', 'tip', 'dokument', 'status', 'demo_rezhim', 'data')
    list_filter = ('tip', 'status', 'demo_rezhim')


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ('brigada', 'status', 'username', 'telegram_id')
    list_filter = ('status',)
