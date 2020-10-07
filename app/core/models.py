from django.db import models

# Create your models here.

class Account(models.Model):
    '''账号
    '''

    #: 账户名
    username = models.CharField(max_length=100, unique=True)
    #: 用户
    user_full_name = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f'{self.username} / {self.user_full_name}'

class RawTransaction(models.Model):
    '''交易
    '''

    class Origin(models.IntegerChoices):
        TAOBAO = 1
        ALIPAY = 2
        OTHER = 3


    class FundsState(models.IntegerChoices):
        AWAITING_EXPENDITURE = 1
        PAID = 2
        FUNDS_TRANSFER = 3
        FROZEN = 4
        RECEIVED = 5
        UNFROZEN = 6
    

    class Categroy(models.IntegerChoices):
        ALIPAY_PROTECTED = 1
        BOOKING = 2
        INSTANT = 3


    class Sign(models.IntegerChoices):
        EXPENDITURE = 1
        INCOME = 2


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


    class RefundComplete(models.IntegerChoices):
        pass


    account = models.ForeignKey(to=Account, on_delete=models.CASCADE)
    alipay_id = models.CharField(max_length=100, unique=True)
    creation_date = models.DateTimeField()
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    origin = models.IntegerField(choices=Origin.choices)
    category = models.IntegerField(choices=Categroy.choices)
    sign = models.IntegerField(choices=Sign.choices, null=True)
    state = models.IntegerField(choices=State.choices)
    funds_state = models.IntegerField(choices=FundsState.choices, null=True)
    order_num = models.CharField(max_length=100)
    last_modified_date = models.DateTimeField(null=True, blank=True)
    payment_date = models.DateTimeField(null=True, blank=True)
    counterpart = models.CharField(max_length=100)
    product_name = models.CharField(max_length=100)
    service_fee = models.DecimalField(max_digits=8, decimal_places=2)
    notes = models.TextField(blank=True)
    # refund_complete = None
