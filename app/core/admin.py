from django.contrib import admin

# Register your models here.

from core.models import Account, RawTransaction, Order


class BaseInline(admin.TabularInline):
    extra = 0
    show_change_link = True
    can_delete = False


class RawTransactionAdmin(admin.ModelAdmin):
    common = ('account', 'other_party_account', 'order')
    list_display = ('__str__',) + common + ('creation_date', 'amount')
    search_fields = common + ('alipay_id',)


class OrderAdmin(admin.ModelAdmin):

    class RawTransactionInline(BaseInline):
        model = RawTransaction
        fields = RawTransactionAdmin.list_display
        readonly_fields = fields


    common = ('account', 'other_party_account', 'product_name')
    list_display = common + ('creation_date', 'amount')
    search_fields = common + ('alipay_id',)
    inlines = [
        RawTransactionInline,
    ]


class OrderInline(BaseInline):
    model = Order
    fields = OrderAdmin.list_display
    readonly_fields = fields
    fk_name = 'other_party_account'


class AccountAdmin(admin.ModelAdmin):

    class RawTransactionInline(BaseInline):
        model = RawTransaction
        fields = RawTransactionAdmin.list_display
        readonly_fields = fields
        fk_name = 'other_party_account'


    common = ('username', 'user_full_name')
    list_display = common + ('kind',)
    search_fields = common
    inlines = [
        RawTransactionInline,
        OrderInline,
    ]


admin.site.register(Account, AccountAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(RawTransaction, RawTransactionAdmin)
