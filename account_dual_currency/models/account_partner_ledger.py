# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.tools.misc import format_date

from odoo.tools.misc import formatLang, format_date

class ReportPartnerLedger(models.AbstractModel):
    _inherit = 'account.partner.ledger'

    @api.model
    def _get_options_domain(self, options):
        # OVERRIDE
        # Handle filter_unreconciled + filter_account_type
        domain = super(ReportPartnerLedger, self)._get_options_domain(options)
        if options.get('unreconciled'):
            domain += ['&', ('full_reconcile_id', '=', False), ('balance', '!=', '0')]
        exch_code = self.env['res.company'].browse(self.env.context.get('company_ids')).mapped('currency_exchange_journal_id')
        if exch_code:
            domain += ['!', '&', '&', '&', ('credit', '=', 0.0), ('debit', '=', 0.0), ('credit_usd', '=', 0.0), ('debit_usd', '=', 0.0), ('amount_currency', '!=', 0.0), ('journal_id.id', 'in', exch_code.ids)]
        domain.append(('account_id.internal_type', 'in', [t['id'] for t in self._get_options_account_type(options)]))

        return domain

    @api.model
    def _get_query_sums(self, options, expanded_partner=None):
        ''' Construct a query retrieving all the aggregated sums to build the report. It includes:
        - sums for all partners.
        - sums for the initial balances.
        :param options:             The report options.
        :param expanded_partner:    An optional res.partner record that must be specified when expanding a line
                                    with of without the load more.
        :return:                    (query, params)
        '''
        params = []
        queries = []

        if expanded_partner is not None:
            domain = [('partner_id', '=', expanded_partner.id)]
        else:
            domain = []

        # Create the currency table.
        ct_query = self.env['res.currency']._get_query_currency_table(options)

        # Get sums for all partners.
        # period: [('date' <= options['date_to']), ('date' >= options['date_from'])]
        new_options = self._get_options_sum_balance(options)
        tables, where_clause, where_params = self._query_get(new_options, domain=domain)
        params += where_params
        currency_dif = options['currency_dif']
        if currency_dif == 'Bs':
            queries.append('''
                    SELECT
                        account_move_line.partner_id        AS groupby,
                        'sum'                               AS key,
                        SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM %s
                    LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                    WHERE %s
                    GROUP BY account_move_line.partner_id
                ''' % (tables, ct_query, where_clause))
        else:
            queries.append('''
                        SELECT
                            account_move_line.partner_id        AS groupby,
                            'sum'                               AS key,
                            SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                            SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                            SUM(ROUND((account_move_line.debit_usd - account_move_line.credit_usd), currency_table.precision)) AS balance
                        FROM %s
                        LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                        WHERE %s
                        GROUP BY account_move_line.partner_id
                    ''' % (tables, ct_query, where_clause))

        # Get sums for the initial balance.
        # period: [('date' <= options['date_from'] - 1)]
        new_options = self._get_options_initial_balance(options)
        tables, where_clause, where_params = self._query_get(new_options, domain=domain)
        params += where_params
        if currency_dif == 'Bs':
            queries.append('''
                    SELECT
                        account_move_line.partner_id        AS groupby,
                        'initial_balance'                   AS key,
                        SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM %s
                    LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                    WHERE %s
                    GROUP BY account_move_line.partner_id
                ''' % (tables, ct_query, where_clause))
        else:
            queries.append('''
                        SELECT
                            account_move_line.partner_id        AS groupby,
                            'initial_balance'                   AS key,
                            SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                            SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                            SUM(ROUND((account_move_line.debit_usd - account_move_line.credit_usd), currency_table.precision)) AS balance
                        FROM %s
                        LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                        WHERE %s
                        GROUP BY account_move_line.partner_id
                    ''' % (tables, ct_query, where_clause))

        return ' UNION ALL '.join(queries), params

    @api.model
    def _get_report_line_partner(self, options, partner, initial_balance, debit, credit, balance):
        company_currency = self.env.company.currency_id
        unfold_all = self._context.get('print_mode') and not options.get('unfolded_lines')
        currency_dif = options['currency_dif']
        columns = [
            {'name': self.format_value(initial_balance) if currency_dif == 'Bs' else self.format_value_usd(initial_balance), 'class': 'number'},
            {'name': self.format_value(debit) if currency_dif == 'Bs' else self.format_value_usd(debit), 'class': 'number'},
            {'name': self.format_value(credit) if currency_dif == 'Bs' else self.format_value_usd(credit), 'class': 'number'},
        ]
        #if self.user_has_groups('base.group_multi_currency'):
        #   columns.append({'name': ''})
        columns.append({'name': self.format_value(balance) if currency_dif == 'Bs' else self.format_value_usd(balance), 'class': 'number'})

        return {
            'id': 'partner_%s' % (partner.id if partner else 0),
            'partner_id': partner.id if partner else None,
            'name': partner is not None and (partner.name or '')[:128] or _('Unknown Partner'),
            'columns': columns,
            'level': 2,
            'trust': partner.trust if partner else None,
            'unfoldable': not company_currency.is_zero(debit) or not company_currency.is_zero(credit),
            'unfolded': 'partner_%s' % (partner.id if partner else 0) in options['unfolded_lines'] or unfold_all,
            'colspan': 6,
        }

    @api.model
    def _get_lines_without_partner(self, options, expanded_partner=None, offset=0, limit=0):
        ''' Get the detail of lines without partner reconciled with a line with a partner. Those lines should be
        considered as belonging the partner for the reconciled amount as it may clear some of the partner invoice/bill
        and they have to be accounted in the partner balance.'''

        params = []
        if expanded_partner:
            partner_clause = '= %s'
            params = [expanded_partner.id] + params
        else:
            partner_clause = 'IS NOT NULL'
        new_options = self._get_options_without_partner(options)
        params += [options['date']['date_from'], options['date']['date_to']]
        tables, where_clause, where_params = self._query_get(new_options, domain=[])
        params += where_params + [offset]
        limit_clause = ''
        if limit != 0:
            params += [limit]
            limit_clause = "LIMIT %s"
        currency_dif = options['currency_dif']
        if currency_dif == 'Bs':
            query = '''
                SELECT
                    account_move_line.id,
                    account_move_line.date,
                    account_move_line.date_maturity,
                    account_move_line.name,
                    account_move_line.ref,
                    account_move_line.company_id,
                    account_move_line.account_id,
                    account_move_line.payment_id,
                    aml_with_partner.partner_id,
                    account_move_line.currency_id,
                    account_move_line.amount_currency,
                    account_move_line.matching_number,
                    CASE WHEN aml_with_partner.balance > 0 THEN 0 ELSE partial.amount END AS debit,
                    CASE WHEN aml_with_partner.balance < 0 THEN 0 ELSE partial.amount END AS credit,
                    CASE WHEN aml_with_partner.balance > 0 THEN -partial.amount ELSE partial.amount END AS balance,
                    account_move_line__move_id.name         AS move_name,
                    account_move_line__move_id.move_type    AS move_type,
                    account.code                            AS account_code,
                    account.name                            AS account_name,
                    journal.code                            AS journal_code,
                    journal.name                            AS journal_name,
                    full_rec.name                           AS full_rec_name
                FROM {tables},
                    account_partial_reconcile partial
                    LEFT JOIN account_full_reconcile full_rec ON full_rec.id = partial.full_reconcile_id,
                    account_move_line aml_with_partner,
                    account_journal journal,
                    account_account account
                WHERE (account_move_line.id = partial.debit_move_id OR account_move_line.id = partial.credit_move_id)
                   AND account_move_line.partner_id IS NULL
                   AND (aml_with_partner.id = partial.debit_move_id OR aml_with_partner.id = partial.credit_move_id)
                   AND aml_with_partner.partner_id {partner_clause}
                   AND journal.id = account_move_line.journal_id
                   AND account.id = account_move_line.account_id
                   AND partial.max_date BETWEEN %s AND %s
                   AND {where_clause}
                ORDER BY account_move_line.date, account_move_line.id
                OFFSET %s
                {limit_clause}
            '''.format(tables=tables, partner_clause=partner_clause, where_clause=where_clause,
                       limit_clause=limit_clause)
        else:
            query = '''
                        SELECT
                            account_move_line.id,
                            account_move_line.date,
                            account_move_line.date_maturity,
                            account_move_line.name,
                            account_move_line.ref,
                            account_move_line.company_id,
                            account_move_line.account_id,
                            account_move_line.payment_id,
                            aml_with_partner.partner_id,
                            account_move_line.currency_id,
                            account_move_line.amount_currency,
                            account_move_line.matching_number,
                            CASE WHEN (aml_with_partner.debit_usd - aml_with_partner.credit_usd) > 0 THEN 0 ELSE partial.amount_usd END AS debit,
                            CASE WHEN (aml_with_partner.debit_usd - aml_with_partner.credit_usd) < 0 THEN 0 ELSE partial.amount_usd END AS credit,
                            CASE WHEN (aml_with_partner.debit_usd - aml_with_partner.credit_usd) > 0 THEN -partial.amount_usd ELSE partial.amount_usd END AS balance,
                            account_move_line__move_id.name         AS move_name,
                            account_move_line__move_id.move_type    AS move_type,
                            account.code                            AS account_code,
                            account.name                            AS account_name,
                            journal.code                            AS journal_code,
                            journal.name                            AS journal_name,
                            full_rec.name                           AS full_rec_name
                        FROM {tables},
                            account_partial_reconcile partial
                            LEFT JOIN account_full_reconcile full_rec ON full_rec.id = partial.full_reconcile_id,
                            account_move_line aml_with_partner,
                            account_journal journal,
                            account_account account
                        WHERE (account_move_line.id = partial.debit_move_id OR account_move_line.id = partial.credit_move_id)
                           AND account_move_line.partner_id IS NULL
                           AND (aml_with_partner.id = partial.debit_move_id OR aml_with_partner.id = partial.credit_move_id)
                           AND aml_with_partner.partner_id {partner_clause}
                           AND journal.id = account_move_line.journal_id
                           AND account.id = account_move_line.account_id
                           AND partial.max_date BETWEEN %s AND %s
                           AND {where_clause}
                        ORDER BY account_move_line.date, account_move_line.id
                        OFFSET %s
                        {limit_clause}
                    '''.format(tables=tables, partner_clause=partner_clause, where_clause=where_clause,
                               limit_clause=limit_clause)

        return query, params

    @api.model
    def _get_sums_without_partner(self, options, expanded_partner=None):
        ''' Get the sum of lines without partner reconciled with a line with a partner, grouped by partner. Those lines
        should be considered as belonging the partner for the reconciled amount as it may clear some of the partner
        invoice/bill and they have to be accounted in the partner balance.'''

        params = []
        if expanded_partner:
            partner_clause = '= %s'
            params = [expanded_partner.id]
        else:
            partner_clause = 'IS NOT NULL'

        new_options = self._get_options_without_partner(options)
        params = [options['date']['date_from']] + params + [options['date']['date_to']]
        tables, where_clause, where_params = self._query_get(new_options, domain=[])
        params += where_params
        currency_dif = options['currency_dif']
        if currency_dif == 'Bs':
            query = '''
                    SELECT
                        aml_with_partner.partner_id AS groupby,
                        SUM(CASE WHEN aml_with_partner.balance > 0 THEN 0 ELSE partial.amount END) AS debit,
                        SUM(CASE WHEN aml_with_partner.balance < 0 THEN 0 ELSE partial.amount END) AS credit,
                        SUM(CASE WHEN aml_with_partner.balance > 0 THEN -partial.amount ELSE partial.amount END) AS balance,
                        CASE WHEN partial.max_date < %s THEN 'initial_balance' ELSE 'sum' END as key
                    FROM {tables}, account_partial_reconcile partial, account_move_line aml_with_partner
                    WHERE (account_move_line.id = partial.debit_move_id OR account_move_line.id = partial.credit_move_id)
                       AND account_move_line.partner_id IS NULL
                       AND (aml_with_partner.id = partial.debit_move_id OR aml_with_partner.id = partial.credit_move_id)
                       AND aml_with_partner.partner_id {partner_clause}
                       AND partial.max_date <= %s
                       AND {where_clause}
                    GROUP BY aml_with_partner.partner_id, key
                '''.format(tables=tables, partner_clause=partner_clause, where_clause=where_clause)
        else:
            query = '''
                        SELECT
                            aml_with_partner.partner_id AS groupby,
                            SUM(CASE WHEN (aml_with_partner.debit_usd - aml_with_partner.credit_usd) > 0 THEN 0 ELSE partial.amount_usd END) AS debit,
                            SUM(CASE WHEN (aml_with_partner.debit_usd - aml_with_partner.credit_usd) < 0 THEN 0 ELSE partial.amount_usd END) AS credit,
                            SUM(CASE WHEN (aml_with_partner.debit_usd - aml_with_partner.credit_usd) > 0 THEN -partial.amount_usd ELSE partial.amount_usd END) AS balance,
                            CASE WHEN partial.max_date < %s THEN 'initial_balance' ELSE 'sum' END as key
                        FROM {tables}, account_partial_reconcile partial, account_move_line aml_with_partner
                        WHERE (account_move_line.id = partial.debit_move_id OR account_move_line.id = partial.credit_move_id)
                           AND account_move_line.partner_id IS NULL
                           AND (aml_with_partner.id = partial.debit_move_id OR aml_with_partner.id = partial.credit_move_id)
                           AND aml_with_partner.partner_id {partner_clause}
                           AND partial.max_date <= %s
                           AND {where_clause}
                        GROUP BY aml_with_partner.partner_id, key
                    '''.format(tables=tables, partner_clause=partner_clause, where_clause=where_clause)
        return query, params

    @api.model
    def _get_query_amls(self, options, expanded_partner=None, offset=None, limit=None):
        ''' Construct a query retrieving the account.move.lines when expanding a report line with or without the load
        more.
        :param options:             The report options.
        :param expanded_partner:    The res.partner record corresponding to the expanded line.
        :param offset:              The offset of the query (used by the load more).
        :param limit:               The limit of the query (used by the load more).
        :return:                    (query, params)
        '''
        unfold_all = options.get('unfold_all') or (self._context.get('print_mode') and not options['unfolded_lines'])

        # Get sums for the account move lines.
        # period: [('date' <= options['date_to']), ('date', '>=', options['date_from'])]
        if expanded_partner is not None:
            domain = [('partner_id', '=', expanded_partner.id)]
        elif unfold_all:
            domain = []
        elif options['unfolded_lines']:
            domain = [('partner_id', 'in', [int(line[8:]) for line in options['unfolded_lines']])]

        new_options = self._get_options_sum_balance(options)
        tables, where_clause, where_params = self._query_get(new_options, domain=domain)
        ct_query = self.env['res.currency']._get_query_currency_table(options)
        currency_dif = options['currency_dif']
        if currency_dif == 'Bs':
            query = '''
                    SELECT
                        account_move_line.id,
                        account_move_line.date,
                        account_move_line.date_maturity,
                        account_move_line.name,
                        account_move_line.ref,
                        account_move_line.company_id,
                        account_move_line.account_id,
                        account_move_line.payment_id,
                        account_move_line.partner_id,
                        account_move_line.currency_id,
                        account_move_line.amount_currency,
                        account_move_line.matching_number,
                        ROUND(account_move_line.debit * currency_table.rate, currency_table.precision)   AS debit,
                        ROUND(account_move_line.credit * currency_table.rate, currency_table.precision)  AS credit,
                        ROUND(account_move_line.balance * currency_table.rate, currency_table.precision) AS balance,
                        account_move_line__move_id.name         AS move_name,
                        company.currency_id                     AS company_currency_id,
                        partner.name                            AS partner_name,
                        account_move_line__move_id.move_type    AS move_type,
                        account.code                            AS account_code,
                        account.name                            AS account_name,
                        journal.code                            AS journal_code,
                        journal.name                            AS journal_name
                    FROM %s
                    LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                    LEFT JOIN res_company company               ON company.id = account_move_line.company_id
                    LEFT JOIN res_partner partner               ON partner.id = account_move_line.partner_id
                    LEFT JOIN account_account account           ON account.id = account_move_line.account_id
                    LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
                    WHERE %s
                    ORDER BY account_move_line.date, account_move_line.id
                ''' % (tables, ct_query, where_clause)
        else:
            query = '''
                        SELECT
                            account_move_line.id,
                            account_move_line.date,
                            account_move_line.date_maturity,
                            account_move_line.name,
                            account_move_line.ref,
                            account_move_line.company_id,
                            account_move_line.account_id,
                            account_move_line.payment_id,
                            account_move_line.partner_id,
                            account_move_line.currency_id,
                            account_move_line.amount_currency,
                            account_move_line.matching_number,
                            ROUND(account_move_line.debit_usd, currency_table.precision)   AS debit,
                            ROUND(account_move_line.credit_usd, currency_table.precision)  AS credit,
                            ROUND((account_move_line.debit_usd - account_move_line.credit_usd), currency_table.precision) AS balance,
                            account_move_line__move_id.name         AS move_name,
                            company.currency_id                     AS company_currency_id,
                            partner.name                            AS partner_name,
                            account_move_line__move_id.move_type    AS move_type,
                            account.code                            AS account_code,
                            account.name                            AS account_name,
                            journal.code                            AS journal_code,
                            journal.name                            AS journal_name
                        FROM account_move_line
                        LEFT JOIN account_move account_move_line__move_id ON account_move_line__move_id.id = account_move_line.move_id
                        LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                        LEFT JOIN res_company company               ON company.id = account_move_line.company_id
                        LEFT JOIN res_partner partner               ON partner.id = account_move_line.partner_id
                        LEFT JOIN account_account account           ON account.id = account_move_line.account_id
                        LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
                        WHERE %s
                        ORDER BY account_move_line.date, account_move_line.id
                    ''' % (ct_query, where_clause)

        if offset:
            query += ' OFFSET %s '
            where_params.append(offset)
        if limit:
            query += ' LIMIT %s '
            where_params.append(limit)

        return query, where_params

    @api.model
    def _get_report_line_move_line(self, options, partner, aml, cumulated_init_balance, cumulated_balance):
        if aml['payment_id']:
            caret_type = 'account.payment'
        else:
            caret_type = 'account.move'
        currency_dif = options['currency_dif']
        date_maturity = aml['date_maturity'] and format_date(self.env, fields.Date.from_string(aml['date_maturity']))
        columns = [
            {'name': aml['journal_code']},
            {'name': aml['account_code']},
            {'name': self._format_aml_name(aml['name'], aml['ref'], aml['move_name']),
             'class': 'o_account_report_line_ellipsis'},
            {'name': date_maturity or '', 'class': 'date'},
            {'name': aml['matching_number'] or ''},
            {'name': self.format_value(cumulated_init_balance) if currency_dif == 'Bs' else self.format_value_usd(cumulated_init_balance), 'class': 'number'},
            {'name': self.format_value(aml['debit'], blank_if_zero=True) if currency_dif == 'Bs' else self.format_value_usd(aml['debit'], blank_if_zero=True), 'class': 'number'},
            {'name': self.format_value(aml['credit'], blank_if_zero=True) if currency_dif == 'Bs' else self.format_value_usd(aml['credit'], blank_if_zero=True), 'class': 'number'},
        ]
        # if self.user_has_groups('base.group_multi_currency'):
        #     if aml['currency_id']:
        #         currency = self.env['res.currency'].browse(aml['currency_id'])
        #         formatted_amount = self.format_value(aml['amount_currency'], currency=currency, blank_if_zero=True)
        #         columns.append({'name': formatted_amount, 'class': 'number'})
        #     else:
        #       columns.append({'name': ''}) #currency columna
        columns.append({'name': self.format_value(cumulated_balance) if currency_dif == 'Bs' else self.format_value_usd(cumulated_balance), 'class': 'number'})
        return {
            'id': aml['id'],
            'parent_id': 'partner_%s' % (partner.id if partner else 0),
            'name': format_date(self.env, aml['date']),
            'class': 'text' + aml.get('class', ''),  # do not format as date to prevent text centering
            'columns': columns,
            'caret_options': caret_type,
            'level': 2,
        }

    @api.model
    def _get_report_line_total(self, options, initial_balance, debit, credit, balance):
        currency_dif = options['currency_dif']
        columns = [
            {'name': self.format_value(initial_balance) if currency_dif == 'Bs' else self.format_value_usd(initial_balance), 'class': 'number'},
            {'name': self.format_value(debit) if currency_dif == 'Bs' else self.format_value_usd(debit), 'class': 'number'},
            {'name': self.format_value(credit) if currency_dif == 'Bs' else self.format_value_usd(credit), 'class': 'number'},
        ]
        #if self.user_has_groups('base.group_multi_currency'):
        #   columns.append({'name': ''}) #currency columna
        columns.append({'name': self.format_value(balance) if currency_dif == 'Bs' else self.format_value_usd(balance), 'class': 'number'})
        return {
            'id': 'partner_ledger_total_%s' % self.env.company.id,
            'name': _('Total'),
            'class': 'total',
            'level': 1,
            'columns': columns,
            'colspan': 6,
        }

    def _get_columns_name(self, options):
        columns = [
            {},
            {'name': _('JRNL')},
            {'name': _('Account')},
            {'name': _('Ref')},
            {'name': _('Due Date'), 'class': 'date'},
            {'name': _('Matching Number')},
            {'name': _('Initial Balance'), 'class': 'number'},
            {'name': _('Debit'), 'class': 'number'},
            {'name': _('Credit'), 'class': 'number'}]

        #if self.user_has_groups('base.group_multi_currency'):
        #    columns.append({'name': _('Amount Currency'), 'class': 'number'})

        columns.append({'name': _('Balance'), 'class': 'number'})

        return columns

    @api.model
    def _get_report_line_load_more(self, options, partner, offset, remaining, progress):
        return {
            'id': 'loadmore_%s' % (partner.id if partner else 0),
            'offset': offset,
            'progress': progress,
            'remaining': remaining,
            'class': 'o_account_reports_load_more text-center',
            'parent_id': 'partner_%s' % (partner.id if partner else 0),
            'name': _('Load more... (%s remaining)', remaining),
            'colspan': 9,
            #'colspan': 10 if self.user_has_groups('base.group_multi_currency') else 9,
            'columns': [{}],
        }