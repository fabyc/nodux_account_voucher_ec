# This file is part of the sale_payment module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
#! -*- coding: utf8 -*-
from trytond.pool import PoolMeta, Pool
import os

__all__ = ['Sale']
__metaclass__ = PoolMeta

class Sale:
    __name__ = 'sale.sale'
    
    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        print cls
        
    @classmethod
    def get_residual_amount_voucher(cls, sales, names, residual_amount):
        return residual_amount
        
    @classmethod
    def get_paid_amount_voucher(cls, sales, names, paid_amount):
        return paid_amount
    
    
