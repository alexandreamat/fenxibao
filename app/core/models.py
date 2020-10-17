from django.db import models


# Create your models here.

class Account(models.Model):
    '''账号'''

    class Kind(models.IntegerChoices):
        PERSONAL = 1
        ENTERPRISE = 2

    #: 账户名
    username = models.CharField(max_length=100, unique=True, null=True,
                                blank=True)
    #: 用户
    user_full_name = models.CharField(max_length=100, blank=True, null=True)
    kind = models.IntegerField(choices=Kind.choices)

    def __str__(self):
        return self.user_full_name


class Order(models.Model):
    '''订单'''

    alipay_id = models.CharField(max_length=100, unique=True)
    buyer = models.ForeignKey(to=Account, on_delete=models.CASCADE,
                              related_name='orders_as_buyer')
    seller = models.ForeignKey(to=Account, on_delete=models.CASCADE,
                               related_name='orders_as_seller')
    name = models.CharField(max_length=100)

    @property
    def amount(self):
        return sum([rt.amount for rt in self.transaction_set.all()])

    @property
    def creation_date(self):
        return min([rt.creation_date for rt in self.transaction_set.all()])

    @property
    def last_modified_date(self):
        return max([rt.last_modified_date
                    for rt in self.transaction_set.all()])

    def __str__(self):
        return self.name


class Transfer(models.Model):
    sender = models.ForeignKey(to=Account, related_name='transfers_as_sender',
                               on_delete=models.CASCADE)
    receiver = models.ForeignKey(to=Account,
                                 related_name='transfers_as_receiver',
                                 on_delete=models.CASCADE)

    @property
    def amount(self):
        return self.transaction.amount


class Transaction(models.Model):
    '''交易'''

    class Origin(models.IntegerChoices):
        TAOBAO = 1
        ALIPAY = 2
        OTHER = 3

    class Categroy(models.IntegerChoices):
        ALIPAY_PROTECTED = 1
        BOOKING = 2
        INSTANT = 3

    class State(models.IntegerChoices):
        AWAITING_RECEPTION_CONFIRMATION = 1
        CLOSED = 2
        PAID = 3
        TRANSFER_FAILED = 4
        ADDED_VALUE = 5
        FAILURE = 6
        UNFREEZED = 7
        PAID_BY_OTHERS = 8
        FREEZED = 9
        AWAITING_PAYMENT = 10
        REFUNDED = 11
        TRANSACTION_SUCCESSFUL = 12
        TRANSACTION_CLOSED = 13

    alipay_id = models.CharField(max_length=100, unique=True)
    creation_date = models.DateTimeField()
    last_modified_date = models.DateTimeField()
    payment_date = models.DateTimeField(null=True, blank=True)
    order = models.ForeignKey(to=Order, on_delete=models.CASCADE,
                              null=True, blank=True)
    transfer = models.ForeignKey(to=Transfer, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    notes = models.TextField(blank=True)
    # TODO deprecate
    state = models.IntegerField(choices=State.choices)
    # TODO deprecate
    origin = models.IntegerField(choices=Origin.choices)
    # TODO deprecate
    category = models.IntegerField(choices=Categroy.choices)

    # def __str__(self):
    #     if self.order:
    #         return f'Commercial transaction with {self.order.seller.user_full_name}'
    #     else:
    #         return f'Personal transfer with {self.other_party_account.user_full_name}'
