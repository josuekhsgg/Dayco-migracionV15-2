# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.tools.misc import format_date
from odoo.osv import expression
from datetime import date, datetime, timedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _compute_for_followup(self):
        """
        Compute the fields 'total_due', 'total_overdue','followup_level' and 'followup_status'
        """
        first_followup_level = self.env['account_followup.followup.line'].search([('company_id', '=', self.env.company.id)], order="delay asc", limit=1)
        followup_data = self._query_followup_level()
        today = fields.Date.context_today(self)
        for record in self:
            total_due = 0
            total_overdue = 0
            followup_status = "no_action_needed"
            # for aml in record.unreconciled_aml_ids:
            #     if aml.company_id == self.env.company:
            #         amount = aml.amount_residual
            #         total_due += amount
            #         is_overdue = today > aml.date_maturity if aml.date_maturity else today > aml.date
            #         if is_overdue and not aml.blocked:
            #             total_overdue += amount
            for aml in record.unpaid_invoices:
                if aml.company_id == self.env.company:
                    amount = aml.amount_residual_usd * aml.currency_id_dif.tasa_referencia
                    total_due += amount
                    l = aml.line_ids.filtered_domain([('account_id', '=', record.property_account_receivable_id.id)])
                    is_overdue = today > l.date_maturity if l.date_maturity else today > aml.date
                    if is_overdue and not l.blocked:
                        total_overdue += amount

            record.total_due = total_due
            record.total_overdue = total_overdue
            if record.id in followup_data:
                record.followup_status = followup_data[record.id]['followup_status']
                record.followup_level = self.env['account_followup.followup.line'].browse(followup_data[record.id]['followup_level']) or first_followup_level
            else:
                record.followup_status = 'no_action_needed'
                record.followup_level = first_followup_level
