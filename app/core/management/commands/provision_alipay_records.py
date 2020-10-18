# -*- coding: utf-8 -*-

import zipfile
import io
import glob
import re
import datetime
from typing import Optional
from tqdm import tqdm
from decimal import Decimal
from enum import Enum, auto


import djclick as click
from django.db import transaction

from core.models import (
    Transaction,
    Account,
    Order,
    Transfer,
)


HEADER_DELIMITER = ('---------------------------------'
                    '交易记录明细列表------------------------------------\n')
FOOTER_DELIMITER = ('---------------------------------------------------------'
                    '---------------------------\n')
ENCODING = 'gb18030'
PATTERN = r':\[(.*?)\]'
ACCOUNT_ZH = '账号'
TWOPLACES = Decimal(10) ** -2


class AlipayRecord:

    DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'  

    class FileSection(Enum):
        HEADER = auto()
        LABELS = auto()
        BODY = auto()
        FOOTER = auto()

    class Origin(Enum):
        # TODO do something with this
        #: Taobao purchases, refunds, installments
        TAOBAO = '淘宝'
        #: Transfers between friends, transfer to bank accounts,
        #: transfers between own's bank and alipay
        #: utilities payments
        ALIPAY = '支付宝网站'
        #: Physical shops + meituan + eleme + hema ...
        OTHER = '其他（包括阿里巴巴和外部商家）'

    class Category(Enum):
        # TODO do something with this
        #: Only for taobao transactions, have funds state = awaiting payment
        ALIPAY_PROTECTED = '支付宝担保交易'
        # For deposits, no actual transaction
        BOOKING = '预订交易'
        #: Most of transactions with normal shops and some taobao purchases
        INSTANT = '即时到账交易'

    class State(Enum):
        # TODO do something with this
        #: awaiting reception confirmation + taobao + expenditure = normal transaction
        AWAITING_RECEPTION_CONFIRMATION = '等待确认收货'
        CLOSED = '已关闭'
        #: paid + taobao + expenditure = paid in installments
        PAID = '支付成功'
        TRANSFER_FAILED = '转账失败'
        #: added value + alipay + expenditure = normal transaction
        ADDED_VALUE = '充值成功'
        FAILURE = '失败'
        UNFREEZED = '解冻成功'
        #: paid by others + alipay + expenditure = rare normal transaction
        PAID_BY_OTHERS = '代付成功'
        FREEZED = '冻结成功'
        #: awaiting payment + taobao + expenditure = operation cancelled
        AWAITING_PAYMENT = '等待付款'
        #: refunded + other = refund
        REFUNDED = '退款成功'
        TRANSACTION_SUCCESSFUL = '交易成功'
        #: transaction closed + taobao + expenditure = totally refunded purchase
        TRANSACTION_CLOSED = '交易关闭'

    class FundsState(Enum):
        '''Possible values for Funds State
        
        Only paid and received are used to sign the amount, the rest is laid 
        out here for completion.

        Notes:
            * empty funds state + taobao + transaction successful = paid by others
            * empty funds state + taobao + awaiting reception confirmation = paid by others
            * empty funds state + taobao + transaction closed = purchase cancelled
            * empty funds state + alipay + transaction closed = operation cancelled
            * empty funds state + alipay + closed = operation cancelled
            * empty funds state + other + transaction closed = operation cancelled
            * It is safe to ignore empty funds state operations
        '''

        #: Paid
        PAID = '已支出'
        #: Income
        RECEIVED = '已收入'
        #: Pending payment, transaction neither complete nor cancelled
        AWAITING_EXPENDITURE = '待支出'
        #: Transfer between own's bank and Alipay
        FUNDS_TRANSFER = '资金转移'
        #: Deposits
        FROZEN = '冻结'
        #: Deposits
        UNFROZEN = '解冻'

    class Sign(Enum):
        ''' Expenditure / income

        empty sign + taobao + transaction successful = paid by others
        empty sign + taobao + transaction closed = purchase cancelled
        empty sign + alipay + transaction successful = transfers between bank and alipay
        empty sign + alipay + transaction closed = operation cancelled
        empty sign + alipay + closed = operation cancelled
        empty sign + alipay + failure = operation cancelled
        empty sign + other + transaction closed = operation cancelled
        empty sign + other + frozen / unfrozen = deposit
        It is safe to ignore empty sign operations
        '''

        EXPENDITURE = '支出'
        INCOME = '收入'

    # PRODUCT_NAME_PATTERNS = {
    #     #: Transfers: when the issueing party writes a note, then that is used as a product name
    #     r'收款': ProductName.ALIPAY_TRANSFER,
    #     r'转账': ProductName.ALIPAY_TRANSFER,
    #     r'付款-.*': ProductName.ALIPAY_TRANSFER,
    #     r'转账到银行卡-.*': ProductName.BANK_TRANSFER,
    # }

    class Label(Enum):
        '''Labels of record CSV file
        
        This class contains the labels of the CSV file, enumerated by column
        number
        '''

        #: Transaction ID in Alipay servers
        ALIPAY_ID = 0 #: 交易号
        #: Order ID, for purchases and bills; transfers do not have order ID (optional)
        #:  Taobao prefixes this value with either TX00P where X is 1 or 2
        #:  Taobao keeps reusing this number as long as new transactions are related to it
        #:  Utilities companies keeps reusing this number month after month for the same service
        #:  Only ORIGIN = alipay will leave this empty, but not always
        ORDER_NUM = 1 #: 商家订单号
        CREATION_DATE = 2 #: 交易创建时间
        #: (optional)
        PAYMENT_DATE = 3 #: 付款时间
        LAST_MOD_DATE = 4 #: 最近修改时间
        #: Source of transaction: Taobao, Alipay, or others
        ORIGIN = 5 #: 交易来源地
        #: Type of transaction (does not tell us much)
        CATEGORY = 6 #: 类型
        #: for purchases, shop name; for transfers, account name; deposits have
        #:  no counterpart (optional)
        COUNTERPART = 7 #: 交易对方
        #: Item name
        PRODUCT_NAME = 8 #: 商品名称
        #: Transaction amount, always positive
        AMOUNT = 9 #: 金额（元）
        # Expenditure / income (optional)
        SIGN = 10 #: 收/支
        STATE = 11 #: 交易状态
        #: only for origin = Alipay, is charged together with the amount
        SERVICE_FEE = 12 #: 服务费（元）
        #: some old transactions have a returned amount in the same 
        #:  transaction, should be combined with amount
        REFUND_AMOUNT = 13 #: 成功退款（元）
        #: Notes (optional). Observation: origin = alipay + notes empty -> utilities
        #: or other commercial stuff. origin = alipay + some notes -> transfers!
        NOTES = 14 #: 备注
        #: More truthful and detailed version of sign, since it has less empty 
        #:  values, and no false expenditure (optional)
        FUNDS_STATE = 15 #: 资金状态


    def __init__(self, file_paths: str):
        self.file_paths = file_paths
        self.account = None
        self.parse_zip_files()

    def _parse_amount(self, amount: str) -> Decimal:
        return Decimal(amount).quantize(TWOPLACES)

    def _parse_date(self, date: str) -> Optional[datetime.datetime]:
        try:
            return datetime.datetime.strptime(date, self.DATETIME_FORMAT)
        except ValueError:
            return None

    def parse_header_row(self, row: str):
        if ACCOUNT_ZH in row:
            match = re.search(ACCOUNT_ZH + PATTERN, row)
            if match:
                username = match.group(1)
                self.account, _ = Account.objects.get_or_create(
                    username=username
                )
        # if '起始日期' in row:
        #     match = re.search(r'起始日期' + PATTERN, row)
        #     if match:
        #         start_date = match.group(1)
        # if '终止日期' in row:
        #     match = re.search(r'终止日期' + PATTERN, row)
        #     if match:
        #         end_date = match.group(1)

    def _parse_transfer_row(self, counterpart: Account,
                            funds_state: FundsState, alipay_id: str
                            ) -> Transfer:
        # transfers
        if funds_state == self.FundsState.PAID:
            transfer, _ = Transfer.objects.get_or_create(alipay_id=alipay_id,
                                                         sender=self.account,
                                                         receiver=counterpart)
            return transfer
        elif funds_state == self.FundsState.RECEIVED:
            transfer, _ = Transfer.objects.get_or_create(alipay_id=alipay_id,
                                                         sender=counterpart,
                                                         receiver=self.account)
            return transfer

    def _parse_order_row(self, seller: Account, order_name: str, order_num: str
                         ) -> Order:
        try:
            order = Order.objects.get(alipay_id=order_num)
            if order_name in order.name:
                order.name = order_name
                order.save()
        except Order.DoesNotExist:
            order = Order.objects.create(
                alipay_id=order_num,
                name=order_name,
                buyer=self.account,
                seller=seller,
            )
        return order

    def _update_objects(self, transaction: Transaction, counterpart: str):
        transfer = transaction.transfer
        if not transfer:
            return
        if self.account in (transfer.receiver, transfer.sender):
            return
        if transfer.sender.user_full_name in counterpart:
            transfer.receiver = self.account
        elif transfer.receiver.user_full_name in counterpart:
            transfer.sender = self.account
        transfer.save()
        return

    def _create_objects(self, counterpart, origin, order_num, notes, alipay_id, funds_state, product_name, raw_amount, service_fee, refund_amount, creation_date, payment_date, last_mod_date):
        counterpart, _ = Account.objects.get_or_create(
            user_full_name=counterpart,
        )
        if origin == self.Origin.ALIPAY and not(order_num and not notes):
            transfer = self._parse_transfer_row(
                alipay_id=alipay_id,
                funds_state=funds_state,
                counterpart=counterpart,
            )
            order = None
        elif order_num:
            order = self._parse_order_row(
                seller=counterpart,
                order_name=product_name,
                order_num=order_num,
            )
            transfer = None
        else:
            return
        amount = raw_amount + service_fee - refund_amount
        Transaction.objects.create(
            alipay_id=alipay_id,
            creation_date=creation_date,
            payment_date=payment_date,
            last_modified_date=last_mod_date,
            amount=amount,
            order=order,
            transfer=transfer,
            notes=notes,
        )

    def parse_body_row(self, row: str):
        cols = [column.strip() for column in row.split(',')]
        funds_state = cols[self.Label.FUNDS_STATE.value]
        try:
            funds_state = self.FundsState(funds_state)
        except ValueError:
            return
        if funds_state not in [self.FundsState.PAID, self.FundsState.RECEIVED]:
            return
        counterpart = cols[self.Label.COUNTERPART.value]
        order_num = cols[self.Label.ORDER_NUM.value]
        notes = cols[self.Label.NOTES.value]
        origin = self.Origin(cols[self.Label.ORIGIN.value])
        creation_date = self._parse_date(cols[self.Label.CREATION_DATE.value])
        last_mod_date = self._parse_date(cols[self.Label.LAST_MOD_DATE.value])
        payment_date = self._parse_date(cols[self.Label.PAYMENT_DATE.value])
        raw_amount = self._parse_amount(cols[self.Label.AMOUNT.value])
        service_fee = self._parse_amount(cols[self.Label.SERVICE_FEE.value])
        refund_amount = self._parse_amount(cols[self.Label.REFUND_AMOUNT.value])
        product_name = cols[self.Label.PRODUCT_NAME.value]
        alipay_id = cols[self.Label.ALIPAY_ID.value]
        try:
            transaction = Transaction.objects.get(alipay_id=alipay_id)
            self._update_objects(transaction=transaction,
                                 counterpart=counterpart)
        except Transaction.DoesNotExist:
            self._create_objects(
                counterpart, origin, order_num, notes, alipay_id, funds_state,
                product_name, raw_amount, service_fee, refund_amount,
                creation_date, payment_date, last_mod_date
            )

    def parse_footer_row(self, row: str):
        if '用户' in row:
            match = re.search(r'(?<=用户:).*', row)
            if match:
                self.account.user_full_name = match.group(0)
                self.account.save()
  
    def parse_ext_file(self, ext_file: zipfile.ZipExtFile, file_size: int):
        current_section = self.FileSection.HEADER
        acum_size = 0
        stream = io.TextIOWrapper(ext_file, ENCODING)
        with tqdm(total=file_size, unit_scale=True, unit='B') as pbar:
            for row in stream:
                pbar.update(len(row.encode(ENCODING)))
                if current_section == self.FileSection.HEADER:
                    if row == HEADER_DELIMITER:
                        current_section = self.FileSection.LABELS
                        continue
                    self.parse_header_row(row=row)
                elif current_section == self.FileSection.LABELS:
                    # TODO check labels order
                    current_section = self.FileSection.BODY
                    continue
                elif current_section == self.FileSection.BODY:
                    if row == FOOTER_DELIMITER:
                        current_section = self.FileSection.FOOTER
                        continue
                    self.parse_body_row(row=row)
                elif current_section == self.FileSection.FOOTER:
                    self.parse_footer_row(row=row)
        assert current_section == self.FileSection.FOOTER, ('File delimiters '
                                                            'not found.')

    def parse_zip_files(self):
        for file_path in self.file_paths:
            with zipfile.ZipFile(file_path) as zip_dir:
                for zip_file in zip_dir.namelist():
                    file_size = zip_dir.getinfo(zip_file).file_size
                    with zip_dir.open(zip_file) as ext_file:
                        self.parse_ext_file(
                            ext_file=ext_file,
                            file_size=file_size
                        )

@click.command(help='Provision Alipay records from .zip file')
@click.argument('file_paths')
def command(file_paths):
    click.secho("Processing records files...")
    with transaction.atomic():
        AlipayRecord(file_paths=glob.glob(file_paths))
