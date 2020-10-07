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

class Transaction(models.Model):
    '''交易
    '''

    account = models.ForeignKey(to=Account, on_delete=models.CASCADE)
    #: 交易号
    alipay_id = models.CharField(max_length=100, unique=True)
    #: 商家订单号
    #: 交易创建时间
    #: 付款时间
    #: 最近修改时间
    #: 交易来源地
    #: 类型
    #: 交易对方
    #: 商品名称
    #: 金额（元）
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    #: 收/支
    #: 交易状态
    #: 服务费（元）
    #: 成功退款（元）
    #: 备注
    #: 资金状态
