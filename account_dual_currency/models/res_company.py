# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command

class ResCompany(models.Model):
    _inherit = "res.company"

    currency_id_dif = fields.Many2one("res.currency",
                                      string="Moneda Dual Ref.",
                                      default=lambda self: self.env['res.currency'].search([('name', '=', 'USD')],
                                                                                           limit=1), )

    # IGTF Divisa
    aplicar_igtf_divisa = fields.Boolean(
        'Retención de IGTF Divisa',
        help='Cuando sea Verdadero, la Retención de la IGTF Cliente estará disponible en el pago de factura',
        default=False)
    igtf_divisa_porcentage = fields.Float('% IGTF Divisa', help="El porcentaje a aplicar para retener ", default=3)

    account_debit_wh_igtf_id = fields.Many2one('account.account', string="Cuenta Recibos IGTF",
                                               help="Esta cuenta se utilizará en lugar de la predeterminada"
                                                    "para generar el asiento del IGTF Divisa")

    account_credit_wh_igtf_id = fields.Many2one('account.account', string="Cuenta Pagos IGTF",
                                                help="Esta cuenta se utilizará en lugar de la predeterminada"
                                                     "para generar el asiento del IGTF Divisa")
