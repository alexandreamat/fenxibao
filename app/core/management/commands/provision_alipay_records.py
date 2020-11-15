# -*- coding: utf-8 -*-

import zipfile
import io
import glob
import re
import datetime
from typing import Optional, Dict, Iterable, List

from tqdm import tqdm
from decimal import Decimal
from enum import Enum, auto


import djclick as click
from django.db import transaction
from django.db.models import Q

from core.models import (
    Transaction,
    Account,
    Order,
    Transfer,
)


TWOPLACES = Decimal(10) ** -2
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


def parse_amount(amount: str) -> Decimal:
    return Decimal(amount).quantize(TWOPLACES)


def parse_date(date: str) -> Optional[datetime.datetime]:
    try:
        return datetime.datetime.strptime(date, DATETIME_FORMAT)
    except ValueError:
        return None


def split_strip_row(row: str) -> List[str]:
    return [column.strip() for column in row.split(',')]

class OrphanTransactionError(Exception):
    pass

class IncompleteTransferError(Exception):
    pass

class UnknownTransactionTypeError(Exception):
    pass

class AlipayRecord:

    ACCOUNT_ZH = '账号'
    ENCODING = 'gb18030'
    PATTERN = r':\[(.*?)\]'
    HEADER_DELIMITER = ('---------------------------------'
                        '交易记录明细列表------------------------------------\n')
    FOOTER_DELIMITER = ('-----------------------------------------------------'
                        '-------------------------------\n')

    class FileSection(Enum):
        HEADER = auto()
        LABELS = auto()
        BODY = auto()
        FOOTER = auto()

    class RawTransaction:

        class Label(Enum):
            '''Labels of record CSV file

            This class contains the labels of the CSV file, enumerated by column
            number
            '''

            #: Transaction ID in Alipay servers
            ALIPAY_ID = '交易号'
            #: Order ID, for purchases and bills; transfers do not have order ID (optional)
            #:  Taobao prefixes this value with either TX00P where X is 1 or 2
            #:  Taobao keeps reusing this number as long as new transactions are related to it
            #:  Utilities companies keeps reusing this number month after month for the same service
            #:  Only ORIGIN = alipay will leave this empty, but not always
            ORDER_NUM = '商家订单号'
            CREATED = '交易创建时间'
            #: (optional)
            PAID = '付款时间'
            MODIFIED = '最近修改时间'
            #: Source of transaction: Taobao, Alipay, or others
            ORIGIN = '交易来源地'
            #: Type of transaction (does not tell us much)
            CATEGORY = '类型'
            #: for purchases, shop name; for transfers, account name; deposits have
            #:  no counterpart (optional)
            COUNTERPART = '交易对方'
            #: Item name
            PRODUCT_NAME = '商品名称'
            #: Transaction amount, always positive
            AMOUNT = '金额（元）'
            # Expenditure / income (optional)
            SIGN = '收/支'
            STATE = '交易状态'
            #: only for origin = Alipay, is charged together with the amount
            SERVICE_FEE = '服务费（元）'
            #: some old transactions have a returned amount in the same
            #:  transaction, should be combined with amount
            REFUND_AMOUNT = '成功退款（元）'
            #: Notes (optional). Observation: origin = alipay + notes empty -> utilities
            #: or other commercial stuff. origin = alipay + some notes -> transfers
            NOTES = '备注'
            #: More truthful and detailed version of sign, since it has less empty
            #:  values, and no false expenditure (optional)
            FUNDS_STATE = '资金状态'

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
            #: Blank: cancelled transactions, movements between accounts
            BLANK = ''

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


        def __init__(self, row: str, labels: Dict[Label, int],
                     account: Account):
            cols = split_strip_row(row=row)
            self.account = account
            self.alipay_id = cols[labels[self.Label.ALIPAY_ID]]
            self.counterpart = cols[labels[self.Label.COUNTERPART]]
            self.order_num = cols[labels[self.Label.ORDER_NUM]]
            self.product_name = cols[labels[self.Label.PRODUCT_NAME]]
            self.origin = self.Origin(cols[labels[self.Label.ORIGIN]])
            self.funds_state = self.FundsState(
                cols[labels[self.Label.FUNDS_STATE]]
            )
            self.created = parse_date(cols[labels[self.Label.CREATED]])
            self.modified = parse_date(cols[labels[self.Label.MODIFIED]])
            self.paid = parse_date(cols[labels[self.Label.PAID]])
            self.raw_amount = parse_amount(cols[labels[self.Label.AMOUNT]])
            self.service_fee = parse_amount(
                cols[labels[self.Label.SERVICE_FEE]]
            )
            self.refund_amount = parse_amount(
                cols[labels[self.Label.REFUND_AMOUNT]]
            )
            self.notes = cols[labels[self.Label.NOTES]]

        def _create_transfer(self, counterpart: Account) -> Transfer:
            """Create transfer object in the DB

            This function creates a transaction with sender and receiver and
            returns the transaction object.
            """

            if self.funds_state == self.FundsState.PAID:
                transfer = Transfer.objects.create(
                    alipay_id=self.alipay_id,
                    sender=self.account,
                    receiver=counterpart,
                )
                return transfer
            elif self.funds_state == self.FundsState.RECEIVED:
                transfer = Transfer.objects.create(
                    alipay_id=self.alipay_id,
                    sender=counterpart,
                    receiver=self.account,
                )
                return transfer

        def _update_or_create_order(self, seller: Account) -> Order:
            """Update or create order in the DB

            This function will check if the order exists, and create one if it
            does not. If the order exists, it might update the name of the
            product with the new information. This is useful when the product
            name includes irrelevant information like '退款'.
            """

            try:
                order = Order.objects.get(alipay_id=self.order_num)
                if self.product_name in order.name:
                    order.name = self.product_name
                    order.save()
            except Order.DoesNotExist:
                order = Order.objects.create(
                    alipay_id=self.order_num,
                    name=self.product_name,
                    buyer=self.account,
                    seller=seller,
                )
            return order

        def _create_transaction(self, order: Order = None,
                                transfer: Transfer = None) -> None:
            amount = self.raw_amount + self.service_fee - self.refund_amount
            transaction = Transaction.objects.create(
                alipay_id=self.alipay_id,
                creation_date=self.created,
                payment_date=self.paid,
                last_modified_date=self.modified,
                amount=amount,
                order=order,
                transfer=transfer,
                notes=self.notes,
            )

        def _update_existing_transfer(self, transfer: Transfer):
            """Update transfer information

            Transfer already exists, but the then counterpart might
            have been registered with another name. Since the transaction
            number is the same, the account must be one of the two parties.

            The return value is a bool on whether the DB was changed.

            This function assumes that the given transfer contains new
            information.
            """

            if transfer.sender.username:
                # Transfer object first created with sender record
                assert not transfer.receiver.username
                unknown_account_id = transfer.receiver.id
                transfer.receiver = self.account
            elif transfer.receiver.username:
                # Transfer object first created with receiver record
                assert not transfer.sender.username
                unknown_account_id = transfer.sender.id
                transfer.sender = self.account
            else:
                raise IncompleteTransferError
            transfer.save()
            remaining_transfers = Transfer.objects.filter(
                Q(sender__id=unknown_account_id)
                | Q(receiver__id=unknown_account_id)
            ).count()
            if not remaining_transfers:
                Account.objects.get(pk=unknown_account_id).delete()

        def _process_new_transaction(self) -> None:
            """Create transfer or order, and their corresponding transaction

            First classify transactions between transfers and orders, create
            (or update) them, and finally create transaction objects.
            """

            counterpart, _ = Account.objects.get_or_create(
                user_full_name=self.counterpart,
            )
            if self.origin == self.Origin.ALIPAY and not (
                    self.order_num and not self.notes
            ):
                # Transfers
                transfer = self._create_transfer(counterpart=counterpart)
                order = None
            elif self.order_num:
                # Orders
                order = self._update_or_create_order(seller=counterpart)
                transfer = None
            else:
                raise UnknownTransactionTypeError
            self._create_transaction(order=order, transfer=transfer)

        def _process_existing_transaction(self, transaction: Transaction
                                          ) -> bool:
            """Update DB based on new information about existing transaction

            This function only implements updating information about transfer
            transactions.
            """

            if transfer := transaction.transfer:
                assert not transaction.order
                if self.account in (transfer.receiver, transfer.sender):
                    # no additional information to be added
                    return False
                self._update_existing_transfer(transfer=transfer)
                return True
            elif transaction.order:
                assert not transaction.transfer
                raise NotImplementedError('Seller records not supported yet.')
            else:
                raise OrphanTransactionError

        def dump(self) -> bool:
            """Write relevant information in the DB

            First assess if the information is relevant, and then either
            update existing objects (previously registered transactions) or
            create new objects (new transaction).

            Returns bool on changed database.
            """

            if self.funds_state not in [
                self.FundsState.PAID,
                self.FundsState.RECEIVED,
            ]:
                return False
            try:
                transaction = Transaction.objects.get(
                    alipay_id = self.alipay_id
                )
                self._process_existing_transaction(transaction)
            except Transaction.DoesNotExist:
                self._process_new_transaction()
            return True


    def __init__(self, file_paths: str):
        self.file_paths = file_paths
        self.account = None

    def _parse_header_row(self, row: str) -> None:
        if self.ACCOUNT_ZH not in row:
            return
        match = re.search(self.ACCOUNT_ZH + self.PATTERN, row)
        if not match:
            return
        username = match.group(1)
        self.account, _ = Account.objects.get_or_create(username=username)
        return

    def _parse_labels_row(self, row: str):
        file_labels = split_strip_row(row=row)
        self.labels = {
            label: file_labels.index(label.value)
            for label in self.RawTransaction.Label
        }

    def _parse_body_row(self, row: str):
        try:
            transaction = self.RawTransaction(row=row, labels=self.labels,
                                              account=self.account)
            transaction.dump()
        except IndexError:
            pass

    def _parse_footer_row(self, row: str):
        if '用户' in row:
            match = re.search(r'(?<=用户:).*', row)
            if match:
                self.account.user_full_name = match.group(0)
                self.account.save()

    def _parse_stream(self, stream: Iterable[str], file_size: int):
        current_section = self.FileSection.HEADER
        with tqdm(total=file_size, unit_scale=True, unit='B') as pbar:
            for row in stream:
                pbar.update(len(row.encode(self.ENCODING)))
                if current_section == self.FileSection.HEADER:
                    if row == self.HEADER_DELIMITER:
                        current_section = self.FileSection.LABELS
                        continue
                    self._parse_header_row(row=row)
                elif current_section == self.FileSection.LABELS:
                    self._parse_labels_row(row=row)
                    current_section = self.FileSection.BODY
                elif current_section == self.FileSection.BODY:
                    if row == self.FOOTER_DELIMITER:
                        current_section = self.FileSection.FOOTER
                        continue
                    self._parse_body_row(row=row)
                elif current_section == self.FileSection.FOOTER:
                    self._parse_footer_row(row=row)
            assert current_section == self.FileSection.FOOTER, (
                'File delimiters not found.')

    def _parse_zip_files(self):
        for file_path in glob.glob(self.file_paths):
            with zipfile.ZipFile(file_path) as zip_dir:
                for zip_file in zip_dir.namelist():
                    file_size = zip_dir.getinfo(zip_file).file_size
                    with zip_dir.open(zip_file) as ext_file:
                        stream = io.TextIOWrapper(ext_file, self.ENCODING)
                        self._parse_stream(stream=stream, file_size=file_size)

    def dump(self):
        print(self.file_paths)
        self._parse_zip_files()


@click.command(help='Provision Alipay records from .zip file')
@click.argument('file_paths')
def command(file_paths):
    click.secho("Processing records files...")
    with transaction.atomic():
        record = AlipayRecord(file_paths=file_paths)
        record.dump()
