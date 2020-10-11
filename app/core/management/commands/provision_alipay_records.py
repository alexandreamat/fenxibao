import zipfile
import io
import glob
import types
import re
import datetime
from tqdm import tqdm
from decimal import Decimal
from enum import Enum, auto


import djclick as click
from django.db import transaction

from core.models import Transaction, Account, Operation


HEADER_DELIMITER = '---------------------------------交易记录明细列表------------------------------------\n'
FOOTER_DELIMITER = '------------------------------------------------------------------------------------\n'
ENCODING = 'gb18030'
PATTERN = r':\[(.*?)\]'
ACCOUNT_ZH = '账号'
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
TWOPLACES = Decimal(10) ** -2


class AlipayRecord:

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
        PAID = auto()
        #: Income
        RECEIVED = auto()
        #: Pending payment, transaction neither complete nor cancelled
        AWAITING_EXPENDITURE = auto()
        #: Transfer between own's bank and Alipay
        FUNDS_TRANSFER = auto()
        #: Deposits
        FROZEN = auto()
        #: Deposits
        UNFROZEN = auto()


    TRANSACTION_ORIGIN_CHOICES = {
        #: Taobao purchases, refunds, installments
        '淘宝': Transaction.Origin.TAOBAO,
        #: Transfers between friends, transfer to bank accounts,
        #: transfers between own's bank and alipay (might have order number)
        #: utilities payments (have order number)
        '支付宝网站': Transaction.Origin.ALIPAY,
        #: Physical shops + meituan + eleme + hema
        '其他（包括阿里巴巴和外部商家）': Transaction.Origin.OTHER,
    }
    TRANSACTION_TYPE_CHOICES = {
        #: Only for taobao transactions, have funds state = awaiting payment
        '支付宝担保交易': Transaction.Categroy.ALIPAY_PROTECTED,
        # For deposits, no actual transaction
        '预订交易': Transaction.Categroy.BOOKING,
        #: Most of transactions with normal shops and some taobao purchases
        '即时到账交易': Transaction.Categroy.INSTANT,
    }
    TRANSACTION_SIGN_CHOICES = {
        '支出': Transaction.Sign.EXPENDITURE,
        '收入': Transaction.Sign.INCOME,
        #: empty sign + taobao + transaction successful = paid by others
        #: empty sign + taobao + transaction closed = purchase cancelled
        #: empty sign + alipay + transaction successful = transfers between bank and alipay
        #: empty sign + alipay + transaction closed = operation cancelled
        #: empty sign + alipay + closed = operation cancelled
        #: empty sign + alipay + failure = operation cancelled
        #: empty sign + other + transaction closed = operation cancelled
        #: empty sign + other + frozen / unfrozen = deposit
        #: It is safe to ignore empty sign operations
    }
    TRANSACTION_STATE_CHOICES = {
        #: awaiting reception confirmation + taobao + expenditure = normal transaction
        '等待确认收货': Transaction.State.AWAITING_RECEPTION_CONFIRMATION,
        '已关闭': Transaction.State.CLOSED,
        #: paid + taobao + expenditure = paid in installments
        '支付成功': Transaction.State.PAID,
        '转账失败': Transaction.State.TRANSFER_FAILED,
        #: added value + alipay + expenditure = normal transaction
        '充值成功': Transaction.State.ADDED_VALUE,
        '失败': Transaction.State.FAILURE,
        '解冻成功': Transaction.State.UNFREEZED,
        #: paid by others + alipay + expenditure = rare normal transaction
        '代付成功': Transaction.State.PAID_BY_OTHERS,
        '冻结成功': Transaction.State.FREEZED,
        #: awaiting payment + taobao + expenditure = operation cancelled
        '等待付款': Transaction.State.AWAITING_PAYMENT,
        #: refunded + other = refund
        '退款成功': Transaction.State.REFUNDED,
        '交易成功': Transaction.State.TRANSACTION_SUCCESSFUL,
        #: transaction closed + taobao + expenditure = totally refunded purchase
        '交易关闭': Transaction.State.TRANSACTION_CLOSED,
    }
    FUNDS_STATE_CHOICES = {
        '待支出': FundsState.AWAITING_EXPENDITURE,
        '已支出': FundsState.PAID,
        '资金转移': FundsState.FUNDS_TRANSFER,
        '冻结': FundsState.FROZEN,
        '已收入': FundsState.RECEIVED,
        '解冻': FundsState.UNFROZEN,
    }
    # PRODUCT_NAME_PATTERNS = {
    #     #: Transfers: when the issueing party writes a note, then that is used as a product name
    #     r'收款': Transaction.ProductName.ALIPAY_TRANSFER,
    #     r'转账': Transaction.ProductName.ALIPAY_TRANSFER,
    #     r'付款-.*': Transaction.ProductName.ALIPAY_TRANSFER,
    #     r'转账到银行卡-.*': Transaction.ProductName.BANK_TRANSFER,
    # }

    class FileSection(Enum):
        HEADER = auto()
        LABELS = auto()
        BODY = auto()
        FOOTER = auto()


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
        LAST_MODIFIED_DATE = 4 #: 最近修改时间
        #: Source of transaction: Taobao, Alipay, or others
        ORIGIN = 5 #: 交易来源地
        #: Type of transaction (does not tell us much)
        TYPE = 6 #: 类型
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
        # TODO rename to refunded amount or similar
        REFUND_COMPLETE = 13 #: 成功退款（元）
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

    def parse_header_row(self, row: str):
        if ACCOUNT_ZH in row:
            match = re.search(ACCOUNT_ZH + PATTERN, row)
            if match:
                username = match.group(1)
                self.account, _ = Account.objects.get_or_create(
                    username=username,
                    kind=Account.Kind.PERSONAL,
                )
        # if '起始日期' in row:
        #     match = re.search(r'起始日期' + PATTERN, row)
        #     if match:
        #         start_date = match.group(1)
        # if '终止日期' in row:
        #     match = re.search(r'终止日期' + PATTERN, row)
        #     if match:
        #         end_date = match.group(1)

    def parse_body_row(self, row: str):
        columns = [column.strip() for column in row.split(',')]
        # get columns' values according to column number
        alipay_id = columns[self.Label.ALIPAY_ID.value]
        creation_date = columns[self.Label.CREATION_DATE.value]
        amount = columns[self.Label.AMOUNT.value]
        origin = columns[self.Label.ORIGIN.value]
        category = columns[self.Label.TYPE.value]
        sign = columns[self.Label.SIGN.value]
        state = columns[self.Label.STATE.value]
        funds_state = columns[self.Label.FUNDS_STATE.value]
        order_num = columns[self.Label.ORDER_NUM.value]
        last_modified_date = columns[self.Label.LAST_MODIFIED_DATE.value]
        payment_date = columns[self.Label.PAYMENT_DATE.value]
        counterpart = columns[self.Label.COUNTERPART.value]
        product_name = columns[self.Label.PRODUCT_NAME.value]
        service_fee = columns[self.Label.SERVICE_FEE.value]
        refund_complete = columns[self.Label.REFUND_COMPLETE.value]
        notes = columns[self.Label.NOTES.value]
        # convert to choices
        origin = self.TRANSACTION_ORIGIN_CHOICES.get(origin)
        category = self.TRANSACTION_TYPE_CHOICES.get(category)
        sign = self.TRANSACTION_SIGN_CHOICES.get(sign)
        state = self.TRANSACTION_STATE_CHOICES.get(state)
        funds_state = self.FUNDS_STATE_CHOICES.get(funds_state)
        # Cast to the correct types
        amount = Decimal(amount).quantize(TWOPLACES)
        service_fee = Decimal(service_fee).quantize(TWOPLACES)
        refund_complete = Decimal(refund_complete).quantize(TWOPLACES)
        # Complete and sign amount
        if funds_state == self.FundsState.PAID:
            amount = -(amount + service_fee) + refund_complete
        elif funds_state == self.FundsState.RECEIVED:
            amount = amount
        else:
            return
        # Create datetime objects
        creation_date = datetime.datetime.strptime(
            creation_date,
            DATETIME_FORMAT,
        )
        last_modified_date = datetime.datetime.strptime(
            last_modified_date,
            DATETIME_FORMAT,
        )
        if payment_date:
            payment_date = datetime.datetime.strptime(
                payment_date,
                DATETIME_FORMAT,
            )
        else:
            payment_date = None
        # create objects
        if origin == Transaction.Origin.ALIPAY and not(order_num
                                                       and not notes):
            # personal transfers, might have order_num, altough irrelevant
            # instead, counterpart is important
            counterpart, _ = Account.objects.get_or_create(
                user_full_name=counterpart,
                kind=Account.Kind.PERSONAL,
            )
            operation = None
            account = self.account
        elif order_num:
            # commercial transactions
            counterpart, _ = Account.objects.get_or_create(
                user_full_name=counterpart,
                kind=Account.Kind.ENTERPRISE,
            )
            try:
                operation = Operation.objects.get(alipay_id=order_num)
                # subsequent transactions are prefixed e.g. with `refund`
                if product_name in operation.product_name:
                    operation.product_name = product_name
                    operation.save()
            except Operation.DoesNotExist:
                operation = Operation.objects.create(
                    alipay_id=order_num,
                    product_name=product_name,
                    account=self.account,
                    other_party_account=counterpart,
                )
            account = None
            counterpart = None
        else:
            # ignore commercial transactions without order number
            return
        Transaction.objects.get_or_create(
            account=account,
            alipay_id=alipay_id,
            creation_date=creation_date,
            amount=amount,
            origin=origin,
            category=category,
            state=state,
            operation=operation,
            last_modified_date=last_modified_date,
            payment_date=payment_date,
            other_party_account=counterpart,
            notes=notes,
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