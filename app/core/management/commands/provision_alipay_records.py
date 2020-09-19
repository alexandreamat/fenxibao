import zipfile
import io
import glob
import types
from enum import Enum, auto


import djclick as click
from django.db import transaction

from core.models import Transaction, Account


HEADER_DELIMITER = '---------------------------------交易记录明细列表------------------------------------\n'
FOOTER_DELIMITER = '------------------------------------------------------------------------------------\n'
# FILE_PATHS = glob.glob('alipay_record_*.zip')
ENCODING = 'gb18030'


class TransactionRecord:

    class FileSection(Enum):
        HEADER = auto()
        BODY = auto()
        FOOTER = auto()


    def __init__(self, file_paths):
        self.file_paths = file_paths
        self.max_len_transaction_id = 0
        self.parse_zip_files()

    def parse_header_row(self):
        pass

    def parse_body_row(self, row: str):
        columns = [column.strip() for column in row.split(',')]
        transaction_id = columns[0]
        transaction_creation_time = columns[2]
        if len(transaction_id) > self.max_len_transaction_id:
            self.max_len_transaction_id = len(transaction_id)

    def parse_footer_row(self):
        pass

    def parse_ext_file(self, ext_file: zipfile.ZipExtFile):
        current_section = self.FileSection.HEADER
        for i, row in enumerate(io.TextIOWrapper(ext_file, ENCODING)):
            if current_section == self.FileSection.HEADER:
                if row == HEADER_DELIMITER:
                    current_section = self.FileSection.BODY
                    continue
                self.parse_header_row()
            elif current_section == self.FileSection.BODY:
                if row == FOOTER_DELIMITER:
                    current_section = self.FileSection.FOOTER
                    continue
                self.parse_body_row(row=row)
            elif current_section == self.FileSection.FOOTER:
                self.parse_footer_row()
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