from django.contrib import admin

# Register your models here.

from core.models import Account, Order, Transfer, Transaction


class BaseInline(admin.TabularInline):
    extra = 0
    show_change_link = True
    can_delete = False


class TransactionAdmin(admin.ModelAdmin):
    list_display = ('creation_date', 'amount')
    search_fields = ('alipay_id',)


class TransactionInline(BaseInline):
    model = Transaction
    fields = TransactionAdmin.list_display
    readonly_fields = fields


class OrderAdmin(admin.ModelAdmin):
    list_display = ('name', 'buyer', 'seller', 'creation_date', 'amount')
    search_fields = ('name', 'buyer__full_name', 'seller__full_name',
                     'alipay_id',)
    inlines = [
        TransactionInline,
    ]

class TransferAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'amount')
    search_fields = ('sender__user_full_name', 'receiver__user_full_name')
    inlines = [
        TransactionInline,
    ]

class SenderTransferInline(BaseInline):
    model = Transfer
    fields = TransferAdmin.list_display
    readonly_fields = fields
    fk_name = 'sender'
    verbose_name_plural = "transfers as sender"


class ReceiverTransferInline(BaseInline):
    model = Transfer
    fields = TransferAdmin.list_display
    readonly_fields = fields
    fk_name = 'receiver'
    verbose_name_plural = "transfers as receiver"


class SellerOrderInline(BaseInline):
    model = Order
    fields = OrderAdmin.list_display
    readonly_fields = fields
    fk_name = 'seller'
    verbose_name_plural = "orders as seller"


class BuyerOrderInline(BaseInline):
    model = Order
    fields = OrderAdmin.list_display
    readonly_fields = fields
    fk_name = 'buyer'
    verbose_name_plural = "orders as buyer"


class AccountAdmin(admin.ModelAdmin):
    common = ('user_full_name', 'username', )
    list_display = common
    search_fields = common
    inlines = [
        # SellerOrderInline,
        # BuyerOrderInline,
        # # ReceiverTransferInline,
        # # SenderTransferInline,
    ]


admin.site.register(Account, AccountAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Transfer, TransferAdmin)
admin.site.register(Transaction, TransactionAdmin)
