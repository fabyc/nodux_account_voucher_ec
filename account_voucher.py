# -*- coding: utf-8 -*-
#This file is part of the nodux_account_voucher_ec module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelSingleton, ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pyson import Bool, Eval, Not, In
from trytond.pool import Pool
from trytond.report import Report
import pytz
from datetime import datetime,timedelta
import time
from trytond.modules.company import CompanyReport
from trytond.wizard import Wizard, StateAction, StateView, StateTransition, \
    Button

conversor = None
try:
    from numword import numword_es
    conversor = numword_es.NumWordES()
except:
    print("Warning: Does not possible import numword module!")
    print("Please install it...!")


__all__ = ['AccountVoucherSequence', 'AccountVoucherSequencePayment', 'AccountVoucher',
    'AccountVoucherLine', 'AccountVoucherLineCredits', 'AccountVoucherPayMode',
    'AccountVoucherLineDebits', 'AccountVoucherLinePaymode', 'VoucherReport',
    'PrintMove', 'PrintCheck', 'CancelVoucherStart', 'CancelVoucher']

_STATES = {
    'readonly': In(Eval('state'), ['posted', 'canceled']),
}

_NOPAGOS = [
    ('',''),
    ('1', '1 Pago'),
    ('2', '2 Pagos'),
    ('3', '3 Pagos'),
    ('4', '4 Pagos'),
]

class AccountVoucherSequence(ModelSingleton, ModelSQL, ModelView):
    'Account Voucher Sequence'
    __name__ = 'account.voucher.sequence'

    voucher_sequence = fields.Property(fields.Many2One('ir.sequence',
        'Voucher Sequence', required=True,
        domain=[('code', '=', 'account.voucher')]))

class AccountVoucherSequencePayment(ModelSingleton, ModelSQL, ModelView):
    'Account Voucher Sequence Payment'
    __name__ = 'account.voucher.sequence_payment'

    voucher_sequence_payment = fields.Property(fields.Many2One('ir.sequence',
        'Voucher Sequence Payment', required=True,
        domain=[('code', '=', 'account.voucher')]))


class AccountVoucherPayMode(ModelSQL, ModelView):
    'Forma de Pago'
    __name__ = 'account.voucher.paymode'

    name = fields.Char('Name')
    account = fields.Many2One('account.account', 'Account')

    def change_account(self, banco):
        res= {}
        res[self.account] = banco
        #self.write([self],{'account': banco})
        return res

class AccountVoucher(ModelSQL, ModelView):
    'Account Voucher'
    __name__ = 'account.voucher'
    _rec_name = 'number'

    number = fields.Char('Number', readonly=True, help="Voucher Number")
    party = fields.Many2One('party.party', 'Party', states={
                'required': ~Eval('active', True),
                'readonly': In(Eval('state'), ['posted', 'canceled']),
                })
    voucher_type = fields.Selection([
        ('payment', 'Payment'),
        ('receipt', 'Receipt'),
        ], 'Type', select=True, required=True, states=_STATES)
    pay_lines = fields.One2Many('account.voucher.line.paymode', 'voucher',
        'Pay Mode Lines', states=_STATES)
    date = fields.Date('Date', required=True, states=_STATES)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        states=_STATES)
    currency = fields.Many2One('currency.currency', 'Currency', states=_STATES)
    company = fields.Many2One('company.company', 'Company', states=_STATES)
    lines = fields.One2Many('account.voucher.line', 'voucher', 'Lines',
        states=_STATES)
    lines_credits = fields.One2Many('account.voucher.line.credits', 'voucher',
        'Credits', states={
            'invisible': ~Eval('lines_credits'),
            'readonly': In(Eval('state'), ['posted', 'canceled']),
            })
    lines_debits = fields.One2Many('account.voucher.line.debits', 'voucher',
        'Debits', states={
            'invisible': ~Eval('lines_debits'),
            'readonly': In(Eval('state'), ['posted', 'canceled']),
            })
    comment = fields.Text('Comment', states=_STATES)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('canceled', 'Canceled'),
        ], 'State', select=True, readonly=True)
    amount = fields.Function(fields.Numeric('Payment', digits=(16, 2)),
        'on_change_with_amount')
    amount_to_pay = fields.Function(fields.Numeric('To Pay', digits=(16, 2)),
        'on_change_with_amount_to_pay')
    amount_invoices = fields.Function(fields.Numeric('Invoices',
        digits=(16, 2)), 'on_change_with_amount_invoices')
    move = fields.Many2One('account.move', 'Move', readonly=True)
    move_canceled = fields.Many2One('account.move', 'Move Canceled',
        readonly=True, states={
            'invisible': ~Eval('move_canceled'),
            })
    from_pay_invoice = fields.Boolean('Voucher launched from Pay invoice')
    amount_to_pay_words = fields.Char('Amount to Pay (Words)',
            states={'readonly': True})

    transfer = fields.Boolean('Realizar movimiento', help='Realizar movimiento de caja a bancos, o transferencia entre bancos',states={
                'readonly':In(Eval('state'), ['posted', 'canceled']),
                })

    description = fields.Char('Description', states=_STATES)

    no_pagos = fields.Selection(_NOPAGOS, 'No. de Pagos', states={
        'invisible': (Eval('voucher_type') != 'payment') | (Not(Bool(Eval('lines')))),
        'readonly': In(Eval('state'), ['posted', 'canceled']),
    })

    plazo1 = fields.Integer('Dias', states={
        'invisible': (Eval('voucher_type') != 'payment') | (Not(Bool(Eval('lines')))) | (Eval('no_pagos').in_([''])),
        'required': Eval('no_pagos').in_(['1','2','3', '4'])  & (Eval('voucher_type') == 'payment'),
        'readonly': In(Eval('state'), ['posted', 'canceled']),
    })
    plazo2 = fields.Integer('Dias', states={
        'invisible': Eval('no_pagos').in_(['','1']) | (Eval('voucher_type') != 'payment'),
        'required': Eval('no_pagos').in_(['2', '3', '4']) & (Eval('voucher_type') == 'payment'),
        'readonly': In(Eval('state'), ['posted', 'canceled']),
    })
    plazo3 = fields.Integer('Dias', states={
        'invisible': Eval('no_pagos').in_(['','1', '2']) | (Eval('voucher_type') != 'payment'),
        'required': Eval('no_pagos').in_(['3', '4'])  & (Eval('voucher_type') == 'payment'),
        'readonly': In(Eval('state'), ['posted', 'canceled']),
    })
    plazo4 = fields.Integer('Dias', states={
        'invisible': Eval('no_pagos').in_(['','1', '2', '3']) | (Eval('voucher_type') != 'payment'),
        'required': Eval('no_pagos').in_(['4'])  & (Eval('voucher_type') == 'payment'),
        'readonly': In(Eval('state'), ['posted', 'canceled']),
    })

    recaudador = fields.Many2One('res.user', 'Recaudador',
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state', 'company'])

    @classmethod
    def __setup__(cls):
        super(AccountVoucher, cls).__setup__()
        cls._error_messages.update({
            'missing_pay_lines': 'You have to enter pay mode lines!',
            'delete_voucher': 'You can not delete a voucher that is posted!',
            'payment_advanced' :u'¿Desea generar un anticipo?',
        })
        cls._buttons.update({
                'post': {
                    'invisible': Eval('state') != 'draft',
                    },
                'cancel':{
                    'invisible': Eval('state') != 'posted',
                    },
                })
        cls._order.insert(0, ('date', 'DESC'))
        cls._order.insert(1, ('number', 'DESC'))

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_transfer():
        return False

    @staticmethod
    def default_no_pagos():
        return ''

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        company_id = Transaction().context.get('company')
        if company_id:
            return Company(company_id).currency.id

    @staticmethod
    def default_recaudador():
        User = Pool().get('res.user')
        user = User(Transaction().user)
        return user.id

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_journal():
        pool = Pool()
        Journal = pool.get('account.journal')
        journal = Journal.search([('type','=', 'expense')])
        journal_r = Journal.search([('type', '=', 'revenue')])
        voucher_type_id = Transaction().context.get('voucher_type')
        if voucher_type_id == 'receipt':
            for j in journal_r:
                return j.id

        if voucher_type_id == 'payment':
            for j in journal:
                return j.id

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @staticmethod
    def default_from_pay_invoice():
        return False

    def set_number(self):
        Sequence = Pool().get('ir.sequence')
        AccountVoucherSequence = Pool().get('account.voucher.sequence')
        AccountVoucherSequencePayment = Pool().get('account.voucher.sequence_payment')
        sequence_r = Sequence.search ([('code','=', 'account.voucher.receipt')])
        sequence_p = Sequence.search([('code', '=', 'account.voucher.payment')])
        for s in sequence_r:
            s_receipt = s
        for s in sequence_p:
            s_payment = s
        if self.voucher_type == 'receipt':
            sequence_r = AccountVoucherSequence(1)
            self.write([self], {'number': Sequence.get_id(
                s_receipt.id)})
        elif self.voucher_type == 'payment':
            sequence_p = AccountVoucherSequencePayment(1)
            self.write([self], {'number': Sequence.get_id(
                s_payment.id)})

    @fields.depends('party','lines', 'pay_lines', 'lines_credits', 'lines_debits')
    def on_change_with_amount(self, name=None):
        amount = Decimal('0.0')
        if self.pay_lines:
            for line in self.pay_lines:
                if line.pay_amount:
                    amount += line.pay_amount
        """
        if self.lines_credits:
            for line in self.lines_credits:
                if line.amount_original:
                    amount += line.amount_original
        if self.lines_debits:
            for line in self.lines_debits:
                if line.amount_original:
                    amount += line.amount_original
        """
        return amount

    @fields.depends('party', 'lines')
    def on_change_with_amount_to_pay(self, name=None):
        total = 0
        if self.lines:
            for line in self.lines:
                if line.to_pay == True:
                    total += line.amount_unreconciled or Decimal('0.00')
        return total

    @fields.depends('lines', 'pay_lines')
    def on_change_with_amount_invoices(self, name=None):
        total = 0
        if self.lines:
            for line in self.lines:
                total += line.amount or Decimal('0.00')
        return total

    @fields.depends('plazo1', 'plazo2', 'plazo3', 'plazo4', 'amount_to_pay',
    'lines', 'date', 'pay_lines', 'no_pagos')
    def on_change_plazo1(self):
        res = {}
        res['pay_lines'] = {}

        if self.pay_lines:
            res['pay_lines']['remove'] = [x['id'] for x in self.pay_lines]

        fecha = self.date
        date = self.date

        amount_unreconciled = Decimal(0.0)
        if self.lines:
            for line in self.lines:
                if line.to_pay == True:
                    date = line.date
        dias = timedelta(self.plazo1)

        fecha = date + dias
        if self.no_pagos == '1':
            payment_line = {
                'fecha': fecha,
                'pay_amount': self.amount_to_pay
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
        elif self.no_pagos == '2':
            payment_line = {
                'fecha': fecha,
                'pay_amount': self.amount_to_pay
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))

            if self.plazo2:
                valor = self.amount_to_pay/2
                dias2 = timedelta(self.plazo2)
                fecha2 = date + dias
                payment_line = {
                    'fecha': fecha,
                    'pay_amount': valor
                }
                res['pay_lines'].setdefault('add', []).append((0, payment_line))
                payment_line = {
                    'fecha': fecha2,
                    'pay_amount': valor
                }
                res['pay_lines'].setdefault('add', []).append((0, payment_line))
        elif self.no_pagos == '3':
            payment_line = {
                'fecha': fecha,
                'pay_amount': self.amount_to_pay
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            if self.plazo2 and self.plazo3:
                valor = self.amount_to_pay/3
                dias2 = timedelta(self.plazo2)
                fecha2 = date + dias2
                dias3= timedelta(self.plazo3)
                fecha3 = date + dias3

                payment_line = {
                    'fecha': fecha,
                    'pay_amount': valor
                }
                res['pay_lines'].setdefault('add', []).append((0, payment_line))
                payment_line = {
                    'fecha': fecha2,
                    'pay_amount': valor
                }
                res['pay_lines'].setdefault('add', []).append((0, payment_line))
                payment_line = {
                    'fecha': fecha3,
                    'pay_amount': valor
                }
                res['pay_lines'].setdefault('add', []).append((0, payment_line))
        elif self.no_pagos == '4':

            if self.plazo2 and self.plazo3 and self.plazo4:
                valor = self.amount_to_pay/4
                dias2 = timedelta(self.plazo2)
                fecha2 = date + dias2
                dias3= timedelta(self.plazo3)
                fecha3 = date + dias3
                dias4 = timedelta(self.plazo4)
                fecha4 = date + dias4

                payment_line = {
                    'fecha': fecha,
                    'pay_amount': valor
                }
                res['pay_lines'].setdefault('add', []).append((0, payment_line))
                payment_line = {
                    'fecha': fecha2,
                    'pay_amount': valor
                }
                res['pay_lines'].setdefault('add', []).append((0, payment_line))
                payment_line = {
                    'fecha': fecha3,
                    'pay_amount': valor
                }
                res['pay_lines'].setdefault('add', []).append((0, payment_line))
                payment_line = {
                    'fecha': fecha4,
                    'pay_amount': valor
                }
                res['pay_lines'].setdefault('add', []).append((0, payment_line))

        return res

    @fields.depends('plazo1', 'plazo2', 'plazo3', 'plazo4', 'amount_to_pay',
    'lines', 'date', 'pay_lines', 'no_pagos')
    def on_change_plazo2(self):
        res = {}
        res['pay_lines'] = {}
        if self.pay_lines:
            res['pay_lines']['remove'] = [x['id'] for x in self.pay_lines]

        fecha = self.date
        date = self.date

        amount_unreconciled = Decimal(0.0)
        if self.lines:
            for line in self.lines:
                if line.to_pay == True:
                    date = line.date

        dias = timedelta(self.plazo1)
        fecha = date + dias
        if self.no_pagos == '1':
            payment_line = {
                'fecha': fecha,
                'pay_amount': self.amount_to_pay
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
        elif self.no_pagos == '2':
            valor = self.amount_to_pay/2
            dias2 = timedelta(self.plazo2)
            fecha2 = date + dias2
            payment_line = {
                'fecha': fecha,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha2,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
        elif self.no_pagos == '3':
            valor = self.amount_to_pay/3
            dias2 = timedelta(self.plazo2)
            fecha2 = date + dias2
            dias3= timedelta(self.plazo3)
            fecha3 = date + dias3

            payment_line = {
                'fecha': fecha,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha2,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha3,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
        elif self.no_pagos == '4':
            valor = self.amount_to_pay/4
            dias2 = timedelta(self.plazo2)
            fecha2 = date + dias2
            dias3= timedelta(self.plazo3)
            fecha3 = date + dias3
            dias4 = timedelta(self.plazo4)
            fecha4 = date + dias4

            payment_line = {
                'fecha': fecha,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha2,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha3,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha4,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
        return res

    @fields.depends('plazo1', 'plazo2', 'plazo3', 'plazo4', 'amount_to_pay',
    'lines', 'date', 'pay_lines', 'no_pagos')
    def on_change_plazo3(self):
        res = {}
        res['pay_lines'] = {}
        if self.pay_lines:
            res['pay_lines']['remove'] = [x['id'] for x in self.pay_lines]

        fecha = self.date
        date = self.date

        amount_unreconciled = Decimal(0.0)
        if self.lines:
            for line in self.lines:
                if line.to_pay == True:
                    date = line.date

        dias = timedelta(self.plazo1)
        fecha = date + dias
        if self.no_pagos == '1':
            payment_line = {
                'fecha': fecha,
                'pay_amount': self.amount_to_pay
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
        elif self.no_pagos == '2':
            valor = self.amount_to_pay/2
            dias2 = timedelta(self.plazo2)
            fecha2 = date + dias
            payment_line = {
                'fecha': fecha,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha2,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
        elif self.no_pagos == '3':
            valor = self.amount_to_pay/3
            dias2 = timedelta(self.plazo2)
            fecha2 = date + dias2
            dias3= timedelta(self.plazo3)
            fecha3 = date + dias3

            payment_line = {
                'fecha': fecha,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha2,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha3,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
        elif self.no_pagos == '4':
            valor = self.amount_to_pay/4
            dias2 = timedelta(self.plazo2)
            fecha2 = date + dias2
            dias3= timedelta(self.plazo3)
            fecha3 = date + dias3
            dias4 = timedelta(self.plazo4)
            fecha4 = date + dias4

            payment_line = {
                'fecha': fecha,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha2,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha3,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha4,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
        return res

    @fields.depends('plazo1', 'plazo2', 'plazo3', 'plazo4', 'amount_to_pay',
    'lines', 'date', 'pay_lines', 'no_pagos')
    def on_change_plazo4(self):
        res = {}
        res['pay_lines'] = {}
        if self.pay_lines:
            res['pay_lines']['remove'] = [x['id'] for x in self.pay_lines]

        fecha = self.date
        date = self.date

        amount_unreconciled = Decimal(0.0)
        if self.lines:
            for line in self.lines:
                if line.to_pay == True:
                    date = line.date

        dias = timedelta(self.plazo1)
        fecha = date + dias
        if self.no_pagos == '1':
            payment_line = {
                'fecha': fecha,
                'pay_amount': self.amount_to_pay
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
        elif self.no_pagos == '2':
            valor = self.amount_to_pay/2
            dias2 = timedelta(self.plazo2)
            fecha2 = date + dias
            payment_line = {
                'fecha': fecha,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha2,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
        elif self.no_pagos == '3':
            valor = self.amount_to_pay/3
            dias2 = timedelta(self.plazo2)
            fecha2 = date + dias2
            dias3= timedelta(self.plazo3)
            fecha3 = date + dias3

            payment_line = {
                'fecha': fecha,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha2,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha3,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
        elif self.no_pagos == '4':
            valor = self.amount_to_pay/4
            dias2 = timedelta(self.plazo2)
            fecha2 = date + dias2
            dias3= timedelta(self.plazo3)
            fecha3 = date + dias3
            dias4 = timedelta(self.plazo4)
            fecha4 = date + dias4

            payment_line = {
                'fecha': fecha,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha2,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha3,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
            payment_line = {
                'fecha': fecha4,
                'pay_amount': valor
            }
            res['pay_lines'].setdefault('add', []).append((0, payment_line))
        return res

    @fields.depends('party', 'voucher_type', 'lines', 'lines_credits',
        'lines_debits', 'from_pay_invoice')
    def on_change_party(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        InvoiceAccountMoveLine = pool.get('account.invoice-account.move.line')
        description = None
        withholdings = None

        if self.from_pay_invoice:
            # The voucher was launched from Invoice's PayInvoice wizard:
            # 'lines', 'lines_credits', 'lines_debits' should be set there
            return {}

        res = {}
        res['lines'] = {}
        res['lines_credits'] = {}
        res['lines_debits'] = {}

        if self.lines:
            res['lines']['remove'] = [x['id'] for x in self.lines]
        if self.lines_credits:
            res['lines_credits']['remove'] = \
                [x['id'] for x in self.lines_credits]
        if self.lines_debits:
            res['lines_debits']['remove'] = \
                [x['id'] for x in self.lines_debits]

        if not self.party:
            return res

        if self.voucher_type == 'receipt':
            account_types = ['receivable']
        else:
            res['description'] = "PAGO DE FACTURA "+self.party.name
            account_types = ['payable']
        move_lines = MoveLine.search([
            ('party', '=', self.party),
            ('account.kind', 'in', account_types),
            ('state', '=', 'valid'),
            ('reconciliation', '=', None),
        ])
        for line in move_lines:
            monto_anticipos = Decimal(0.0)
            monto_comprobante = Decimal(0.0)
            monto_retenciones = Decimal(0.0)
            invoice = InvoiceAccountMoveLine.search([
                ('line', '=', line.id),
            ])
            if invoice:
                continue

            if line.credit:
                line_type = 'cr'
                amount = line.credit
            else:
                amount = line.debit
                line_type = 'dr'

            name = ''
            model = str(line.origin)
            if model[:model.find(',')] == 'account.invoice':
                name = Invoice(line.origin.id).number
                description = Invoice(line.origin.id).description
            if self.voucher_type == "receipt":
                if description:
                    move_voucher = Move.search([('description', '=', description)])
                    if move_voucher:
                        for voucher in move_voucher:
                            for line_v in voucher.lines:
                                if line_v.reconciliation == None and line_v.credit > Decimal(0.0) and line_v.party == self.party:
                                    if "withholding" in str(move_line.origin):
                                        pass
                                    else:
                                        monto_anticipos += line_v.credit
                        move_lines = MoveLine.search([('reconciliation', '=', None),('party', '=', self.party), ('account', '=', self.party.account_receivable)])
                        for move_line in move_lines:
                            if move_line.credit > Decimal(0.0):
                                if  "voucher" in str(move_line.origin):
                                    if move_line.description == name:
                                        monto_anticipos += move_line.credit
                                if "withholding" in str(move_line.origin):
                                    pass
                    else:
                        move_lines = MoveLine.search([('reconciliation', '=', None),('party', '=', self.party), ('account', '=', self.party.account_receivable)])

                        for move_line in move_lines:
                            if move_line.credit > Decimal(0.0):
                                if  "voucher" in str(move_line.origin):
                                    if move_line.description == name:
                                        monto_anticipos += move_line.credit
                                if "withholding" in str(move_line.origin):
                                    pass
                                """
                                Check advanced_payment
                                else:
                                    monto_anticipos += move_line.credit
                                """

                if name:
                    Withholding = pool.get('account.withholding')
                    withholdings = Withholding.search([('number_w', '=', name), ('state', '=','posted')])
                    if withholdings:
                        for withholding in withholdings:
                            for line_w in withholding.move.lines:
                                if line_w.reconciliation == None and line_w.credit > Decimal(0.0) and line_w.party  == self.party:
                                    monto_retenciones += line_w.credit
                    MoveLine = pool.get('account.move.line')
                    movelines = MoveLine.search([('description', '=', name), ('party', '=', self.party), ('credit', '>', 0), ('reconciliation', '=', None)])
                    if movelines:
                        for moveline in movelines:
                            monto_comprobante += moveline.credit

            else:
                lines_payments = MoveLine.search([('description', '=', name), ('reconciliation', '=', None), ('party', '=', self.party), ('debit', '>', 0)])
                if lines_payments:
                    for line_payment in lines_payments:
                        monto_anticipos += line_payment.debit

            if self.voucher_type == 'receipt':
                new_amount = line.debit
            else:
                new_amount = line.credit

            payment_line = {
                'name': name,
                'account': line.account.id,
                'amount': Decimal('0.00'),
                'amount_original': amount,
                'amount_unreconciled': abs((new_amount)-(monto_anticipos+monto_retenciones+monto_comprobante)),#abs(line.credit) - (monto_anticipos + monto_retenciones)
                'line_type': line_type,
                'move_line': line.id,
                'date': line.date,
                'date_expire': line.maturity_date,
            }
            if line.credit and self.voucher_type == 'receipt':
                res['lines_credits'].setdefault('add', []).append((0,
                    payment_line))
            elif line.debit and self.voucher_type == 'payment':
                res['lines_debits'].setdefault('add', []).append((0,
                    payment_line))
            else:
                res['lines'].setdefault('add', []).append((0, payment_line))
        return res

    @classmethod
    def delete(cls, vouchers):
        if not vouchers:
            return True
        for voucher in vouchers:
            if voucher.state == 'posted':
                cls.raise_user_error('delete_voucher')
        return super(AccountVoucher, cls).delete(vouchers)

    def create_cancel_move(self):
        pool = Pool()
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        Period = pool.get('account.period')
        Reconciliation = pool.get('account.move.reconciliation')
        Invoice = pool.get('account.invoice')
        Date = pool.get('ir.date')

        canceled_date = Date.today()
        canceled_move, = Move.copy([self.move], {
                'period': Period.find(self.company.id, date=canceled_date),
                'date': canceled_date,
            })
        self.write([self], {
                'move_canceled': canceled_move.id,
                })

        for line in canceled_move.lines:
            aux = line.debit
            line.debit = line.credit
            line.credit = aux
            line.save()

        Move.post([self.move_canceled])

        reconciliations = [x.reconciliation for x in self.move.lines
                            if x.reconciliation]
        with Transaction().set_user(0, set_context=True):
            if reconciliations:
                Reconciliation.delete(reconciliations)
        for line in self.lines:
            origin = str(line.move_line.origin)
            origin = origin[:origin.find(',')]
            if origin not in ['account.invoice',
                    'account.voucher']:
                continue
            if line.amount == Decimal("0.00"):
                continue
            invoice = Invoice(line.move_line.origin.id)
            for move_line in self.move_canceled.lines:
                if move_line.description == 'advance':
                    continue
                if move_line.description == invoice.number:
                    Invoice.write([invoice], {
                        'payment_lines': [('add', [move_line.id])],
                        })
        lines_to_reconcile = []
        for line in self.move.lines:
            if line.account.reconcile:
                #if line.reconciliations != None:
                lines_to_reconcile.append(line)
        for cancel_line in canceled_move.lines:
            if cancel_line.account.reconcile:
                lines_to_reconcile.append(cancel_line)
        if lines_to_reconcile:
            MoveLine.reconcile(lines_to_reconcile)
        return True

    def prepare_move_lines(self):
        pool = Pool()
        Period = pool.get('account.period')
        Move = pool.get('account.move')
        Invoice = pool.get('account.invoice')
        Sale = pool.get('sale.sale')
        original = Decimal(0.0)
        unreconcilied = Decimal(0.0)
        paid_amount = Decimal(0.0)
        residual_amount = Decimal(0.0)
        name = None
        invoice_d = None
        # Check amount
        if not self.amount > Decimal("0.0"):
            self.raise_user_error('missing_pay_lines')

        move_lines = []
        line_move_ids = []
        move, = Move.create([{
            'period': Period.find(self.company.id, date=self.date),
            'journal': self.journal.id,
            'date': self.date,
            'origin': str(self),
            'description':self.description,
        }])
        self.write([self], {
                'move': move.id,
                })

        #verificar saldo para dejar como anticipo
        total = self.amount
        if self.lines:
            for line in self.lines:
                if line.to_pay == True:
                    if not line.amount:
                        continue
                    total -= line.amount

        #
        # Pay Modes
        #
        cont = 1
        if self.pay_lines:
            for line in self.pay_lines:
                if cont == len(self.pay_lines) and total > Decimal('0.00'):
                    if self.voucher_type == 'receipt':
                        debit = line.pay_amount - total
                        credit = Decimal('0.0')
                        account = line.pay_mode.account.id
                        account_advanced_new =  line.pay_mode.account

                else:
                    if self.voucher_type == 'receipt':
                        debit = line.pay_amount
                        credit = Decimal('0.0')
                        if line.banco:
                            account = line.banco.account_expense.id
                        else:
                            account = line.pay_mode.account.id

                    else:
                        debit = Decimal('0.0')
                        credit = line.pay_amount
                        if line.banco:
                            account = line.banco.account_expense.id
                        else:
                            account = line.pay_mode.account.id

                move_lines.append({
                    'debit': debit,
                    'credit': credit,
                    'account': account,
                    'move': move.id,
                    'journal': self.journal.id,
                    'period': Period.find(self.company.id, date=self.date),
                })
                cont += 1
        #
        # Credits
        #
        """
        if self.lines_credits:
            for line in self.lines_credits:
                debit = line.amount_original
                credit = Decimal('0.0')
                move_lines.append({
                    'description': 'advance',
                    'debit': debit,
                    'credit': credit,
                    'account': line.account.id,
                    'move': move.id,
                    'journal': self.journal.id,
                    'period': Period.find(self.company.id, date=self.date),
                    'party': self.party.id,
                })

        #
        # Debits
        #
        if self.lines_debits:
            for line in self.lines_debits:
                debit = Decimal('0.0')
                credit = line.amount_original
                move_lines.append({
                    'description': 'advance',
                    'debit': debit,
                    'credit': credit,
                    'account': line.account.id,
                    'move': move.id,
                    'journal': self.journal.id,
                    'period': Period.find(self.company.id, date=self.date),
                    'party': self.party.id,
                })
        """
        #
        # Voucher Lines
        #
        if self.lines:
            for line in self.lines:
                if line.to_pay == True:
                    if not line.amount:
                        continue
                    line_move_ids.append(line.move_line)
                    if self.voucher_type == 'receipt':
                        debit = Decimal('0.00')
                        credit = line.amount
                    else:
                        debit = line.amount
                        credit = Decimal('0.00')
                    move_lines.append({
                        'description': Invoice(line.move_line.origin.id).number,
                        'debit': debit,
                        'credit': credit,
                        'account': line.account.id,
                        'move': move.id,
                        'journal': self.journal.id,
                        'period': Period.find(self.company.id, date=self.date),
                        'party': self.party.id,
                    })

        if total != Decimal('0.00'):
            #crear anticipo y asientos de anticipo
            if self.voucher_type == 'receipt':
                Advanced = pool.get('sale.advanced')
                advanced_new = Advanced()

                Configuration = pool.get('account.configuration')

                if Configuration(1).default_account_e == account_advanced_new:
                    pay = "efectivo"
                elif Configuration(1).default_account_c == account_advanced_new:
                    pay = "cheque"
                elif Configuration(1).default_account_t == account_advanced_new:
                    pay = "transferencia"
                elif Configuration(1).default_account_t_c == account_advanced_new:
                    pay = "tarjeta"
                elif Configuration(1).default_account_d == account_advanced_new:
                    pay = "deposito"
                elif Configuration(1).default_account_wf == account_advanced_new:
                    pay = "fuente"
                elif Configuration(1).default_account_wi ==account_advanced_new:
                    pay = "iva"
                else:
                    pay = "efectivo"

                advanced_new.amount = total
                advanced_new.party = self.party
                advanced_new.date = self.date
                advanced_new.pay = pay
                advanced_new.comment = "Diferencia de Pago"
                advanced_new.save()
                advanced_new.prepare_move_lines()
                advanced_new.set_number()

        return move_lines


    def create_move(self, move_lines):
        pool = Pool()
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        Invoice = pool.get('account.invoice')
        created_lines = MoveLine.create(move_lines)
        Move.post([self.move])
        Sale = pool.get('sale.sale')
        sale = None
        invoice_d = None
        sales = None
        lines_payments = None
        name = None
        invoice = None
        withholdings = None

        for line in self.lines:
            if line.to_pay == True:
                original = line.amount_original
                unreconciled = line.amount_unreconciled
                name = line.name
        if name != None:
            invoice = Invoice.search([('number', '=', name), ('description', '!=', None)])
        if invoice:
            for i in invoice:
                invoice_d = i.description
        if invoice_d != None:
            sales = Sale.search([('reference', '=', invoice_d)])

        if sales:
            for s in sales:
                sale = s
            paid_amount = Decimal(original - unreconciled)
            residual_amount = Decimal(unreconciled)
            sale.get_residual_amount([sale], ['residual_amount'])
            sale.get_paid_amount([sale], ['paid_amount'])

        # reconcile check
        for line in self.lines:
            if line.to_pay == True:
                if line.amount == Decimal("0.00"):
                    continue
                invoice = Invoice(line.move_line.origin.id)

                monto_anticipos = Decimal(0.0)
                monto_retenciones = Decimal(0.0)
                monto_comprobante = Decimal(0.0)

                move_voucher = Move.search([('description', '!=', None)])

                if self.voucher_type == 'receipt':

                    if move_voucher:
                        for voucher in move_voucher:
                            for line_v in voucher.lines:
                                if sale:
                                    description_line = 'used'+str(sale.reference)

                                    if line_v.reconciliation == None and line_v.credit > Decimal(0.0) and line_v.party == self.party and line_v.description == description_line:
                                        monto_anticipos += line_v.credit
                                    """
                                    if line_v.reconciliation == None and line_v.credit > Decimal(0.0) and line_v.party == self.party and line_v.description == None:
                                        monto_anticipos += line_v.credit
                                    """

                    if line.name:
                        Withholding = pool.get('account.withholding')
                        withholdings = Withholding.search([('number_w', '=', line.name), ('type', '=', 'out_withholding')])
                        if withholdings:
                            for withholding in withholdings:
                                for line_w in withholding.move.lines:
                                    if line_w.reconciliation == None and line_w.credit > Decimal(0.0) and line_w.party  == self.party:
                                        monto_retenciones += line_w.credit

                        MoveLine = pool.get('account.move.line')
                        movelines = MoveLine.search([('description', '=', name), ('party', '=', self.party), ('credit', '>', 0), ('reconciliation', '=', None)])
                        if movelines:
                            for moveline in movelines:
                                monto_comprobante += moveline.credit

                else:
                    lines_payments = MoveLine.search([('description', '=', line.name), ('reconciliation', '=', None), ('party', '=', self.party), ('debit', '>', 0)])
                    if lines_payments:
                        for line_payment in lines_payments:
                            monto_anticipos += line_payment.debit

                if self.voucher_type == 'receipt':
                    amount = line.amount + monto_anticipos + monto_retenciones + monto_comprobante
                else:
                    amount = -(line.amount)
                reconcile_lines, remainder = \
                    Invoice.get_reconcile_lines_for_amount(
                        invoice, amount)

                if lines_payments:
                    for line_pay_ in lines_payments:
                        reconcile_lines.append(line_pay_ )


                move_voucher = Move.search([('description', '!=', None)])
                if move_voucher:
                    for voucher in move_voucher:
                        if self.voucher_type == 'receipt':

                            for line_v in voucher.lines:
                                """
                                if line_v.reconciliation == None and line_v.credit > Decimal(0.0) and  line_v.party == self.party and line_v.description == None:
                                    line_v.state = 'valid'
                                    line_v.save()
                                    reconcile_lines.append(line_v)
                                """
                                if sale:
                                    description_line = 'used'+str(sale.reference)
                                    if line_v.reconciliation == None and line_v.credit > Decimal(0.0) and  line_v.party == self.party and line_v.description == description_line:
                                        line_v.state = 'valid'
                                        line_v.save()
                                        reconcile_lines.append(line_v)

                else:
                    move_lines = MoveLine.search([('reconciliation', '=', None),('party', '=', self.party), ('account', '=', self.party.account_receivable)])
                    for move_l in move_lines:
                        if move_l.credit > Decimal(0.0):
                            move_l.state = 'valid'
                            move_l.save()
                            reconcile_lines.append(move_l)

                if line.name:
                    if withholdings:
                        for withholding in withholdings:
                            for line_w in withholding.move.lines:
                                if line_w.reconciliation == None and line_w.credit > Decimal(0.0) and line_w.party  == self.party:
                                    line_w.state = 'valid'
                                    line_w.save()
                                    reconcile_lines.append(line_w)

                    MoveLine = pool.get('account.move.line')
                    movelines = MoveLine.search([('description', '=', name), ('party', '=', self.party), ('credit', '>', 0), ('reconciliation', '=', None)])
                    if movelines:
                        for moveline in movelines:
                            reconcile_lines.append(moveline)


                for move_line in created_lines:
                    if move_line.description == 'advance':
                        continue
                    if move_line.description == invoice.number:
                        move_line.state = 'valid'
                        move_line.save()
                        reconcile_lines.append(move_line)
                        Invoice.write([invoice], {
                            'payment_lines': [('add', [move_line.id])],
                        })

                #print "remainder", remainder
                #print "reconcile_lines", reconcile_lines
                #print "Mal ", mal
                if remainder == Decimal('0.00'):
                    MoveLine.reconcile(reconcile_lines)
        return True

    def prepare_postdated_lines(self):
        pool = Pool()
        Period = pool.get('account.period')
        Move = pool.get('account.move')
        Invoice = pool.get('account.invoice')

        postdated_lines = None

        if self.pay_lines:
            for line in self.pay_lines:
                if line.pay_mode.account.name == 'EFECTOS DE COBRO INMEDIATO (CHEQUES)':
                    postdated_lines = []
                    postdated_lines.append({
                    'reference': line.voucher.move,
                    'name': line.voucher.number,
                    'amount': line.pay_amount,
                    'account': line.pay_mode.account.id,
                    'date_expire': line.fecha,
                    'date': self.date,
                    'num_check' : line.numero_doc,
                    'num_account' : line.cuenta_tercero,
                })

        return postdated_lines

    def create_postdated_check(self, postdated_lines):
        pool = Pool()
        Postdated = pool.get('account.postdated')
        PostdatedLine = pool.get('account.postdated.line')
        postdated = Postdated()
        if postdated_lines != None:
            for line in postdated_lines:
                date = line['date']
                postdated.postdated_type = 'check'
                postdated.party = self.party
                postdated.post_check_type = 'receipt'
                postdated.journal = 1
                postdated.lines = postdated_lines
                postdated.state = 'draft'
                postdated.date = date
                postdated.save()

    def prepare_bank_reconciliation(self):
        pool = Pool()
        Reconciled = pool.get('account.reconciliation')
        AllReconciled = pool.get('account.reconciliation_all')
        Bank = pool.get('bank')
        reconciled = Reconciled()
        allreconciled = AllReconciled()
        amount_total = Decimal(0.0)

        if self.pay_lines:
            for line in self.pay_lines:
                account = line.banco.account_expense.id
                banks = Bank.search([('account_expense', '=', account)])
                if banks:
                    for bank in banks:
                        if bank.nro_cuenta_bancaria:
                            nro_cuenta_bancaria = bank.nro_cuenta_bancaria
                        else:
                            self.raise_user_error('Configure el numero de cuenta bancaria')
                        if bank.party.name:
                            name_bank = bank.party.name
                        else:
                            self.raise_user_error('Configure el nombre del Banco')
                else:
                    self.raise_user_error('Configure los datos del Banco')

                all_rs = AllReconciled.search([('account_bank', '=', nro_cuenta_bancaria)])

                if all_rs:
                    for a_r in all_rs:
                        allreconciled = a_r
                else:
                    allreconciled.name_bank = name_bank
                    allreconciled.account_bank = nro_cuenta_bancaria
                    allreconciled.save()
                if line.pay_mode.account.name == 'EFECTOS DE COBRO INMEDIATO (CHEQUES)':
                    amount_total += line.pay_amount
                    reconciled.bank_account_ref = allreconciled.id
                    reconciled.amount = line.pay_amount
                    reconciled.conciliar = False
                    reconciled.account = line.banco.account_expense.id
                    reconciled.state = 'draft'
                    reconciled.date = self.date
                    reconciled.expired = line.fecha
                    reconciled.party = self.party
                    reconciled.ch_num = line.numero_doc
                    reconciled.bank_account = line.banco.nro_cuenta_bancaria
                    reconciled.save()

                allreconciled.libro_debito = allreconciled.libro_debito  + amount_total
                allreconciled.libro_balance = (allreconciled.libro_inicial + allreconciled.libro_credito)-allreconciled.libro_debito
                allreconciled.save()


    def get_value_lines(self):
        amount_invoice = self.amount
        if self.lines:
            res = {}
            for line in self.lines:
                if line.to_pay == True:
                    if line.amount_unreconciled < amount_invoice:
                        value = Decimal('0.0')
                        amount_invoice -= line.amount_unreconciled
                        line.write([line],{ 'amount': line.amount_unreconciled})
                        line.write([line],{ 'amount_unreconciled': value})

                    if line.amount_unreconciled >= amount_invoice:
                        value = line.amount_unreconciled - amount_invoice
                        line.write([line],{ 'amount': amount_invoice})
                        line.write([line],{ 'amount_unreconciled': value})
                        amount_invoice = Decimal('0.0')

            if amount_invoice != 0:
                warning_name = u'Tiene un excedente ¿Desea generar un anticipo?'
                self.raise_user_warning(warning_name, 'payment_advanced')


    def get_amount2words(self, value):
            if conversor:
                return (conversor.cardinal(int(value))).upper()
            else:
                return ''

    def get_toWords(self):
        if self.lines:
            amount = Decimal('0.0')
            for line in self.lines:
                if line.to_pay == True:
                    amount += line.amount
                    value_words = self.get_amount2words(amount)
                    self.write([self],{ 'amount_to_pay_words': value_words})
        else:
            if self.amount > Decimal('0.0'):
                value_words = self.get_amount2words(self.amount)
                self.write([self], {'amount_to_pay_words': value_words})

    @classmethod
    @ModelView.button
    def post(cls, vouchers):
        pool = Pool()
        module = None
        Module = pool.get('ir.module.module')
        module = Module.search([('name', '=', 'nodux_account_postdated_check'), ('state', '=', 'installed')])
        module_bank = Module.search([('name','=','nodux_account_bank_reconcilation'), ('state', '=', 'installed')])
        Banco = pool.get('bank')

        for voucher in vouchers:
            if voucher.voucher_type == 'payment':
                if module_bank:
                    voucher.prepare_bank_reconciliation()
                    for line in voucher.pay_lines:
                        if line.numero_doc:
                            numero = int(line.numero_doc[2:])
                            bancos = Banco.search([('id', '=', line.banco.id)])
                            for banco in bancos:
                                numero_actual = banco.nro_documento
                                banco.nro_documento = numero + 1
                                banco.save()

            voucher.get_value_lines()
            voucher.get_toWords()
            voucher.set_number()
            move_lines = voucher.prepare_move_lines()
            voucher.create_move(move_lines)
            if module and (voucher.voucher_type == 'receipt'):
                postdated_lines = voucher.prepare_postdated_lines()
                voucher.create_postdated_check(postdated_lines)
            voucher.set_number()
        cls.write(vouchers, {'state': 'posted'})

    @classmethod
    @ModelView.button
    def cancel(cls, vouchers):
        for voucher in vouchers:
            voucher.create_cancel_move()
        cls.write(vouchers, {'state': 'canceled'})

class AccountVoucherLine(ModelSQL, ModelView):
    'Account Voucher Line'
    __name__ = 'account.voucher.line'

    voucher = fields.Many2One('account.voucher', 'Voucher')
    reference = fields.Function(fields.Char('reference',),
        'get_reference')
    name = fields.Char('Name')
    account = fields.Many2One('account.account', 'Account')
    amount = fields.Numeric('Amount', digits=(16, 2))
    line_type = fields.Selection([
        ('cr', 'Credit'),
        ('dr', 'Debit'),
        ], 'Type', select=True)
    move_line = fields.Many2One('account.move.line', 'Move Line')
    amount_original = fields.Numeric('Original Amount', digits=(16, 2))
    amount_unreconciled = fields.Numeric('Unreconciled amount', digits=(16, 2))
    date = fields.Date('Date')
    date_expire = fields.Function(fields.Date('Expire date'),
            'get_expire_date')

    to_pay = fields.Boolean('To pay')

    def get_reference(self, name):
        Invoice = Pool().get('account.invoice')

        if self.move_line.move:
            invoices = Invoice.search(
                [('move', '=', self.move_line.move.id)])
            if invoices:
                return invoices[0].reference

    def get_expire_date(self, name):
        res = self.move_line.maturity_date
        return res


class AccountVoucherLineCredits(ModelSQL, ModelView):
    'Account Voucher Line Credits'
    __name__ = 'account.voucher.line.credits'

    voucher = fields.Many2One('account.voucher', 'Voucher')
    name = fields.Char('Name')
    account = fields.Many2One('account.account', 'Account')
    amount = fields.Numeric('Amount', digits=(16, 2))
    line_type = fields.Selection([
        ('cr', 'Credit'),
        ('dr', 'Debit'),
        ], 'Type', select=True)
    move_line = fields.Many2One('account.move.line', 'Move Line')
    amount_original = fields.Numeric('Original Amount', digits=(16, 2))
    amount_unreconciled = fields.Numeric('Unreconciled amount', digits=(16, 2))
    date = fields.Date('Date')


class AccountVoucherLineDebits(ModelSQL, ModelView):
    'Account Voucher Line Debits'
    __name__ = 'account.voucher.line.debits'

    voucher = fields.Many2One('account.voucher', 'Voucher')
    name = fields.Char('Name')
    account = fields.Many2One('account.account', 'Account')
    amount = fields.Numeric('Amount', digits=(16, 2))
    line_type = fields.Selection([
        ('cr', 'Credit'),
        ('dr', 'Debit'),
        ], 'Type', select=True)
    move_line = fields.Many2One('account.move.line', 'Move Line')
    amount_original = fields.Numeric('Original Amount', digits=(16, 2))
    amount_unreconciled = fields.Numeric('Unreconciled amount', digits=(16, 2))
    date = fields.Date('Date')


class AccountVoucherLinePaymode(ModelSQL, ModelView):
    'Account Voucher Line Pay Mode'
    __name__ = 'account.voucher.line.paymode'

    voucher = fields.Many2One('account.voucher', 'Voucher', ondelete='CASCADE',
        select=True)
    pay_mode = fields.Many2One('account.voucher.paymode', 'Pay Mode',
        required=True, states=_STATES)
    pay_amount = fields.Numeric('Pay Amount', digits=(16, 2), required=True,
        states=_STATES)
    banco = fields.Many2One('bank', 'Banco')
    cuenta_tercero = fields.Char(u'Numero de Cuenta')
    numero_doc = fields.Char(u'Numero de Documento')
    titular_cuenta = fields.Char(u'Titular de la cuenta')
    fecha = fields.Date('Fecha de cheque')

    @classmethod
    def __setup__(cls):
        super(AccountVoucherLinePaymode, cls).__setup__()

    @fields.depends('_parent_voucher.party', '_parent_voucher.voucher_type', '_parent_voucher.company', 'pay_mode')
    def on_change_pay_mode(self):
        result = {}
        if self.voucher:
            if self.pay_mode:
                name_mode = self.pay_mode.name
                name = name_mode.lower()
                if 'cheque' in name:
                    if self.voucher.voucher_type == 'receipt':
                        if self.voucher.party:
                            titular_cuenta = self.voucher.party.name
                        else:
                            titular_cuenta = ""
                        result['titular_cuenta'] = titular_cuenta
                    else:
                        if self.voucher.company:
                            result['titular_cuenta'] = self.voucher.company.party.name
                        else:
                            result['titular_cuenta'] = ""
        else:
            titular_cuenta = ""
            result['titular_cuenta'] = titular_cuenta

        return result

    @fields.depends('_parent_voucher.party','pay_mode', 'banco')
    def on_change_banco(self):
        result = {}
        Account = Pool().get('account.account')
        accounts = Account.search([('kind', '=', 'other')])
        PayMode = Pool().get('account.voucher.paymode')

        if self.voucher:
            if self.pay_mode:
                default = self.pay_mode.account.id
                paymode= PayMode(self.pay_mode)
                if self.banco:
                    result['cuenta_tercero'] = self.banco.nro_cuenta_bancaria
                    result['numero_doc'] = '00'+str(self.banco.nro_documento)
                    name = paymode.name.lower()
                    if ('deposito' in name) or (u'depósito' in name) or ('transferencia' in name):
                        if self.banco.account_expense:
                            banco = self.banco.account_expense.id
                        else:
                            self.raise_user_error('No ha configurado la cuenta contable de Bancos')
                        result['paymode.account'] = banco
                    else:
                        result['paymode.account'] = default
        return result

class VoucherReport(Report):
    'Voucher Report'
    __name__ = 'account.voucher.report'

    @classmethod
    def parse(cls, report, objects, data, localcontext=None):
        Company = Pool().get('company.company')
        company_id = Transaction().context.get('company')
        company = Company(company_id)
        for obj in objects:
            d = str(obj.amount)
            decimales = d[-2:]
            if decimales[0] == '.':
                 decimales = decimales[1]+'0'

        if company.timezone:
            timezone = pytz.timezone(company.timezone)
            dt = datetime.now()
            hora = datetime.astimezone(dt.replace(tzinfo=pytz.utc), timezone)

        localcontext['company'] = company
        localcontext['decimales'] = decimales
        localcontext['hora'] = hora.strftime('%H:%M:%S')
        localcontext['fecha'] = hora.strftime('%d/%m/%Y')
        localcontext['transfer'] = 'false'

        new_objs = []
        for obj in objects:
            if obj.amount_to_pay and conversor and not obj.amount_to_pay_words:
                obj.amount_to_pay_words = obj.get_amount2words(obj.amount_to_pay)
            new_objs.append(obj)
        return super(VoucherReport, cls).parse(report,
                new_objs, data, localcontext)

class PrintMove(CompanyReport):
    'Print Move'
    __name__ = 'account.voucher.print_move'

    @classmethod
    def __setup__(cls):
        super(PrintMove, cls).__setup__()

    @classmethod
    def parse(cls, report, objects, data, localcontext=None):
        pool = Pool()
        Move = pool.get('account.move')
        sum_debit = Decimal('0.0')
        sum_credit = Decimal('0.0')
        invoice = Transaction().context.get('move')
        for invoice in objects:
            for line in invoice.move.lines:
                sum_debit += line.debit
                sum_credit += line.credit

        localcontext['company'] = Transaction().context.get('company')
        localcontext['move'] = Transaction().context.get('company')
        localcontext['invoice'] = Transaction().context.get('voucher')
        localcontext['sum_debit'] = sum_debit
        localcontext['sum_credit'] = sum_credit

        return super(PrintMove, cls).parse(report,
                objects, data, localcontext)

class PrintCheck(Report):
    'Print Check'
    __name__ = 'account.voucher.print_check'

    @classmethod
    def parse(cls, report, objects, data, localcontext=None):
        Company = Pool().get('company.company')
        company_id = Transaction().context.get('company')
        company = Company(company_id)
        for obj in objects:
            d = str(obj.amount)
            decimales = d[-2:]
            if decimales[0] == '.':
                 decimales = decimales[1]+'0'

        if company.timezone:
            timezone = pytz.timezone(company.timezone)
            dt = datetime.now()
            hora = datetime.astimezone(dt.replace(tzinfo=pytz.utc), timezone)

        localcontext['company'] = company
        localcontext['decimales'] = decimales
        localcontext['hora'] = hora.strftime('%H:%M:%S')
        localcontext['fecha'] = hora.strftime('%d/%m/%Y')

        new_objs = []
        for obj in objects:
            if obj.amount_to_pay and conversor and not obj.amount_to_pay_words:
                obj.amount_to_pay_words = obj.get_amount2words(obj.amount_to_pay)
            new_objs.append(obj)
        return super(PrintCheck, cls).parse(report,
                new_objs, data, localcontext)

class CancelVoucherStart(ModelView):
    'Cancel Voucher Start'
    __name__ = 'account.voucher.cancel_voucher.start'


class CancelVoucher(Wizard):
    'Cancel Voucher'
    __name__ = 'account.voucher.cancel_voucher'
    start = StateView('account.voucher.cancel_voucher.start',
        'nodux_account_voucher_ec.cancel_voucher_start_view_form', [
            Button('Exit', 'end', 'tryton-cancel'),
            Button('Ok', 'cancel_', 'tryton-ok', default=True),
            ])

    cancel_ = StateAction('nodux_account_voucher_ec.act_voucher_form')

    def do_cancel_(self, action):
        pool = Pool()
        Voucher = pool.get('account.voucher')
        vouchers = Voucher.browse(Transaction().context['active_ids'])
        for voucher in vouchers:
            voucher.create_cancel_move()
            voucher.state = 'canceled'
            voucher.save()
