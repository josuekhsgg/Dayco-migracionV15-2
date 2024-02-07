# -*- coding: utf-8 -*-

from collections import defaultdict
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools.misc import formatLang, format_date, parse_date, frozendict
from odoo.tools import html2plaintext


class AccountReconciliation(models.AbstractModel):
    _inherit = 'account.reconciliation.widget'

    @api.model
    def process_bank_statement_line(self, st_line_ids, data):
        """ Handles data sent from the bank statement reconciliation widget
            (and can otherwise serve as an old-API bridge)

            :param st_line_ids
            :param list of dicts data: must contains the keys
                'counterpart_aml_dicts', 'payment_aml_ids' and 'new_aml_dicts',
                whose value is the same as described in process_reconciliation
                except that ids are used instead of recordsets.
            :returns dict: used as a hook to add additional keys.
        """
        st_lines = self.env['account.bank.statement.line'].browse(st_line_ids)
        ctx = dict(self._context, force_price_include=False)

        for st_line, datum in zip(st_lines, data):
            if datum.get('partner_id') is not None:
                st_line.write({'partner_id': datum['partner_id']})
            print(st_line)
            print('******')
            print(datum)
            st_line.with_context(ctx).reconcile(datum.get('lines_vals_list', []), to_check=datum.get('to_check', False))
        return {'statement_line_ids': st_lines, 'moves': st_lines.move_id}

    @api.model
    def _get_statement_line(self, st_line):
        """ Returns the data required by the bank statement reconciliation widget to display a statement line """

        if st_line.foreign_currency_id:
            amount = st_line.amount_currency
            amount_currency = st_line.amount
            amount_currency_str = formatLang(self.env, abs(amount_currency), currency_obj=st_line.currency_id)
        else:
            amount = st_line.amount
            amount_currency = amount
            amount_currency_str = ""
        amount_str = formatLang(self.env, abs(amount), currency_obj=st_line.foreign_currency_id or st_line.currency_id)
        amount_usd_str = formatLang(self.env, abs(st_line.amount_usd_statement), currency_obj=st_line.currency_id_dif_statement)

        data = {
            'id': st_line.id,
            'ref': st_line.ref,
            'note': html2plaintext(st_line.narration) or "",
            'name': st_line.payment_ref,
            'date': format_date(self.env, st_line.date),
            'amount': amount,
            'amount_str': amount_str,  # Amount in the statement line currency
            'amount_usd_str': amount_usd_str,  # Amount in dual currency
            'currency_id': st_line.foreign_currency_id.id or st_line.currency_id.id,
            'partner_id': st_line.partner_id.id,
            'journal_id': st_line.journal_id.id,
            'statement_id': st_line.statement_id.id,
            'account_id': [st_line.journal_id.default_account_id.id,
                           st_line.journal_id.default_account_id.display_name],
            'account_code': st_line.journal_id.default_account_id.code,
            'account_name': st_line.journal_id.default_account_id.name,
            'partner_name': st_line.partner_id.name,
            'communication_partner_name': st_line.partner_name,
            'amount_currency_str': amount_currency_str,  # Amount in the statement currency
            'amount_currency': amount_currency,  # Amount in the statement currency
            'has_no_partner': not st_line.partner_id.id,
            'company_id': st_line.company_id.id,
        }
        if st_line.partner_id:
            data[
                'open_balance_account_id'] = amount > 0 and st_line.partner_id.property_account_receivable_id.id or st_line.partner_id.property_account_payable_id.id

        return data

    @api.model
    def _prepare_js_reconciliation_widget_move_line(self, statement_line, line, recs_count=0):
        def format_name(line):
            if (line.name or '/') == '/':
                line_name = line.move_id.name
            else:
                line_name = line.name
                if line_name != line.move_id.name:
                    line_name = '%s: %s' % (line.move_id.name, line_name)
            return line_name

        # Full amounts.
        rec_vals = statement_line._prepare_counterpart_move_line_vals({
            'balance': -line.amount_currency if line.currency_id else -line.balance,
        }, move_line=line)
        # Residual amounts.
        rec_vals_residual = statement_line._prepare_counterpart_move_line_vals({}, move_line=line)
        if rec_vals_residual['currency_id'] != statement_line.company_currency_id.id:
            currency = self.env['res.currency'].browse(rec_vals_residual['currency_id'])
            amount_currency = rec_vals_residual['debit'] - rec_vals_residual['credit']
            balance = rec_vals_residual['amount_currency']
            balance_usd = rec_vals_residual['amount_currency']
            amount_str = formatLang(self.env, abs(balance), currency_obj=currency)
            amount_usd_str = formatLang(self.env, abs(balance_usd), currency_obj=line.company_id.currency_id_dif)
            amount_currency_str = formatLang(self.env, abs(amount_currency), currency_obj=line.company_currency_id)
            total_amount_currency_str = formatLang(self.env, abs(rec_vals['debit'] - rec_vals['credit']),
                                                   currency_obj=line.company_currency_id)
            total_amount_str = formatLang(self.env, abs(rec_vals['amount_currency']), currency_obj=currency)
        else:
            balance = rec_vals_residual['debit'] - rec_vals_residual['credit']
            balance_usd = rec_vals_residual['debit_usd'] - rec_vals_residual['credit_usd']
            amount_currency = 0.0
            amount_str = formatLang(self.env, abs(balance), currency_obj=line.company_currency_id)
            amount_usd_str = formatLang(self.env, abs(balance_usd), currency_obj=line.company_id.currency_id_dif)
            amount_currency_str = ''
            total_amount_currency_str = ''
            total_amount_str = formatLang(self.env, abs(rec_vals['debit'] - rec_vals['credit']),
                                          currency_obj=line.company_currency_id)

        js_vals = {
            'id': line.id,
            'name': format_name(line),
            'ref': line.ref or '',
            'date': format_date(self.env, line.date),
            'date_maturity': format_date(self.env, line.date_maturity),
            'account_id': [line.account_id.id, line.account_id.display_name],
            'account_code': line.account_id.code,
            'account_name': line.account_id.name,
            'account_type': line.account_id.internal_type,
            'journal_id': [line.journal_id.id, line.journal_id.display_name],
            'partner_id': line.partner_id.id,
            'partner_name': line.partner_id.name,
            'is_liquidity_line': bool(line.payment_id),
            'currency_id': rec_vals_residual['currency_id'],
            'debit': -balance if balance < 0.0 else 0.0,
            'credit': balance if balance > 0.0 else 0.0,
            'debit_usd': -balance_usd if balance_usd < 0.0 else 0.0,
            'credit_usd': balance_usd if balance_usd > 0.0 else 0.0,
            'amount_str': amount_str,
            'amount_usd_str': amount_usd_str,
            'amount_currency': -amount_currency,
            'amount_currency_str': amount_currency_str,
            'total_amount_currency_str': total_amount_currency_str,
            'total_amount_str': total_amount_str,
            'recs_count': recs_count,
        }

        return js_vals
