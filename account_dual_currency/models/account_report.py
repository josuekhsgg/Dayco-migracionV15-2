# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.tools.misc import format_date

from collections import defaultdict
from odoo.tools.misc import formatLang, format_date

class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    CURRENCY_DIF = None

    # TO BE OVERWRITTEN
    def _get_templates(self):
        return {
            'main_template': 'account_reports.main_template',
            'main_table_header_template': 'account_reports.main_table_header',
            'line_template': 'account_reports.line_template',
            'footnotes_template': 'account_reports.footnotes_template',
            'search_template': 'account_dual_currency.search_template_generic_currency_dif',
            'line_caret_options': 'account_reports.line_caret_options',
        }

    def _get_options(self, previous_options=None):
        # Create default options.
        options = {
            'unfolded_lines': previous_options and previous_options.get('unfolded_lines') or [],
        }

        for filter_key in self._get_filters_in_init_sequence():
            options_key = filter_key[7:]
            init_func = getattr(self, '_init_%s' % filter_key, None)
            if init_func:
                init_func(options, previous_options=previous_options)
            else:
                filter_opt = getattr(self, filter_key, None)
                if filter_opt is not None:
                    if previous_options and options_key in previous_options:
                        options[options_key] = previous_options[options_key]
                    else:
                        options[options_key] = filter_opt
        currency_dif = 'Bs'
        if previous_options:
            if "currency_dif" in previous_options:
                currency_dif = previous_options['currency_dif']
        options['currency_dif'] = currency_dif
        self = self.with_context(report_options=options)
        #self.env.context['report_options'] = options
        #print('no entra para context')
        #self = self.with_context(self._set_context(options))
        return options


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
    def _create_hierarchy(self, lines, options):
        """Compute the hierarchy based on account groups when the option is activated.

        The option is available only when there are account.group for the company.
        It should be called when before returning the lines to the client/templater.
        The lines are the result of _get_lines(). If there is a hierarchy, it is left
        untouched, only the lines related to an account.account are put in a hierarchy
        according to the account.group's and their prefixes.
        """
        unfold_all = self.env.context.get('print_mode') and len(options.get('unfolded_lines')) == 0 or options.get(
            'unfold_all')
        currency_dif = options['currency_dif']
        def add_to_hierarchy(lines, key, level, parent_id, hierarchy):
            val_dict = hierarchy[key]
            unfolded = val_dict['id'] in options.get('unfolded_lines') or unfold_all
            # add the group totals
            lines.append({
                'id': val_dict['id'],
                'name': val_dict['name'],
                'title_hover': val_dict['name'],
                'unfoldable': True,
                'unfolded': unfolded,
                'level': level,
                'parent_id': parent_id,
                'columns': [{'name': (self.format_value(c) if currency_dif == 'Bs' else self.format_value_usd(c)) if isinstance(c, (int, float)) else c, 'no_format_name': c}
                            for c in val_dict['totals']],
            })
            if not self._context.get('print_mode') or unfolded:
                for i in val_dict['children_codes']:
                    hierarchy[i]['parent_code'] = i
                all_lines = [hierarchy[id] for id in val_dict["children_codes"]] + val_dict["lines"]
                children = []
                for line in sorted(all_lines, key=lambda k: k.get('account_code', '') + k['name']):
                    if 'children_codes' in line:
                        # if the line is a child group, add it recursively
                        add_to_hierarchy(children, line['parent_code'], level + 1, val_dict['id'], hierarchy)
                        lines.extend(children)
                    else:
                        # add lines that are in this group but not in one of this group's children groups
                        line['level'] = level + 1
                        line['parent_id'] = val_dict['id']
                        lines.append(line)

        def compute_hierarchy(lines, level, parent_id):
            # put every line in each of its parents (from less global to more global) and compute the totals
            hierarchy = defaultdict(
                lambda: {'totals': [None] * len(lines[0]['columns']), 'lines': [], 'children_codes': set(), 'name': '',
                         'parent_id': None, 'id': ''})
            for line in lines:
                account = self.env['account.account'].browse(
                    line.get('account_id', self._get_caret_option_target_id(line.get('id'))))
                codes = self.get_account_codes(account)  # id, name
                for code in codes:
                    hierarchy[code[0]]['id'] = self._get_generic_line_id('account.group', code[0],
                                                                         parent_line_id=line['id'])
                    hierarchy[code[0]]['name'] = code[1]
                    for i, column in enumerate(line['columns']):
                        if 'no_format_name' in column:
                            no_format = column['no_format_name']
                        elif 'no_format' in column:
                            no_format = column['no_format']
                        else:
                            no_format = None
                        if isinstance(no_format, (int, float)):
                            if hierarchy[code[0]]['totals'][i] is None:
                                hierarchy[code[0]]['totals'][i] = no_format
                            else:
                                hierarchy[code[0]]['totals'][i] += no_format
                for code, child in zip(codes[:-1], codes[1:]):
                    hierarchy[code[0]]['children_codes'].add(child[0])
                    hierarchy[child[0]]['parent_id'] = hierarchy[code[0]]['id']
                hierarchy[codes[-1][0]]['lines'] += [line]
            # compute the tree-like structure by starting at the roots (being groups without parents)
            hierarchy_lines = []
            for root in [k for k, v in hierarchy.items() if not v['parent_id']]:
                add_to_hierarchy(hierarchy_lines, root, level, parent_id, hierarchy)
            return hierarchy_lines

        new_lines = []
        account_lines = []
        current_level = 0
        parent_id = 'root'
        for line in lines:
            if not (line.get('caret_options') == 'account.account' or line.get('account_id')):
                # make the hierarchy with the lines we gathered, append it to the new lines and restart the gathering
                if account_lines:
                    new_lines.extend(compute_hierarchy(account_lines, current_level + 1, parent_id))
                account_lines = []
                new_lines.append(line)
                current_level = line['level']
                parent_id = line['id']
            else:
                # gather all the lines we can create a hierarchy on
                account_lines.append(line)
        # do it one last time for the gathered lines remaining
        if account_lines:
            new_lines.extend(compute_hierarchy(account_lines, current_level + 1, parent_id))
        return new_lines