# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError
from odoo.tools import float_is_zero, float_compare, safe_eval, date_utils, email_split, email_escape_char, email_re
from json import dumps

import json


class AccountMove(models.Model):
    _inherit = 'account.move'

    currency_id_dif = fields.Many2one("res.currency",
                                      string="Divisa de Referencia",
                                      related="company_id.currency_id_dif", store=True)

    acuerdo_moneda = fields.Boolean(string="Acuerdo de Factura Bs.", default=False)

    tax_today = fields.Float(string="Tasa", store=True, default=lambda self: self.env.company.currency_id_dif.tasa_referencia,
                             track_visibility='onchange', digits='Dual_Currency_rate')

    edit_trm = fields.Boolean(string="Editar tasa", compute='_edit_trm')

    name_rate = fields.Char(store=True, readonly=True, compute='_name_ref')
    amount_untaxed_usd = fields.Monetary(currency_field='currency_id_dif', string="Base imponible Ref.", store=True,
                                         compute="_amount_untaxed_usd", digits='Dual_Currency')
    amount_tax_usd = fields.Monetary(currency_field='currency_id_dif', string="Impuestos Ref.", store=True,
                                     readonly=True, digits='Dual_Currency')
    amount_total_usd = fields.Monetary(currency_field='currency_id_dif', string='Total Ref.', store=True, readonly=True,
                                       compute='_amount_all_usd',
                                       digits='Dual_Currency', track_visibility='onchange')

    amount_residual_usd = fields.Monetary(currency_field='currency_id_dif', string='Adeudado Ref.', store=True,
                                          readonly=True, digits='Dual_Currency')
    invoice_payments_widget_usd = fields.Text(groups="account.group_account_invoice",
                                              compute='_compute_payments_widget_reconciled_info_USD')

    invoice_payments_widget_bs = fields.Text(groups="account.group_account_invoice",
                                              compute='_compute_payments_widget_reconciled_info_bs')

    move_igtf_id = fields.Many2one('account.move', string='Asiento Retención IGTF', copy=False)

    amount_untaxed_bs = fields.Monetary(currency_field='company_currency_id', string="Base imponible Bs.", store=True,
                                         compute="_amount_untaxed_usd")
    amount_tax_bs = fields.Monetary(currency_field='company_currency_id', string="Impuestos Bs.", store=True,
                                     readonly=True)
    amount_total_bs = fields.Monetary(currency_field='company_currency_id', string='Total Bs.', store=True, readonly=True,
                                       compute='_amount_all_usd')

    same_currency = fields.Boolean(string="Mismo tipo de moneda", compute='_same_currency')

    asset_remaining_value_ref = fields.Monetary(currency_field='currency_id_dif', string='Valor depreciable Ref.', copy=False)
    asset_depreciated_value_ref = fields.Monetary(currency_field='currency_id_dif', string='Depreciación Acu. Ref.', copy=False)

    @api.depends('currency_id')
    def _same_currency(self):
        for rec in self:
            if rec.currency_id == rec.company_currency_id:
                rec.same_currency = True
            else:
                rec.same_currency = False
    def _check_balanced(self):
        if self.env.context.get('active_model') == 'account.move':
            super(AccountMove, self)._check_balanced()
        else:
            return

    def generar_retencion_igtf(self):
        for rec in self:
            return {'name': _('Aplicar Retención IGTF'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'generar.igtf.wizard',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'domain': "",
                    'context': {
                            'default_invoice_id': rec.id,
                            'default_igtf_porcentage': rec.company_id.igtf_divisa_porcentage,
                            'default_tax_today': rec.currency_id_dif.tasa_referencia,
                            'default_currency_id_dif': rec.currency_id_dif.id,
                            'default_currency_id_company': rec.company_id.currency_id.id,
                            'default_amount': rec.amount_residual_usd,
                        },
                    }

    @api.depends('state','move_type')
    def _edit_trm(self):
        for rec in self:
            edit_trm = False
            if rec.move_type in ('in_invoice', 'in_refund', 'in_receipt','entry'):
                if rec.state == 'draft' and not rec.acuerdo_moneda:
                    edit_trm = True
                else:
                    edit_trm = False
            else:
                edit_trm = self.env.user.has_group('account_dual_currency.group_edit_trm')
                if edit_trm:
                    if rec.state == 'draft' and not rec.acuerdo_moneda:
                        edit_trm = True
                    else:
                        edit_trm = False
            #print(edit_trm)
            rec.edit_trm = edit_trm


    @api.onchange('tax_today')
    def _onchange_tax_today(self):
        for rec in self:
            self.env.context = dict(self.env.context, tasa_factura=rec.tax_today)
            for l in rec.invoice_line_ids:
                l.price_unit = (l.price_unit_usd * rec.tax_today) if rec.currency_id == rec.company_id.currency_id else l.price_unit_usd
                l._onchange_price_subtotal()
                l._onchange_amount_currency()
                l._onchange_mark_recompute_taxes()
            rec._onchange_invoice_line_ids()
            if not rec.currency_id == rec.company_id.currency_id:
                rec._onchange_currency()
            rec._recompute_dynamic_lines(recompute_all_taxes=True)
            self.env.context = dict(self.env.context, tasa_factura=None)
            # for aml in rec.line_ids:
            #     aml.currency_id = rec.currency_id
            #     aml.with_context(check_move_validity=False).debit = aml.debit_usd * rec.tax_today
            #     aml.with_context(check_move_validity=False).credit = aml.credit_usd * rec.tax_today

    @api.model_create_multi
    def create(self, values):
        #print('Valores de la factura', values)
        if values:
            for val in values:
                if not 'tax_today' in val:
                    module_dual_currency = self.env['ir.module.module'].sudo().search(
                        [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
                    if module_dual_currency:
                        val.update({'tax_today': self.env.company.currency_id_dif.tasa_referencia})
                # elif 'tax_today' in val:
                #     if val['tax_today'] == 0:
                #         module_dual_currency = self.env['ir.module.module'].sudo().search(
                #             [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
                #         if module_dual_currency:
                #             val.update({'tax_today': self.env.company.currency_id_dif.tasa_referencia})
        res = super(AccountMove, self).create(values)
        return res

    @api.onchange('invoice_line_ids')
    def _onchange_invoice_line_ids(self):
        super(AccountMove, self)._onchange_invoice_line_ids()
        for rec in self:
            for m in rec.line_ids:
                if not m.debit == 0:
                    if rec.currency_id == self.env.company.currency_id:
                        m.debit_usd = (m.debit / rec.tax_today) if rec.tax_today > 0 else 0
                    else:
                        m.debit_usd = (m.amount_currency if m.amount_currency > 0 else (m.amount_currency * -1))
                else:
                    m.debit_usd = 0

                if not m.credit == 0:
                    if rec.currency_id == self.env.company.currency_id:
                        m.credit_usd = (m.credit / rec.tax_today) if rec.tax_today > 0 else 0
                    else:
                        m.credit_usd = (m.amount_currency if m.amount_currency > 0 else (m.amount_currency * -1))

                else:
                    m.credit_usd = 0

    @api.depends('amount_total', 'currency_id_dif', 'currency_id')
    def _amount_all_usd(self):
        for record in self:
            if record.currency_id_dif.name == record.currency_id.name:
                record[("amount_total_usd")] = record.amount_total
            if record.currency_id_dif.name != record.currency_id.name:
                if record.tax_today > 0:
                    record[("amount_total_usd")] = record.amount_total / record.tax_today
                else:
                    record[("amount_total_usd")] = 0
            record.amount_total_bs = record.amount_total_usd * record.tax_today

    @api.depends('currency_id_dif')
    def _name_ref(self):
        for record in self:
            record.name_rate = record.currency_id_dif.currency_unit_label

    # @api.onchange('currency_id_dif')
    # def _tax_today(self):
    #     """
    #     Compute the total amounts of the SO.
    #     """
    #     for record in self:
    #         if record.currency_id_dif.rate:
    #             if record.currency_id_dif.name == record.currency_id.name:
    #                 record[("tax_today")] = 1
    #             if record.currency_id_dif.name != record.currency_id.name:
    #                 if record.currency_id != self.env.company.currency_id:
    #                     record[("tax_today")] = 1 / record.currency_id.rate
    #                 else:
    #                     record[("tax_today")] = record.currency_id.rate / record.currency_id_dif.rate

    @api.onchange('currency_id')
    def _onchange_currency(self):
        for rec in self:
            if rec.currency_id == self.env.company.currency_id:
                for l in rec.invoice_line_ids:
                    # pass
                    l.currency_id = rec.currency_id
                    l.price_unit = (l.price_unit_usd * (rec.tax_today if rec.tax_today > 0 else l.price_unit))

            else:
                for l in rec.invoice_line_ids:
                    # pass
                    l.currency_id = rec.currency_id
                    l.price_unit = l.price_unit_usd

            rec.invoice_line_ids._onchange_price_subtotal()

            rec._recompute_dynamic_lines(recompute_all_taxes=True)
            for aml in rec.line_ids:
                aml.currency_id = rec.currency_id


            rec._onchange_invoice_line_ids()

    def _get_default_tasa(self):
        for rec in self:
            print('Tasa por defecto')
            return self.env.company.currency_id_dif.tasa_referencia

    def _get_default_currency_id_dif(self):
        for rec in self:
            module_dual_currency = self.env['ir.module.module'].sudo().search(
                [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
            if module_dual_currency:
                rec.currency_id_dif = self.env.company.currency_id_dif.id if self.env.company.currency_id_dif else 0
                return self.env.company.currency_id_dif.id if self.env.company.currency_id_dif else 0
            else:
                rec.currency_id_dif = self.env['res.currency'].search([('name', '=', 'USD')],limit=1).id
                return self.env['res.currency'].search([('name', '=', 'USD')],limit=1).id

    @api.depends('amount_untaxed', 'amount_tax', 'currency_id_dif', 'currency_id')
    def _amount_untaxed_usd(self):
        for rec in self:
            if rec.currency_id != self.env.company.currency_id:
                rec.amount_untaxed_usd = rec.amount_untaxed
                rec.amount_tax_usd = rec.amount_tax
            else:
                rec.amount_untaxed_usd = (rec.amount_untaxed / rec.tax_today) if rec.tax_today > 0 else 0
                rec.amount_tax_usd = (rec.amount_tax / rec.tax_today) if rec.tax_today > 0 else 0

            rec.amount_untaxed_bs = rec.amount_untaxed_usd * rec.tax_today
            rec.amount_tax_bs = rec.amount_tax_usd * rec.tax_today


    @api.depends('move_type', 'line_ids.amount_residual_usd')
    def _compute_payments_widget_reconciled_info_USD(self):
        for move in self:
            if move.state != 'posted' or not move.is_invoice(include_receipts=True):
                move.invoice_payments_widget_usd = json.dumps(False)
                continue
            reconciled_vals = move._get_reconciled_info_JSON_values_USD()
            if reconciled_vals:
                info = {
                    'title': _('Less Payment'),
                    'outstanding': False,
                    'content': reconciled_vals,
                }
                total_pagado = 0
                for r in reconciled_vals:
                    total_pagado = total_pagado + float(r['amount'])
                for n in move.debit_note_ids:
                    total_pagado = total_pagado + n.amount_total_usd
                if total_pagado < move.amount_total_usd:
                    move.amount_residual_usd = move.amount_total_usd - total_pagado
                else:
                    move.amount_residual_usd = 0
                if move.amount_residual_usd > 0:
                    move.payment_state = 'partial'
                else:
                    move.payment_state = 'paid'
                move.invoice_payments_widget_usd = json.dumps(info, default=date_utils.json_default)

            else:
                move.amount_residual_usd = move.amount_total_usd
                move.invoice_payments_widget_usd = json.dumps(False)

    @api.depends('move_type', 'line_ids.amount_residual_usd')
    def _compute_payments_widget_reconciled_info_bs(self):
        for move in self:
            if move.state != 'posted' or not move.is_invoice(include_receipts=True):
                move.invoice_payments_widget_bs = json.dumps(False)
                continue
            reconciled_vals = move._get_reconciled_info_JSON_values_bs()
            if reconciled_vals:
                info = {
                    'title': _('Less Payment'),
                    'outstanding': False,
                    'content': reconciled_vals,
                }
                move.invoice_payments_widget_bs = json.dumps(info, default=date_utils.json_default)
            else:
                move.invoice_payments_widget_bs = json.dumps(False)

    def _get_reconciled_info_JSON_values_USD(self):
        self.ensure_one()
        foreign_currency = self.currency_id if self.currency_id != self.company_id.currency_id else False

        reconciled_vals = []
        pay_term_line_ids = self.line_ids.filtered(
            lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
        partials = pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')
        for partial in partials:
            counterpart_lines = partial.debit_move_id + partial.credit_move_id
            print(partial)
            counterpart_line = counterpart_lines.filtered(lambda line: line not in self.line_ids)
            # if counterpart_line.payment_id:
            #     amount =
            if counterpart_line.credit_usd > 0:
                amount = counterpart_line.credit_usd
            else:
                amount = counterpart_line.debit_usd

            # print(counterpart_line.payment_id)
            # if foreign_currency and partial.currency_id == foreign_currency:
            #     amount = partial.amount_currency
            # else:
            #     amount = partial.company_currency_id._convert(partial.amount, self.currency_id, self.company_id, self.date)
            #
            # if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
            #     continue

            ref = counterpart_line.move_id.name
            if counterpart_line.move_id.ref:
                ref += ' (' + counterpart_line.move_id.ref + ')'

            reconciled_vals.append({
                'name': counterpart_line.name,
                'journal_name': counterpart_line.journal_id.name,
                'amount': abs(partial.amount_usd),
                'currency': self.currency_id_dif.symbol,
                'digits': [69, 3],
                'position': self.currency_id_dif.position,
                'date': counterpart_line.date,
                'payment_id': counterpart_line.id,
                'account_payment_id': counterpart_line.payment_id.id,
                'payment_method_name': counterpart_line.payment_id.payment_method_id.name if counterpart_line.journal_id.type == 'bank' else None,
                'move_id': counterpart_line.move_id.id,
                'ref': ref,
            })
        # print(reconciled_vals)
        return reconciled_vals

    def _get_reconciled_info_JSON_values_bs(self):
        self.ensure_one()
        foreign_currency = self.currency_id if self.currency_id != self.company_id.currency_id else False

        reconciled_vals = []
        pay_term_line_ids = self.line_ids.filtered(
            lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
        partials = pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')
        for partial in partials:
            counterpart_lines = partial.debit_move_id + partial.credit_move_id

            counterpart_line = counterpart_lines.filtered(lambda line: line not in self.line_ids)

            if counterpart_line.credit > 0:
                amount = counterpart_line.credit
            else:
                amount = counterpart_line.debit

            ref = counterpart_line.move_id.name
            if counterpart_line.move_id.ref:
                ref += ' (' + counterpart_line.move_id.ref + ')'

            reconciled_vals.append({
                'name': counterpart_line.name,
                'journal_name': counterpart_line.journal_id.name,
                'amount': abs(partial.amount),
                'currency': self.company_id.currency_id.symbol,
                'digits': [69, 2],
                'position': self.company_id.currency_id.position,
                'date': counterpart_line.date,
                'payment_id': counterpart_line.id,
                'account_payment_id': counterpart_line.payment_id.id,
                'payment_method_name': counterpart_line.payment_id.payment_method_id.name if counterpart_line.journal_id.type == 'bank' else None,
                'move_id': counterpart_line.move_id.id,
                'ref': ref,
            })
        # print(reconciled_vals)
        return reconciled_vals

    # def js_remove_outstanding_partial(self, partial_id):
    #     r = super().js_remove_outstanding_partial(partial_id)
    #     print("recargar")
    #     self._compute_payments_widget_to_reconcile_info()
    #     return r

    def _compute_payments_widget_to_reconcile_info(self):
        for move in self:
            move.invoice_outstanding_credits_debits_widget = json.dumps(False)
            move.invoice_has_outstanding = False

            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue

            pay_term_lines = move.line_ids \
                .filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))

            domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.commercial_partner_id.id),
                '|', ('amount_residual', '!=', 0.0), ('amount_residual_usd', '!=', 0.0),
            ]

            payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

            if move.is_inbound():
                domain.append(('balance', '<', 0.0))
                payments_widget_vals['title'] = _('Outstanding credits')
            else:
                domain.append(('balance', '>', 0.0))
                payments_widget_vals['title'] = _('Outstanding debits')
            # print(domain)
            for line in self.env['account.move.line'].search(domain):

                # print(line)
                if line.debit == 0 and line.credit == 0 and not line.full_reconcile_id:
                    if abs(line.amount_residual_usd) > 0:
                        payments_widget_vals['content'].append({
                            'journal_name': line.ref or line.move_id.name,
                            'amount': 0,
                            'amount_usd': abs(line.amount_residual_usd),
                            'currency': move.currency_id.symbol,
                            'id': line.id,
                            'move_id': line.move_id.id,
                            'position': move.currency_id.position,
                            'digits': [69, move.currency_id.decimal_places],
                            'payment_date': fields.Date.to_string(line.date),
                        })
                        continue
                if line.currency_id == move.currency_id:
                    # Same foreign currency.
                    amount = abs(line.amount_residual_currency)
                    # print("******* %s -- %s" % (line.amount_residual_currency,line.amount_residual_usd))
                    amount_usd = abs(line.amount_residual_usd)
                else:
                    # Different foreign currencies.
                    # amount = move.company_currency_id._convert(
                    #     abs(line.amount_residual),
                    #     move.currency_id,
                    #     move.company_id,
                    #     line.date,
                    # )
                    if move.currency_id == move.company_id.currency_id_dif and line.currency_id == line.company_id.currency_id:
                        amount = abs(line.amount_residual_usd)
                    else:
                        amount = abs(line.amount_residual_currency)
                    #amount = line.amount_residual

                    amount_usd = abs(line.amount_residual_usd)

                if move.currency_id.is_zero(amount) and amount_usd == 0:
                    continue

                payments_widget_vals['content'].append({
                    'journal_name': line.ref or line.move_id.name,
                    'amount': amount,
                    'amount_usd': amount_usd if move.currency_id == move.company_id.currency_id else abs(line.amount_residual),
                    'currency': move.currency_id.symbol,
                    'currency_ref': move.currency_id_dif.symbol if move.currency_id == move.company_id.currency_id else move.company_id.currency_id.symbol,
                    'id': line.id,
                    'move_id': line.move_id.id,
                    'position': move.currency_id.position,
                    'position_ref': move.currency_id_dif.position if move.currency_id == move.company_id.currency_id else move.company_id.currency_id.position,
                    'digits': [69, move.currency_id.decimal_places],
                    'payment_date': fields.Date.to_string(line.date),
                })

            if not payments_widget_vals['content']:
                continue

            move.invoice_outstanding_credits_debits_widget = json.dumps(payments_widget_vals)
            move.invoice_has_outstanding = True

    def js_assign_outstanding_line(self, line_id):
        ''' Called by the 'payment' widget to reconcile a suggested journal item to the present
        invoice.

        :param line_id: The id of the line to reconcile with the current invoice.
        '''
        self.ensure_one()
        lines = self.env['account.move.line'].browse(line_id)
        l = self.line_ids.filtered(lambda line: line.account_id == lines[0].account_id and not line.reconciled)
        if abs(lines[0].amount_residual) == 0 and abs(lines[0].amount_residual_usd) > 0:
            if l.full_reconcile_id:
                l.full_reconcile_id.unlink()
            partial = self.env['account.partial.reconcile'].create([{
                'amount': 0,
                'amount_usd': l.move_id.amount_residual_usd if abs(
                    lines[0].amount_residual_usd) > l.move_id.amount_residual_usd else abs(
                    lines[0].amount_residual_usd),
                'debit_amount_currency': 0,
                'credit_amount_currency': 0,
                'debit_move_id': l.id,
                'credit_move_id': line_id,
            }])
            p = (lines + l).reconcile()
            (lines + l)._compute_amount_residual_usd()
            return p
        else:
            results = (lines + l).reconcile()
            if 'partials' in results:
                if results['partials'].amount_usd == 0:
                    monto_usd = 0
                    if abs(lines[0].amount_residual_usd) > 0:

                        # print("1")
                        if abs(lines[0].amount_residual_usd) > self.amount_residual_usd:
                            # print("2")
                            monto_usd = self.amount_residual_usd
                        else:
                            # print("3")
                            monto_usd = abs(lines[0].amount_residual_usd)
                    results['partials'].write({'amount_usd': monto_usd})
                    lines[0]._compute_amount_residual_usd()
            return results

    @api.model
    def _prepare_move_for_asset_depreciation(self, vals):
        move_vals = super(AccountMove, self)._prepare_move_for_asset_depreciation(vals)
        asset_id = vals.get('asset_id')
        move_vals['tax_today'] = asset_id.tax_today
        move_vals['currency_id_dif'] = asset_id.currency_id_dif.id
        move_vals['asset_remaining_value_ref'] = move_vals['asset_remaining_value'] / asset_id.tax_today
        move_vals['asset_depreciated_value_ref'] = move_vals['asset_depreciated_value'] / asset_id.tax_today
        return move_vals


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    debit_usd = fields.Monetary(currency_field='currency_id_dif', string='Débito $', store=True, compute="_debit_usd",
                                digits='Dual_Currency', readonly=False)
    credit_usd = fields.Monetary(currency_field='currency_id_dif', string='Crédito $', store=True,
                                 compute="_credit_usd", digits='Dual_Currency', readonly=False)
    tax_today = fields.Float(related="move_id.tax_today", store=True, digits='Dual_Currency_rate')
    currency_id_dif = fields.Many2one("res.currency", store=True)
    price_unit_usd = fields.Monetary(currency_field='currency_id_dif', string='Precio $', store=True,
                                     compute='_price_unit_usd', digits='Dual_Currency')
    price_subtotal_usd = fields.Monetary(currency_field='currency_id_dif', string='SubTotal $', store=True,
                                         compute="_price_subtotal_usd", digits='Dual_Currency')
    amount_residual_usd = fields.Monetary(currency_field='currency_id_dif', string='Residual Amount USD', store=True,
                                       compute='_compute_amount_residual_usd',
                                       help="The residual amount on a journal item expressed in the company currency.")
    balance_usd = fields.Monetary(string='Balance', store=True,
                                  currency_field='currency_id_dif',
                                  compute='_compute_balance_usd',
                                  default=lambda self: self._compute_balance_usd(),
                                  help="Technical field holding the debit_usd - credit_usd in order to open meaningful graph views from reports")

    @api.onchange('amount_currency')
    def _onchange_amount_currency(self):
        super()._onchange_amount_currency()
        self._debit_usd()
        self._credit_usd()

    @api.onchange('product_id')
    def _onchange_product_id(self):
        super()._onchange_product_id()
        self._price_unit_usd()

    @api.depends('debit_usd', 'credit_usd')
    def _compute_balance_usd(self):
        for line in self:
            line.balance_usd = line.debit_usd - line.credit_usd


    @api.depends('price_unit', 'product_id')
    def _price_unit_usd(self):
        for rec in self:
            if rec.price_unit > 0:
                if rec.move_id.currency_id == self.env.company.currency_id:
                    rec.price_unit_usd = (rec.price_unit / rec.tax_today) if rec.tax_today > 0 else 0
                else:
                    rec.price_unit_usd = rec.price_unit * rec.tax_today
            else:
                rec.price_unit_usd = 0

            # if rec.price_unit_usd > 0:
            #     if rec.move_id.currency_id == self.env.company.currency_id:
            #         rec.price_unit = rec.price_unit_usd * rec.tax_today
            #     else:
            #         rec.price_unit = rec.price_unit_usd
            # else:
            #     rec.price_unit = 0

    @api.depends('price_subtotal')
    def _price_subtotal_usd(self):
        is_main_currency = self.env.company.currency_id
        is_inverse_currency = self.env.company.currency_id_dif

        for rec in self:
            if rec.price_subtotal > 0:
                if rec.move_id.currency_id == self.env.company.currency_id:
                    rec.price_subtotal_usd = (rec.price_subtotal / rec.tax_today) if rec.tax_today > 0 else 0
                    rec.currency_id_dif = is_inverse_currency.id
                else:
                    rec.price_subtotal_usd = rec.price_subtotal * rec.tax_today
                    rec.currency_id_dif = is_main_currency.id

            else:
                rec.price_subtotal_usd = 0
                rec.currency_id_dif = is_inverse_currency.id if rec.move_id.currency_id == self.env.company.currency_id else is_main_currency.id

            # if rec.price_subtotal_usd > 0:
            #     if rec.move_id.currency_id == self.env.company.currency_id:
            #         rec.price_subtotal = rec.price_subtotal_usd * rec.tax_today
            #     else:
            #         rec.price_subtotal = rec.price_subtotal_usd
            # else:
            #     rec.price_subtotal = 0

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        if 'tax_today' not in fields:
            return super(AccountMoveLine, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                           orderby=orderby, lazy=lazy)
        res = super(AccountMoveLine, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                      orderby=orderby, lazy=lazy)
        for group in res:
            if group.get('__domain'):
                records = self.search(group['__domain'])
                group['tax_today'] = 0
        return res

    @api.depends('amount_currency', 'tax_today')
    def _debit_usd(self):
        for rec in self:
            if not rec.debit == 0:
                if rec.move_id.currency_id == self.env.company.currency_id:
                    amount_currency = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1))
                    rec.debit_usd = (amount_currency / rec.tax_today) if rec.tax_today > 0 else 0
                    #rec.debit = amount_currency
                else:
                    rec.debit_usd = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1))
                    # if not 'calcular_dual_currency' in self.env.context:
                    #     if not rec.move_id.stock_move_id:
                    #         module_dual_currency = self.env['ir.module.module'].sudo().search(
                    #             [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
                    #         if module_dual_currency:
                    #             # rec.debit = ((rec.amount_currency * rec.tax_today) if rec.amount_currency > 0 else (
                    #             #         (rec.amount_currency * -1) * rec.tax_today))
                    #             rec.debit = (rec.debit_usd * rec.tax_today)

            else:
                rec.debit_usd = 0

    @api.depends('amount_currency', 'tax_today')
    def _credit_usd(self):
        for rec in self:
            # tmp = rec.credit_usd if rec.credit_usd > 0 else 0
            if not rec.credit == 0:
                if rec.move_id.currency_id == self.env.company.currency_id:
                    amount_currency = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1))
                    rec.credit_usd = (amount_currency / rec.tax_today) if rec.tax_today > 0 else 0
                    #rec.credit = amount_currency
                else:
                    rec.credit_usd = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1))
                    # if not 'calcular_dual_currency' in self.env.context:
                    #     if not rec.move_id.stock_move_id:
                    #         module_dual_currency = self.env['ir.module.module'].sudo().search(
                    #             [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
                    #         if module_dual_currency:
                    #             #rec.credit = ((rec.amount_currency * rec.tax_today) if rec.amount_currency > 0 else (
                    #             #        (rec.amount_currency * -1) * rec.tax_today))
                    #             rec.credit = rec.credit_usd * rec.tax_today

            else:
                rec.credit_usd = 0

    @api.depends('debit_usd', 'credit_usd', 'amount_currency', 'account_id', 'currency_id', 'move_id.state',
                 'company_id',
                 'matched_debit_ids', 'matched_credit_ids')
    def _compute_amount_residual_usd(self):
        """ Computes the residual amount of a move line from a reconcilable account in the company currency and the line's currency.
            This amount will be 0 for fully reconciled lines or lines from a non-reconcilable account, the original line amount
            for unreconciled lines, and something in-between for partially reconciled lines.
        """
        for line in self:
            if line.id and (line.account_id.reconcile or line.account_id.internal_type == 'liquidity'):
                reconciled_balance = sum(line.matched_credit_ids.mapped('amount_usd')) \
                                     - sum(line.matched_debit_ids.mapped('amount_usd'))

                line.amount_residual_usd = (line.debit_usd - line.credit_usd) - reconciled_balance

                line.reconciled = (line.amount_residual_usd == 0)
            else:
                # Must not have any reconciliation since the line is not eligible for that.
                line.amount_residual_usd = 0.0
                line.reconciled = False

    def reconcile(self):
        ''' Reconcile the current move lines all together.
        :return: A dictionary representing a summary of what has been done during the reconciliation:
                * partials:             A recorset of all account.partial.reconcile created during the reconciliation.
                * full_reconcile:       An account.full.reconcile record created when there is nothing left to reconcile
                                        in the involved lines.
                * tax_cash_basis_moves: An account.move recordset representing the tax cash basis journal entries.
        '''
        results = {}

        if not self:
            return results

        # List unpaid invoices
        not_paid_invoices = self.move_id.filtered(
            lambda move: move.is_invoice(include_receipts=True) and move.payment_state not in ('paid', 'in_payment')
        )

        # ==== Check the lines can be reconciled together ====
        company = None
        account = None
        for line in self:
            # if line.reconciled and line.move_id.move_type == '' and line.move_id.amount_residual_usd == 0:
            #    raise UserError(_("You are trying to reconcile some entries that are already reconciled."))
            if not line.account_id.reconcile and line.account_id.internal_type != 'liquidity':
                raise UserError(
                    _("Account %s does not allow reconciliation. First change the configuration of this account to allow it.")
                    % line.account_id.display_name)
            if line.move_id.state != 'posted':
                raise UserError(_('You can only reconcile posted entries.'))
            if company is None:
                company = line.company_id
            elif line.company_id != company:
                raise UserError(_("Entries doesn't belong to the same company: %s != %s")
                                % (company.display_name, line.company_id.display_name))
            if account is None:
                account = line.account_id
            elif line.account_id != account:
                raise UserError(_("Entries are not from the same account: %s != %s")
                                % (account.display_name, line.account_id.display_name))

        sorted_lines = self.sorted(key=lambda line: (line.date_maturity or line.date, line.currency_id))

        # ==== Collect all involved lines through the existing reconciliation ====

        involved_lines = sorted_lines
        involved_partials = self.env['account.partial.reconcile']
        current_lines = involved_lines
        current_partials = involved_partials
        while current_lines:
            current_partials = (current_lines.matched_debit_ids + current_lines.matched_credit_ids) - current_partials
            involved_partials += current_partials
            current_lines = (current_partials.debit_move_id + current_partials.credit_move_id) - current_lines
            involved_lines += current_lines

        # ==== Create partials ====
        print('sorted_lines', sorted_lines)
        prepare_reconciliation_partials = sorted_lines._prepare_reconciliation_partials()
        print('prepare_reconciliation_partials', prepare_reconciliation_partials)
        partials = self.env['account.partial.reconcile'].create(prepare_reconciliation_partials)

        # Track newly created partials.
        results['partials'] = partials
        involved_partials += partials

        # ==== Create entries for cash basis taxes ====

        is_cash_basis_needed = account.user_type_id.type in ('receivable', 'payable')
        if is_cash_basis_needed and not self._context.get('move_reverse_cancel'):
            tax_cash_basis_moves = partials._create_tax_cash_basis_moves()
            results['tax_cash_basis_moves'] = tax_cash_basis_moves

        # ==== Check if a full reconcile is needed ====

        if involved_lines[0].currency_id and all(
                line.currency_id == involved_lines[0].currency_id for line in involved_lines):
            is_full_needed = all(line.currency_id.is_zero(line.amount_residual_currency) for line in involved_lines)
        else:
            is_full_needed = all(line.company_currency_id.is_zero(line.amount_residual) for line in involved_lines)

        if is_full_needed:

            # ==== Create the exchange difference move ====

            # if self._context.get('no_exchange_difference'):
            #     exchange_move = None
            # else:
            #     exchange_move = involved_lines._create_exchange_difference_move()
            #     if exchange_move:
            #         exchange_move_lines = exchange_move.line_ids.filtered(lambda line: line.account_id == account)
            #
            #         # Track newly created lines.
            #         involved_lines += exchange_move_lines
            #
            #         # Track newly created partials.
            #         exchange_diff_partials = exchange_move_lines.matched_debit_ids \
            #                                  + exchange_move_lines.matched_credit_ids
            #         involved_partials += exchange_diff_partials
            #         results['partials'] += exchange_diff_partials
            #
            #         exchange_move._post(soft=False)

            # ==== Create the full reconcile ====
            exchange_move = None
            results['full_reconcile'] = self.env['account.full.reconcile'].create({
                'exchange_move_id': exchange_move and exchange_move.id,
                'partial_reconcile_ids': [(6, 0, involved_partials.ids)],
                'reconciled_line_ids': [(6, 0, involved_lines.ids)],
            })

        # Trigger action for paid invoices
        not_paid_invoices \
            .filtered(lambda move: move.payment_state in ('paid', 'in_payment')) \
            .action_invoice_paid()

        for parcial in results['partials']:

            amount_usd = min(abs(parcial.debit_move_id.amount_residual_usd), abs(parcial.credit_move_id.amount_residual_usd))
            print('pasando por parcials', parcial)
            print('monto usd', amount_usd)
            parcial.write({'amount_usd': abs(amount_usd)})
            self.env.cr.commit()
            parcial.debit_move_id._compute_amount_residual_usd()
            parcial.credit_move_id._compute_amount_residual_usd()
            self.env.cr.commit()

        return results

    def _prepare_reconciliation_partials(self):
        ''' Prepare the partials on the current journal items to perform the reconciliation.
        /!\ The order of records in self is important because the journal items will be reconciled using this order.

        :return: A recordset of account.partial.reconcile.
        '''
        def fix_remaining_cent(currency, abs_residual, partial_amount):
            if abs_residual - currency.rounding <= partial_amount <= abs_residual + currency.rounding:
                return abs_residual
            else:
                return partial_amount

        debit_lines = iter(self.filtered(lambda line: line.balance > 0.0 or line.amount_currency > 0.0 and not line.reconciled))
        credit_lines = iter(self.filtered(lambda line: line.balance < 0.0 or line.amount_currency < 0.0 and not line.reconciled))
        void_lines = iter(self.filtered(lambda line: not line.balance and not line.amount_currency and not line.reconciled))
        debit_line = None
        credit_line = None

        debit_amount_residual = 0.0
        debit_amount_residual_currency = 0.0
        credit_amount_residual = 0.0
        credit_amount_residual_currency = 0.0
        debit_line_currency = None
        credit_line_currency = None

        partials_vals_list = []

        while True:

            # Move to the next available debit line.
            if not debit_line:
                debit_line = next(debit_lines, None) or next(void_lines, None)
                if not debit_line:
                    break
                debit_amount_residual = debit_line.amount_residual

                if debit_line.currency_id:
                    debit_amount_residual_currency = debit_line.amount_residual_currency
                    debit_line_currency = debit_line.currency_id
                else:
                    debit_amount_residual_currency = debit_amount_residual
                    debit_line_currency = debit_line.company_currency_id

            # Move to the next available credit line.
            if not credit_line:
                credit_line = next(void_lines, None) or next(credit_lines, None)
                if not credit_line:
                    break
                credit_amount_residual = credit_line.amount_residual

                if credit_line.currency_id:
                    credit_amount_residual_currency = credit_line.amount_residual_currency
                    credit_line_currency = credit_line.currency_id
                else:
                    credit_amount_residual_currency = credit_amount_residual
                    credit_line_currency = credit_line.company_currency_id

            min_amount_residual = min(debit_amount_residual, -credit_amount_residual)

            if debit_line_currency == credit_line_currency:
                # Reconcile on the same currency.

                min_amount_residual_currency = min(debit_amount_residual_currency, -credit_amount_residual_currency)
                min_debit_amount_residual_currency = min_amount_residual_currency
                min_credit_amount_residual_currency = min_amount_residual_currency

            else:
                # Reconcile on the company's currency.
                if credit_line_currency == credit_line.company_currency_id and debit_line_currency == debit_line.company_id.currency_id_dif:
                    self.env.context = dict(self.env.context, tasa_factura=debit_line.tax_today)
                    min_debit_amount_residual_currency = credit_line.company_currency_id._convert(
                        min_amount_residual,
                        debit_line.currency_id,
                        credit_line.company_id,
                        credit_line.date,
                    )
                    min_debit_amount_residual_currency = fix_remaining_cent(
                        debit_line.currency_id,
                        debit_amount_residual_currency,
                        min_debit_amount_residual_currency,
                    )

                    self.env.context = dict(self.env.context, tasa_factura=None)
                    min_credit_amount_residual_currency = debit_line.company_currency_id._convert(
                        min_amount_residual,
                        credit_line.currency_id,
                        debit_line.company_id,
                        debit_line.date,
                    )
                    min_credit_amount_residual_currency = fix_remaining_cent(
                        credit_line.currency_id,
                        -credit_amount_residual_currency,
                        min_credit_amount_residual_currency,
                    )

                if debit_line_currency == debit_line.company_currency_id and credit_line_currency == credit_line.company_id.currency_id_dif:
                    min_debit_amount_residual_currency = credit_line.company_currency_id._convert(
                        min_amount_residual,
                        debit_line.currency_id,
                        credit_line.company_id,
                        credit_line.date,
                    )
                    min_debit_amount_residual_currency = fix_remaining_cent(
                        debit_line.currency_id,
                        debit_amount_residual_currency,
                        min_debit_amount_residual_currency,
                    )
                    self.env.context = dict(self.env.context, tasa_factura=credit_line.tax_today)
                    min_credit_amount_residual_currency = debit_line.company_currency_id._convert(
                        min_amount_residual,
                        credit_line.currency_id,
                        debit_line.company_id,
                        debit_line.date,
                    )
                    min_credit_amount_residual_currency = fix_remaining_cent(
                        credit_line.currency_id,
                        -credit_amount_residual_currency,
                        min_credit_amount_residual_currency,
                    )
                    self.env.context = dict(self.env.context, tasa_factura=None)
                else:
                    min_debit_amount_residual_currency = credit_line.company_currency_id._convert(
                        min_amount_residual,
                        debit_line.currency_id,
                        credit_line.company_id,
                        credit_line.date,
                    )
                    min_debit_amount_residual_currency = fix_remaining_cent(
                        debit_line.currency_id,
                        debit_amount_residual_currency,
                        min_debit_amount_residual_currency,
                    )
                    min_credit_amount_residual_currency = debit_line.company_currency_id._convert(
                        min_amount_residual,
                        credit_line.currency_id,
                        debit_line.company_id,
                        debit_line.date,
                    )
                    min_credit_amount_residual_currency = fix_remaining_cent(
                        credit_line.currency_id,
                        -credit_amount_residual_currency,
                        min_credit_amount_residual_currency,
                    )

            debit_amount_residual -= min_amount_residual
            debit_amount_residual_currency -= min_debit_amount_residual_currency
            credit_amount_residual += min_amount_residual
            credit_amount_residual_currency += min_credit_amount_residual_currency

            partials_vals_list.append({
                'amount': min_amount_residual,
                'debit_amount_currency': min_debit_amount_residual_currency,
                'credit_amount_currency': min_credit_amount_residual_currency,
                'debit_move_id': debit_line.id,
                'credit_move_id': credit_line.id,
            })

            has_debit_residual_left = not debit_line.company_currency_id.is_zero(debit_amount_residual) and debit_amount_residual > 0.0
            has_credit_residual_left = not credit_line.company_currency_id.is_zero(credit_amount_residual) and credit_amount_residual < 0.0
            has_debit_residual_curr_left = not debit_line_currency.is_zero(debit_amount_residual_currency) and debit_amount_residual_currency > 0.0
            has_credit_residual_curr_left = not credit_line_currency.is_zero(credit_amount_residual_currency) and credit_amount_residual_currency < 0.0

            if debit_line_currency == credit_line_currency:
                # The debit line is now fully reconciled because:
                # - either amount_residual & amount_residual_currency are at 0.
                # - either the credit_line is not an exchange difference one.
                if not has_debit_residual_curr_left and (has_credit_residual_curr_left or not has_debit_residual_left):
                    debit_line = None

                # The credit line is now fully reconciled because:
                # - either amount_residual & amount_residual_currency are at 0.
                # - either the debit is not an exchange difference one.
                if not has_credit_residual_curr_left and (has_debit_residual_curr_left or not has_credit_residual_left):
                    credit_line = None

            else:
                # The debit line is now fully reconciled since amount_residual is 0.
                if not has_debit_residual_left:
                    debit_line = None

                # The credit line is now fully reconciled since amount_residual is 0.
                if not has_credit_residual_left:
                    credit_line = None

        return partials_vals_list
