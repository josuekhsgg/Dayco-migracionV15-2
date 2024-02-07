from odoo import models, fields, api, _
from odoo.tools import float_is_zero, classproperty

from itertools import chain


class MulticurrencyRevaluationReport(models.Model):
    _inherit = 'account.multicurrency.revaluation'


    def _get_options(self, previous_options=None):
        options = super()._get_options(previous_options)
        rates = self.env['res.currency'].search([('active', '=', True)])._get_rates(self.env.company, options.get('date').get('date_to'))
        for key in rates.keys():  # normalize the rates to the company's currency
            rates[key] /= rates[self.env.company.currency_id.id]
        options['currency_rates'] = {
            str(currency_id.id): {
                'currency_id': currency_id.id,
                'currency_name': currency_id.name,
                'currency_main': self.env.company.currency_id.name,
                'rate': (rates[currency_id.id]
                         if not (previous_options or {}).get('currency_rates', {}).get(str(currency_id.id), {}).get('rate') else
                         float(previous_options['currency_rates'][str(currency_id.id)]['rate'])),
            } for currency_id in self.env['res.currency'].search([('active', '=', True)])
        }
        options['company_currency'] = options['currency_rates'].pop(str(self.env.company.currency_id.id))
        options['custom_rate'] = any(
            not float_is_zero(cr['rate'] - rates[cr['currency_id']], 6)
            for cr in options['currency_rates'].values()
        )
        options['warning_multicompany'] = len(self.env.companies) > 1
        currency_dif = 'Bs'
        if previous_options:
            if "currency_dif" in previous_options:
                currency_dif = previous_options['currency_dif']
        options['currency_dif'] = currency_dif
        self = self.with_context(report_options=options)
        return options