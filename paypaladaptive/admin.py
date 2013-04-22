from django.contrib import admin
from models import Payment, Preapproval, Refund

class PreapprovalAdmin(admin.ModelAdmin):
    list_display = ('preapproval_key', 'valid_until_date', 'status')

class PaymentAdmin(admin.ModelAdmin):
    pass

class RefundAdmin(admin.ModelAdmin):
    pass

# admin.site.register(Payment)
# admin.site.register(Preapproval, PreapprovalAdmin)
# admin.site.register(Refund)