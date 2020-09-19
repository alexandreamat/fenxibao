from django.contrib import admin

# Register your models here.

from core.models import Account, Transaction

admin.site.register(Account)
admin.site.register(Transaction)