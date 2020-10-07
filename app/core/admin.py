from django.contrib import admin

# Register your models here.

from core.models import Account, RawTransaction

admin.site.register(Account)
admin.site.register(RawTransaction)