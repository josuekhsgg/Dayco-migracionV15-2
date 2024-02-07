
from odoo import models, fields, api, _
import logging
#import pyodbc #Librería de conexión a bases de datos SQL.
import string
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)

class SgcOdooHistory(models.Model):
    _name = 'sgc.odoo.history'
    _description = 'Registro de operaciones entre el SGC y Odoo al momento de sincronizar, activar, desactivar, editar o crear data registros.'

    name = fields.Char("Titulo", required=True)
    fecha_registro = fields.Datetime("Fecha de la operación")
    tipo_error = fields.Char("Tipo de error")
    registro_operacion = fields.Text("Detalles de la operación")
    registro_tecnico = fields.Char("Detalles técnicos")
    category = fields.Text("Categoría")