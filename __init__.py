#This file is part of the nodux_account_voucher_ec module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.

from trytond.pool import Pool
from .move import *
from .account_voucher import *
from .invoice import *


def register():
    Pool.register(
        Move,
        Line,
        AccountVoucherSequence,
        AccountVoucherPayMode,
        AccountVoucher,
        AccountVoucherLine,
        AccountVoucherLineCredits,
        AccountVoucherLineDebits,
        AccountVoucherLinePaymode,
        module='nodux_account_voucher_ec', type_='model')
    Pool.register(
        PayInvoice,
        module='nodux_account_voucher_ec', type_='wizard')
    Pool.register(
        VoucherReport,
        module='nodux_account_voucher_ec', type_='report')
