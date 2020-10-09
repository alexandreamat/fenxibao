from django.contrib import admin

# Register your models here.

from core.models import Account, RawTransaction, Order, Counterpart


class RawTransactionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'account', 'creation_date', 'amount')
    search_fields = ('order__alipay_id',
                     'alipay_id', 'account__username')
    pass


class RawTransactionInline(admin.TabularInline):
    extra = 0
    show_change_link = True
    can_delete = False
    model = RawTransaction
    fields = RawTransactionAdmin.list_display
    readonly_fields = fields


class OrderAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'creation_date', 'amount')
    search_fields = ('product_name', 'alipay_id')
    readonly_fields = ('amount', 'creation_date')
    inlines = [
        RawTransactionInline,
    ]


# class BaseInline(admin.TabularInline):
#     extra = 0
#     readonly_fields = fields
#     show_change_link = True
#     can_delete = False


class OrderInline(admin.TabularInline):
    extra = 0
    show_change_link = True
    can_delete = False
    model = Order
    fields = OrderAdmin.list_display
    readonly_fields = fields


class CounterpartAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    inlines = [
        RawTransactionInline,
        OrderInline,
    ]


admin.site.register(Account)
admin.site.register(Order, OrderAdmin)
admin.site.register(RawTransaction, RawTransactionAdmin)
admin.site.register(Counterpart, CounterpartAdmin)