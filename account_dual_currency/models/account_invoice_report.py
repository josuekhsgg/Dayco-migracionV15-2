# -*- coding: utf-8 -*-

from odoo import models, fields, api
from functools import lru_cache

class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    price_subtotal_usd = fields.Float(string='Total libre de impuesto $', readonly=True)
    price_average_usd = fields.Float(string='Precio promedio $', readonly=True, group_operator="avg")

    _depends = {
        'account.move': [
            'name', 'state', 'move_type', 'partner_id', 'invoice_user_id', 'fiscal_position_id',
            'invoice_date', 'invoice_date_due', 'invoice_payment_term_id', 'partner_bank_id',
        ],
        'account.move.line': [
            'quantity', 'price_subtotal', 'amount_residual', 'balance','balance_usd', 'amount_currency',
            'move_id', 'product_id', 'product_uom_id', 'account_id', 'analytic_account_id',
            'journal_id', 'company_id', 'currency_id', 'partner_id',
        ],
        'product.product': ['product_tmpl_id'],
        'product.template': ['categ_id'],
        'uom.uom': ['category_id', 'factor', 'name', 'uom_type'],
        'res.currency.rate': ['currency_id', 'name'],
        'res.partner': ['country_id'],
    }

    @api.model
    def _select(self):
        return '''
            SELECT
                line.id,
                line.move_id,
                line.product_id,
                line.account_id,
                line.analytic_account_id,
                line.journal_id,
                line.company_id,
                line.company_currency_id,
                line.partner_id AS commercial_partner_id,
                move.state,
                move.move_type,
                move.partner_id,
                move.invoice_user_id,
                move.fiscal_position_id,
                move.payment_state,
                move.invoice_date,
                move.invoice_date_due,
                uom_template.id                                             AS product_uom_id,
                template.categ_id                                           AS product_categ_id,
                line.quantity / NULLIF(COALESCE(uom_line.factor, 1) / COALESCE(uom_template.factor, 1), 0.0) * (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt') THEN -1 ELSE 1 END)
                                                                            AS quantity,
                -line.balance * currency_table.rate                         AS price_subtotal,
                -COALESCE(
                   -- Average line price
                   (line.balance / NULLIF(line.quantity, 0.0)) * (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt') THEN -1 ELSE 1 END)
                   -- convert to template uom
                   * (NULLIF(COALESCE(uom_line.factor, 1), 0.0) / NULLIF(COALESCE(uom_template.factor, 1), 0.0)),
                   0.0) * currency_table.rate                               AS price_average,
                -line.balance_usd                                           AS price_subtotal_usd,
                -COALESCE(
                   -- Average line price dollar
                   (line.balance_usd / NULLIF(line.quantity, 0.0)) * (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt') THEN -1 ELSE 1 END)
                   -- convert to template uom
                   * (NULLIF(COALESCE(uom_line.factor, 1), 0.0) / NULLIF(COALESCE(uom_template.factor, 1), 0.0)),
                   0.0)                                                   AS price_average_usd,
                COALESCE(partner.country_id, commercial_partner.country_id) AS country_id
        '''
