#This file is part of the nodux_account_voucher_ec module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import fields
from trytond.pool import Pool, PoolMeta

__all__ = ['Move', 'Line', 'Reconciliation']
__metaclass__ = PoolMeta


class Move:
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        return super(Move, cls)._get_origin() + ['account.voucher']


class Line:
    __name__ = 'account.move.line'
    amount_residual = fields.Function(fields.Numeric('Amount Residual',
        digits=(16, 2)), 'get_amount_residual')

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls._check_modify_exclude = {'reconciliation', 'debit', 'credit', 'state'}

    def get_amount_residual(self, name):
        Invoice = Pool().get('account.invoice')

        res = Decimal('0.0')
        if self.reconciliation or \
        not self.account.kind in ('payable', 'receivable'):
            return res

        move_line_total = self.debit - self.credit

        invoices = Invoice.search([
            ('move', '=', self.move.id),
        ])
        if invoices:
            invoice = invoices[0]
            for payment_line in invoice.payment_lines:
                if payment_line.id == self.id:
                    continue
                move_line_total += payment_line.debit - payment_line.credit
            res = move_line_total
        return res


class Reconciliation():
    __name__ = 'account.move.reconciliation'

    @classmethod
    def __setup__(cls):
        super(Reconciliation, cls).__setup__()

    @classmethod
    def check_lines(cls, reconciliations):
        modules = None
        Lang = Pool().get('ir.lang')
        Configuration = Pool().get('account.configuration')
        Module = Pool().get('ir.module.module')
        modules = Module.search([('name', '=', 'nodux_sale_payment_advanced_payment'), ('state', '=', 'installed')])
        for reconciliation in reconciliations:
            debit = Decimal('0.0')
            credit = Decimal('0.0')
            account = None
            if reconciliation.lines:
                party = reconciliation.lines[0].party
            for line in reconciliation.lines:
                if line.state == 'draft':
                    line.state = 'valid'
                    line.save()
                if line.state != 'valid':
                    cls.raise_user_error('reconciliation_line_not_valid',
                        (line.rec_name,))

                debit += line.debit
                credit += line.credit
                if modules:
                    if not account:
                        account = line.account
                    if account == Configuration(1).default_account_advanced:
                        pass
                else:
                    if not account:
                        account = line.account
                    elif account.id != line.account.id:
                        cls.raise_user_error('reconciliation_different_accounts', {
                                'line': line.rec_name,
                                'account1': line.account.rec_name,
                                'account2': account.rec_name,
                                })
                if not account.reconcile:
                    cls.raise_user_error('reconciliation_account_no_reconcile',
                        {
                            'line': line.rec_name,
                            'account': line.account.rec_name,
                            })
                if line.party != party:
                    cls.raise_user_error('reconciliation_different_parties', {
                            'line': line.rec_name,
                            'party1': line.party.rec_name,
                            'party2': party.rec_name,
                            })
            if not account.company.currency.is_zero(debit - credit):
                language = Transaction().language
                languages = Lang.search([('code', '=', language)])
                if not languages:
                    languages = Lang.search([('code', '=', 'en_US')])
                language = languages[0]
                debit = Lang.currency(
                    language, debit, account.company.currency)
                credit = Lang.currency(
                    language, credit, account.company.currency)
                cls.raise_user_error('reconciliation_unbalanced', {
                        'debit': debit,
                        'credit': credit,
                        })
