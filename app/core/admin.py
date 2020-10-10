from django.contrib import admin

# Register your models here.

from core.models import Account, RawTransaction, Order


class BaseInline(admin.TabularInline):
    extra = 0
    show_change_link = True
    can_delete = False


class RawTransactionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'account', 'creation_date', 'amount')
    search_fields = ('order__alipay_id',
                     'alipay_id', 'account__username')


class OrderAdmin(admin.ModelAdmin):

    class RawTransactionInline(BaseInline):
        model = RawTransaction
        fields = RawTransactionAdmin.list_display
        readonly_fields = fields


    list_display = ('product_name', 'creation_date', 'amount')
    search_fields = ('product_name', 'alipay_id')
    readonly_fields = ('amount', 'creation_date')
    inlines = [
        RawTransactionInline,
    ]


class OrderInline(BaseInline):
    model = Order
    fields = OrderAdmin.list_display
    readonly_fields = fields


class AccountAdmin(admin.ModelAdmin):

    class RawTransactionInline(BaseInline):
        model = RawTransaction
        fields = RawTransactionAdmin.list_display
        readonly_fields = fields
        fk_name = 'other_party_account'


    list_display = ('username', 'user_full_name', 'kind')
    search_fields = ('username', 'user_full_name')
    inlines = [
        RawTransactionInline,
        OrderInline,
    ]


admin.site.register(Account, AccountAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(RawTransaction, RawTransactionAdmin)
