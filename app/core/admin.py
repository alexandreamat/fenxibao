from django.contrib import admin

# Register your models here.

from core.models import Account, RawTransaction, Order

admin.site.register(Account)
admin.site.register(Order)
admin.site.register(RawTransaction)