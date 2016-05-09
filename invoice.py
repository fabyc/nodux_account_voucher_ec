#This file is part of the nodux_account_voucher_ec module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from decimal import Decimal
from trytond.wizard import Wizard, StateView, Button
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['PayInvoice']


class PayInvoice(Wizard):
    'Pay Invoice'
    __name__ = 'account.invoice.pay'

    start = StateView('account.voucher',
        'nodux_account_voucher_ec.account_voucher_form', [
            Button('Cerrar', 'end', 'tryton-ok', default=True),
            ])

    def default_start(self, fields):
        Date = Pool().get('ir.date')
        default = {
            'lines': [],
        }
        Invoice = Pool().get('account.invoice')
        Journal = Pool().get('account.journal')
        
        invoice = Invoice(Transaction().context.get('active_id'))
        default['date'] = Date.today()
        default['party'] = invoice.party.id
        default['from_pay_invoice'] = True
        default['journal'] = invoice.journal.id
        
                
        amount_to_pay = Decimal('0.0')
        if invoice.type in( 'in_invoice', 'in_withholding'):
            default['voucher_type'] = 'payment'
            line_type = 'cr'
        elif invoice.type in ('out_invoice', 'out_withholding'):
            default['voucher_type'] = 'receipt'
            line_type = 'dr'
            amount_to_pay = invoice.amount_to_pay
        line_to_pay = invoice.lines_to_pay
        
        for l in line_to_pay:
            if l.reconciliation == None:
                line_to_pay = l
        
            lines = {
                'name': invoice.number,
                'account': line_to_pay.account.id,
                'amount': Decimal('0.00'),
                'amount_original': invoice.total_amount,
                'amount_unreconciled': abs(line_to_pay.amount_residual),
                'line_type': line_type,
                'move_line': line_to_pay.id,
                'date': line_to_pay.date,
                'date_expire': line_to_pay.maturity_date,
                }
            default['lines'].append(lines)
        return default
