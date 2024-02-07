# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools.misc import format_date, DEFAULT_SERVER_DATE_FORMAT
from datetime import timedelta

class AccountGeneralLedgerReport(models.AbstractModel):
    _inherit = "account.general.ledger"

    @api.model
    def _get_query_sums(self, options_list, expanded_account=None):
        ''' Construct a query retrieving all the aggregated sums to build the report. It includes:
        - sums for all accounts.
        - sums for the initial balances.
        - sums for the unaffected earnings.
        - sums for the tax declaration.
        :param options_list:        The report options list, first one being the current dates range, others being the
                                    comparisons.
        :param expanded_account:    An optional account.account record that must be specified when expanding a line
                                    with of without the load more.
        :return:                    (query, params)
        '''
        options = options_list[0]
        unfold_all = options.get('unfold_all') or (self._context.get('print_mode') and not options['unfolded_lines'])
        currency_dif = options['currency_dif']
        params = []
        queries = []

        # Create the currency table.
        # As the currency table is the same whatever the comparisons, create it only once.
        ct_query = self.env['res.currency']._get_query_currency_table(options)

        # ============================================
        # 1) Get sums for all accounts.
        # ============================================

        domain = [('account_id', '=', expanded_account.id)] if expanded_account else []

        for i, options_period in enumerate(options_list):
            # The period domain is expressed as:
            # [
            #   ('date' <= options['date_to']),
            #   '|',
            #   ('date' >= fiscalyear['date_from']),
            #   ('account_id.user_type_id.include_initial_balance', '=', True),
            # ]

            new_options = self._get_options_sum_balance(options_period)
            tables, where_clause, where_params = self._query_get(new_options, domain=domain)
            params += where_params
            if currency_dif == 'Bs':
                queries.append('''
                        SELECT
                            account_move_line.account_id                            AS groupby,
                            'sum'                                                   AS key,
                            MAX(account_move_line.date)                             AS max_date,
                            %s                                                      AS period_number,
                            COALESCE(SUM(account_move_line.amount_currency), 0.0)   AS amount_currency,
                            SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                            SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                            SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                        FROM %s
                        LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                        WHERE %s
                        GROUP BY account_move_line.account_id
                    ''' % (i, tables, ct_query, where_clause))
            else:
                queries.append('''
                                        SELECT
                                            account_move_line.account_id                            AS groupby,
                                            'sum'                                                   AS key,
                                            MAX(account_move_line.date)                             AS max_date,
                                            %s                                                      AS period_number,
                                            COALESCE(SUM(account_move_line.amount_currency), 0.0)   AS amount_currency,
                                            SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                                            SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                                            SUM(ROUND((account_move_line.debit_usd - account_move_line.credit_usd), currency_table.precision)) AS balance
                                        FROM %s
                                        LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                                        WHERE %s
                                        GROUP BY account_move_line.account_id
                                    ''' % (i, tables, ct_query, where_clause))

        # ============================================
        # 2) Get sums for the unaffected earnings.
        # ============================================

        domain = [('account_id.user_type_id.include_initial_balance', '=', False)]
        if expanded_account:
            domain.append(('company_id', '=', expanded_account.company_id.id))

        # Compute only the unaffected earnings for the oldest period.

        i = len(options_list) - 1
        options_period = options_list[-1]

        # The period domain is expressed as:
        # [
        #   ('date' <= fiscalyear['date_from'] - 1),
        #   ('account_id.user_type_id.include_initial_balance', '=', False),
        # ]

        new_options = self._get_options_unaffected_earnings(options_period)
        tables, where_clause, where_params = self._query_get(new_options, domain=domain)
        params += where_params
        if currency_dif == 'Bs':
            queries.append('''
                    SELECT
                        account_move_line.company_id                            AS groupby,
                        'unaffected_earnings'                                   AS key,
                        NULL                                                    AS max_date,
                        %s                                                      AS period_number,
                        COALESCE(SUM(account_move_line.amount_currency), 0.0)   AS amount_currency,
                        SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM %s
                    LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                    WHERE %s
                    GROUP BY account_move_line.company_id
                ''' % (i, tables, ct_query, where_clause))
        else:
            queries.append('''
                                SELECT
                                    account_move_line.company_id                            AS groupby,
                                    'unaffected_earnings'                                   AS key,
                                    NULL                                                    AS max_date,
                                    %s                                                      AS period_number,
                                    COALESCE(SUM(account_move_line.amount_currency), 0.0)   AS amount_currency,
                                    SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                                    SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                                    SUM(ROUND((account_move_line.debit_usd - account_move_line.credit_usd), currency_table.precision)) AS balance
                                FROM %s
                                LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                                WHERE %s
                                GROUP BY account_move_line.company_id
                            ''' % (i, tables, ct_query, where_clause))

        # ============================================
        # 3) Get sums for the initial balance.
        # ============================================

        domain = []
        if expanded_account:
            domain = [('account_id', '=', expanded_account.id)]
        elif not unfold_all and options['unfolded_lines']:
            domain = [('account_id', 'in', [int(line[8:]) for line in options['unfolded_lines']])]

        for i, options_period in enumerate(options_list):
            # The period domain is expressed as:
            # [
            #   ('date' <= options['date_from'] - 1),
            #   '|',
            #   ('date' >= fiscalyear['date_from']),
            #   ('account_id.user_type_id.include_initial_balance', '=', True)
            # ]

            new_options = self._get_options_initial_balance(options_period)
            tables, where_clause, where_params = self._query_get(new_options, domain=domain)
            params += where_params
            if currency_dif == 'Bs':
                queries.append('''
                        SELECT
                            account_move_line.account_id                            AS groupby,
                            'initial_balance'                                       AS key,
                            NULL                                                    AS max_date,
                            %s                                                      AS period_number,
                            COALESCE(SUM(account_move_line.amount_currency), 0.0)   AS amount_currency,
                            SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                            SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                            SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                        FROM %s
                        LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                        WHERE %s
                        GROUP BY account_move_line.account_id
                    ''' % (i, tables, ct_query, where_clause))
            else:
                queries.append('''
                                        SELECT
                                            account_move_line.account_id                            AS groupby,
                                            'initial_balance'                                       AS key,
                                            NULL                                                    AS max_date,
                                            %s                                                      AS period_number,
                                            COALESCE(SUM(account_move_line.amount_currency), 0.0)   AS amount_currency,
                                            SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                                            SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                                            SUM(ROUND((account_move_line.debit_usd - account_move_line.credit_usd), currency_table.precision)) AS balance
                                        FROM %s
                                        LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                                        WHERE %s
                                        GROUP BY account_move_line.account_id
                                    ''' % (i, tables, ct_query, where_clause))

        # ============================================
        # 4) Get sums for the tax declaration.
        # ============================================

        journal_options = self._get_options_journals(options)
        if not expanded_account and len(journal_options) == 1 and journal_options[0]['type'] in ('sale', 'purchase'):
            for i, options_period in enumerate(options_list):
                tables, where_clause, where_params = self._query_get(options_period)
                params += where_params + where_params
                if currency_dif == 'Bs':
                    queries += ['''
                            SELECT
                                tax_rel.account_tax_id                  AS groupby,
                                'base_amount'                           AS key,
                                NULL                                    AS max_date,
                                %s                                      AS period_number,
                                0.0                                     AS amount_currency,
                                0.0                                     AS debit,
                                0.0                                     AS credit,
                                SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                            FROM account_move_line_account_tax_rel tax_rel, %s
                            LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                            WHERE account_move_line.id = tax_rel.account_move_line_id AND %s
                            GROUP BY tax_rel.account_tax_id
                        ''' % (i, tables, ct_query, where_clause), '''
                            SELECT
                            account_move_line.tax_line_id               AS groupby,
                            'tax_amount'                                AS key,
                                NULL                                    AS max_date,
                                %s                                      AS period_number,
                                0.0                                     AS amount_currency,
                                0.0                                     AS debit,
                                0.0                                     AS credit,
                                SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                            FROM %s
                            LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                            WHERE %s
                            GROUP BY account_move_line.tax_line_id
                        ''' % (i, tables, ct_query, where_clause)]
                else:
                    queries += ['''
                                                SELECT
                                                    tax_rel.account_tax_id                  AS groupby,
                                                    'base_amount'                           AS key,
                                                    NULL                                    AS max_date,
                                                    %s                                      AS period_number,
                                                    0.0                                     AS amount_currency,
                                                    0.0                                     AS debit,
                                                    0.0                                     AS credit,
                                                    SUM(ROUND((account_move_line.debit_usd - account_move_line.credit_usd), currency_table.precision)) AS balance
                                                FROM account_move_line_account_tax_rel tax_rel, %s
                                                LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                                                WHERE account_move_line.id = tax_rel.account_move_line_id AND %s
                                                GROUP BY tax_rel.account_tax_id
                                            ''' % (i, tables, ct_query, where_clause), '''
                                                SELECT
                                                account_move_line.tax_line_id               AS groupby,
                                                'tax_amount'                                AS key,
                                                    NULL                                    AS max_date,
                                                    %s                                      AS period_number,
                                                    0.0                                     AS amount_currency,
                                                    0.0                                     AS debit,
                                                    0.0                                     AS credit,
                                                    SUM(ROUND((account_move_line.debit_usd - account_move_line.credit_usd), currency_table.precision)) AS balance
                                                FROM %s
                                                LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                                                WHERE %s
                                                GROUP BY account_move_line.tax_line_id
                                            ''' % (i, tables, ct_query, where_clause)]

        return ' UNION ALL '.join(queries), params

    def _get_query_amls(self, options, expanded_account, offset=None, limit=None):
        ''' Construct a query retrieving the account.move.lines when expanding a report line with or without the load
        more.
        :param options:             The report options.
        :param expanded_account:    The account.account record corresponding to the expanded line.
        :param offset:              The offset of the query (used by the load more).
        :param limit:               The limit of the query (used by the load more).
        :return:                    (query, params)
        '''

        unfold_all = options.get('unfold_all') or (self._context.get('print_mode') and not options['unfolded_lines'])

        # Get sums for the account move lines.
        # period: [('date' <= options['date_to']), ('date', '>=', options['date_from'])]
        if expanded_account:
            domain = [('account_id', '=', expanded_account.id)]
        elif unfold_all:
            domain = []
        elif options['unfolded_lines']:
            domain = [('account_id', 'in', [int(line[8:]) for line in options['unfolded_lines']])]
        currency_dif = options['currency_dif']
        new_options = self._force_strict_range(options)
        tables, where_clause, where_params = self._query_get(new_options, domain=domain)
        ct_query = self.env['res.currency']._get_query_currency_table(options)
        select = self._get_query_amls_select_clause()
        from_clause = self._get_query_amls_from_clause()
        if currency_dif != 'Bs':
            select = select.replace('account_move_line.debit * currency_table.rate', 'account_move_line.debit_usd')
            select = select.replace('account_move_line.credit * currency_table.rate', 'account_move_line.credit_usd')
            select = select.replace('account_move_line.balance * currency_table.rate', 'account_move_line.balance_usd')

        print('select', select)
        query = '''
            SELECT %s
            FROM %s
            WHERE %s
            ORDER BY account_move_line.date, account_move_line.id
        ''' % (select, from_clause % (tables, ct_query), where_clause)

        if offset:
            query += ' OFFSET %s '
            where_params.append(offset)
        if limit:
            query += ' LIMIT %s '
            where_params.append(limit)

        return query, where_params

    @api.model
    def _get_columns_name(self, options):
        columns_names = [
            {'name': ''},
            {'name': _('Date'), 'class': 'date'},
            {'name': _('Communication')},
            {'name': _('Partner')},
            {'name': _('Debit'), 'class': 'number'},
            {'name': _('Credit'), 'class': 'number'},
            {'name': _('Balance'), 'class': 'number'}
        ]
        #if self.user_has_groups('base.group_multi_currency'):
        #    columns_names.insert(4, {'name': _('Currency'), 'class': 'number'})
        return columns_names

    @api.model
    def _get_account_title_line(self, options, account, amount_currency, debit, credit, balance, has_lines):
        currency_dif = options['currency_dif']

        has_foreign_currency = account.currency_id and account.currency_id != account.company_id.currency_id or False
        unfold_all = self._context.get('print_mode') and not options.get('unfolded_lines')

        name = '%s %s' % (account.code, account.name)
        columns = [
            {'name': self.format_value(debit) if currency_dif == 'Bs' else self.format_value_usd(debit), 'class': 'number'},
            {'name': self.format_value(credit) if currency_dif == 'Bs' else self.format_value_usd(credit), 'class': 'number'},
            {'name': self.format_value(balance) if currency_dif == 'Bs' else self.format_value_usd(balance), 'class': 'number'},
        ]
        #if self.user_has_groups('base.group_multi_currency'):
        #    columns.insert(0, {
        #        'name': has_foreign_currency and self.format_value(amount_currency, currency=account.currency_id,
        #                                                           blank_if_zero=True) or '', 'class': 'number'})
        return {
            'id': 'account_%d' % account.id,
            'name': name,
            'columns': columns,
            'level': 1,
            'unfoldable': has_lines,
            'unfolded': has_lines and 'account_%d' % account.id in options.get('unfolded_lines') or unfold_all,
            'colspan': 4,
            'class': 'o_account_reports_totals_below_sections' if self.env.company.totals_below_sections else '',
        }

    @api.model
    def _get_initial_balance_line(self, options, account, amount_currency, debit, credit, balance):
        currency_dif = options['currency_dif']
        columns = [
            {'name': self.format_value(debit) if currency_dif == 'Bs' else self.format_value_usd(debit), 'class': 'number'},
            {'name': self.format_value(credit) if currency_dif == 'Bs' else self.format_value_usd(credit), 'class': 'number'},
            {'name': self.format_value(balance) if currency_dif == 'Bs' else self.format_value_usd(balance), 'class': 'number'},
        ]

        has_foreign_currency = account.currency_id and account.currency_id != account.company_id.currency_id or False
        #if self.user_has_groups('base.group_multi_currency'):
        #    columns.insert(0, {
        #        'name': has_foreign_currency and self.format_value(amount_currency, currency=account.currency_id,
        #                                                           blank_if_zero=True) or '', 'class': 'number'})
        return {
            'id': 'initial_%d' % account.id,
            'class': 'o_account_reports_initial_balance',
            'name': _('Initial Balance'),
            'parent_id': 'account_%d' % account.id,
            'columns': columns,
            'colspan': 4,
        }

    @api.model
    def _get_aml_line(self, options, account, aml, cumulated_balance):
        currency_dif = options['currency_dif']
        if aml['payment_id']:
            caret_type = 'account.payment'
        else:
            caret_type = 'account.move'

        if (aml['currency_id'] and aml['currency_id'] != account.company_id.currency_id.id) or account.currency_id:
            currency = self.env['res.currency'].browse(aml['currency_id'])
        else:
            currency = False

        columns = [
            {'name': format_date(self.env, aml['date']), 'class': 'date'},
            {'name': self._format_aml_name(aml['name'], aml['ref']), 'class': 'o_account_report_line_ellipsis'},
            {'name': aml['partner_name'], 'class': 'o_account_report_line_ellipsis'},
            {'name': self.format_value(aml['debit'], blank_if_zero=True) if currency_dif == 'Bs' else self.format_value_usd(aml['debit'], blank_if_zero=True), 'class': 'number'},
            {'name': self.format_value(aml['credit'], blank_if_zero=True) if currency_dif == 'Bs' else self.format_value_usd(aml['credit'], blank_if_zero=True), 'class': 'number'},
            {'name': self.format_value(cumulated_balance) if currency_dif == 'Bs' else self.format_value_usd(cumulated_balance), 'class': 'number'},
        ]
        #if self.user_has_groups('base.group_multi_currency'):
        #    columns.insert(3, {'name': currency and aml['amount_currency'] and self.format_value(aml['amount_currency'],
        #                                                                                         currency=currency,
        #                                                                                         blank_if_zero=True) or '',
        #                       'class': 'number'})
        return {
            'id': aml['id'],
            'caret_options': caret_type,
            'parent_id': 'account_%d' % aml['account_id'],
            'name': aml['move_name'],
            'columns': columns,
            'level': 2,
        }

    @api.model
    def _get_load_more_line(self, options, account, offset, remaining, progress):
        return {
            'id': 'loadmore_%s' % account.id,
            'offset': offset,
            'progress': progress,
            'remaining': remaining,
            'class': 'o_account_reports_load_more text-center',
            'parent_id': 'account_%s' % account.id,
            'name': _('Load more... (%s remaining)', remaining),
            'colspan': 6,
            'columns': [{}],
        }

    @api.model
    def _get_account_total_line(self, options, account, amount_currency, debit, credit, balance):
        has_foreign_currency = account.currency_id and account.currency_id != account.company_id.currency_id or False
        currency_dif = options['currency_dif']
        columns = []
        # if self.user_has_groups('base.group_multi_currency'):
        #     columns.append({'name': has_foreign_currency and self.format_value(amount_currency,
        #                                                                        currency=account.currency_id,
        #                                                                        blank_if_zero=True) or '',
        #                     'class': 'number'})

        columns += [
            {'name': self.format_value(debit) if currency_dif == 'Bs' else self.format_value_usd(debit),
             'class': 'number'},
            {'name': self.format_value(credit) if currency_dif == 'Bs' else self.format_value_usd(credit),
             'class': 'number'},
            {'name': self.format_value(balance) if currency_dif == 'Bs' else self.format_value_usd(balance),
             'class': 'number'}
        ]

        return {
            'id': 'total_%s' % account.id,
            'class': 'o_account_reports_domain_total',
            'parent_id': 'account_%s' % account.id,
            'name': _('Total %s', account["display_name"]),
            'columns': columns,
            'colspan': 4,
        }

    @api.model
    def _get_total_line(self, options, debit, credit, balance):
        currency_dif = options['currency_dif']
        return {
            'id': 'general_ledger_total_%s' % self.env.company.id,
            'name': _('Total'),
            'class': 'total',
            'level': 1,
            'columns': [
                {'name': self.format_value(debit) if currency_dif == 'Bs' else self.format_value_usd(debit),
                 'class': 'number'},
                {'name': self.format_value(credit) if currency_dif == 'Bs' else self.format_value_usd(credit),
                 'class': 'number'},
                {'name': self.format_value(balance) if currency_dif == 'Bs' else self.format_value_usd(balance),
                 'class': 'number'}
            ],
            'colspan': 4,
        }