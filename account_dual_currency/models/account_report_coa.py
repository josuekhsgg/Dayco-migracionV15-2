# -*- coding: utf-8 -*-
from copy import deepcopy

from odoo import models, api, _, fields
from odoo.tools.misc import formatLang, format_date

class AccountChartOfAccountReport(models.AbstractModel):
    _inherit = "account.coa.report"

    @api.model
    def _get_lines(self, options, line_id=None):
        # Create new options with 'unfold_all' to compute the initial balances.
        # Then, the '_do_query' will compute all sums/unaffected earnings/initial balances for all comparisons.
        new_options = options.copy()
        new_options['unfold_all'] = True
        options_list = self._get_options_periods_list(new_options)
        accounts_results, taxes_results = self.env['account.general.ledger']._do_query(options_list, fetch_lines=False)
        currency_dif = options['currency_dif']
        lines = []
        totals = [0.0] * (2 * (len(options_list) + 2))

        # Add lines, one per account.account record.
        for account, periods_results in accounts_results:
            sums = []
            account_balance = 0.0
            for i, period_values in enumerate(reversed(periods_results)):
                account_sum = period_values.get('sum', {})
                account_un_earn = period_values.get('unaffected_earnings', {})
                account_init_bal = period_values.get('initial_balance', {})

                if i == 0:
                    # Append the initial balances.
                    initial_balance = account_init_bal.get('balance', 0.0) + account_un_earn.get('balance', 0.0)
                    sums += [
                        initial_balance > 0 and initial_balance or 0.0,
                        initial_balance < 0 and -initial_balance or 0.0,
                    ]
                    account_balance += initial_balance

                # Append the debit/credit columns.
                sums += [
                    account_sum.get('debit', 0.0) - account_init_bal.get('debit', 0.0),
                    account_sum.get('credit', 0.0) - account_init_bal.get('credit', 0.0),
                ]
                account_balance += sums[-2] - sums[-1]

            # Append the totals.
            sums += [
                account_balance > 0 and account_balance or 0.0,
                account_balance < 0 and -account_balance or 0.0,
            ]

            # account.account report line.
            columns = []
            for i, value in enumerate(sums):
                # Update totals.
                totals[i] += value

                # Create columns.
                columns.append(
                    {'name': self.format_value(value, blank_if_zero=True) if currency_dif == 'Bs' else self.format_value_usd(value, blank_if_zero=True), 'class': 'number', 'no_format_name': value})

            name = account.name_get()[0][1]

            lines.append({
                'id': self._get_generic_line_id('account.account', account.id),
                'name': name,
                'title_hover': name,
                'columns': columns,
                'unfoldable': False,
                'caret_options': 'account.account',
                'class': 'o_account_searchable_line o_account_coa_column_contrast',
            })

        # Total report line.
        lines.append({
            'id': self._get_generic_line_id(None, None, markup='grouped_accounts_total'),
            'name': _('Total'),
            'class': 'total o_account_coa_column_contrast',
            'columns': [{'name': self.format_value(total) if currency_dif == 'Bs' else self.format_value_usd(total), 'class': 'number'} for total in totals],
            'level': 1,
        })

        return lines