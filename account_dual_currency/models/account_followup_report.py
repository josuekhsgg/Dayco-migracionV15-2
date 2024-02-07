import time
from odoo import models, fields, api
from odoo.tools.misc import formatLang, format_date, get_lang
from odoo.tools.translate import _
from odoo.tools import append_content_to_html, DEFAULT_SERVER_DATE_FORMAT, html2plaintext
from odoo.exceptions import UserError

class AccountFollowupReport(models.AbstractModel):
    _inherit = "account.followup.report"

    def _get_columns_name(self, options):
        """
        Override
        Return the name of the columns of the follow-ups report
        """
        headers = [{},
                   {'name': _('Date'), 'class': 'date', 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Due Date'), 'class': 'date', 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Source Document'), 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Communication'), 'style': 'text-align:right; white-space:nowrap;'},
                   {'name': _('Expected Date'), 'class': 'date', 'style': 'white-space:nowrap;'},
                   {'name': _('Excluded'), 'class': 'date', 'style': 'white-space:nowrap;'},
                   {'name': _('Adeudo Total $'), 'class': 'number o_price_total','style': 'text-align:right; white-space:nowrap;'},
                   {'name': _('Tasa'), 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Total Due'), 'class': 'number o_price_total', 'style': 'text-align:right; white-space:nowrap;'},
                  ]
        if self.env.context.get('print_mode'):
            headers = headers[:5] + headers[7:]  # Remove the 'Expected Date' and 'Excluded' columns
        return headers

    def _get_lines(self, options, line_id=None):
        """
        Override
        Compute and return the lines of the columns of the follow-ups report.
        """
        # Get date format for the lang
        partner = options.get('partner_id') and self.env['res.partner'].browse(options['partner_id']) or False
        if not partner:
            return []

        lang_code = partner.lang if self._context.get('print_mode') else self.env.user.lang or get_lang(self.env).code
        lines = []
        columns = []
        res = {}
        today = fields.Date.today()
        line_num = 0
        for l in partner.unreconciled_aml_ids.filtered(lambda l: l.company_id == self.env.company):
            if l.company_id == self.env.company:
                if self.env.context.get('print_mode') and l.blocked:
                    continue
                currency = l.currency_id or l.company_id.currency_id
                if currency not in res:
                    res[currency] = []
                res[currency].append(l)

        for m in partner.unpaid_invoices:
            if m.amount_residual_usd != 0:
                l = m.line_ids.filtered_domain([('account_id', '=', partner.property_account_receivable_id.id)])
                currency = l.currency_id or l.company_id.currency_id
                if currency not in res:
                    res[currency] = []
                if l not in res[currency]:
                    res[currency].append(l)
        #print(res.items())
        for currency, aml_recs in res.items():
            total = 0
            total_issued = 0
            currency_id_dif = None
            for aml in aml_recs:
                currency_id_dif = aml.move_id.currency_id_dif
                amount = aml.move_id.amount_residual_usd * aml.move_id.currency_id_dif.tasa_referencia
                amount_usd = aml.move_id.amount_residual_usd
                date_due = format_date(self.env, aml.date_maturity or aml.date, lang_code=lang_code)
                total += not aml.blocked and amount_usd or 0
                is_overdue = today > aml.date_maturity if aml.date_maturity else today > aml.date
                is_payment = aml.payment_id
                if is_overdue or is_payment:
                    total_issued += not aml.blocked and amount_usd or 0
                if is_overdue:
                    date_due = {'name': date_due, 'class': 'color-red date', 'style': 'white-space:nowrap;text-align:center;color: red;'}
                if is_payment:
                    date_due = ''
                move_line_name = self._format_aml_name(aml.name, aml.move_id.ref, aml.move_id.name)
                if self.env.context.get('print_mode'):
                    move_line_name = {'name': move_line_name, 'style': 'text-align:right; white-space:normal;'}


                if amount_usd != 0 or amount != 0:
                    amount = formatLang(self.env, amount, currency_obj=self.env.company.currency_id)
                    amount_usd = formatLang(self.env, amount_usd, currency_obj=aml.move_id.currency_id_dif)
                    line_num += 1
                    expected_pay_date = format_date(self.env, aml.expected_pay_date, lang_code=lang_code) if aml.expected_pay_date else ''
                    invoice_origin = aml.move_id.invoice_origin or ''
                    if len(invoice_origin) > 43:
                        invoice_origin = invoice_origin[:40] + '...'
                    tasa = formatLang(self.env, aml.move_id.currency_id_dif.tasa_referencia, currency_obj=self.env.company.currency_id)
                    columns = [
                        format_date(self.env, aml.date, lang_code=lang_code),
                        date_due,
                        invoice_origin,
                        move_line_name,
                        (expected_pay_date and expected_pay_date + ' ') + (aml.internal_note or ''),
                        {'name': '', 'blocked': aml.blocked},
                        amount_usd,
                        tasa,
                        amount,
                    ]
                    if self.env.context.get('print_mode'):
                        columns = columns[:4] + columns[6:]
                    lines.append({
                        'id': aml.id,
                        'account_move': aml.move_id,
                        'name': aml.move_id.name,
                        'caret_options': 'followup',
                        'move_id': aml.move_id.id,
                        'type': is_payment and 'payment' or 'unreconciled_aml',
                        'unfoldable': False,
                        'columns': [type(v) == dict and v or {'name': v} for v in columns],
                    })
            total_due = formatLang(self.env, total, currency_obj=currency_id_dif)
            line_num += 1
            lines.append({
                'id': line_num,
                'name': '',
                'class': 'total',
                'style': 'border-top-style: double',
                'unfoldable': False,
                'level': 3,
                'columns': [{'name': v} for v in [''] * (3 if self.env.context.get('print_mode') else 5) + [total >= 0 and _('Total Due') or '', total_due]],
            })
            if total_issued > 0:
                total_issued = formatLang(self.env, total_issued, currency_obj=currency_id_dif)
                line_num += 1
                lines.append({
                    'id': line_num,
                    'name': '',
                    'class': 'total',
                    'unfoldable': False,
                    'level': 3,
                    'columns': [{'name': v} for v in [''] * (3 if self.env.context.get('print_mode') else 5) + [_('Total Overdue'), total_issued]],
                })
            # Add an empty line after the total to make a space between two currencies
            line_num += 1
            if len(columns)>0:
                lines.append({
                    'id': line_num,
                    'name': '',
                    'class': '',
                    'style': 'border-bottom-style: none',
                    'unfoldable': False,
                    'level': 0,
                    'columns': [{} for col in columns],
                })
        # Remove the last empty line
        if lines:
            lines.pop()
        return lines
