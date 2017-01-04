#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = ['Bank']


class Bank:
    'Bank'
    __name__ = 'bank'
    account_expense = fields.Many2One('account.account', 'Account')
    nro_cuenta_bancaria = fields.Char('No. Cuenta Bancaria')
    nro_documento = fields.Integer('No. Documento')
    saldo_inicial = fields.Numeric('Saldo Inicial')
