import copy
import json
from odoo import models, fields, api, _
from odoo.tools.misc import formatLang

class ReportAccountFinancialReport(models.Model):
    _inherit = "account.financial.html.report"
    _description = "Account Report Dual Currency (HTML)"

    # @api.model
    # def _get_options(self, previous_options=None):
    #     rslt = super()._get_options(previous_options)
    #     currency_dif = 'Bs'
    #     if previous_options:
    #         if "currency_dif" in previous_options:
    #             currency_dif = previous_options['currency_dif']
    #     previous_options['currency_dif'] = currency_dif
    #     return rslt

    def _get_options(self, previous_options=None):
        # OVERRIDE
        options = super(ReportAccountFinancialReport, self)._get_options(previous_options)

        # If manual values were stored in the context, we store them as options.
        # This is useful for report printing, were relying only on the context is
        # not enough, because of the use of a route to download the report (causing
        # a context loss, but keeping the options).
        if self._context.get('financial_report_line_values'):
            options['financial_report_line_values'] = self.env.context['financial_report_line_values']
        currency_dif = 'Bs'
        if previous_options:
            if "currency_dif" in previous_options:
                currency_dif = previous_options['currency_dif']
        options['currency_dif'] = currency_dif
        return options

    # def get_report_informations(self, options):
    #     '''
    #     return a dictionary of informations that will be needed by the js widget, manager_id, footnotes, html of report and searchview, ...
    #     '''
    #
    #     currency_dif = 'Bs'
    #     if options:
    #         if "currency_dif" in options:
    #             currency_dif = options['currency_dif']
    #     options = self._get_options(options)
    #     options['currency_dif'] = currency_dif
    #     searchview_dict = {'options': options, 'context': self.env.context}
    #
    #     # Check if report needs analytic
    #     if options.get('analytic_accounts') is not None:
    #         options['selected_analytic_account_names'] = [self.env['account.analytic.account'].browse(int(account)).name for account in options['analytic_accounts']]
    #     if options.get('analytic_tags') is not None:
    #         options['selected_analytic_tag_names'] = [self.env['account.analytic.tag'].browse(int(tag)).name for tag in options['analytic_tags']]
    #     if options.get('partner'):
    #         options['selected_partner_ids'] = [self.env['res.partner'].browse(int(partner)).name for partner in options['partner_ids']]
    #         options['selected_partner_categories'] = [self.env['res.partner.category'].browse(int(category)).name for category in (options.get('partner_categories') or [])]
    #
    #     # Check whether there are unposted entries for the selected period or not (if the report allows it)
    #     if options.get('date') and options.get('all_entries') is not None:
    #         date_to = options['date'].get('date_to') or options['date'].get('date') or fields.Date.today()
    #         period_domain = [('state', '=', 'draft'), ('date', '<=', date_to)]
    #         options['unposted_in_period'] = bool(self.env['account.move'].search_count(period_domain))
    #
    #     if options.get('journals'):
    #         journals_selected = set(journal['id'] for journal in options['journals'] if journal.get('selected'))
    #         for journal_group in self.env['account.journal.group'].search([('company_id', '=', self.env.company.id)]):
    #             if journals_selected and journals_selected == set(self._get_filter_journals().ids) - set(journal_group.excluded_journal_ids.ids):
    #                 options['name_journal_group'] = journal_group.name
    #                 break
    #
    #     report_manager = self._get_report_manager(options)
    #     if "currency_dif" in options:
    #         info = {'options': options,
    #             'context': self.env.context,
    #             'report_manager_id': report_manager.id,
    #             'footnotes': [{'id': f.id, 'line': f.line, 'text': f.text} for f in report_manager.footnotes_ids],
    #             'buttons': self._get_reports_buttons_in_sequence(options),
    #             'main_html': self.get_html(options),
    #             'searchview_html': self.env['ir.ui.view']._render_template(self._get_templates_new().get('search_template', 'account_dual_currency.search_template_generic_currency_dif'), values=searchview_dict),
    #             }
    #     else:
    #         info = {'options': options,
    #                 'context': self.env.context,
    #                 'report_manager_id': report_manager.id,
    #                 'footnotes': [{'id': f.id, 'line': f.line, 'text': f.text} for f in report_manager.footnotes_ids],
    #                 'buttons': self._get_reports_buttons_in_sequence(options),
    #                 'main_html': self.get_html(options),
    #                 'searchview_html': self.env['ir.ui.view']._render_template(
    #                     self._get_templates().get('search_template','account_dual_currency.search_template_generic_currency_dif'),
    #                     values=searchview_dict),
    #                 }
    #     return info

    @api.model
    def _format_cell_value_usd(self, financial_line, amount, currency=False, blank_if_zero=False):
        ''' Format the value to display inside a cell depending the 'figure_type' field in the financial report line.
        :param financial_line:  An account.financial.html.report.line record.
        :param amount:          A number.
        :param currency:        An optional res.currency record.
        :param blank_if_zero:   An optional flag forcing the string to be empty if amount is zero.
        :return:
        '''
        if not financial_line.formulas:
            return ''

        if self._context.get('no_format'):
            return amount

        if financial_line.figure_type == 'float':
            return super().format_value_usd(amount, currency=currency, blank_if_zero=blank_if_zero)
        elif financial_line.figure_type == 'percents':
            return str(round(amount * 100, 1)) + '%'
        elif financial_line.figure_type == 'no_unit':
            return round(amount, 1)
        return amount

    @api.model
    def format_value_usd(self, amount, currency=False, blank_if_zero=False):
        ''' Format amount to have a monetary display (with a currency symbol).
        E.g: 1000 => 1000.0 $

        :param amount:          A number.
        :param currency:        An optional res.currency record.
        :param blank_if_zero:   An optional flag forcing the string to be empty if amount is zero.
        :return:                The formatted amount as a string.
        '''
        currency_id = self.env.company.currency_id_dif
        if currency_id.is_zero(amount):
            if blank_if_zero:
                return ''
            # don't print -0.0 in reports
            amount = abs(amount)

        if self.env.context.get('no_format'):
            return amount
        return formatLang(self.env, amount, currency_obj=currency_id)

    @api.model
    def _compute_debug_info_column(self, options, solver, financial_line):
        ''' Helper to get the additional columns to display the debug info popup.
        :param options:             The report options.
        :param solver:              The FormulaSolver instance used to compute the formulas.
        :param financial_line:      An account.financial.html.report.line record.
        :return:                    The new columns to add to line['columns'].
        '''
        if financial_line.formulas:
            results = solver.get_results(financial_line)
            if "currency_dif" in options:
                return {
                    'style': 'width: 1%; text-align: right;',
                    'template': 'account_reports.cell_template_debug_popup_financial_reports',
                    'line_code': financial_line.code or '',
                    'popup_template': 'accountReports.FinancialReportInfosTemplate',
                    'popup_class': 'fa fa-info-circle',
                    'popup_attributes': {'tabindex': 1},
                    'popup_data': json.dumps({
                        'id': financial_line.id,
                        'name': financial_line.name,
                        'code': financial_line.code or '',
                        'formula': solver.get_formula_popup(financial_line),
                        'formula_with_values': solver.get_formula_string(financial_line),
                        'formula_balance': self._format_cell_value_usd(financial_line, sum(results['formula'].values()))
                                    if options['currency_dif'] == 'USD' else self._format_cell_value(financial_line,
                                                                                                         sum(results['formula'].values())),
                        'domain': str(financial_line.domain) if solver.is_leaf(
                            financial_line) and financial_line.domain else '',
                        'display_button': solver.has_move_lines(financial_line),
                    }),
                }
            else:
                return {
                    'style': 'width: 1%; text-align: right;',
                    'template': 'account_reports.cell_template_debug_popup_financial_reports',
                    'line_code': financial_line.code or '',
                    'popup_template': 'accountReports.FinancialReportInfosTemplate',
                    'popup_class': 'fa fa-info-circle',
                    'popup_attributes': {'tabindex': 1},
                    'popup_data': json.dumps({
                        'id': financial_line.id,
                        'name': financial_line.name,
                        'code': financial_line.code or '',
                        'formula': solver.get_formula_popup(financial_line),
                        'formula_with_values': solver.get_formula_string(financial_line),
                        'formula_balance': self._format_cell_value(financial_line, sum(results['formula'].values())),
                        'domain': str(financial_line.domain) if solver.is_leaf(
                            financial_line) and financial_line.domain else '',
                        'display_button': solver.has_move_lines(financial_line),
                    }),
                }
        else:
            return {'style': 'width: 1%;'}

    @api.model
    def _get_financial_line_report_line(self, options, financial_line, solver, groupby_keys):
        ''' Create the report line for an account.financial.html.report.line record.
        :param options:             The report options.
        :param financial_line:      An account.financial.html.report.line record.
        :param solver_results:      An instance of the FormulaSolver class.
        :param groupby_keys:        The sorted encountered keys in the solver.
        :return:                    The dictionary corresponding to a line to be rendered.
        '''
        results = solver.get_results(financial_line)['formula']

        is_leaf = solver.is_leaf(financial_line)
        has_lines = solver.has_move_lines(financial_line)
        has_something_to_unfold = is_leaf and has_lines and bool(financial_line.groupby)

        # Compute if the line is unfoldable or not.
        is_unfoldable = has_something_to_unfold and financial_line.show_domain == 'foldable'

        # Compute if the line is unfolded or not.
        # /!\ Take care about the case when the line is unfolded but not unfoldable with show_domain == 'always'.
        if not has_something_to_unfold or financial_line.show_domain == 'never':
            is_unfolded = False
        elif financial_line.show_domain == 'always':
            is_unfolded = True
        elif financial_line.show_domain == 'foldable' and financial_line.id in options['unfolded_lines']:
            is_unfolded = True
        else:
            is_unfolded = False

        # Standard columns.
        columns = []
        for key in groupby_keys:
            amount = results.get(key, 0.0)
            if "currency_dif" in options:
                columns.append(
                    {'name': self._format_cell_value_usd(financial_line, amount) if options['currency_dif'] == 'USD' else self._format_cell_value(financial_line, amount), 'no_format': amount, 'class': 'number'})
            else:
                columns.append(
                    {'name': self._format_cell_value(financial_line, amount), 'no_format': amount, 'class': 'number'})
        # Growth comparison column.
        if self._display_growth_comparison(options):
            columns.append(self._compute_growth_comparison_column(options,
                                                                  columns[0]['no_format'],
                                                                  columns[1]['no_format'],
                                                                  green_on_positive=financial_line.green_on_positive
                                                                  ))

        # Debug info columns.
        if self._display_debug_info(options):
            columns.append(self._compute_debug_info_column(options, solver, financial_line))

        financial_report_line = {
            'id': financial_line.id,
            'name': financial_line.name,
            'level': financial_line.level,
            'class': 'o_account_reports_totals_below_sections' if self.env.company.totals_below_sections else '',
            'columns': columns,
            'unfoldable': is_unfoldable,
            'unfolded': is_unfolded,
            'page_break': financial_line.print_on_new_page,
            'action_id': financial_line.action_id.id,
        }

        # Custom caret_options for tax report.
        if self.tax_report and financial_line.domain and not financial_line.action_id:
            financial_report_line['caret_options'] = 'tax.report.line'

        return financial_report_line

    @api.model
    def _get_financial_aml_report_line(self, options, financial_line, groupby_id, display_name, results, groupby_keys):
        ''' Create the report line for the account.move.line grouped by any key.
        :param options:             The report options.
        :param financial_line:      An account.financial.html.report.line record.
        :param groupby_id:          The key used as the vertical group_by. It could be a record's id or a value for regular field.
        :param display_name:        The full name of the line to display.
        :param results:             The results given by the FormulaSolver class for the given line.
        :param groupby_keys:        The sorted encountered keys in the solver.
        :return:                    The dictionary corresponding to a line to be rendered.
        '''
        # Standard columns.
        columns = []
        for key in groupby_keys:
            amount = results.get(key, 0.0)
            if "currency_dif" in options:
                columns.append(
                    {'name': self._format_cell_value_usd(financial_line, amount) if options['currency_dif'] == 'USD' else self._format_cell_value(financial_line, amount), 'no_format': amount, 'class': 'number'})
            else:
                columns.append(
                    {'name': self._format_cell_value(financial_line, amount), 'no_format': amount, 'class': 'number'})
        # Growth comparison column.
        if self._display_growth_comparison(options):
            columns.append(self._compute_growth_comparison_column(options,
                                                                  columns[0]['no_format'],
                                                                  columns[1]['no_format'],
                                                                  green_on_positive=financial_line.green_on_positive
                                                                  ))

        if self._display_debug_info(options):
            columns.append({'name': '', 'style': 'width: 1%;'})

        return {
            'id': 'financial_report_group_%s_%s' % (financial_line.id, groupby_id),
            'name': display_name,
            'level': financial_line.level + 1,
            'parent_id': financial_line.id,
            'caret_options': financial_line.groupby == 'account_id' and 'account.account' or financial_line.groupby,
            'columns': columns,
        }

class AccountFinancialReportLine(models.Model):
    _inherit = "account.financial.html.report.line"

    def _compute_amls_results(self, options_list, calling_financial_report=None, sign=1):
        ''' Compute the results for the unfolded lines by taking care about the line order and the group by filter.

        Suppose the line has '-sum' as formulas with 'partner_id' in groupby and 'currency_id' in group by filter.
        The result will be something like:
        [
            (0, 'partner 0', {(0,1): amount1, (0,2): amount2, (1,1): amount3}),
            (1, 'partner 1', {(0,1): amount4, (0,2): amount5, (1,1): amount6}),
            ...               |
        ]    |                |
             |__ res.partner ids
                              |_ key where the first element is the period number, the second one being a res.currency id.

        :param options_list:                The report options list, first one being the current dates range, others
                                            being the comparisons.
        :param calling_financial_report:    The financial report called by the user to be rendered.
        :param sign:                        1 or -1 to get negative values in case of '-sum' formula.
        :return:                            A list (groupby_key, display_name, {key: <balance>...}).
        '''
        self.ensure_one()
        params = []
        queries = []

        AccountFinancialReportHtml = self.financial_report_id
        horizontal_groupby_list = AccountFinancialReportHtml._get_options_groupby_fields(options_list[0])
        groupby_list = [self.groupby] + horizontal_groupby_list
        groupby_clause = ','.join('account_move_line.%s' % gb for gb in groupby_list)
        groupby_field = self.env['account.move.line']._fields[self.groupby]

        ct_query = self.env['res.currency']._get_query_currency_table(options_list[0])
        parent_financial_report = self._get_financial_report()

        # Prepare a query by period as the date is different for each comparison.

        for i, options in enumerate(options_list):
            new_options = self._get_options_financial_line(options, calling_financial_report, parent_financial_report)
            line_domain = self._get_domain(new_options, parent_financial_report)

            tables, where_clause, where_params = AccountFinancialReportHtml._query_get(new_options, domain=line_domain)

            if "currency_dif" in options:
                if options['currency_dif'] == 'USD':
                    queries.append('''
                        SELECT
                            ''' + (groupby_clause and '%s,' % groupby_clause) + '''
                            %s AS period_index,
                            COALESCE(SUM(ROUND(%s * account_move_line.balance_usd, currency_table.precision)), 0.0) AS balance
                        FROM ''' + tables + '''
                        JOIN ''' + ct_query + ''' ON currency_table.company_id = account_move_line.company_id
                        WHERE ''' + where_clause + '''
                        ''' + (groupby_clause and 'GROUP BY %s' % groupby_clause) + '''
                    ''')
                else:
                    queries.append('''
                                                        SELECT
                                                            ''' + (groupby_clause and '%s,' % groupby_clause) + '''
                                                            %s AS period_index,
                                                            COALESCE(SUM(ROUND(%s * account_move_line.balance * currency_table.rate, currency_table.precision)), 0.0) AS balance
                                                        FROM ''' + tables + '''
                                                        JOIN ''' + ct_query + ''' ON currency_table.company_id = account_move_line.company_id
                                                        WHERE ''' + where_clause + '''
                                                        ''' + (groupby_clause and 'GROUP BY %s' % groupby_clause) + '''
                                                    ''')
            else:
                queries.append('''
                                    SELECT
                                        ''' + (groupby_clause and '%s,' % groupby_clause) + '''
                                        %s AS period_index,
                                        COALESCE(SUM(ROUND(%s * account_move_line.balance * currency_table.rate, currency_table.precision)), 0.0) AS balance
                                    FROM ''' + tables + '''
                                    JOIN ''' + ct_query + ''' ON currency_table.company_id = account_move_line.company_id
                                    WHERE ''' + where_clause + '''
                                    ''' + (groupby_clause and 'GROUP BY %s' % groupby_clause) + '''
                                ''')
            params += [i, sign] + where_params

        # Fetch the results.
        # /!\ Take care of both vertical and horizontal group by clauses.

        results = {}

        #parent_financial_report._cr_execute(options_list[0], ' UNION ALL '.join(queries), params)
        self._cr.execute(' UNION ALL '.join(queries), params)
        for res in self._cr.dictfetchall():
            # Build the key.
            key = [res['period_index']]
            for gb in horizontal_groupby_list:
                key.append(res[gb])
            key = tuple(key)

            results.setdefault(res[self.groupby], {})
            results[res[self.groupby]][key] = res['balance']

        # Sort the lines according to the vertical groupby and compute their display name.
        if groupby_field.relational:
            # Preserve the table order by using search instead of browse.
            sorted_records = self.env[groupby_field.comodel_name].search([('id', 'in', tuple(results.keys()))])
            sorted_values = sorted_records.name_get()
        else:
            # Sort the keys in a lexicographic order.
            sorted_values = [(v, v) for v in sorted(list(results.keys()))]

        return [(groupby_key, display_name, results[groupby_key]) for groupby_key, display_name in sorted_values]

    def _compute_sum(self, options_list, calling_financial_report=None):
        ''' Compute the values to be used inside the formula for the current line.
        If called, it means the current line formula contains something making its line a leaf ('sum' or 'count_rows')
        for example.

        The results is something like:
        {
            'sum':                  {key: <balance>...},
            'sum_if_pos':           {key: <balance>...},
            'sum_if_pos_groupby':   {key: <balance>...},
            'sum_if_neg':           {key: <balance>...},
            'sum_if_neg_groupby':   {key: <balance>...},
            'count_rows':           {period_index: <number_of_rows_in_period>...},
        }

        ... where:
        'period_index' is the number of the period, 0 being the current one, others being comparisons.

        'key' is a composite key containing the period_index and the additional group by enabled on the financial report.
        For example, suppose a group by 'partner_id':

        The keys could be something like (0,1), (1,2), (1,3), meaning:
        * (0,1): At the period 0, the results for 'partner_id = 1' are...
        * (1,2): At the period 1 (first comparison), the results for 'partner_id = 2' are...
        * (1,3): At the period 1 (first comparison), the results for 'partner_id = 3' are...

        :param options_list:                The report options list, first one being the current dates range, others
                                            being the comparisons.
        :param calling_financial_report:    The financial report called by the user to be rendered.
        :return:                            A python dictionary.
        '''
        self.ensure_one()
        params = []
        queries = []

        AccountFinancialReportHtml = self.financial_report_id
        groupby_list = AccountFinancialReportHtml._get_options_groupby_fields(options_list[0])
        all_groupby_list = groupby_list.copy()
        groupby_in_formula = any(x in (self.formulas or '') for x in ('sum_if_pos_groupby', 'sum_if_neg_groupby'))
        if groupby_in_formula and self.groupby and self.groupby not in all_groupby_list:
            all_groupby_list.append(self.groupby)
        groupby_clause = ','.join('account_move_line.%s' % gb for gb in all_groupby_list)

        ct_query = self.env['res.currency']._get_query_currency_table(options_list[0])
        parent_financial_report = self._get_financial_report()

        # Prepare a query by period as the date is different for each comparison.

        for i, options in enumerate(options_list):
            new_options = self._get_options_financial_line(options, calling_financial_report, parent_financial_report)
            line_domain = self._get_domain(new_options, parent_financial_report)

            tables, where_clause, where_params = AccountFinancialReportHtml._query_get(new_options, domain=line_domain)
            if "currency_dif" in options:
                if options['currency_dif'] == 'USD':
                    queries.append('''
                        SELECT
                            ''' + (groupby_clause and '%s,' % groupby_clause) + ''' %s AS period_index,
                            COUNT(DISTINCT account_move_line.''' + (self.groupby or 'id') + ''') AS count_rows,
                            COALESCE(SUM(ROUND(account_move_line.balance_usd, currency_table.precision)), 0.0) AS balance
                        FROM ''' + tables + '''
                        JOIN ''' + ct_query + ''' ON currency_table.company_id = account_move_line.company_id
                        WHERE ''' + where_clause + '''
                        ''' + (groupby_clause and 'GROUP BY %s' % groupby_clause) + '''
                    ''')
                else:
                    queries.append('''
                                        SELECT
                                            ''' + (groupby_clause and '%s,' % groupby_clause) + ''' %s AS period_index,
                                            COUNT(DISTINCT account_move_line.''' + (self.groupby or 'id') + ''') AS count_rows,
                                            COALESCE(SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)), 0.0) AS balance
                                        FROM ''' + tables + '''
                                        JOIN ''' + ct_query + ''' ON currency_table.company_id = account_move_line.company_id
                                        WHERE ''' + where_clause + '''
                                        ''' + (groupby_clause and 'GROUP BY %s' % groupby_clause) + '''
                                    ''')
            else:
                queries.append('''
                                    SELECT
                                        ''' + (groupby_clause and '%s,' % groupby_clause) + ''' %s AS period_index,
                                        COUNT(DISTINCT account_move_line.''' + (self.groupby or 'id') + ''') AS count_rows,
                                        COALESCE(SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)), 0.0) AS balance
                                    FROM ''' + tables + '''
                                    JOIN ''' + ct_query + ''' ON currency_table.company_id = account_move_line.company_id
                                    WHERE ''' + where_clause + '''
                                    ''' + (groupby_clause and 'GROUP BY %s' % groupby_clause) + '''
                                ''')
            params.append(i)
            params += where_params

        # Fetch the results.

        results = {
            'sum': {},
            'sum_if_pos': {},
            'sum_if_pos_groupby': {},
            'sum_if_neg': {},
            'sum_if_neg_groupby': {},
            'count_rows': {},
        }

        #parent_financial_report._cr_execute(options_list[0], ' UNION ALL '.join(queries), params)
        self._cr.execute(' UNION ALL '.join(queries), params)
        for res in self._cr.dictfetchall():
            # Build the key.
            key = [res['period_index']]
            for gb in groupby_list:
                key.append(res[gb])
            key = tuple(key)

            # Compute values.
            results['count_rows'].setdefault(res['period_index'], 0)
            results['count_rows'][res['period_index']] += res['count_rows']
            results['sum'][key] = res['balance']
            if results['sum'][key] > 0:
                results['sum_if_pos'][key] = results['sum'][key]
                results['sum_if_pos_groupby'].setdefault(key, 0.0)
                results['sum_if_pos_groupby'][key] += res['balance']
            if results['sum'][key] < 0:
                results['sum_if_neg'][key] = results['sum'][key]
                results['sum_if_neg_groupby'].setdefault(key, 0.0)
                results['sum_if_neg_groupby'][key] += res['balance']

        return results

