# -*- coding: utf-8 -*-
#This file is part of the nodux_account_voucher_ec module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelSingleton, ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pyson import Eval, In
from trytond.pool import Pool
from trytond.report import Report
import pytz
from datetime import datetime,timedelta
import time

conversor = None
try:
    from numword import numword_es
    conversor = numword_es.NumWordES()
except:
    print("Warning: Does not possible import numword module!")
    print("Please install it...!")
    

__all__ = ['AccountVoucherSequence', 'AccountVoucherPayMode', 'AccountVoucher',
    'AccountVoucherLine', 'AccountVoucherLineCredits',
    'AccountVoucherLineDebits', 'AccountVoucherLinePaymode', 'VoucherReport']

_STATES = {
    'readonly': In(Eval('state'), ['posted']),
}

class AccountVoucherSequence(ModelSingleton, ModelSQL, ModelView):
    'Account Voucher Sequence'
    __name__ = 'account.voucher.sequence'

    voucher_sequence = fields.Property(fields.Many2One('ir.sequence',
        'Voucher Sequence', required=True,
        domain=[('code', '=', 'account.voucher')]))


class AccountVoucherPayMode(ModelSQL, ModelView):
    'Forma de Pago'
    __name__ = 'account.voucher.paymode'

    name = fields.Char('Name')
    account = fields.Many2One('account.account', 'Account')


class AccountVoucher(ModelSQL, ModelView):
    'Account Voucher'
    __name__ = 'account.voucher'
    _rec_name = 'number'

    number = fields.Char('Number', readonly=True, help="Voucher Number")
    party = fields.Many2One('party.party', 'Party', required=True,
        states=_STATES)
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
            })
    lines_debits = fields.One2Many('account.voucher.line.debits', 'voucher',
        'Debits', states={
            'invisible': ~Eval('lines_debits'),
            })
    comment = fields.Text('Comment', states=_STATES)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ], 'State', select=True, readonly=True)
    amount = fields.Function(fields.Numeric('Payment', digits=(16, 2)),
        'on_change_with_amount')
    amount_to_pay = fields.Function(fields.Numeric('To Pay', digits=(16, 2)),
        'on_change_with_amount_to_pay')
    amount_invoices = fields.Function(fields.Numeric('Invoices',
        digits=(16, 2)), 'on_change_with_amount_invoices')
    move = fields.Many2One('account.move', 'Move', readonly=True)
    from_pay_invoice = fields.Boolean('Voucher launched from Pay invoice')
    amount_to_pay_words = fields.Char('Amount to Pay (Words)',
            states={'readonly': True})
            
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
                    'invisible': Eval('state') == 'posted',
                    },
                })
        cls._order.insert(0, ('date', 'DESC'))
        cls._order.insert(1, ('number', 'DESC'))


    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        company_id = Transaction().context.get('company')
        if company_id:
            return Company(company_id).currency.id

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

        sequence = AccountVoucherSequence(1)
        self.write([self], {'number': Sequence.get_id(
            sequence.voucher_sequence.id)})
    
    @fields.depends('party','lines', 'pay_lines', 'lines_credits', 'lines_debits')
    def on_change_with_amount(self, name=None):
        amount = Decimal('0.0')
        if self.pay_lines:
            for line in self.pay_lines:
                if line.pay_amount:
                    amount += line.pay_amount
        if self.lines_credits:
            for line in self.lines_credits:
                if line.amount_original:
                    amount += line.amount_original
        if self.lines_debits:
            for line in self.lines_debits:
                if line.amount_original:
                    amount += line.amount_original
        return amount

    @fields.depends('party', 'lines')
    def on_change_with_amount_to_pay(self, name=None):
        total = 0
        if self.lines:
            for line in self.lines:
                total += line.amount_unreconciled or Decimal('0.00')
        return total
    
    """    
    @fields.depends('pay_lines','party')
    def on_change_pay_lines(self):
        res= {}
        res['pay_lines']={}
        
        if self.party:
            name = self.party.name
            
        
        if self.pay_lines:
            for p_l in self.pay_lines:
                print "La linea de pago ",p_l
                if p_l.banco:
                    result = {
                        'pay_mode':p_l.pay_mode,
                        'pay_amount':p_l.pay_amount,
                        'banco':p_l.banco,
                        'titular_cuenta': name,
                         } 
                    res['pay_lines'].setdefault('add', []).append((0, result))
                       
        print "LO QUE SE VA A AGREGAR ", res
        
        return res
    """    
    @fields.depends('lines', 'pay_lines')
    def on_change_with_amount_invoices(self, name=None):
        total = 0
        if self.lines:
            for line in self.lines:
                total += line.amount or Decimal('0.00')
        return total

    @fields.depends('party', 'voucher_type', 'lines', 'lines_credits',
        'lines_debits', 'from_pay_invoice')
    def on_change_party(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        MoveLine = pool.get('account.move.line')
        InvoiceAccountMoveLine = pool.get('account.invoice-account.move.line')

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
            account_types = ['payable']
        move_lines = MoveLine.search([
            ('party', '=', self.party),
            ('account.kind', 'in', account_types),
            ('state', '=', 'valid'),
            ('reconciliation', '=', None),
        ])

        for line in move_lines:

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
            payment_line = {
                'name': name,
                'account': line.account.id,
                'amount': Decimal('0.00'),
                'amount_original': amount,
                'amount_unreconciled': abs(line.amount_residual),
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

    def prepare_move_lines(self):
        pool = Pool()
        Period = pool.get('account.period')
        Move = pool.get('account.move')
        Invoice = pool.get('account.invoice')

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
        }])
        self.write([self], {
                'move': move.id,
                })

        #
        # Pay Modes
        #
        if self.pay_lines:
            for line in self.pay_lines:
                if self.voucher_type == 'receipt':
                    debit = line.pay_amount
                    credit = Decimal('0.0')
                else:
                    debit = Decimal('0.0')
                    credit = line.pay_amount

                move_lines.append({
                    'debit': debit,
                    'credit': credit,
                    'account': line.pay_mode.account.id,
                    'move': move.id,
                    'journal': self.journal.id,
                    'period': Period.find(self.company.id, date=self.date),
                })

        #
        # Credits
        #
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

        #
        # Voucher Lines
        #
        total = self.amount
        if self.lines:
            for line in self.lines:
                if not line.amount:
                    continue
                line_move_ids.append(line.move_line)
                if self.voucher_type == 'receipt':
                    debit = Decimal('0.00')
                    credit = line.amount
                else:
                    debit = line.amount
                    credit = Decimal('0.00')
                total -= line.amount
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
            if self.voucher_type == 'receipt':
                debit = Decimal('0.00')
                credit = total
                account_id = self.party.account_receivable.id
            else:
                debit = total
                credit = Decimal('0.00')
                account_id = self.party.account_payable.id
            move_lines.append({
                'description': self.number,
                'debit': debit,
                'credit': credit,
                'account': account_id,
                'move': move.id,
                'journal': self.journal.id,
                'period': Period.find(self.company.id, date=self.date),
                'date': self.date,
                'party': self.party.id,
            })

        return move_lines

    def create_move(self, move_lines):
        pool = Pool()
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        Invoice = pool.get('account.invoice')

        created_lines = MoveLine.create(move_lines)
        Move.post([self.move])

        # reconcile check
        for line in self.lines:
            if line.amount == Decimal("0.00"):
                continue
            invoice = Invoice(line.move_line.origin.id)
            if self.voucher_type == 'receipt':
                amount = line.amount
            else:
                amount = -line.amount
            reconcile_lines, remainder = \
                Invoice.get_reconcile_lines_for_amount(
                    invoice, amount)
            for move_line in created_lines:
                if move_line.description == 'advance':
                    continue
                if move_line.description == invoice.number:
                    reconcile_lines.append(move_line)
                    Invoice.write([invoice], {
                        'payment_lines': [('add', [move_line.id])],
                        })
            if remainder == Decimal('0.00'):
                MoveLine.reconcile(reconcile_lines)

        reconcile_lines = []
        for line in self.lines_credits:
            reconcile_lines.append(line.move_line)
            for move_line in created_lines:
                if move_line.description == 'advance':
                    reconcile_lines.append(move_line)
            MoveLine.reconcile(reconcile_lines)

        reconcile_lines = []
        for line in self.lines_debits:
            reconcile_lines.append(line.move_line)
            for move_line in created_lines:
                if move_line.description == 'advance':
                    reconcile_lines.append(move_line)
            MoveLine.reconcile(reconcile_lines)

        return True
    
    def get_value_lines(self):
        amount_invoice = self.amount
        if self.lines:
            res = {}
            for line in self.lines:
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
                amount += line.amount 
                value_words = self.get_amount2words(amount)
                self.write([self],{ 'amount_to_pay_words': value_words})
    
    @classmethod
    @ModelView.button
    def post(cls, vouchers):
        for voucher in vouchers:
            voucher.get_value_lines()
            voucher.get_toWords()
            voucher.set_number()
            move_lines = voucher.prepare_move_lines()
            voucher.create_move(move_lines)
        cls.write(vouchers, {'state': 'posted'})


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
    
    voucher = fields.Many2One('account.voucher', 'Voucher')
    pay_mode = fields.Many2One('account.voucher.paymode', 'Pay Mode',
        required=True, states=_STATES)
    pay_amount = fields.Numeric('Pay Amount', digits=(16, 2), required=True,
        states=_STATES)
    banco = fields.Many2One('bank', 'Banco')
    cuenta_tercero = fields.Char(u'Numero de Cuenta')
    numero_doc = fields.Char(u'Numero de Documento')
    titular_cuenta = fields.Char(u'Titular de la cuenta')
    
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
        
        new_objs = []
        for obj in objects:
            if obj.amount_to_pay and conversor and not obj.amount_to_pay_words:
                obj.amount_to_pay_words = obj.get_amount2words(obj.amount_to_pay)
            new_objs.append(obj)
        return super(VoucherReport, cls).parse(report,
                new_objs, data, localcontext)              
                

