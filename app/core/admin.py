from django.contrib import admin

# Register your models here.

from core.models import Account, RawTransaction, Order, Counterpart

admin.site.register(Account)
admin.site.register(Order)
admin.site.register(RawTransaction)
admin.site.register(Counterpart)