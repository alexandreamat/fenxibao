from django.contrib import admin

# Register your models here.

from core.models import Account, Order, Transfer, Transaction


class BaseInline(admin.TabularInline):
    extra = 0
    show_change_link = True
    can_delete = False


class TransactionAdmin(admin.ModelAdmin):
    common = ('order', 'transfer')
    list_display = common + ('creation_date', 'amount')
    search_fields = common + ('alipay_id',)


class OrderAdmin(admin.ModelAdmin):

    class TransactionInline(BaseInline):
        model = Transaction
        fields = TransactionAdmin.list_display
        readonly_fields = fields


    common = ('buyer', 'seller', 'name')
    list_display = common + ('creation_date', 'amount')
    search_fields = common + ('alipay_id',)
    inlines = [
        TransactionInline,
    ]


class TransferAdmin(admin.ModelAdmin):
    common = ('sender', 'receiver')
    list_display = common + ('amount',)
    search_fields = common


class SenderTransferInline(BaseInline):
    model = Transfer
    fields = TransferAdmin.list_display
    readonly_fields = fields
    fk_name = 'sender'


class ReceiverTransferInline(BaseInline):
    model = Transfer
    fields = TransferAdmin.list_display
    readonly_fields = fields
    fk_name = 'receiver'


class SellerOrderInline(BaseInline):
    model = Order
    fields = OrderAdmin.list_display
    readonly_fields = fields
    fk_name = 'seller'


class BuyerOrderInline(BaseInline):
    model = Order
    fields = OrderAdmin.list_display
    readonly_fields = fields
    fk_name = 'buyer'


class AccountAdmin(admin.ModelAdmin):
    common = ('username', 'user_full_name')
    list_display = common + ('kind',)
    search_fields = common
    inlines = [
        SellerOrderInline,
        BuyerOrderInline,
        ReceiverTransferInline,
        SenderTransferInline,
    ]


admin.site.register(Account, AccountAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Transfer, TransferAdmin)
admin.site.register(Transaction, TransactionAdmin)
