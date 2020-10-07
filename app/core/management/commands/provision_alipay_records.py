import zipfile
import io
import glob
import types
import re
import datetime
from tqdm import tqdm
from enum import Enum, auto


import djclick as click
from django.db import transaction

from core.models import RawTransaction, Account


HEADER_DELIMITER = '---------------------------------交易记录明细列表------------------------------------\n'
FOOTER_DELIMITER = '------------------------------------------------------------------------------------\n'
ENCODING = 'gb18030'
PATTERN = r':\[(.*?)\]'
ACCOUNT_ZH = '账号'

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


class AlipayRecord:


    TRANSACTION_ORIGIN_CHOICES = {
        '淘宝': RawTransaction.Origin.TAOBAO,
        '支付宝网站': RawTransaction.Origin.ALIPAY,
        '其他（包括阿里巴巴和外部商家）': RawTransaction.Origin.OTHER,
    }
    TRANSACTION_TYPE_CHOICES = {
        '支付宝担保交易': RawTransaction.Categroy.ALIPAY_PROTECTED,
        '预订交易': RawTransaction.Categroy.BOOKING,
        '即时到账交易': RawTransaction.Categroy.INSTANT,
    }
    TRANSACTION_SIGN_CHOICES = {
        '支出': RawTransaction.Sign.EXPENDITURE,
        '收入': RawTransaction.Sign.INCOME,
        # '': Transaction.Sign.EMPTY,
    }
    TRANSACTION_STATE_CHOICES = {
        '等待确认收货': RawTransaction.State.AWAITING_RECEPTION_CONFIRMATION,
        '已关闭': RawTransaction.State.CLOSED,
        '支付成功': RawTransaction.State.PAID,
        '转账失败': RawTransaction.State.TRANSFER_FAILED,
        '充值成功': RawTransaction.State.ADDED_VALUE,
        '失败': RawTransaction.State.FAILURE,
        '解冻成功': RawTransaction.State.UNFREEZED,
        '代付成功': RawTransaction.State.PAID_BY_OTHERS,
        '冻结成功': RawTransaction.State.FREEZED,
        '等待付款': RawTransaction.State.AWAITING_PAYMENT,
        '退款成功': RawTransaction.State.REFUNDED,
        '交易成功': RawTransaction.State.TRANSACTION_SUCCESSFUL,
        '交易关闭': RawTransaction.State.TRANSACTION_CLOSED,
    }
    FUNDS_STATE_CHOICES = {
        '待支出': RawTransaction.FundsState.AWAITING_EXPENDITURE,
        '已支出': RawTransaction.FundsState.PAID,
        '资金转移': RawTransaction.FundsState.FUNDS_TRANSFER,
        '冻结': RawTransaction.FundsState.FROZEN,
        '已收入': RawTransaction.FundsState.RECEIVED,
        '解冻': RawTransaction.FundsState.UNFROZEN,
        # '': Transaction.FundsState.EMPTY,
    }

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

        ALIPAY_ID = 0 #: 交易号
        ORDER_NUM = 1 #: 商家订单号
        CREATION_DATE = 2 #: 交易创建时间
        LAST_MODIFIED_DATE = 3 #: 最近修改时间
        PAYMENT_DATE = 4 #: 付款时间
        ORIGIN = 5 #: 交易来源地
        TYPE = 6 #: 类型
        COUNTERPART = 7 #: 交易对方
        PRODUCT_NAME = 8 #: 商品名称
        AMOUNT = 9 #: 金额（元）
        SIGN = 10 #: 收/支
        STATE = 11 #: 交易状态
        SERVICE_FEE = 12 #: 服务费（元）
        REFUND_COMPLETE = 13 #: 成功退款（元）
        NOTES = 14 #: 备注
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
        # Create datetime objects
        creation_date = datetime.datetime.strptime(
            creation_date,
            DATETIME_FORMAT,
        )
        if last_modified_date:
            last_modified_date = datetime.datetime.strptime(
                last_modified_date,
                DATETIME_FORMAT,
            )
        else:
            last_modified_date = None
        if payment_date:
            payment_date = datetime.datetime.strptime(
                payment_date,
                DATETIME_FORMAT,
            )
        else:
            payment_date = None
        # create objects
        RawTransaction.objects.get_or_create(
            account=self.account,
            alipay_id=alipay_id,
            creation_date=creation_date,
            amount=amount,
            origin=origin,
            category=category,
            sign=sign,
            state=state,
            funds_state=funds_state,
            order_num=order_num,
            last_modified_date=last_modified_date,
            payment_date=payment_date,
            counterpart=counterpart,
            product_name=product_name,
            service_fee=service_fee,
            # refund_complete=refund_complete,
            notes=notes,
        )

    def parse_footer_row(self, row: str):
        pass
        # if '用户' in row:
        #     match = re.search(r'用户:.*', row)
        #     if match:
        #         print(match)
        #         self.user_full_name = match.group(1)
  
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