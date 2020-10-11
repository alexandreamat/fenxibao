from django.contrib import admin

# Register your models here.

from core.models import Account, Transaction, Operation


class BaseInline(admin.TabularInline):
    extra = 0
    show_change_link = True
    can_delete = False


class TransactionAdmin(admin.ModelAdmin):
    common = ('account', 'other_party_account', 'operation')
    list_display = ('__str__',) + common + ('creation_date', 'amount')
    search_fields = common + ('alipay_id',)


class OperationAdmin(admin.ModelAdmin):

    class TransactionInline(BaseInline):
        model = Transaction
        fields = TransactionAdmin.list_display
        readonly_fields = fields


    common = ('account', 'other_party_account', 'product_name')
    list_display = common + ('creation_date', 'amount')
    search_fields = common + ('alipay_id',)
    inlines = [
        TransactionInline,
    ]


class OperationInline(BaseInline):
    model = Operation
    fields = OperationAdmin.list_display
    readonly_fields = fields
    fk_name = 'other_party_account'


class AccountAdmin(admin.ModelAdmin):

    class TransactionInline(BaseInline):
        model = Transaction
        fields = TransactionAdmin.list_display
        readonly_fields = fields
        fk_name = 'other_party_account'


    common = ('username', 'user_full_name')
    list_display = common + ('kind',)
    search_fields = common
    inlines = [
        TransactionInline,
        OperationInline,
    ]


admin.site.register(Account, AccountAdmin)
admin.site.register(Operation, OperationAdmin)
admin.site.register(Transaction, TransactionAdmin)
