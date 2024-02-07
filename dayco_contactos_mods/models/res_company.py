from odoo import models, fields, api, _
import logging
#import pyodbc #Librería de conexión a bases de datos SQL.
import string
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)

class ResCompanyExtrasSGC(models.Model):
    _inherit = 'res.company'
    _description = 'Parámetros adicionales del SGC para cada compañía en Odoo'

    fecha_ultima_sincronizacion = fields.Datetime("Fecha de la última sincronización desde SGC", store=True)
    ip_conexion_sgc = fields.Char("Dirección IP", store=True, default='200.74.215.68')
    puerto_conexion_sgc = fields.Char("Puerto", store=True, default='4022')
    bd_conexion_sgc = fields.Char("Base de datos", store=True, default='Dayco_SGC')
    user_conexion_sgc = fields.Char("Usuario", store=True, default='Odoo')
    pass_conexion_sgc = fields.Char("Contraseña", store=True, default='Dayco2022$')

    @api.model
    def create(self, vals):
        """ Implement to avoid res.partner vat validation
        """
        return super(ResCompanyExtrasSGC, self.with_context(
            creating_company=True)).create(vals)
