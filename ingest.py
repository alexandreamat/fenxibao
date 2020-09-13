import zipfile
import io
import glob

file_paths = glob.glob('alipay_record_*.zip')
encoding = 'gb18030'

for file_path in file_paths:
    with zipfile.ZipFile(file_path) as zip_dir:
        for zip_file in zip_dir.namelist():
            with zip_dir.open(zip_file) as unzip_file:
                for i, row in enumerate(io.TextIOWrapper(unzip_file, encoding)):
                    columns = [column.strip() for column in row.split(',')]
                    print(columns)
                    if i == 100:
                        exit()