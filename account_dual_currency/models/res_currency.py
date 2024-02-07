from odoo import api, fields, models, _
from datetime import date, timedelta, datetime
from bs4 import BeautifulSoup
from pytz import timezone
import requests
import logging
import urllib3
urllib3.disable_warnings()
_logger = logging.getLogger(__name__)

class ResCurrency(models.Model):
    _inherit = 'res.currency'

    tasa_referencia = fields.Float(string="Tasa Referencia", compute="_tasa_referencia", digits='Dual_Currency_rate')

    facturas_por_actualizar = fields.Integer(compute="_facturas_por_actualizar")

    #habilitar sincronización automatica
    sincronizar = fields.Boolean(string="Sincronizar", default=False)

    #campo listado de servidores, bcv o dolar today
    server = fields.Selection([('bcv', 'BCV'), ('dolar_today', 'Dolar Today Promedio')], string='Servidor', default='bcv')

    def _convert(self, from_amount, to_currency, company, date, round=True):
        """Returns the converted amount of ``from_amount``` from the currency
           ``self`` to the currency ``to_currency`` for the given ``date`` and
           company.

           :param company: The company from which we retrieve the convertion rate
           :param date: The nearest date from which we retriev the conversion rate.
           :param round: Round the result or not
        """
        #print('convertir ', from_amount,' desde', self, 'hasta', to_currency, 'en la fecha', date, 'para la compañia', company)
        self, to_currency = self or to_currency, to_currency or self
        assert self, "convert amount from unknown currency"
        assert to_currency, "convert amount to unknown currency"
        assert company, "convert amount from unknown company"
        assert date, "convert amount from unknown date"
        # apply conversion rate
        if self == to_currency:
            to_amount = from_amount
        else:
            if self.env.context.get('tasa_factura'):
                if to_currency == self.env.company.currency_id_dif:
                    to_amount = from_amount / self.env.context.get('tasa_factura')
                else:
                    to_amount = from_amount * self.env.context.get('tasa_factura')
            else:
                to_amount = from_amount * self._get_conversion_rate(self, to_currency, company, date)
        # apply rounding
        return to_currency.round(to_amount) if round else to_amount

    def _facturas_por_actualizar(self):
        for rec in self:
            if rec.name == self.env.company.currency_id_dif.name:
                rec.facturas_por_actualizar = self.env['account.move'].search_count([('acuerdo_moneda', '=', True),('state', 'in', ['draft','posted']),('tax_today','!=',rec.tasa_referencia)])
            else:
                rec.facturas_por_actualizar = 0

    def _tasa_referencia(self):
        for rec in self:
            if self.rate_ids:
                rec.tasa_referencia = self.rate_ids[0].tasa_referencia
            else:
                rec.tasa_referencia = 1 / rec.rate

    def actualizar_facturas(self):
        for rec in self:
            # actualizar tasa a las facturas dinamicas
            facturas = self.env['account.move'].search([('acuerdo_moneda', '=', True)])
            if facturas:
                for f in facturas:
                    f.tax_today = rec.tasa_referencia
                    for l in f.line_ids:
                        l.tax_today = rec.tasa_referencia
                        l._debit_usd()
                        l._credit_usd()
                    for d in f.invoice_line_ids:
                        d.tax_today = rec.tasa_referencia
                        d._price_unit_usd()
                        d._price_subtotal_usd()
                    f._amount_untaxed_usd()
                    f._amount_all_usd()
                    f._compute_payments_widget_reconciled_info_USD()

    def actualizar_productos(self):
        for rec in self:
            product_ids = self.env['product.template'].search([('list_price_usd','>',0)])

            for p in product_ids:
                p.list_price = p.list_price_usd * rec.tasa_referencia

            product_product_ids = self.env['product.product'].search([('list_price_usd', '>', 0)])
            for p in product_product_ids:
                p.list_price = p.list_price_usd * rec.tasa_referencia

            list_product_ids = self.env['product.pricelist.item'].search([('currency_id', '=', self.id)])

            for lp in list_product_ids:
                # buscar el producto en la lista de Bs y actualizar
                dominio = [('currency_id', '=', lp.company_id.currency_id.id or self.env.company.currency_id.id)]
                if lp.product_id:
                    dominio.append((('product_id', '=', lp.product_id.id)))
                elif lp.product_tmpl_id:
                    dominio.append((('product_tmpl_id', '=', lp.product_tmpl_id.id)))
                product_id_bs = self.env['product.pricelist.item'].search(dominio)
                for p in product_id_bs:
                    p.fixed_price = lp.fixed_price * rec.tasa_referencia

            channel_id = self.env.ref('account_dual_currency.trm_channel')
            channel_id.message_post(
                body="Todos los productos han sido actualizados con la nueva tasa de cambio",
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

            #bus_bus_obj._sendone('#general','simple_notification','Todos los productos han sido actualizados')

            #self._cr.commit()
            # self.env.cr.execute("""
            #     UPDATE product_template set list_price = (list_price_usd * %s) WHERE list_price_usd > 0;
            # """ % rec.tasa_referencia)
            # self._cr.commit()
            
    def actualizar_productos_cron(self):
        rec = self.env.user.company_id.currency_id_dif
        product_ids = self.env['product.template'].search([('list_price_usd','>',0)])

        for p in product_ids:
            p.list_price = p.list_price_usd * rec.tasa_referencia

        product_product_ids = self.env['product.product'].search([('list_price_usd', '>', 0)])
        for p in product_product_ids:
            p.list_price = p.list_price_usd * rec.tasa_referencia

        list_product_ids = self.env['product.pricelist.item'].search([('currency_id', '=', self.id)])

        for lp in list_product_ids:
            # buscar el producto en la lista de Bs y actualizar
            dominio = [('currency_id', '=', lp.company_id.currency_id.id or self.env.company.currency_id.id)]
            if lp.product_id:
                dominio.append((('product_id', '=', lp.product_id.id)))
            elif lp.product_tmpl_id:
                dominio.append((('product_tmpl_id', '=', lp.product_tmpl_id.id)))
            product_id_bs = self.env['product.pricelist.item'].search(dominio)
            for p in product_id_bs:
                p.fixed_price = lp.fixed_price * rec.tasa_referencia

        channel_id = self.env.ref('account_dual_currency.trm_channel')
        channel_id.message_post(
            body="Todos los productos han sido actualizados con la nueva tasa de cambio",
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

    def get_bcv(self):
        url = "https://www.bcv.org.ve/"
        req = requests.get(url, verify=False)

        status_code = req.status_code
        if status_code == 200:

            html = BeautifulSoup(req.text, "html.parser")
            # Dolar
            dolar = html.find('div', {'id': 'dolar'})
            dolar = str(dolar.find('strong')).split()
            dolar = str.replace(dolar[1], '.', '')
            dolar = float(str.replace(dolar, ',', '.'))
            # Euro
            euro = html.find('div', {'id': 'euro'})
            euro = str(euro.find('strong')).split()
            euro = str.replace(euro[1], '.', '')
            euro = float(str.replace(euro, ',', '.'))

            if self.name == 'USD':
                bcv = dolar
            elif self.name == 'EUR':
                bcv = euro
            else:
                bcv = False

            return bcv
        else:
            return False

    def get_dolar_today_promedio(self):
        url = "https://s3.amazonaws.com/dolartoday/data.json"
        response = requests.get(url)
        status_code = response.status_code

        if status_code == 200:
            response = response.json()
            usd = float(response['USD']['transferencia'])
            eur = float(response['EUR']['transferencia'])
            if self.name == 'USD':
                data = usd
            elif self.name == 'EUR':
                data = eur
            else:
                data = False

            return data
        else:
            return False

    def actualizar_tasa(self):
        for rec in self:
            nueva_tasa = 0
            if rec.server == 'bcv':
                tasa_bcv = rec.get_bcv()
                if tasa_bcv:
                    nueva_tasa = tasa_bcv
            elif rec.server == 'dolar_today':
                tasa_dt = rec.get_dolar_today_promedio()
                if tasa_dt:
                    nueva_tasa = tasa_dt

            if nueva_tasa > 0:
                channel_id = self.env.ref('account_dual_currency.trm_channel')
                tasa_actual = self.env['res.currency.rate'].search(
                    [('name', '=', datetime.now()), ('currency_id', '=', rec.id)])
                if len(tasa_actual) == 0:
                    self.env['res.currency.rate'].create({
                        'currency_id': rec.id,
                        'name': datetime.now(),
                        'tasa_referencia': nueva_tasa,
                        'rate': 1 / nueva_tasa
                    })
                    channel_id.message_post(
                        body="Nueva tasa de cambio del %s: %s, actualizada desde %s a las %s." % (rec.name, nueva_tasa, rec.server, datetime.strftime(fields.Datetime.context_timestamp(self, datetime.now()), "%d-%m-%Y %H:%M:%S")),
                        message_type='notification',
                        subtype_xmlid='mail.mt_comment',
                    )
                else:
                    if rec.server== 'dolar_today':
                        tasa_actual.tasa_referencia = nueva_tasa
                        tasa_actual.rate = 1 / nueva_tasa
                        channel_id.message_post(
                            body="Tasa de cambio actualizada del %s: %s, desde %s a las %s." % (
                            rec.name, nueva_tasa, rec.server, datetime.strftime(fields.Datetime.context_timestamp(self, datetime.now()), "%d-%m-%Y %H:%M:%S")),
                            message_type='notification',
                            subtype_xmlid='mail.mt_comment',
                        )

    @api.model
    def _cron_actualizar_tasa(self):
        monedas = self.env['res.currency'].search([('active', '=', True), ('sincronizar', '=',True)])
        for m in monedas:
            m.actualizar_tasa()

        self.actualizar_productos_cron()

class ResCurrencyRate(models.Model):
    _inherit = 'res.currency.rate'

    tasa_referencia = fields.Float(string="Tasa Referencia", digits='Dual_Currency_rate')

    # @api.model
    # def create(self, vals):
    #     result = super(ResCurrencyRate, self).create(vals)
    #     for rec in self:
    #         if rec.currency_id.name == 'USD':
    #             #actualizar tasa a las facturas dinamicas
    #             facturas = self.env['account.move'].search([('acuerdo_moneda','=',True)])
    #             if facturas:
    #                 for f in facturas:
    #                     f.tax_today = float(result['tasa_referencia'])
    #     return result
    #
    # @api.model
    # def update(self, vals):
    #     result = super(ResCurrencyRate, self).update(vals)
    #     print(result)
    #     for rec in self:
    #         if rec.currency_id.name == 'USD':
    #             # actualizar tasa a las facturas dinamicas
    #             facturas = self.env['account.move'].search([('acuerdo_moneda', '=', True)])
    #             if facturas:
    #                 for f in facturas:
    #                     f.tax_today = float(result['tasa_referencia'])
    #     return result

    # @api.model
    # def write(self, vals, kwargs):
    #     result = super(ResCurrencyRate, self).write(vals,kwargs)
    #     print(result)
    #     for rec in self:
    #         if rec.currency_id.name == 'USD':
    #             # actualizar tasa a las facturas dinamicas
    #             facturas = self.env['account.move'].search([('acuerdo_moneda', '=', True)])
    #             if facturas:
    #                 for f in facturas:
    #                     f.tax_today = float(result['tasa_referencia'])
    #     return result

    @api.onchange('tasa_referencia')
    def _tasa_referencia_onchange(self):
        for rec in self:
            if rec.tasa_referencia > 0:
                #buscar tasa para la fecha
                rec.rate = 1 / rec.tasa_referencia

    @api.onchange('rate')
    def _tasa_referencia_rate(self):
        for rec in self:
            if rec.rate > 0:
                # buscar tasa para la fecha
                rec.tasa_referencia = 1 / rec.rate
