import zipfile
import io
import glob
import types
import re
from tqdm import tqdm
from enum import Enum, auto


import djclick as click
from django.db import transaction

from core.models import Transaction, Account


HEADER_DELIMITER = '---------------------------------交易记录明细列表------------------------------------\n'
FOOTER_DELIMITER = '------------------------------------------------------------------------------------\n'
ENCODING = 'gb18030'
PATTERN = r':\[(.*?)\]'
ACCOUNT_ZH = '账号'

class AlipayRecord:

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

        NUM = 0 #: 交易号
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


    class TransactionOrigin:
        TAOBAO = '淘宝'
        ALIPAY = '支付宝网站'
        OTHER = '其他（包括阿里巴巴和外部商家）'
    

    class TransactionType:
        ALIPAY_PROTECTED = '支付宝担保交易'
        BOOKING = '预订交易'
        INSTANT = '即时到账交易'


    class Sign:
        EXPENDITURE = '支出'
        INCOME = '收入'
        EMPTY = ''


    class State:
        AWAITING_RECEPTION_CONFIRMATION = '等待确认收货'
        CLOSED = '已关闭'
        PAID = '支付成功'
        TRANSFER_FAILED = '转账失败'
        ADDED_VALUE = '充值成功'
        FAILURE = '失败'
        UNFREEZED = '解冻成功'
        PAID_BY_OTHERS = '代付成功'
        FREEZED = '冻结成功'
        AWAITING_PAYMENT = '等待付款'
        REFUNDED = '退款成功'
        TRANSACTION_SUCCESSFUL = '交易成功'
        TRANSACTION_CLOSED = '交易关闭'


    class FundState:
        AWAITING_EXPENDITURE = '待支出'
        PAID = '已支出'
        FUNDS_TRANSFER = '资金转移'
        FROZEN = '冻结'
        RECEIVED = '已收入'
        UNFROZEN = '解冻'}
        EMPTY = ''


    def __init__(self, file_paths: str):
        self.file_paths = file_paths
        self.parse_zip_files()

    def parse_header_row(self, row: str):
        if ACCOUNT_ZH in row:
            match = re.search(ACCOUNT_ZH + PATTERN, row)
            if match:
                self.username = match.group(1)
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
        alipay_id = columns[self.Label.NUM.value]
        creation_date = columns[self.Label.CREATION_DATE.value]
        amount = columns[self.Label.AMOUNT.value]
        origin = columns[self.Label.ORIGIN.value]
        type_ = columns[self.Label.TYPE.value]
        sign = columns[self.Label.SIGN.value]
        state = columns[self.Label.STATE.value]
        funds_state = columns[self.Label.FUNDS_STATE.value]
        account, _ = Account.objects.get_or_create(username=self.username)
        Transaction.objects.get_or_create(
            alipay_id=alipay_id,
            account=account,
            # creation_date=creation_date,
            amount=amount,
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
        # assert False

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