import zipfile
import datetime
from pathlib import Path
from decimal import Decimal
from typing import Optional, List

import pytest
from ddf import G

from core.models import (
    Account,
    Transaction,
    Order,
    Transfer,
)
from core.management.commands.provision_alipay_records import (
    AlipayRecord,
    parse_amount,
    parse_date,
    split_strip_row,
    OrphanTransactionError,
    IncompleteTransferError,
    UnknownTransactionTypeError,
)

RawTransaction = AlipayRecord.RawTransaction

ENCODING = 'gb18030'
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

@pytest.fixture
def mock_data():
    return """支付宝交易记录明细查询
账号:[123123123123123]
起始日期:[2011-10-18 00:00:00]    终止日期:[2020-10-18 19:20:31]
---------------------------------交易记录明细列表------------------------------------
交易号                  ,商家订单号               ,交易创建时间              ,付款时间                ,最近修改时间              ,交易来源地     ,类型              ,交易对方            ,商品名称                ,金额（元）   ,收/支     ,交易状态    ,服务费（元）   ,成功退款（元）  ,备注                  ,资金状态     ,
4564564564564564564564564556	,09090009090909090909090909090909090909090909099999090	,2020-10-18 17:40:27 ,2020-10-18 17:40:28 ,2020-10-18 17:40:28 ,其他（包括阿里巴巴和外部商家）,即时到账交易          ,越南妈(番禺店)        ,越南妈(番禺店)            ,114.00  ,支出      ,交易成功    ,0.00     ,0.00     ,                    ,已支出      ,
7897897897897897897897897897	,454545455454545454545454554545454554545454	,2020-10-16 20:15:06 ,2020-10-16 20:15:15 ,2020-10-16 20:15:15 ,其他（包括阿里巴巴和外部商家）,即时到账交易          ,燕子              ,Item                ,396.00  ,支出      ,交易成功    ,0.00     ,0.00     ,                    ,已支出      ,
2342342342342342342342342342	,10010101010101010101010100101010101010	,2017-02-28 19:15:36 ,2017-02-28 19:15:37 ,2017-05-30 19:15:53 ,其他（包括阿里巴巴和外部商家）,即时到账交易          ,代永锁             ,联华超市(百新店)消费         ,68.10   ,支出      ,交易成功    ,0.00     ,0.00     ,                    ,已支出      ,
------------------------------------------------------------------------------------
共4613笔记录
已收入:284笔,81485.91元
待收入:0笔,0.00元
已支出:4278笔,509468.67元
待支出:0笔,0.00元
导出时间:[2020-10-18 19:20:37]    用户:小明"""


@pytest.fixture
def mock_stream(mock_data: str):
    return mock_data.split('\n')


@pytest.fixture
def mock_file_path(mock_data: List[str], tmp_path: Path):
    with zipfile.ZipFile(tmp_path / 'tmp.zip', 'w') as zip_dir:
        with zip_dir.open('tmp.csv', 'w') as ext_file:
            ext_file.write(mock_data.encode(ENCODING))
    return str(tmp_path / 'tmp.zip')

@pytest.mark.django_db
@pytest.fixture
def record(mock_file_path: str):
    return AlipayRecord(file_paths=mock_file_path)

@pytest.fixture
@pytest.mark.django_db
def account():
    return G(Account)

@pytest.fixture
def row():
    return ('454545,90909090,2020-10-18 17:40:27,2020-10-18 17:40:28,'
            '2020-10-18 17:40:29 ,其他（包括阿里巴巴和外部商家）,即时到账交易,'
            '你去买东西的地方,你买的东西,114.00,支出,交易成功,1.00,2.00,欢迎再来,'
            '已支出,')

@pytest.mark.django_db
@pytest.fixture
def labels(row, record):
    labels = ('交易号,商家订单号,交易创建时间,付款时间,最近修改时间,交易来源地,类型,'
              '交易对方,商品名称,金额（元）,收/支,交易状态,服务费（元）,成功退款（元）,'
              '备注,资金状态,')
    record._parse_labels_row(row=labels)
    return record.labels

@pytest.mark.django_db
@pytest.fixture
def raw_transaction(row, labels, account: Account):
    return RawTransaction(account=account, row=row, labels=labels)


def test_parse_amount():
    assert parse_amount('12.34') == Decimal('12.34')
    assert parse_amount('12.3') == Decimal('12.30')
    assert parse_amount('12.345') == Decimal('12.34')

def test_parse_date():
    now = datetime.datetime.now().replace(microsecond=0)
    assert parse_date(now.strftime(DATETIME_FORMAT)) == now
    assert parse_date('foo') is None


ARGVALUES = [
    ('foo,bar', ['foo', 'bar']),
    ('   foo    ,    bar    ', ['foo', 'bar']),
    ('foo;bar', ['foo;bar']),
]

@pytest.mark.parametrize(argnames=('row', 'cols'), argvalues=ARGVALUES)
def test_split_strip_row(row: str, cols: List[str]):
    assert split_strip_row(row=row) == cols

@pytest.mark.django_db
def test_parse_zip_files(record: AlipayRecord):
    record._parse_zip_files()
    assert Account.objects.filter(username=123123123123123).count() == 1
    assert Transaction.objects.filter(
        alipay_id=7897897897897897897897897897,
    ).count() == 1


ARGVALUES = [
    ("""支付宝交易记录明细查询
账号:[123123123123123]
起始日期:[2011-10-18 00:00:00]    终止日期:[2020-10-18 19:20:31]
---------------------------------交易记录明细列表------------------------------------
交易号                  ,商家订单号               ,交易创建时间              ,付款时间                ,最近修改时间              ,交易来源地     ,类型              ,交易对方            ,商品名称                ,金额（元）   ,收/支     ,交易状态    ,服务费（元）   ,成功退款（元）  ,备注                  ,资金状态     ,
4564564564564564564564564556	,09090009090909090909090909090909090909090909099999090	,2020-10-18 17:40:27 ,2020-10-18 17:40:28 ,2020-10-18 17:40:28 ,其他（包括阿里巴巴和外部商家）,即时到账交易          ,越南妈(番禺店)        ,越南妈(番禺店)            ,114.00  ,支出      ,交易成功    ,0.00     ,0.00     ,                    ,已支出      ,
7897897897897897897897897897	,454545455454545454545454554545454554545454	,2020-10-16 20:15:06 ,2020-10-16 20:15:15 ,2020-10-16 20:15:15 ,其他（包括阿里巴巴和外部商家）,即时到账交易          ,燕子              ,Item                ,396.00  ,支出      ,交易成功    ,0.00     ,0.00     ,                    ,已支出      ,
2342342342342342342342342342	,10010101010101010101010100101010101010	,2017-02-28 19:15:36 ,2017-02-28 19:15:37 ,2017-05-30 19:15:53 ,其他（包括阿里巴巴和外部商家）,即时到账交易          ,代永锁             ,联华超市(百新店)消费         ,68.10   ,支出      ,交易成功    ,0.00     ,0.00     ,                    ,已支出      ,
------------------------------------------------------------------------------------
共4613笔记录
已收入:284笔,81485.91元
待收入:0笔,0.00元
已支出:4278笔,509468.67元
待支出:0笔,0.00元
导出时间:[2020-10-18 19:20:37]    用户:小明""", True),
    ("""支付宝交易记录明细查询
账号:[123123123123123]
起始日期:[2011-10-18 00:00:00]    终止日期:[2020-10-18 19:20:31]
---------------------------------交易记录明细列表------------------------------------
交易号                  ,商家订单号               ,交易创建时间              ,付款时间                ,最近修改时间              ,交易来源地     ,类型              ,交易对方            ,商品名称                ,金额（元）   ,收/支     ,交易状态    ,服务费（元）   ,成功退款（元）  ,备注                  ,资金状态     ,
4564564564564564564564564556	,09090009090909090909090909090909090909090909099999090	,2020-10-18 17:40:27 ,2020-10-18 17:40:28 ,2020-10-18 17:40:28 ,其他（包括阿里巴巴和外部商家）,即时到账交易          ,越南妈(番禺店)        ,越南妈(番禺店)            ,114.00  ,支出      ,交易成功    ,0.00     ,0.00     ,                    ,已支出      ,
7897897897897897897897897897	,454545455454545454545454554545454554545454	,2020-10-16 20:15:06 ,2020-10-16 20:15:15 ,2020-10-16 20:15:15 ,其他（包括阿里巴巴和外部商家）,即时到账交易          ,燕子              ,Item                ,396.00  ,支出      ,交易成功    ,0.00     ,0.00     ,                    ,已支出      ,
2342342342342342342342342342	,10010101010101010101010100101010101010	,2017-02-28 19:15:36 ,2017-02-28 19:15:37 ,2017-05-30 19:15:53 ,其他（包括阿里巴巴和外部商家）,即时到账交易          ,代永锁             ,联华超市(百新店)消费         ,68.10   ,支出      ,交易成功    ,0.00     ,0.00     ,                    ,已支出      ,
共4613笔记录
已收入:284笔,81485.91元
待收入:0笔,0.00元
已支出:4278笔,509468.67元
待支出:0笔,0.00元
导出时间:[2020-10-18 19:20:37]    用户:小明""", False),
    ("""支付宝交易记录明细查询
账号:[123123123123123]
起始日期:[2011-10-18 00:00:00]    终止日期:[2020-10-18 19:20:31]
交易号                  ,商家订单号               ,交易创建时间              ,付款时间                ,最近修改时间              ,交易来源地     ,类型              ,交易对方            ,商品名称                ,金额（元）   ,收/支     ,交易状态    ,服务费（元）   ,成功退款（元）  ,备注                  ,资金状态     ,
4564564564564564564564564556	,09090009090909090909090909090909090909090909099999090	,2020-10-18 17:40:27 ,2020-10-18 17:40:28 ,2020-10-18 17:40:28 ,其他（包括阿里巴巴和外部商家）,即时到账交易          ,越南妈(番禺店)        ,越南妈(番禺店)            ,114.00  ,支出      ,交易成功    ,0.00     ,0.00     ,                    ,已支出      ,
7897897897897897897897897897	,454545455454545454545454554545454554545454	,2020-10-16 20:15:06 ,2020-10-16 20:15:15 ,2020-10-16 20:15:15 ,其他（包括阿里巴巴和外部商家）,即时到账交易          ,燕子              ,Item                ,396.00  ,支出      ,交易成功    ,0.00     ,0.00     ,                    ,已支出      ,
2342342342342342342342342342	,10010101010101010101010100101010101010	,2017-02-28 19:15:36 ,2017-02-28 19:15:37 ,2017-05-30 19:15:53 ,其他（包括阿里巴巴和外部商家）,即时到账交易          ,代永锁             ,联华超市(百新店)消费         ,68.10   ,支出      ,交易成功    ,0.00     ,0.00     ,                    ,已支出      ,
------------------------------------------------------------------------------------
共4613笔记录
已收入:284笔,81485.91元
待收入:0笔,0.00元
已支出:4278笔,509468.67元
待支出:0笔,0.00元
导出时间:[2020-10-18 19:20:37]    用户:小明""", False),
]

@pytest.mark.parametrize(argnames=('data', 'is_valid'), argvalues=ARGVALUES)
@pytest.mark.django_db
def test_parse_stream(record: AlipayRecord, data: str, is_valid: bool):
    stream = [row + '\n' for row in data.split('\n')]
    if is_valid:
        record._parse_stream(stream=stream, file_size=1)
        assert Account.objects.filter(username=123123123123123).count() == 1
        assert Transaction.objects.filter(
            alipay_id=7897897897897897897897897897
        ).count() == 1
        assert Account.objects.filter(user_full_name='小明').count() == 1
    else:
        with pytest.raises(AssertionError):
            record._parse_stream(stream=stream, file_size=1)


ARGVALUES = [
    ('账号:[123123123123123]', True),
    ('账号:[123123123123123], 起始日期:[2011-10-18 00:00:00]', True),
    ('支付宝交易记录明细查询', False),
    ('账号: [123123123123123]', False),
    ('账号:123123123123123', False),
    ('账户:[123123123123123]', False),
]

@pytest.mark.django_db
@pytest.mark.parametrize(argnames=('row', 'is_valid'), argvalues=ARGVALUES)
def test_parse_header_row(record: AlipayRecord, row: str, is_valid: bool):
    record._parse_header_row(row=row)
    if is_valid:
        assert Account.objects.filter(username=123123123123123).count() == 1
    else:
        assert Account.objects.filter(username=123123123123123).count() == 0


ARGVALUES = [
    (
        '交易号,商家订单号,交易创建时间,付款时间,最近修改时间,交易来源地,类型,交易对方,'
        '商品名称,金额（元）,收/支,交易状态,服务费（元）,成功退款（元）,备注,资金状态,',
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
        'OK',
    ),
    (
        '商家订单号,交易号,交易创建时间,付款时间,最近修改时间,交易来源地,类型,交易对方,'
        '商品名称,金额（元）,收/支,交易状态,服务费（元）,成功退款（元）,备注,资金状态,',
        [1, 0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
        'Different order',
    ),
    (
        'extra,交易号,商家订单号,交易创建时间,付款时间,最近修改时间,交易来源地,类型,交易对方,'
        '商品名称,金额（元）,收/支,交易状态,服务费（元）,成功退款（元）,备注,资金状态,',
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
        'Additional labels',
    ),
    (
        '交易,商家订单号,交易创建时间,付款时间,最近修改时间,交易来源地,类型,交易对方,'
        '商品名称,金额（元）,收/支,交易状态,服务费（元）,成功退款（元）,备注,资金状态,',
        None,
        'Not matching labels',
    ),
]
@pytest.mark.django_db
@pytest.mark.parametrize(
    argnames=('row', 'indices', 'message'),
    argvalues=ARGVALUES,
)
def test_parse_labels_row(record: AlipayRecord, row: str,
                          indices: Optional[List['int']], message: str):
    if indices:
        record._parse_labels_row(row=row)
        expected = dict(zip(RawTransaction.Label, indices))
        assert record.labels == expected, message
    else:
        with pytest.raises(ValueError):
            record._parse_labels_row(row=row)

@pytest.mark.django_db
def test_parse_body_row(record: AlipayRecord):
    row = """456456, 789789,
    2020-10-18 17:40:27,2020-10-18 17:40:28,2020-10-18 17:40:28,
    其他（包括阿里巴巴和外部商家）,即时到账交易,越南妈(番禺店),越南妈(番禺店),114.00,支出,
    交易成功,0.00,0.00,,已支出,"""
    record.labels = dict(zip(RawTransaction.Label, range(15+1)))
    record.account = G(Account)
    record._parse_body_row(row=row)
    assert Transaction.objects.filter(alipay_id=456456).count() == 1
    assert Order.objects.filter(alipay_id=789789).count() == 1


ARGVALUES = [
    ('导出时间:[2020-10-18 19:20:37]    用户:小明', True),
    ('用户:小明', True),
    ('用户:小明    导出时间:[2020-10-18 19:20:37]', False),
    ('已支出:4278笔,509468.67元', False),
    ('导出时间:[2020-10-18 19:20:37]    用户:[小明]', False),
]

@pytest.mark.django_db
@pytest.mark.parametrize(argnames=('row', 'is_valid'), argvalues=ARGVALUES)
def test_parse_footer_row(record: AlipayRecord, row: str, is_valid: bool):
    record.account = G(Account)
    record._parse_footer_row(row=row)
    if is_valid:
        assert Account.objects.filter(user_full_name='小明').count() == 1
    else:
        assert Account.objects.filter(user_full_name='小明').count() == 0


@pytest.mark.django_db
def test_raw_transaction_create_transfer_paid(
        raw_transaction: RawTransaction
):
    # account pays, counterpart receives
    account = G(model=Account)
    counterpart = G(model=Account)
    raw_transaction.account = account
    raw_transaction.funds_state = RawTransaction.FundsState.PAID
    transfer = raw_transaction._create_transfer(counterpart=counterpart)
    assert transfer.sender == account
    assert transfer.receiver == counterpart
    assert Transfer.objects.filter(
        sender=account,
        receiver=counterpart,
    ).count() == 1

@pytest.mark.django_db
def test_raw_transaction_create_transfer_received(
        raw_transaction: RawTransaction
):
    # account receives, counterpart pays
    account = G(model=Account)
    counterpart = G(model=Account)
    raw_transaction.account = account
    raw_transaction.funds_state = RawTransaction.FundsState.RECEIVED
    transfer = raw_transaction._create_transfer(counterpart=counterpart)
    assert transfer.sender == counterpart
    assert transfer.receiver == account
    assert Transfer.objects.filter(
        sender=counterpart,
        receiver=account,
    ).count() == 1


ARGVALUES = [
    ('123123123', 'foo', '456456456', 'bar', 'bar'),
    ('123123123', 'refund: foo', '123123123', 'foo', 'foo'),
    ('123123123', 'foo', '123123123', 'refund: foo', 'foo'),
]

@pytest.mark.django_db
@pytest.mark.parametrize(
    argnames=('existing_alipay_id', 'existing_name', 'order_num',
              'product_name', 'expected_name'),
    argvalues=ARGVALUES
)
def test_raw_transaction_update_or_create_order(
        raw_transaction: RawTransaction,
        existing_alipay_id: str,
        existing_name: str,
        order_num: str,
        product_name: str,
        expected_name: str,
):
    buyer = G(model=Account)
    seller = G(model=Account)
    raw_transaction.account = buyer
    raw_transaction.order_num = order_num
    raw_transaction.product_name = product_name
    existing_order = G(
        model=Order,
        name=existing_name,
        seller=seller,
        buyer=buyer,
        alipay_id=existing_alipay_id,
    )
    order = raw_transaction._update_or_create_order(seller=seller)
    assert order.buyer.id == raw_transaction.account.id
    assert order.seller.id == seller.id
    assert (order.id == existing_order.id) == (order_num == existing_alipay_id)
    assert order.alipay_id == order_num
    assert order.name == expected_name
    assert Order.objects.filter(
        alipay_id=order_num,
        name=expected_name,
        buyer=raw_transaction.account,
        seller=seller,
    ).count() == 1


@pytest.mark.django_db
def test_raw_transaction_create_transaction(
        raw_transaction: RawTransaction,
):
    raw_amount = Decimal('100.00')
    refund_amount = Decimal('10.00')
    service_fee = Decimal('1.00')
    transfer = G(model=Transfer)
    order = G(model=Order)
    raw_transaction.raw_amount = raw_amount
    raw_transaction.refund_amount = refund_amount
    raw_transaction.service_fee = service_fee
    raw_transaction._create_transaction(order=order, transfer=transfer)
    assert Transaction.objects.filter(
        alipay_id=raw_transaction.alipay_id,
        creation_date=raw_transaction.created,
        payment_date=raw_transaction.paid,
        last_modified_date=raw_transaction.modified,
        amount=raw_amount+service_fee-refund_amount,
        order=order,
        transfer=transfer,
        notes=raw_transaction.notes,
    ).count() == 1

@pytest.mark.django_db
def test_raw_transaction_process_existing_transaction(
        raw_transaction: RawTransaction,
):
    # transaction has transfer but does not have order
        # raw transaction account is transfer receiver
    account = G(Account, username='foo')
    transaction = G(Transaction, transfer=G(Transfer, receiver=account))
    raw_transaction.account = account
    assert not raw_transaction._process_existing_transaction(transaction)
    assert raw_transaction.account in [
        transaction.transfer.sender, transaction.transfer.receiver
    ]
        # raw transaction account is transfer sender
    account = G(Account, username='bar')
    transaction = G(Transaction, transfer=G(Transfer, sender=account))
    raw_transaction.account = account
    assert not raw_transaction._process_existing_transaction(transaction)
    assert raw_transaction.account in [
        transaction.transfer.sender, transaction.transfer.receiver
    ]
    # transaction does not have transfer but has order
    transaction = G(Transaction, order=G(Order))
    with pytest.raises(NotImplementedError):
        raw_transaction._process_existing_transaction(transaction)
    # transaction does not have either transfer nor order
    transaction = G(Transaction, order=G(Order), transfer=G(Transfer))
    with pytest.raises(AssertionError):
        raw_transaction._process_existing_transaction(transaction)
    # transaction has both transfer and order
    transaction = G(Transaction)
    with pytest.raises(OrphanTransactionError):
        raw_transaction._process_existing_transaction(transaction)




ARGVALUES = [
    (False, True, False),
    (False, True, True),
    (True, False, False),
    (True, False, True),
    (True, True, False),
    (False, False, False),
]

@pytest.mark.parametrize(
    argnames=('known_receiver', 'known_sender', 'other_transfers'),
    argvalues = ARGVALUES,
)
@pytest.mark.django_db
def test_raw_transaction_update_existing_transfer(
        raw_transaction: RawTransaction,
        known_receiver: bool,
        known_sender: bool,
        other_transfers: bool,
):
    receiver = G(Account, username='foo') if known_receiver else G(Account)
    sender = G(Account, username='bar') if known_sender else G(Account)
    if not known_receiver:
        unknown_account_id = receiver.id
    if not known_sender:
        unknown_account_id = sender.id
    transfer = G(Transfer, sender=sender, receiver=receiver)
    if other_transfers:
        G(Transfer, sender=sender, receiver=receiver)
        G(Transfer, sender=sender)
        G(Transfer, receiver=receiver)
    if known_receiver and known_sender:
        with pytest.raises(AssertionError):
            raw_transaction._update_existing_transfer(transfer)
    elif not (known_receiver or known_sender):
        with pytest.raises(IncompleteTransferError):
            raw_transaction._update_existing_transfer(transfer)
    else:
        raw_transaction._update_existing_transfer(transfer)
        remains = bool(Account.objects.filter(
            pk=unknown_account_id
        ).count())
        assert remains == other_transfers
        if not known_sender:
            assert transfer.sender.id == raw_transaction.account.id
        if not known_receiver:
            assert transfer.receiver.id == raw_transaction.account.id

ARGVALUES = [
    (RawTransaction.Origin.ALIPAY, '456456456', 'some notes', True, False),
    (RawTransaction.Origin.ALIPAY, '', 'some notes', True, False),
    (RawTransaction.Origin.ALIPAY, '456456456', '', False, False),
    (RawTransaction.Origin.ALIPAY, '', '', True, False),
    (RawTransaction.Origin.TAOBAO, '456456456', '', False, False),
    (RawTransaction.Origin.TAOBAO, '456456456', 'some notes', False, False),
    (RawTransaction.Origin.TAOBAO, '', 'some notes', False, True),
    (RawTransaction.Origin.TAOBAO, '', '', False, True),
    (RawTransaction.Origin.OTHER, '456456456', '', False, False),
    (RawTransaction.Origin.OTHER, '456456456', 'some notes', False, False),
    (RawTransaction.Origin.OTHER, '', 'some notes', False, True),
    (RawTransaction.Origin.OTHER, '', '', False, True),
]

@pytest.mark.parametrize(
    argnames=('origin', 'order_num', 'notes', 'is_transfer', 'is_unknown'),
    argvalues = ARGVALUES,
)
@pytest.mark.django_db
def test_raw_transaction_process_new_transaction(
        raw_transaction: RawTransaction,
        origin: RawTransaction.Origin,
        order_num: str,
        notes: str,
        is_transfer: bool,
        is_unknown: bool,
):
    raw_transaction.origin = origin
    raw_transaction.alipay_id = '123123123'
    raw_transaction.counterpart = 'foo'
    raw_transaction.order_num = order_num
    raw_transaction.notes = notes
    if is_unknown:
        with pytest.raises(UnknownTransactionTypeError):
            raw_transaction._process_new_transaction()
    else:
        raw_transaction._process_new_transaction()
        transactions = Transaction.objects.filter(alipay_id='123123123').all()
        assert len(transactions) == 1
        if is_transfer:
            transfer = transactions[0].transfer
            assert transfer
            assert transfer.alipay_id == '123123123'
            assert not transactions[0].order
        else: # is order
            order = transactions[0].order
            assert order
            assert order.alipay_id == order_num
            assert not transactions[0].transfer

@pytest.mark.django_db
def test_raw_transaction_dump_no_change(raw_transaction: RawTransaction):
    raw_transaction.funds_state = RawTransaction.FundsState.FROZEN
    assert not raw_transaction.dump()

@pytest.mark.django_db
def test_raw_transaction_dump_existing(raw_transaction: RawTransaction):
    G(Transaction, alipay_id='123',
      transfer=G(Transfer,sender=G(Account, username='foo')))
    raw_transaction.origin = RawTransaction.Origin.ALIPAY
    raw_transaction.funds_state = RawTransaction.FundsState.PAID
    raw_transaction.alipay_id = '123'
    assert Transaction.objects.filter(alipay_id='123').count() == 1
    assert raw_transaction.dump()
    assert Transaction.objects.filter(alipay_id='123').count() == 1


@pytest.mark.django_db
def test_raw_transaction_dump_new(raw_transaction: RawTransaction):
    raw_transaction.funds_state = RawTransaction.FundsState.PAID
    raw_transaction.alipay_id = '123'
    assert Transaction.objects.filter(alipay_id='123').count() == 0
    assert raw_transaction.dump()
    assert Transaction.objects.filter(alipay_id='123').count() == 1

@pytest.mark.django_db
def test_transaction(record: AlipayRecord, account: Account):
    labels = ('交易号,商家订单号,交易创建时间,付款时间,最近修改时间,交易来源地,类型,'
              '交易对方,商品名称,金额（元）,收/支,交易状态,服务费（元）,成功退款（元）,'
              '备注,资金状态,')
    record._parse_labels_row(row=labels)
    row = ('454545,90909090,2020-10-18 17:40:27,2020-10-18 17:40:28,'
           '2020-10-18 17:40:29 ,其他（包括阿里巴巴和外部商家）,即时到账交易,'
           '你去买东西的地方,你买的东西,114.00,支出,交易成功,1.00,2.00,欢迎再来,'
           '已支出,')
    transaction = RawTransaction(
        row=row,
        labels=record.labels,
        account=account,
    )
    assert transaction.alipay_id == '454545'
    assert transaction.order_num == '90909090'
    assert transaction.created == datetime.datetime(2020, 10, 18, 17, 40, 27)
    assert transaction.paid == datetime.datetime(2020, 10, 18, 17, 40, 28)
    assert transaction.modified == datetime.datetime(2020, 10, 18, 17, 40, 29)
    assert transaction.origin == RawTransaction.Origin.OTHER
    assert transaction.raw_amount == Decimal('114.00')
    assert transaction.counterpart == '你去买东西的地方'
    assert transaction.product_name == '你买的东西'
    assert transaction.funds_state == RawTransaction.FundsState.PAID
    assert transaction.notes == '欢迎再来'
    assert transaction.service_fee == Decimal('1.00')
    assert transaction.refund_amount == Decimal('2.00')

