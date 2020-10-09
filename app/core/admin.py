from django.contrib import admin

# Register your models here.

from core.models import Account, RawTransaction, Order, Counterpart


class RawTransactionAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'counterpart', 'account', 'creation_date',
                    'amount')
    search_fields = ('product_name', 'counterpart__name', 'order__alipay_id',
                     'alipay_id', 'account__username')


class RawTransactionInline(admin.TabularInline):
    model = RawTransaction
    extra = 0
    fields = RawTransactionAdmin.list_display
    readonly_fields = fields
    show_change_link = True
    can_delete = False


class OrderAdmin(admin.ModelAdmin):
    search_fields = ('alipay_id',)
    inlines = [
        RawTransactionInline,
    ]


class CounterpartAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    inlines = [
        RawTransactionInline,
    ]


admin.site.register(Account)
admin.site.register(Order, OrderAdmin)
admin.site.register(RawTransaction, RawTransactionAdmin)
admin.site.register(Counterpart, CounterpartAdmin)