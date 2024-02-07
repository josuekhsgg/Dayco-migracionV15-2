# -*- coding: utf-8 -*-
from odoo import models, api, _, _lt, fields
from datetime import timedelta
from odoo.tools.misc import formatLang, format_date

from collections import defaultdict

class ReportPartnerLedger(models.AbstractModel):
    _inherit = "account.accounting.report"

    # COLUMN/CELL FORMATTING ###################################################
    # ##########################################################################
    def _field_column(self, field_name, sortable=False, name=None, ellipsis=False, blank_if_zero=False):
        """Build a column based on a field.

        The type of the field determines how it is displayed.
        The column's title is the name of the field.
        :param field_name: The name of the fields.Field to use
        :param sortable: Allow the user to sort data based on this column
        :param name: Use a specific name for display.
        :param ellispsis (bool): The text displayed can be truncated in the web browser.
        :param blank_if_zero (bool): For numeric fields, do not display a value if it is equal to zero.
        :return (ColumnDetail): A usable column declaration to build the html
        """
        classes = ['text-nowrap']
        options = self.env.context['report_options'] if 'report_options' in self.env.context else None
        currency_dif = options['currency_dif'] if options else 'Bs'
        def getter(v):
            return self._fields[field_name].convert_to_cache(v.get(field_name, ''), self)

        if self._fields[field_name].type in ['float']:
            classes += ['number']

            def formatter(v):
                return v if v or not blank_if_zero else ''
        elif self._fields[field_name].type in ['monetary']:
            classes += ['number']

            def m_getter(v):
                return (v.get(field_name, ''), self.env['res.currency'].browse(
                    v.get(self._fields[field_name].currency_field, (False,))[0])
                        )

            getter = m_getter

            def formatter(v):
                return self.format_value(v[0], v[1], blank_if_zero=blank_if_zero)  if currency_dif == 'Bs' else self.format_value_usd(v[0], blank_if_zero=blank_if_zero)
        elif self._fields[field_name].type in ['char']:
            classes += ['text-center']

            def formatter(v):
                return v
        elif self._fields[field_name].type in ['date']:
            classes += ['date']

            def formatter(v):
                return format_date(self.env, v)
        elif self._fields[field_name].type in ['many2one']:
            classes += ['text-center']

            def r_getter(v):
                return v.get(field_name, False)

            getter = r_getter

            def formatter(v):
                return v[1] if v else ''

        IrModelFields = self.env['ir.model.fields']
        return self._custom_column(name=name or IrModelFields._get(self._name, field_name).field_description,
                                   getter=getter,
                                   formatter=formatter,
                                   classes=classes,
                                   ellipsis=ellipsis,
                                   sortable=sortable)