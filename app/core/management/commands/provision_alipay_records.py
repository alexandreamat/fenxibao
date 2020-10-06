import zipfile
import io
import glob
import types
import re
from enum import Enum, auto


import djclick as click
from django.db import transaction

from core.models import Transaction, Account


HEADER_DELIMITER = '---------------------------------交易记录明细列表------------------------------------\n'
FOOTER_DELIMITER = '------------------------------------------------------------------------------------\n'
ENCODING = 'gb18030'
PATTERN = r':\[(.*?)\]'


class RecordLabel(Enum):
    NUM = auto() #: 交易号
    ORDER_NUM = auto() #: 商家订单号
    CREATION_DATE = auto() #: 交易创建时间
    LAST_MODIFIED_DATE = auto() #: 最近修改时间
    PAYMENT_TIME = auto() #: 付款时间
    ORIGIN = auto() #: 交易来源地
    TYPE = auto() #: 类型
    COUNTERPART = auto() #: 交易对方
    PRODUCT_NAME = auto() #: 商品名称
    AMOUNT = auto() #: 金额（元）
    SIGN = auto() #: 收/支
    STATUS = auto() #: 交易状态
    SERVICE_FEE = auto() #: 服务费（元）
    REFUND_COMPLETE = auto() #: 成功退款（元）
    NOTES = auto() #: 备注
    FUNDS_STATE = auto() #: 资金状态


class TransactionRecord:

    class FileSection(Enum):
        HEADER = auto()
        LABELS = auto()
        BODY = auto()
        FOOTER = auto()


    def __init__(self, file_paths: str):
        self.file_paths = file_paths
        self.max_len_transaction_id = 0
        self.parse_zip_files()

    def parse_header_row(self, row: str):
        if '账号' in row:
            match = re.search(r'账号' + PATTERN, row)
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
        for i, label in enumerate(RecordLabel):
            if label == RecordLabel.NUM:
                number = columns[i]
            elif label == RecordLabel.CREATION_DATE:
                creation_date = columns[i]
            elif label == RecordLabel.AMOUNT:
                amount = columns[i]
        Transaction.objects.get_or_create(
            number=number,
            creation_date=creation_date,
            amount=amount,
        )

    def parse_footer_row(self, row: str):
        pass
        # if '用户' in row:
        #     match = re.search(r'用户:.*', row)
        #     if match:
        #         print(match)
        #         self.user_full_name = match.group(1)
  
    def parse_ext_file(self, ext_file: zipfile.ZipExtFile):
        current_section = self.FileSection.HEADER
        for i, row in enumerate(io.TextIOWrapper(ext_file, ENCODING)):
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
        print(f'Biggest transaction ID found: {self.max_len_transaction_id}')

    def parse_zip_files(self):
        for file_path in self.file_paths:
            with zipfile.ZipFile(file_path) as zip_dir:
                for zip_file in zip_dir.namelist():
                    with zip_dir.open(zip_file) as ext_file:
                        self.parse_ext_file(ext_file=ext_file)

@click.command(help='Provision Alipay records from .zip file')
@click.argument('file_paths')
def command(file_paths):
    click.secho("Processing records files...")
    with transaction.atomic():
        TransactionRecord(file_paths=glob.glob(file_paths))