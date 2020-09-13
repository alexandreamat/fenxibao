import zipfile
import io
import glob
import types
from enum import Enum, auto


HEADER_DELIMITER = '---------------------------------交易记录明细列表------------------------------------\n'
FOOTER_DELIMITER = '------------------------------------------------------------------------------------\n'
FILE_PATHS = glob.glob('alipay_record_*.zip')
ENCODING = 'gb18030'


class TransactionRecord:

    class FileSection(Enum):
        HEADER = auto()
        BODY = auto()
        FOOTER = auto()


    def __init__(self):
        self.max_len_transaction_id = 0
        self.parse_zip()

    def parse_header_row(self):
        pass

    def parse_body_row(self, row: str):
        columns = [column.strip() for column in row.split(',')]
        transaction_id = columns[0]
        if len(transaction_id) > self.max_len_transaction_id:
            self.max_len_transaction_id = len(transaction_id)

    def parse_footer_row(self):
        pass

    def parse_zip(self):
        for file_path in FILE_PATHS:
            with zipfile.ZipFile(file_path) as zip_dir:
                for zip_file in zip_dir.namelist():
                    with zip_dir.open(zip_file) as unzip_file:
                        current_section = self.FileSection.HEADER
                        for i, row in enumerate(io.TextIOWrapper(unzip_file, ENCODING)):
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
                        assert current_section == self.FileSection.FOOTER, 'File delimiters not found.'
                        print(f'Biggest transaction ID found: {self.max_len_transaction_id}')

if __name__ == '__main__':
    TransactionRecord()