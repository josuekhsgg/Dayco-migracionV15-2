# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging
import string
from datetime import date, datetime, timedelta
from odoo.exceptions import UserError, ValidationError
from time import time
import re
from dateutil.relativedelta import relativedelta
from calendar import monthrange
import math
from odoo.tools import format_date
from odoo.tools.misc import format_date
import pytz

_logger = logging.getLogger(__name__)

class PartPaymentsFixedAmountsInheritDaycoExtras(models.Model):
    _inherit = 'project_sub_task.part_payments_fixed_amounts'

    sent_payment_date = fields.Char(string='Fecha de envío de facturación', tracking=True)
    estimated_payment_date = fields.Date(string="Fecha estimada de facturación", tracking=True)
    
    @api.constrains('sent_payment_date')
    def _check_access_group_fixed_amount(self):

        if (self.env.ref("dayco_project_fixs.edit_sent_payment_date").id not in self.env.user.groups_id.ids) and self.sent_payment_date:
            raise UserError(_("Su Usuario no posee los permisos para modificar la fecha de envío de facturación."))

class PaymentByPercentageInheritDaycoExtras(models.Model):
    _inherit = ['project_sub_task.payment_by_prencentage']

    sent_payment_date = fields.Char(string='Fecha de envío de facturación', tracking=True)
    estimated_payment_date = fields.Date(string="Fecha estimada de facturación", tracking=True)

    @api.constrains('sent_payment_date')
    def _check_access_group_percentage(self):

        if (self.env.ref("dayco_project_fixs.edit_sent_payment_date").id not in self.env.user.groups_id.ids) and self.sent_payment_date:
            raise UserError(_("Su Usuario no posee los permisos para modificar la fecha de envío de facturación."))

class DaycoExtrasProjectTaskCRON(models.Model):
    _inherit = 'project.task'
    _description = 'Modificaciones del módulo de proyectos para automatizaciones (tareas con facturación automática).'

    sent_payment_date = fields.Char(string='Fecha de envío de facturación', tracking=True)
    valid_agree_estimated_payment_date = fields.Date(string="Fecha estimada de facturación", tracking=True)

    #(21/04/2023)--> Se aplica condición para evitar facturación automática en caso de donwgrade
    def evaluar_caso(self, env):
        '''
        Descripcion:
        '''
        if self.rate_type.tipo_tarifa == 'Sharehosting':
            if self.percent_sub >= 100.0:
                self.send_email_and_notify()
        else:
            if self.valid_agree_single_payment:
                # Es pago unico
                self.pago_unico(env)
            elif self.valid_agree_payment_percentage:
                # Es por porcentaje
                self.por_porcentaje(env)
            elif self.valid_agree_fixed_amount_payment:
                self.por_monto_fijo(env)

    #(24/03/2023)--> Se remueve la validación sobre el check de pedido de ventas (temporalmente desactivado).
    @api.onchange('valid_agree_single_payment','valid_agree_payment_percentage',
    'valid_agree_fixed_amount_payment', 'valid_agree_authorization_location',
    'ally_related', 'valid_agree_default_currency')
    def _onchange_uncheck_validate_so(self):
        #self.validate_so = False
        self.validate_finance = False
        self.prorate_amount = 0
        self.is_prorate = False

    #(10/03/2023) --> Se establece que cuando se marque el campo "validate_finance" se amrque automáticamente el campo "validate_so"
    #Al campo validate_so se le habilita el atributo "force_save" en True.
    @api.constrains('validate_finance')
    def _set_checks_status(self):
        _logger.warning("Se establece el check de finanzas y ventas en el estatus del check de finanzas.")
        for task in self:
            task.validate_so = task.validate_finance
    
            if not task.parent_id:
                _logger.warning("Tarea padre!")
                for sub_task in task.child_ids:
                    _logger.warning("Tarea: "+str(sub_task.name))
    
                    sub_task.validate_so = task.validate_finance
                    sub_task.validate_finance = task.validate_finance
    
                    _logger.warning("Ventas: "+str(sub_task.validate_so))
                    _logger.warning("Finanzas: "+str(sub_task.validate_finance))

    #(14/03/2023) --> Permitir editar la fecha estimada de facturación a una fecha anterior (Temporalmente!)
    @api.onchange('valid_agree_single_payment', 'valid_agree_estimated_payment_date')
    def onchange_valid_agree_estimated_payment_date(self):
        # if not self.valid_agree_estimated_payment_date:
        # 	date_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # 	start = datetime.strptime(date_now, "%Y-%m-%d %H:%M:%S")
        context = self._context
        current_uid = context.get('uid')
        user = self.env['res.users'].browse(current_uid)
        # 	tz = pytz.timezone(user.tz) if user.tz else pytz.utc
        # 	start = pytz.utc.localize(start).astimezone(tz)
        # 	tz_date = start.strftime("%Y-%m-%d %H:%M:%S")
        # 	self.sent_payment_date = tz_date

        # Obtener solo la fecha del dia actual, en la zona horaria del usuario actual

        #Comentadas de la función original
        #Comentadas de la función original
        #if self.valid_agree_estimated_payment_date and self.valid_agree_estimated_payment_date < fields.Date.context_today(user):
        #    raise ValidationError(_("La Fecha estimada de facturación no debe ser anterior a la de fecha de hoy"))
        #Comentadas de la función original
        #Comentadas de la función original
        
        if self.factura_pago_unico and (not self.valid_agree_estimated_payment_date or self.valid_agree_estimated_payment_date != self.factura_pago_unico.date):
            raise ValidationError(_("Esta modificando las condiciones de facturacion automatica cuando ya existe una factura"))


    #(10/03/2023) --> .Se establece la fecha límite desde la tarea padre hacía las sub-tareas.
    @api.constrains('date_deadline')
    def _set_date_deadline_on_child_tasks(self):
        if not self.parent_id:
            _logger.warning("Fecha limite a establecer en tareas hijas: "+str(self.date_deadline))
            
            for task in self.child_ids:
                task.date_deadline = self.date_deadline

    @api.constrains('sent_payment_date')
    def _check_access_group(self):

        if (self.env.ref("dayco_project_fixs.edit_sent_payment_date").id not in self.env.user.groups_id.ids) and self.sent_payment_date:
            raise UserError(_("Su Usuario no posee los permisos para modificar la fecha de envío de facturación."))

    #(16/03/2023) --> Se anula esta verificación para evityar prelar el avance de los proyectos
                        #en caso de atraso por parte de finanzas.
    #@api.constrains('percent_sub')
    #def _check_task(self):
    #    _logger.warning("Tarea a revisar: "+str(self.name))

    #    if self.parent_id:
    #        if self.validate_finance or self.percent_sub == 0:
    #            _logger.warning("Tarea padre asociada cumple con autorización de finanzas.")
    #        else:
    #            raise ValidationError(_("No puede asignar el 100% a esta tarea hasta que su tarea padre asociada tenga la autorización de finanzas (Check de finanzas)"))

    #(09/03/2023) --> Cambios en la función de actualización de tipos y montos de pagos en
    #tareas hijas desde tareas padre.
    def upgrade_payment_type(self):
        self.accept_terms = False
        for record in self.child_ids:
            flag = True
            if record.valid_agree_single_payment:
                if record.factura_pago_unico:
                    flag = False
            elif record.valid_agree_payment_percentage:
                if any(payment.factura_por_porcentaje for payment in record.payment_by_prencentage_ids):
                    flag = False
            elif record.valid_agree_fixed_amount_payment:
                if any(payment.factura_por_monto_fijo for payment in record.part_payments_fixed_amounts_ids):
                    flag = False

            if flag:
                record.valid_agree_single_payment = self.valid_agree_single_payment
                record.valid_agree_payment_percentage = self.valid_agree_payment_percentage
                record.valid_agree_fixed_amount_payment = self.valid_agree_fixed_amount_payment
                #Moneda/Localidad/Monto
                record.valid_agree_default_currency = self.valid_agree_default_currency
                record.valid_agree_authorization_location = self.valid_agree_authorization_location
                record.validate_so = self.validate_so
                record.validate_finance = self.validate_finance
                record.ally_related = self.ally_related

                if self.valid_agree_single_payment:
                    _logger.warning("Monto de la subtarea: "+str(record.valid_agree_sales_order_line_amount))
                    record.valid_agree_estimated_payment_date = self.valid_agree_estimated_payment_date
                    
                if self.valid_agree_payment_percentage:
                    for pay in record.payment_by_prencentage_ids:
                        pay.unlink()
                    for rec in self.payment_by_prencentage_ids:
                        #Ajustar la linea a cada tarea específica.
                        #_logger.warning("Monto de la subtarea: "+str(record.valid_agree_sales_order_line_amount))
                        original_rec_amount = rec.amount
                        rec.amount = record.valid_agree_sales_order_line_amount*(rec.percentage_value/100)
                        rec.copy(default={'projectsubtask_payment_by_prencentage_id': record.id})
                        rec.amount = original_rec_amount

                #(09/03/2023.) --> Descartado el monto fijo en las tareas padre, solo se usa únioc y monto fijo.
                #if self.valid_agree_fixed_amount_payment:
                #    for pay in record.part_payments_fixed_amounts_ids:
                #        pay.unlink()
                #    for rec in self.part_payments_fixed_amounts_ids:
                        #Ajustar la linea a cada tarea específica.
                        #1- Se obtiene el monto de la tarea padre.
                        #2- Se cálcula el nuevo porcentaje
                #        new_percentage = float(rec.amount*100)/float(self.valid_agree_sales_order_line_amount)
                #        _logger.warning("Nuevo porcentaje: "+str(new_percentage))
                #        _logger.warning("Monto de la subtarea: "+str(record.valid_agree_sales_order_line_amount)+" Porcentaje a usar: "+str(new_percentage))
                        
                #        original_rec_amount = rec.amount
                #        rec.amount = record.valid_agree_sales_order_line_amount*(new_percentage/100)
                        
                #        _logger.warning("Nuevo monto de linea por monto fijo: "+str(rec.amount))

                #        rec.copy(default={'projectsubtask_part_payments_fixed_amounts_id': record.id})

                #        rec.amount = original_rec_amount

    @api.onchange('valid_agree_estimated_payment_date', 'payment_by_prencentage_ids', 'part_payments_fixed_amounts_ids', 'validate_so','validate_finance')
    def calculate_prorate_amount(self, new_date=None):
        current_uid = self._context.get('uid')
        user = self.env['res.users'].browse(current_uid)
        unit_price = self.valid_agree_sales_order_line_amount / 30
        end_of_month = None
        day_difference = None
        first_payment_date = None
        dates = list()

        if self.rate_type.tipo_tarifa == 'Recurrente' and not self.valid_agree_fixed_amount_payment:
            # Si es un pago único se calcula el monto con la fecha de pago estimada
            if self.valid_agree_estimated_payment_date:
                day_difference = 31 - self.valid_agree_estimated_payment_date.day
            else:
                # Si es por porcentaje, o por partes, se busca la fecha estimada menor
                # Y esta es la utilizada para los cálculos
                if self.payment_by_prencentage_ids:
                    for rec in self.payment_by_prencentage_ids:
                        if rec.estimated_payment_date:
                            day_difference = 31 - rec.estimated_payment_date.day
                            if day_difference and self.parent_id:
                                #'amount' : day_difference * unit_price * (rec.percentage_value / 100)
                                rec.update({
                                    'amount' : self.valid_agree_sales_order_line_amount*(rec.percentage_value/100)
                                })

            if new_date:
                day_difference = 31 - new_date.day

            prorate_amount = 0
            if self.valid_agree_payment_percentage:
                prorate_sum = 0
                for rec in self.payment_by_prencentage_ids:
                    if rec.amount:
                        prorate_sum += rec.amount
                prorate_amount = prorate_sum

            elif self.valid_agree_single_payment and day_difference:
                prorate_amount = day_difference * unit_price

            if day_difference:
                self.is_prorate = True
                self.prorate_amount = prorate_amount
                
                if self.parent_id:
                    if not self.valid_agree_payment_percentage:
                        return {
                            'warning': {
                                'title': 'Alerta',
                                'message': "Se aplica PRORRATEO. El monto a cancelar es: {} ".format(self.prorate_amount)
                            }
                        }
                    else:
                        if len(self.payment_by_prencentage_ids) == 1:
                            return {
                                'warning': {
                                    'title': 'Alerta',
                                    'message': "Se aplica PRORRATEO."
                                }
                            }

    #Función a ejecutar usando un cron job.
    @api.model
    def sync_tareas_finalizadas(self):
        _logger.warning("########## - Ejecución cada día - ##########")
        _logger.warning("########## - Ejecución cada día - ##########")

        #Buscar las tareas activas y verificar que cumplan con los parámetros necesarios para ser revisadas.
        #Deben tener un tipo de servicio establecido.
        tareas_validadas = self.env['project.task'].search([('validate_finance', '=', True),
                                                            ('service_type', '!=', False),
                                                            ('parent_id', '!=', False),
                                                            '|','|',('valid_agree_single_payment', '=', True),
                                                            ('valid_agree_payment_percentage', '=', True),
                                                            ('valid_agree_fixed_amount_payment', '=', True)])

        #Solo debug
        debug_count = 0

        #Se analiza tarea por tarea para ir generando la facturación automática.
        for tarea in tareas_validadas:
            _logger.warning("Nombre: "+str(tarea.name))
            _logger.warning("% de avance de la tarea (Global): "+str(tarea.percent_sub))
            _logger.warning("Proyecto asociado (Antes de validar):: "+str(tarea.project_id.name))
            
            if tarea.rate_type.tipo_tarifa == 'Unica':
                _logger.warning("Tipo de tarifa Única")
                #Se puede verificar la fecha estimada de facturación directamente para determinar
                #si procede al chequeo automático de generación de factura.
                
                #Para colocar fecha de envío de facturación y generar la respectiva factura en status borrador
                #se deben cumplir las siguientes condiciones:

                #1- Fecha estimada de facturación establecida, <= a la fecha actual en la que se ejecuta el cron.
                #2- Checks de ventas en True
                #3- Checks de finanzas en True
                #4- Porcentaje de la tarea al 100%

                #Se trata de una tarea que va incluida en una misma factura
                #Se pueden presentar los siguientes casos:
                
                if tarea.valid_agree_single_payment and 2 == 1:
                    #1- Pago único: Se registra una sola linea de factura con el monto
                    #prorrateado de la tarea.
                    _logger.warning("Tarea con pago único")

                    #Una vez se cumplan dichos parámetros se procede a establecer la fecha de envío y generar
                    #la factura respectiva en estatus borrador de forma automática.
                    #Se debe comprobar si la fecha estimada de facturación existe.
                    if tarea.valid_agree_estimated_payment_date:
                        _logger.warning("Tarea con pago único y tarifa Única")

                        if tarea.valid_agree_estimated_payment_date <= datetime.now().date() and not tarea.sent_payment_date and tarea.validate_finance and tarea.percent_sub > 99:
                            _logger.warning("Tarea "+str(tarea.name)+" (Única) cumple con los requisitos de la facturación automática.")
                            _logger.warning("Proyecto asociado: "+str(tarea.project_id.name))

                            #22/02/2023
                            #Para el alcance actual se establece solo la fecha de envío de facturación
                            #la facturación automática se deja para mejora continua.
                            tarea.sent_payment_date = datetime.now()
                            debug_count = 1000

                """            
                            #Se deben obtener las posibles lineas de facturación que se van a incluir
                            #en una factura existente o se van a incluir en una nueva factura.
                            _logger.warning("Invoices ids: "+str(tarea.sale_line_id.order_id.invoice_ids))
                            #Se verifica si no existe una factura asociada a las tarea con tarifa única
                            #a- Si existe una factura se ignora la tarea.
                            #b- Si no existe una factura se crea una o se agrega a una existente y se establece la fecha de envío de facturación.

                            new_invoice = True
                            #Se deben buscar las tareas que esten relacionadas con el pedido de venta de la tarea a la que se esta analizando
                            if not tarea.sale_line_id.order_id.invoice_ids:
                                _logger.warning("Pedido de venta asociado a la tarea: "+str(tarea.sale_line_id.order_id.name))
                                tareas_proyecto = self.env['project.task'].search([('project_id', '=', tarea.project_id.id),('sale_line_id.order_id', '=', tarea.sale_line_id.order_id.id)])

                                _logger.warning("Tareas de proyecto encontradas: "+str(tareas_proyecto))
                                #Se buscan las facturas existentes asociadas al proyecto
                                for tarea_invoice in tareas_proyecto:
                                    _logger.warning("Tarea a la que se le busca factura: "+str(tarea_invoice.name))
                                    for invoice in tarea_invoice.sale_line_id.order_id.invoice_ids:
                                        #Si hay facturas, se comparan las fechas
                                        #1- Fecha estimada de facturación.
                                        #2- Fecha de creación de la factura.

                                        #Si no hay una factura con fecha de creación igual a la fecha estimada de
                                        #facturación de la tarea que se esta revisando se crea una factura nueva
                                        #con los valores indicados.

                                        _logger.warning("Invoice: "+str(invoice.name))
                                        _logger.warning("Fecha de creación del invoice: "+str(invoice.create_date))
                                        _logger.warning("Fecha estimada de facturación de la tarea: "+str(tarea.valid_agree_estimated_payment_date))

                                        #if invoice.create_date.date() == tarea.valid_agree_estimated_payment_date:
                                        #    _logger.warning("Se inserta la linea de la tarea: "+str(tarea.name)+" en la factura: "+str(invoice.name))
                                        #    new_invoice = False
                                            #Encontró una factura en la cual insertar la nueva linea, se dteiene el proceso.
                                        #    break
                                        #else:
                                        #    _logger.warning("Fechas diferentes, buscando otra factura de las tareas del proyecto.")
                                    
                                    #Si encontró la linea se sale del bucle de busqueda de tareas principal
                                    #if not new_invoice:
                                    #    break
                                    
                                debug_count = 1000
                                #print(awraew)
                                #¿Se debe crear una factura nueva o agregar una nueva linea a una factura existente?
                                
                                #else:
                                #    _logger.warning("Se agrega una linea de facturación a una factura existente y se asocia a esta tarea.")
                                #    print(awraew)

                            else:
                                #Se deben verificar las lineas de la factura asociada a la tarea para verificar que ya la linea asociada a la tarea se
                                #agregó correctamente, de no haberse agregado se asocia la nueva linea a la factura existente
                                #si esta factura se encuentra en la misma fecha que la fecha estimada de facturación de la tarea
                                #que se encuentra en revisión actualmente.

                                for invoice_existente_en_tarea_de_proyecto in tarea.sale_line_id.order_id.invoice_ids:
                                    _logger.warning("Nombre de la factura a revisar para agregar linea nueva: "+str(invoice_existente_en_tarea_de_proyecto.name))
                                    _logger.warning("Fecha de creación de esta factura: "+str(invoice_existente_en_tarea_de_proyecto.create_date.date()))
                                    _logger.warning("Fecha estimada de facturación de la tarea: "+str(tarea.valid_agree_estimated_payment_date))

                                    #Si la fecha de la factura y la fecha estimada de facturación d ela tarea son iguales se procede a revisar las lineas de la factura encontrada.
                                    if invoice_existente_en_tarea_de_proyecto.create_date.date() == tarea.valid_agree_estimated_payment_date:
                                        _logger.warning("Se encontró factura con fecha igual a la fecha estimada de facturación d ela tarea.")
                                        new_invoice = False
                                        existe_linea_en_factura = False

                                        for invoice_line in invoice_existente_en_tarea_de_proyecto:
                                            _logger.warning("Linea de facturación: "+str(invoice_line.name))

                                            #Si existe la linea en la factura no se agrega el item
                                            if invoice_line.name == tarea.name:
                                                existe_linea_en_factura = True

                                        if not existe_linea_en_factura:
                                            #Se agrega la nueva linea a la factura existente.
                                            _logger.warning("Se agrega la nueva linea de facturación a la factura: "+str(invoice_existente_en_tarea_de_proyecto.name))

                                            #Se preparan las lineas de facturación a enviar
                                            sale_order_invoice_lines = tarea.group_invoices_modified(tarea.valid_agree_estimated_payment_date, tarea.valid_agree_authorization_location)

                                            partner_valido_para_invoice_automatica = True
                                            #if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.property_account_payable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.journal_advance_purchases_id or not tarea.project_id.partner_id.account_advance_sales_id or not tarea.project_id.partner_id.account_advance_purchases_id:
                                            if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.account_payment_partial_sales_id:
                                                partner_valido_para_invoice_automatica = False
                                            
                                            if len(sale_order_invoice_lines) > 0 and partner_valido_para_invoice_automatica:
                                                _logger.warning("Se agregan las lineas de facturación encontradas a la factura del Cliente validado exitosamente.")
                                                _logger.warning("Sale order lines nuevas a agregar a la factura existente: "+str(sale_order_invoice_lines))

                                                invoice_existente_en_tarea_de_proyecto.write({'invoice_line_ids': sale_order_invoice_lines})

                                                #Se establece el status en la factura unica o en las partes de las facturas por monto fijo o porcentaje.
                                                tarea._set_status_in_task(invoice_existente_en_tarea_de_proyecto,item)

                                                #Se términa el proceso para evitar agregar esta linea de factura en otra factura repitiendo el mismo registro sin necesidad.
                                                break #--> Este break es del 'for invoice_existente_en_tarea_de_proyecto'
                                        else:
                                            _logger.warning("Se omite la linea de facturación porque ya se encuentra una linea igual en la factura, se debe revisar si se trata de un duplicado que no se debe agregar de nuevo a la factura.")

                                #_logger.warning("Tarea con tarifa única y pago único ya posee factura asociada, revise la tarea en caso de que se deba realizar algún ajuste o rehacer la factura.")
                                #print(awraew)
                            
                            if new_invoice:
                                _logger.warning("Se crea la factura nueva y se inserta una linea de facturación asociada a esta tarea.")

                                #Se envían los datos para crear la factura nueva.                                    
                                sale_order_invoice_lines = tarea.group_invoices_modified(tarea.valid_agree_estimated_payment_date, tarea.valid_agree_authorization_location)
                                _logger.warning("Sale order invoice lines: "+str(sale_order_invoice_lines))

                                #Antes de proceder con la facturación automática, se debe verificar que el Cliente al que se
                                #le va a crear la factura tenga la contabilidad configurada (Ficha del contacto --> ficha de contabilidad)
                                #Los campos a validar son:
                                #1- Cuenta de cobro (Asiento contable)
                                #2- Cuenta de pago (Asiento contable)
                                #3- Diario de anticipos ventas
                                #4- Diario de anticipos compras
                                #5- Cuenta de anticipos ventas
                                #6- Cuenta de anticipos compras

                                partner_valido_para_invoice_automatica = True
                                #if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.property_account_payable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.journal_advance_purchases_id or not tarea.project_id.partner_id.account_advance_sales_id or not tarea.project_id.partner_id.account_advance_purchases_id:
                                if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.account_payment_partial_sales_id:
                                    partner_valido_para_invoice_automatica = False

                                if len(sale_order_invoice_lines) > 0 and partner_valido_para_invoice_automatica:

                                    #1- Se crea la factura y genera un move_id.
                                    #2- Este move_id se asigna al account.move.line.
                                    #3- Este account.move.line se asigna a la factura recien creada.
                                    vals = {
                                        'name': '/',
                                        'invoice_user_id': tarea.user_id.id,
                                        'type': 'out_invoice',
                                        'date': tarea.valid_agree_estimated_payment_date,
                                        'partner_id': tarea.partner_id.id,
                                        'partner_shipping_id': tarea.partner_id.id,
                                    }

                                    tarea.create_invoice_tarifa_unica_recurrente(tarea,vals,sale_order_invoice_lines)
                                else:
                                    _logger.warning("No se procede con la facturación automática porque falta configurar la parte contable del Cliente, por favor, verifique la información contable del Cliente e intente nuevamente.")

                            debug_count = 1000
                """
                
                if tarea.valid_agree_payment_percentage and 2 == 1:
                    #2- Pago por porcentaje: Se registran N lineas de factura con el monto
                    #prorrateado de cada una de las N partes de la tabla de los pagos (%).
                    _logger.warning("Tarea con pago por porcentage")

                    for item in tarea.payment_by_prencentage_ids:
                        _logger.warning("Fecha estimada del item (%): "+str(item.estimated_payment_date))
                        _logger.warning("Fecha de envío de facturación: "+str(item.sent_payment_date))
                        _logger.warning("(%) Avance de la linea: "+str(item.percentage_value)) 

                        if item.estimated_payment_date:
                            if item.estimated_payment_date <= datetime.now().date() and not item.sent_payment_date and tarea.validate_finance and tarea.percent_sub >= item.percentage_value:
                                _logger.warning("Tarea "+str(tarea.name)+" (Porcentaje %) cumple con los requisitos de la facturación automática.")
                                _logger.warning("Proyecto asociado: "+str(tarea.project_id.name))

                                #22/02/2023
                                #Para el alcance actual se establece solo la fecha de envío de facturación
                                #la facturación automática se deja para mejora continua.
                                item.sent_payment_date = datetime.now()
                                debug_count = 1000

                """
                                new_invoice = True
                                #Se deben buscar las tareas que esten relacionadas con el pedido de venta de la tarea a la que se esta analizando
                                if not tarea.sale_line_id.order_id.invoice_ids:
                                    _logger.warning("Pedido de venta asociado a la tarea: "+str(tarea.sale_line_id.order_id.name))
                                    tareas_proyecto = self.env['project.task'].search([('project_id', '=', tarea.project_id.id),('sale_line_id', '=', tarea.sale_line_id.id)])

                                    _logger.warning("Tareas de proyecto encontradas: "+str(tareas_proyecto))
                                    #Se buscan las facturas existentes asociadas al proyecto
                                    for tarea_invoice in tareas_proyecto:
                                        _logger.warning("Tarea a la que se le busca factura: "+str(tarea_invoice.name))
                                        for invoice in tarea_invoice.sale_line_id.order_id.invoice_ids:
                                            #Si hay facturas, se comparan las fechas
                                            #1- Fecha estimada de facturación.
                                            #2- Fecha de creación de la factura.

                                            #Si no hay una factura con fecha de creación igual a la fecha estimada de
                                            #facturación de la tarea que se esta revisando se crea una factura nueva
                                            #con los valores indicados.

                                            _logger.warning("Invoice: "+str(invoice.name))
                                            _logger.warning("Fecha de creación del invoice: "+str(invoice.create_date))
                                            _logger.warning("Fecha estimada de facturación del item: "+str(item.estimated_payment_date))

                                            #if invoice.create_date.date() == item.estimated_payment_date:
                                            #    _logger.warning("Se inserta la linea de la tarea: "+str(tarea.name)+" en la factura: "+str(invoice.name))
                                            #    new_invoice = False
                                            #    #Encontró una factura en la cual insertar la nueva linea, se dteiene el proceso.
                                            #    break
                                            #else:
                                            #    _logger.warning("Fechas diferentes, buscando otra factura de las tareas del proyecto.")
                                        
                                        #Si encontró la linea se sale del bucle de busqueda de tareas principal
                                        #if not new_invoice:
                                        #    break
                                    
                                else:
                                    #En este caso se agrega la linea de facturación a la factura existente o se crea una factura nueva según el caso.
                                    _logger.warning("Revisar facturas existentes para ver si se inserta la nueva linea en una factura existente o se crea una factura nueva.")

                                    #Revisamos las fechas de las facturas existentes
                                    for invoice_existente_en_tarea_de_proyecto in tarea.sale_line_id.order_id.invoice_ids:
                                        _logger.warning("Factura: "+str(invoice_existente_en_tarea_de_proyecto.name))
                                        _logger.warning("Fecha de creación: "+str(invoice_existente_en_tarea_de_proyecto.create_date.date()))

                                        if invoice_existente_en_tarea_de_proyecto.create_date.date() == item.estimated_payment_date and tarea.sale_line_id.order_id.maximum_recurring_lines < 12:
                                            _logger.warning("Se agrega esta linea de facturación a la factura existente: "+str(invoice_existente_en_tarea_de_proyecto.name))
                                            new_invoice = False

                                            existe_linea_en_factura = False

                                            #Evaluar condición!!
                                            #Evaluar condición!!
                                            for invoice_line in invoice_existente_en_tarea_de_proyecto:
                                                _logger.warning("Linea de facturación: "+str(invoice_line.name))

                                                #Si existe la linea en la factura no se agrega el item
                                                if invoice_line.name == tarea.name:
                                                    existe_linea_en_factura = True

                                            #Evaluar condición!!
                                            #Evaluar condición!!

                                            if not existe_linea_en_factura:
                                                #Se agrega la nueva linea a la factura existente.
                                                _logger.warning("Se agrega la nueva linea de facturación a la factura: "+str(invoice_existente_en_tarea_de_proyecto.name))

                                                #Se preparan las lineas de facturación a enviar
                                                sale_order_invoice_lines = tarea.group_invoices_modified(item.estimated_payment_date, tarea.valid_agree_authorization_location)

                                                partner_valido_para_invoice_automatica = True
                                                #if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.property_account_payable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.journal_advance_purchases_id or not tarea.project_id.partner_id.account_advance_sales_id or not tarea.project_id.partner_id.account_advance_purchases_id:
                                                if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.account_payment_partial_sales_id:
                                                    partner_valido_para_invoice_automatica = False
                                                
                                                if len(sale_order_invoice_lines) > 0 and partner_valido_para_invoice_automatica:
                                                    _logger.warning("Se agregan las lineas de facturación encontradas a la factura del Cliente validado exitosamente.")
                                                    _logger.warning("Sale order lines nuevas a agregar a la factura existente: "+str(sale_order_invoice_lines))

                                                    invoice_existente_en_tarea_de_proyecto.write({'invoice_line_ids': sale_order_invoice_lines})
                                                    
                                                    #Se establece el status en la factura unica o en las partes de las facturas por monto fijo o porcentaje.
                                                    tarea._set_status_in_task(invoice_existente_en_tarea_de_proyecto,item)

                                                    #Se términa el proceso para evitar agregar esta linea de factura en otra factura repitiendo el mismo registro sin necesidad.
                                                    break #--> Este break es del 'for invoice_existente_en_tarea_de_proyecto'
                                            else:
                                                _logger.warning("Se omite la linea de facturación porque ya se encuentra una linea igual en la factura, se debe revisar si se trata de un duplicado que no se debe agregar de nuevo a la factura.")

                                        else:
                                            _logger.warning("Factura con fecha de creación a la fecha estimada de facturación establecida.")

                                #¿Se debe crear una factura nueva o agregar una nueva linea a una factura existente?
                                if new_invoice:
                                    _logger.warning("Se crea la factura nueva y se inserta una linea de facturación asociada a esta linea de pago de la tarea.")

                                    #Se envían los datos para crear la factura nueva.                                    
                                    sale_order_invoice_lines = tarea.group_invoices_modified(item.estimated_payment_date, tarea.valid_agree_authorization_location)
                                    _logger.warning("Sale order invoice lines: "+str(sale_order_invoice_lines))

                                    #Antes de proceder con la facturación automática, se debe verificar que el Cliente al que se
                                    #le va a crear la factura tenga la contabilidad configurada (Ficha del contacto --> ficha de contabilidad)
                                    #Los campos a validar son:
                                    #1- Cuenta de cobro (Asiento contable)
                                    #2- Cuenta de pago (Asiento contable)
                                    #3- Diario de anticipos ventas
                                    #4- Diario de anticipos compras
                                    #5- Cuenta de anticipos ventas
                                    #6- Cuenta de anticipos compras

                                    partner_valido_para_invoice_automatica = True
                                    #if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.property_account_payable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.journal_advance_purchases_id or not tarea.project_id.partner_id.account_advance_sales_id or not tarea.project_id.partner_id.account_advance_purchases_id:
                                    if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.account_payment_partial_sales_id:
                                        partner_valido_para_invoice_automatica = False

                                    if len(sale_order_invoice_lines) > 0 and partner_valido_para_invoice_automatica:

                                        #1- Se crea la factura y genera un move_id.
                                        #2- Este move_id se asigna al account.move.line.
                                        #3- Este account.move.line se asigna a la factura recien creada.
                                        vals = {
                                            'name': '/',
                                            'invoice_user_id': tarea.user_id.id,
                                            'type': 'out_invoice',
                                            'date': item.estimated_payment_date,
                                            'partner_id': tarea.partner_id.id,
                                            'partner_shipping_id': tarea.partner_id.id,
                                        }

                                        #Cuando se envía el item se trata de una tarifa única con pago en partes por % o fijo.
                                        #Al crearse la factura se establece el status con la parte o partes necesarias durante
                                        #la creación de dicha factura.
                                        tarea.create_invoice_tarifa_unica_recurrente(tarea,vals,sale_order_invoice_lines, item)

                                #else:
                                #    _logger.warning("Se agrega una linea de facturación a una factura existente y se asocia a esta tarea.")

                                #Solo debug
                                debug_count = 1000

                        else:
                            _logger.warning("Parte de la tarea sin fecha estimada de facturación establecida.")

                """
                
                if tarea.valid_agree_fixed_amount_payment and 2 == 1:
                    #3- Pago por monto fijo: Se registran N lineas de factura con el monto
                    #prorrateado de cada una de las N partes de la tabla de los pagos (fijo)
                    _logger.warning("Tarea con pago por monto fijo")

                    for item in tarea.part_payments_fixed_amounts_ids:
                        _logger.warning("Fecha estimada del item (fijo): "+str(item.estimated_payment_date))
                        _logger.warning("Fecha de envío de facturación: "+str(item.sent_payment_date))
                        _logger.warning("(fijo) Avance de la linea: "+str(item.invoiced_progress_percentage)) 

                        if item.estimated_payment_date:
                            if item.estimated_payment_date <= datetime.now().date() and not item.sent_payment_date and tarea.validate_finance and tarea.percent_sub >= item.invoiced_progress_percentage:
                                _logger.warning("Tarea "+str(tarea.name)+" (fijo) cumple con los requisitos de la facturación automática.")
                                _logger.warning("Proyecto asociado: "+str(tarea.project_id.name))

                                #22/02/2023
                                #Para el alcance actual se establece solo la fecha de envío de facturación
                                #la facturación automática se deja para mejora continua.
                                item.sent_payment_date = datetime.now()
                                debug_count = 1000

                """
                                new_invoice = True
                                #Se deben buscar las tareas que esten relacionadas con el pedido de venta de la tarea a la que se esta analizando
                                if not tarea.sale_line_id.order_id.invoice_ids:
                                    _logger.warning("Pedido de venta asociado a la tarea: "+str(tarea.sale_line_id.order_id.name))
                                    tareas_proyecto = self.env['project.task'].search([('project_id', '=', tarea.project_id.id),('sale_line_id', '=', tarea.sale_line_id.id)])

                                    _logger.warning("Tareas de proyecto encontradas: "+str(tareas_proyecto))
                                    #Se buscan las facturas existentes asociadas al proyecto
                                    for tarea_invoice in tareas_proyecto:
                                        _logger.warning("Tarea a la que se le busca factura: "+str(tarea_invoice.name))
                                        for invoice in tarea_invoice.sale_line_id.order_id.invoice_ids:
                                            #Si hay facturas, se comparan las fechas
                                            #1- Fecha estimada de facturación.
                                            #2- Fecha de creación de la factura.

                                            #Si no hay una factura con fecha de creación igual a la fecha estimada de
                                            #facturación de la tarea que se esta revisando se crea una factura nueva
                                            #con los valores indicados.

                                            _logger.warning("Invoice: "+str(invoice.name))
                                            _logger.warning("Fecha de creación del invoice: "+str(invoice.create_date))
                                            _logger.warning("Fecha estimada de facturación del item: "+str(item.estimated_payment_date))

                                            #if invoice.create_date.date() == item.estimated_payment_date:
                                            #    _logger.warning("Se inserta la linea de la tarea: "+str(tarea.name)+" en la factura: "+str(invoice.name))
                                            #    new_invoice = False
                                                #Encontró una factura en la cual insertar la nueva linea, se dteiene el proceso.
                                            #    break
                                            #else:
                                            #    _logger.warning("Fechas diferentes, buscando otra factura de las tareas del proyecto.")
                                        
                                        #Si encontró la linea se sale del bucle de busqueda de tareas principal
                                        #if not new_invoice:
                                        #    break
                                    
                                else:
                                    #En este caso se agrega la linea de facturación a la factura existente o se crea una factura nueva según el caso.
                                    _logger.warning("Revisar facturas existentes para ver si se inserta la nueva linea en una factura existente o se crea una factura nueva.")

                                    #Revisamos las fechas de las facturas existentes
                                    for invoice_existente_en_tarea_de_proyecto in tarea.sale_line_id.order_id.invoice_ids:
                                        _logger.warning("Factura: "+str(invoice_existente_en_tarea_de_proyecto.name))
                                        _logger.warning("Fecha de creación: "+str(invoice_existente_en_tarea_de_proyecto.create_date))

                                        if invoice_existente_en_tarea_de_proyecto.create_date.date() == item.estimated_payment_date and tarea.sale_line_id.order_id.maximum_recurring_lines < 12:
                                            _logger.warning("Se agrega esta linea de facturación a la factura existente: "+str(invoice_existente_en_tarea_de_proyecto.name))
                                            new_invoice = False

                                            existe_linea_en_factura = False

                                            #Evaluar condición!!
                                            #Evaluar condición!!
                                            for invoice_line in invoice_existente_en_tarea_de_proyecto:
                                                _logger.warning("Linea de facturación: "+str(invoice_line.name))

                                                #Si existe la linea en la factura no se agrega el item
                                                if invoice_line.name == tarea.name:
                                                    existe_linea_en_factura = True

                                            #Evaluar condición!!
                                            #Evaluar condición!!

                                            if not existe_linea_en_factura:
                                                #Se agrega la nueva linea a la factura existente.
                                                _logger.warning("Se agrega la nueva linea de facturación a la factura: "+str(invoice_existente_en_tarea_de_proyecto.name))

                                                #Se preparan las lineas de facturación a enviar
                                                sale_order_invoice_lines = tarea.group_invoices_modified(item.estimated_payment_date, tarea.valid_agree_authorization_location)

                                                partner_valido_para_invoice_automatica = True
                                                #if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.property_account_payable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.journal_advance_purchases_id or not tarea.project_id.partner_id.account_advance_sales_id or not tarea.project_id.partner_id.account_advance_purchases_id:
                                                if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.account_payment_partial_sales_id:
                                                    partner_valido_para_invoice_automatica = False
                                                
                                                if len(sale_order_invoice_lines) > 0 and partner_valido_para_invoice_automatica:
                                                    _logger.warning("Se agregan las lineas de facturación encontradas a la factura del Cliente validado exitosamente.")
                                                    _logger.warning("Sale order lines nuevas a agregar a la factura existente: "+str(sale_order_invoice_lines))

                                                    invoice_existente_en_tarea_de_proyecto.write({'invoice_line_ids': sale_order_invoice_lines})
                                                    
                                                    #Se establece el status en la factura unica o en las partes de las facturas por monto fijo o porcentaje.
                                                    tarea._set_status_in_task(invoice_existente_en_tarea_de_proyecto,item)

                                                    #Se términa el proceso para evitar agregar esta linea de factura en otra factura repitiendo el mismo registro sin necesidad.
                                                    break #--> Este break es del 'for invoice_existente_en_tarea_de_proyecto'
                                            else:
                                                _logger.warning("Se omite la linea de facturación porque ya se encuentra una linea igual en la factura, se debe revisar si se trata de un duplicado que no se debe agregar de nuevo a la factura.")

                                        else:
                                            _logger.warning("Factura con fecha de creación a la fecha estimada de facturación establecida.")

                                #¿Se debe crear una factura nueva o agregar una nueva linea a una factura existente?
                                if new_invoice:
                                    _logger.warning("Se crea la factura nueva y se inserta una linea de facturación asociada a esta linea de pago de la tarea.")

                                    #Se envían los datos para crear la factura nueva.                                    
                                    sale_order_invoice_lines = tarea.group_invoices_modified(item.estimated_payment_date, tarea.valid_agree_authorization_location)
                                    _logger.warning("Sale order invoice lines: "+str(sale_order_invoice_lines))

                                    #Antes de proceder con la facturación automática, se debe verificar que el Cliente al que se
                                    #le va a crear la factura tenga la contabilidad configurada (Ficha del contacto --> ficha de contabilidad)
                                    #Los campos a validar son:
                                    #1- Cuenta de cobro (Asiento contable)
                                    #2- Cuenta de pago (Asiento contable)
                                    #3- Diario de anticipos ventas
                                    #4- Diario de anticipos compras
                                    #5- Cuenta de anticipos ventas
                                    #6- Cuenta de anticipos compras

                                    partner_valido_para_invoice_automatica = True
                                    #if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.property_account_payable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.journal_advance_purchases_id or not tarea.project_id.partner_id.account_advance_sales_id or not tarea.project_id.partner_id.account_advance_purchases_id:
                                    if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.account_payment_partial_sales_id:
                                        partner_valido_para_invoice_automatica = False

                                    if len(sale_order_invoice_lines) > 0 and partner_valido_para_invoice_automatica:

                                        #1- Se crea la factura y genera un move_id.
                                        #2- Este move_id se asigna al account.move.line.
                                        #3- Este account.move.line se asigna a la factura recien creada.
                                        vals = {
                                            'name': '/',
                                            'invoice_user_id': tarea.user_id.id,
                                            'type': 'out_invoice',
                                            'date': item.estimated_payment_date,
                                            'partner_id': tarea.partner_id.id,
                                            'partner_shipping_id': tarea.partner_id.id,
                                        }

                                        #Cuando se envía el item se trata de una tarifa única con pago en partes por % o fijo.
                                        #Al crearse la factura se establece el status con la parte o partes necesarias durante
                                        #la creación de dicha factura.
                                        tarea.create_invoice_tarifa_unica_recurrente(tarea,vals,sale_order_invoice_lines, item)
                                        
                                #else:
                                #    _logger.warning("Se agrega una linea de facturación a una factura existente y se asocia a esta tarea.")
                                #Solo debug
                                debug_count = 1000

                        else:
                            _logger.warning("Parte de la tarea sin fecha estimada de facturación establecida.")
                """

            if tarea.rate_type.tipo_tarifa == 'Recurrente':
                _logger.warning("Tipo de tarifa Recurrente")
                
                if tarea.valid_agree_single_payment and 2 == 1:
                    #1- Pago único: Se registra una sola linea de factura con el monto
                    #prorrateado de la tarea.
                    _logger.warning("Tarea con pago único")

                    #Una vez se cumplan dichos parámetros se procede a establecer la fecha de envío y generar
                    #la factura respectiva en estatus borrador de forma automática.
                    #Se debe comprobar si la fecha estimada de facturación existe.
                    if tarea.valid_agree_estimated_payment_date:
                        _logger.warning("Tarea con pago único y tarifa Recurrente")

                        if tarea.valid_agree_estimated_payment_date <= datetime.now().date() and not tarea.sent_payment_date and tarea.validate_finance and tarea.percent_sub > 99:
                            _logger.warning("Tarea "+str(tarea.name)+" (Única) cumple con los requisitos de la facturación automática.")
                            _logger.warning("Proyecto asociado: "+str(tarea.project_id.name))
                            
                            #22/02/2023
                            #Para el alcance actual se establece solo la fecha de envío de facturación
                            #la facturación automática se deja para mejora continua.
                            tarea.sent_payment_date = datetime.now()
                            debug_count = 1000

                            """
                            #Se deben obtener las posibles lineas de facturación que se van a incluir
                            #en una factura existente o se van a incluir en una nueva factura.
                            _logger.warning("Invoices ids: "+str(tarea.sale_line_id.order_id.invoice_ids))
                            #Se verifica si no existe una factura asociada a las tarea con tarifa única
                            #a- Si existe una factura se ignora la tarea.
                            #b- Si no existe una factura se crea una o se agrega a una existente y se establece la fecha de envío de facturación.

                            new_invoice = True
                            #Se deben buscar las tareas que esten relacionadas con el pedido de venta de la tarea a la que se esta analizando
                            if not tarea.sale_line_id.order_id.invoice_ids:
                                _logger.warning("Pedido de venta asociado a la tarea: "+str(tarea.sale_line_id.order_id.name))
                                tareas_proyecto = self.env['project.task'].search([('project_id', '=', tarea.project_id.id),('sale_line_id.order_id', '=', tarea.sale_line_id.order_id.id)])

                                _logger.warning("Tareas de proyecto encontradas: "+str(tareas_proyecto))
                                #Se buscan las facturas existentes asociadas al proyecto
                                for tarea_invoice in tareas_proyecto:
                                    _logger.warning("Tarea a la que se le busca factura: "+str(tarea_invoice.name))
                                    for invoice in tarea_invoice.sale_line_id.order_id.invoice_ids:
                                        #Si hay facturas, se comparan las fechas
                                        #1- Fecha estimada de facturación.
                                        #2- Fecha de creación de la factura.

                                        #Si no hay una factura con fecha de creación igual a la fecha estimada de
                                        #facturación de la tarea que se esta revisando se crea una factura nueva
                                        #con los valores indicados.

                                        _logger.warning("Invoice: "+str(invoice.name))
                                        _logger.warning("Fecha de creación del invoice: "+str(invoice.create_date))
                                        _logger.warning("Fecha estimada de facturación de la tarea: "+str(tarea.valid_agree_estimated_payment_date))

                                        #if invoice.create_date.date() == tarea.valid_agree_estimated_payment_date:
                                        #    _logger.warning("Se inserta la linea de la tarea: "+str(tarea.name)+" en la factura: "+str(invoice.name))
                                        #    new_invoice = False
                                            #Encontró una factura en la cual insertar la nueva linea, se dteiene el proceso.
                                        #    break
                                        #else:
                                        #    _logger.warning("Fechas diferentes, buscando otra factura de las tareas del proyecto.")
                                    
                                    #Si encontró la linea se sale del bucle de busqueda de tareas principal
                                    #if not new_invoice:
                                    #    break
                                    
                                debug_count = 1000
                                #print(awraew)
                                #¿Se debe crear una factura nueva o agregar una nueva linea a una factura existente?
                                
                                #else:
                                #    _logger.warning("Se agrega una linea de facturación a una factura existente y se asocia a esta tarea.")
                                #    print(awraew)

                            else:
                                #Se deben verificar las lineas de la factura asociada a la tarea para verificar que ya la linea asociada a la tarea se
                                #agregó correctamente, de no haberse agregado se asocia la nueva linea a la factura existente
                                #si esta factura se encuentra en la misma fecha que la fecha estimada de facturación de la tarea
                                #que se encuentra en revisión actualmente.

                                for invoice_existente_en_tarea_de_proyecto in tarea.sale_line_id.order_id.invoice_ids:
                                    _logger.warning("Nombre de la factura a revisar para agregar linea nueva: "+str(invoice_existente_en_tarea_de_proyecto.name))
                                    _logger.warning("Fecha de creación de esta factura: "+str(invoice_existente_en_tarea_de_proyecto.create_date.date()))
                                    _logger.warning("Fecha estimada de facturación de la tarea: "+str(tarea.valid_agree_estimated_payment_date))

                                    #Si la fecha de la factura y la fecha estimada de facturación d ela tarea son iguales se procede a revisar las lineas de la factura encontrada.
                                    if invoice_existente_en_tarea_de_proyecto.create_date.date() == tarea.valid_agree_estimated_payment_date:
                                        _logger.warning("Se encontró factura con fecha igual a la fecha estimada de facturación d ela tarea.")
                                        new_invoice = False
                                        existe_linea_en_factura = False

                                        for invoice_line in invoice_existente_en_tarea_de_proyecto:
                                            _logger.warning("Linea de facturación: "+str(invoice_line.name))

                                            #Si existe la linea en la factura no se agrega el item
                                            if invoice_line.name == tarea.name:
                                                existe_linea_en_factura = True

                                        if not existe_linea_en_factura:
                                            #Se agrega la nueva linea a la factura existente.
                                            _logger.warning("Se agrega la nueva linea de facturación a la factura: "+str(invoice_existente_en_tarea_de_proyecto.name))

                                            #Se preparan las lineas de facturación a enviar
                                            sale_order_invoice_lines = tarea.group_invoices_modified(tarea.valid_agree_estimated_payment_date, tarea.valid_agree_authorization_location)

                                            partner_valido_para_invoice_automatica = True
                                            #if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.property_account_payable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.journal_advance_purchases_id or not tarea.project_id.partner_id.account_advance_sales_id or not tarea.project_id.partner_id.account_advance_purchases_id:
                                            if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.account_payment_partial_sales_id:
                                                partner_valido_para_invoice_automatica = False
                                            
                                            if len(sale_order_invoice_lines) > 0 and partner_valido_para_invoice_automatica:
                                                _logger.warning("Se agregan las lineas de facturación encontradas a la factura del Cliente validado exitosamente.")
                                                _logger.warning("Sale order lines nuevas a agregar a la factura existente: "+str(sale_order_invoice_lines))

                                                invoice_existente_en_tarea_de_proyecto.write({'invoice_line_ids': sale_order_invoice_lines})

                                                #Se establece el status en la factura unica o en las partes de las facturas por monto fijo o porcentaje.
                                                tarea._set_status_in_task(invoice_existente_en_tarea_de_proyecto)

                                                #Se términa el proceso para evitar agregar esta linea de factura en otra factura repitiendo el mismo registro sin necesidad.
                                                break #--> Este break es del 'for invoice_existente_en_tarea_de_proyecto'
                                        else:
                                            _logger.warning("Se omite la linea de facturación porque ya se encuentra una linea igual en la factura, se debe revisar si se trata de un duplicado que no se debe agregar de nuevo a la factura.")

                                #_logger.warning("Tarea con tarifa única y pago único ya posee factura asociada, revise la tarea en caso de que se deba realizar algún ajuste o rehacer la factura.")
                                #print(awraew)
                            
                            if new_invoice:
                                _logger.warning("Se crea la factura nueva y se inserta una linea de facturación asociada a esta tarea.")

                                #Se envían los datos para crear la factura nueva.                                    
                                sale_order_invoice_lines = tarea.group_invoices_modified(tarea.valid_agree_estimated_payment_date, tarea.valid_agree_authorization_location)
                                _logger.warning("Sale order invoice lines: "+str(sale_order_invoice_lines))

                                #Antes de proceder con la facturación automática, se debe verificar que el Cliente al que se
                                #le va a crear la factura tenga la contabilidad configurada (Ficha del contacto --> ficha de contabilidad)
                                #Los campos a validar son:
                                #1- Cuenta de cobro (Asiento contable)
                                #2- Cuenta de pago (Asiento contable)
                                #3- Diario de anticipos ventas
                                #4- Diario de anticipos compras
                                #5- Cuenta de anticipos ventas
                                #6- Cuenta de anticipos compras

                                partner_valido_para_invoice_automatica = True
                                #if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.property_account_payable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.journal_advance_purchases_id or not tarea.project_id.partner_id.account_advance_sales_id or not tarea.project_id.partner_id.account_advance_purchases_id:
                                if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.account_payment_partial_sales_id:
                                    partner_valido_para_invoice_automatica = False

                                if len(sale_order_invoice_lines) > 0 and partner_valido_para_invoice_automatica:

                                    #1- Se crea la factura y genera un move_id.
                                    #2- Este move_id se asigna al account.move.line.
                                    #3- Este account.move.line se asigna a la factura recien creada.
                                    vals = {
                                        'name': '/',
                                        'invoice_user_id': tarea.user_id.id,
                                        'type': 'out_invoice',
                                        'date': tarea.valid_agree_estimated_payment_date,
                                        'partner_id': tarea.partner_id.id,
                                        'partner_shipping_id': tarea.partner_id.id,
                                    }

                                    tarea.create_invoice_tarifa_unica_recurrente(tarea,vals,sale_order_invoice_lines)
                                else:
                                    _logger.warning("No se procede con la facturación automática porque falta configurar la parte contable del Cliente, por favor, verifique la información contable del Cliente e intente nuevamente.")

                            #Dependiendo del tipo de tarifa se debe estudiar el tema de las suscripciones activas
                            #Por ahora solo se considera la revisión de las suscripciones en Tarifa Recurrente.
                            #Pago Único: se envía el porcentaje total de la tarea.
                            tarea.update_subscription_lines_modified(part_payment=tarea.percent_sub)

                            debug_count = 1000
                        """

                if tarea.valid_agree_payment_percentage and 2 == 1:
                    #2- Pago por porcentaje: Se registran N lineas de factura con el monto
                    #prorrateado de cada una de las N partes de la tabla de los pagos (%).
                    _logger.warning("Tarea con pago por porcentage")

                    for item in tarea.payment_by_prencentage_ids:
                        _logger.warning("Fecha estimada del item (%): "+str(item.estimated_payment_date))
                        _logger.warning("Fecha de envío de facturación: "+str(item.sent_payment_date))
                        _logger.warning("(%) Avance de la linea: "+str(item.percentage_value)) 

                        if item.estimated_payment_date:
                            if item.estimated_payment_date <= datetime.now().date() and not item.sent_payment_date and tarea.validate_finance and tarea.percent_sub >= item.percentage_value:
                                _logger.warning("Tarea "+str(tarea.name)+" (Porcentaje %) cumple con los requisitos de la facturación automática.")
                                _logger.warning("Proyecto asociado: "+str(tarea.project_id.name))

                                #22/02/2023
                                #Para el alcance actual se establece solo la fecha de envío de facturación
                                #la facturación automática se deja para mejora continua.
                                item.sent_payment_date = datetime.now()
                                debug_count = 1000

                                """
                                new_invoice = True
                                #Se deben buscar las tareas que esten relacionadas con el pedido de venta de la tarea a la que se esta analizando
                                if not tarea.sale_line_id.order_id.invoice_ids:
                                    _logger.warning("Pedido de venta asociado a la tarea: "+str(tarea.sale_line_id.order_id.name))
                                    tareas_proyecto = self.env['project.task'].search([('project_id', '=', tarea.project_id.id),('sale_line_id', '=', tarea.sale_line_id.id)])

                                    _logger.warning("Tareas de proyecto encontradas: "+str(tareas_proyecto))
                                    #Se buscan las facturas existentes asociadas al proyecto
                                    for tarea_invoice in tareas_proyecto:
                                        _logger.warning("Tarea a la que se le busca factura: "+str(tarea_invoice.name))
                                        for invoice in tarea_invoice.sale_line_id.order_id.invoice_ids:
                                            #Si hay facturas, se comparan las fechas
                                            #1- Fecha estimada de facturación.
                                            #2- Fecha de creación de la factura.

                                            #Si no hay una factura con fecha de creación igual a la fecha estimada de
                                            #facturación de la tarea que se esta revisando se crea una factura nueva
                                            #con los valores indicados.

                                            _logger.warning("Invoice: "+str(invoice.name))
                                            _logger.warning("Fecha de creación del invoice: "+str(invoice.create_date))
                                            _logger.warning("Fecha estimada de facturación del item: "+str(item.estimated_payment_date))

                                            #if invoice.create_date.date() == item.estimated_payment_date:
                                            #    _logger.warning("Se inserta la linea de la tarea: "+str(tarea.name)+" en la factura: "+str(invoice.name))
                                            #    new_invoice = False
                                            #    #Encontró una factura en la cual insertar la nueva linea, se dteiene el proceso.
                                            #    break
                                            #else:
                                            #    _logger.warning("Fechas diferentes, buscando otra factura de las tareas del proyecto.")
                                        
                                        #Si encontró la linea se sale del bucle de busqueda de tareas principal
                                        #if not new_invoice:
                                        #    break
                                    
                                else:
                                    #En este caso se agrega la linea de facturación a la factura existente o se crea una factura nueva según el caso.
                                    _logger.warning("Revisar facturas existentes para ver si se inserta la nueva linea en una factura existente o se crea una factura nueva.")

                                    #Revisamos las fechas de las facturas existentes
                                    for invoice_existente_en_tarea_de_proyecto in tarea.sale_line_id.order_id.invoice_ids:
                                        _logger.warning("Factura: "+str(invoice_existente_en_tarea_de_proyecto.name))
                                        _logger.warning("Fecha de creación: "+str(invoice_existente_en_tarea_de_proyecto.create_date.date()))

                                        if invoice_existente_en_tarea_de_proyecto.create_date.date() == item.estimated_payment_date and tarea.sale_line_id.order_id.maximum_recurring_lines < 12:
                                            _logger.warning("Se agrega esta linea de facturación a la factura existente: "+str(invoice_existente_en_tarea_de_proyecto.name))
                                            new_invoice = False

                                            existe_linea_en_factura = False

                                            #Evaluar condición!!
                                            #Evaluar condición!!
                                            for invoice_line in invoice_existente_en_tarea_de_proyecto:
                                                _logger.warning("Linea de facturación: "+str(invoice_line.name))

                                                #Si existe la linea en la factura no se agrega el item
                                                if invoice_line.name == tarea.name:
                                                    existe_linea_en_factura = True

                                            #Evaluar condición!!
                                            #Evaluar condición!!

                                            if not existe_linea_en_factura:
                                                #Se agrega la nueva linea a la factura existente.
                                                _logger.warning("Se agrega la nueva linea de facturación a la factura: "+str(invoice_existente_en_tarea_de_proyecto.name))

                                                #Se preparan las lineas de facturación a enviar
                                                sale_order_invoice_lines = tarea.group_invoices_modified(item.estimated_payment_date, tarea.valid_agree_authorization_location)

                                                partner_valido_para_invoice_automatica = True
                                                #if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.property_account_payable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.journal_advance_purchases_id or not tarea.project_id.partner_id.account_advance_sales_id or not tarea.project_id.partner_id.account_advance_purchases_id:
                                                if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.account_payment_partial_sales_id:
                                                    partner_valido_para_invoice_automatica = False
                                                
                                                if len(sale_order_invoice_lines) > 0 and partner_valido_para_invoice_automatica:
                                                    _logger.warning("Se agregan las lineas de facturación encontradas a la factura del Cliente validado exitosamente.")
                                                    _logger.warning("Sale order lines nuevas a agregar a la factura existente: "+str(sale_order_invoice_lines))

                                                    invoice_existente_en_tarea_de_proyecto.write({'invoice_line_ids': sale_order_invoice_lines})
                                                    
                                                    #Se establece el status en la factura unica o en las partes de las facturas por monto fijo o porcentaje.
                                                    tarea._set_status_in_task(invoice_existente_en_tarea_de_proyecto,item)

                                                    #Se términa el proceso para evitar agregar esta linea de factura en otra factura repitiendo el mismo registro sin necesidad.
                                                    break #--> Este break es del 'for invoice_existente_en_tarea_de_proyecto'
                                            else:
                                                _logger.warning("Se omite la linea de facturación porque ya se encuentra una linea igual en la factura, se debe revisar si se trata de un duplicado que no se debe agregar de nuevo a la factura.")

                                        else:
                                            _logger.warning("Factura con fecha de creación a la fecha estimada de facturación establecida.")

                                #¿Se debe crear una factura nueva o agregar una nueva linea a una factura existente?
                                if new_invoice:
                                    _logger.warning("Se crea la factura nueva y se inserta una linea de facturación asociada a esta linea de pago de la tarea.")

                                    #Se envían los datos para crear la factura nueva.                                    
                                    sale_order_invoice_lines = tarea.group_invoices_modified(item.estimated_payment_date, tarea.valid_agree_authorization_location)
                                    _logger.warning("Sale order invoice lines: "+str(sale_order_invoice_lines))

                                    #Antes de proceder con la facturación automática, se debe verificar que el Cliente al que se
                                    #le va a crear la factura tenga la contabilidad configurada (Ficha del contacto --> ficha de contabilidad)
                                    #Los campos a validar son:
                                    #1- Cuenta de cobro (Asiento contable)
                                    #2- Cuenta de pago (Asiento contable)
                                    #3- Diario de anticipos ventas
                                    #4- Diario de anticipos compras
                                    #5- Cuenta de anticipos ventas
                                    #6- Cuenta de anticipos compras

                                    partner_valido_para_invoice_automatica = True
                                    #if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.property_account_payable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.journal_advance_purchases_id or not tarea.project_id.partner_id.account_advance_sales_id or not tarea.project_id.partner_id.account_advance_purchases_id:
                                    if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.account_payment_partial_sales_id:
                                        partner_valido_para_invoice_automatica = False

                                    if len(sale_order_invoice_lines) > 0 and partner_valido_para_invoice_automatica:

                                        #1- Se crea la factura y genera un move_id.
                                        #2- Este move_id se asigna al account.move.line.
                                        #3- Este account.move.line se asigna a la factura recien creada.
                                        vals = {
                                            'name': '/',
                                            'invoice_user_id': tarea.user_id.id,
                                            'type': 'out_invoice',
                                            'date': item.estimated_payment_date,
                                            'partner_id': tarea.partner_id.id,
                                            'partner_shipping_id': tarea.partner_id.id,
                                        }

                                        #Cuando se envía el item se trata de una tarifa única con pago en partes por % o fijo.
                                        #Al crearse la factura se establece el status con la parte o partes necesarias durante
                                        #la creación de dicha factura.
                                        tarea.create_invoice_tarifa_unica_recurrente(tarea,vals,sale_order_invoice_lines, item)

                                #else:
                                #    _logger.warning("Se agrega una linea de facturación a una factura existente y se asocia a esta tarea.")

                                #Solo debug
                                debug_count = 1000

                        else:
                            _logger.warning("Parte de la tarea sin fecha estimada de facturación establecida.")
                                """

                if tarea.valid_agree_fixed_amount_payment and 2 == 1:
                    #3- Pago por monto fijo: Se registran N lineas de factura con el monto
                    #prorrateado de cada una de las N partes de la tabla de los pagos (fijo)
                    _logger.warning("Tarea con pago por monto fijo")

                    for item in tarea.part_payments_fixed_amounts_ids:
                        _logger.warning("Fecha estimada del item (fijo): "+str(item.estimated_payment_date))
                        _logger.warning("Fecha de envío de facturación: "+str(item.sent_payment_date))
                        _logger.warning("(fijo) Avance de la linea: "+str(item.invoiced_progress_percentage)) 

                        if item.estimated_payment_date:
                            if item.estimated_payment_date <= datetime.now().date() and not item.sent_payment_date and tarea.validate_finance and tarea.percent_sub >= item.invoiced_progress_percentage:
                                _logger.warning("Tarea "+str(tarea.name)+" (fijo) cumple con los requisitos de la facturación automática.")
                                _logger.warning("Proyecto asociado: "+str(tarea.project_id.name))

                                #22/02/2023
                                #Para el alcance actual se establece solo la fecha de envío de facturación
                                #la facturación automática se deja para mejora continua.
                                item.sent_payment_date = datetime.now()
                                debug_count = 1000

                """
                                new_invoice = True
                                #Se deben buscar las tareas que esten relacionadas con el pedido de venta de la tarea a la que se esta analizando
                                if not tarea.sale_line_id.order_id.invoice_ids:
                                    _logger.warning("Pedido de venta asociado a la tarea: "+str(tarea.sale_line_id.order_id.name))
                                    tareas_proyecto = self.env['project.task'].search([('project_id', '=', tarea.project_id.id),('sale_line_id', '=', tarea.sale_line_id.id)])

                                    _logger.warning("Tareas de proyecto encontradas: "+str(tareas_proyecto))
                                    #Se buscan las facturas existentes asociadas al proyecto
                                    for tarea_invoice in tareas_proyecto:
                                        _logger.warning("Tarea a la que se le busca factura: "+str(tarea_invoice.name))
                                        for invoice in tarea_invoice.sale_line_id.order_id.invoice_ids:
                                            #Si hay facturas, se comparan las fechas
                                            #1- Fecha estimada de facturación.
                                            #2- Fecha de creación de la factura.

                                            #Si no hay una factura con fecha de creación igual a la fecha estimada de
                                            #facturación de la tarea que se esta revisando se crea una factura nueva
                                            #con los valores indicados.

                                            _logger.warning("Invoice: "+str(invoice.name))
                                            _logger.warning("Fecha de creación del invoice: "+str(invoice.create_date))
                                            _logger.warning("Fecha estimada de facturación del item: "+str(item.estimated_payment_date))

                                            #if invoice.create_date.date() == item.estimated_payment_date:
                                            #    _logger.warning("Se inserta la linea de la tarea: "+str(tarea.name)+" en la factura: "+str(invoice.name))
                                            #    new_invoice = False
                                                #Encontró una factura en la cual insertar la nueva linea, se dteiene el proceso.
                                            #    break
                                            #else:
                                            #    _logger.warning("Fechas diferentes, buscando otra factura de las tareas del proyecto.")
                                        
                                        #Si encontró la linea se sale del bucle de busqueda de tareas principal
                                        #if not new_invoice:
                                        #    break
                                    
                                else:
                                    #En este caso se agrega la linea de facturación a la factura existente o se crea una factura nueva según el caso.
                                    _logger.warning("Revisar facturas existentes para ver si se inserta la nueva linea en una factura existente o se crea una factura nueva.")

                                    #Revisamos las fechas de las facturas existentes
                                    for invoice_existente_en_tarea_de_proyecto in tarea.sale_line_id.order_id.invoice_ids:
                                        _logger.warning("Factura: "+str(invoice_existente_en_tarea_de_proyecto.name))
                                        _logger.warning("Fecha de creación: "+str(invoice_existente_en_tarea_de_proyecto.create_date))

                                        if invoice_existente_en_tarea_de_proyecto.create_date.date() == item.estimated_payment_date and tarea.sale_line_id.order_id.maximum_recurring_lines < 12:
                                            _logger.warning("Se agrega esta linea de facturación a la factura existente: "+str(invoice_existente_en_tarea_de_proyecto.name))
                                            new_invoice = False

                                            existe_linea_en_factura = False

                                            #Evaluar condición!!
                                            #Evaluar condición!!
                                            for invoice_line in invoice_existente_en_tarea_de_proyecto:
                                                _logger.warning("Linea de facturación: "+str(invoice_line.name))

                                                #Si existe la linea en la factura no se agrega el item
                                                if invoice_line.name == tarea.name:
                                                    existe_linea_en_factura = True

                                            #Evaluar condición!!
                                            #Evaluar condición!!

                                            if not existe_linea_en_factura:
                                                #Se agrega la nueva linea a la factura existente.
                                                _logger.warning("Se agrega la nueva linea de facturación a la factura: "+str(invoice_existente_en_tarea_de_proyecto.name))

                                                #Se preparan las lineas de facturación a enviar
                                                sale_order_invoice_lines = tarea.group_invoices_modified(item.estimated_payment_date, tarea.valid_agree_authorization_location)

                                                partner_valido_para_invoice_automatica = True
                                                #if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.property_account_payable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.journal_advance_purchases_id or not tarea.project_id.partner_id.account_advance_sales_id or not tarea.project_id.partner_id.account_advance_purchases_id:
                                                if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.account_payment_partial_sales_id:
                                                    partner_valido_para_invoice_automatica = False
                                                
                                                if len(sale_order_invoice_lines) > 0 and partner_valido_para_invoice_automatica:
                                                    _logger.warning("Se agregan las lineas de facturación encontradas a la factura del Cliente validado exitosamente.")
                                                    _logger.warning("Sale order lines nuevas a agregar a la factura existente: "+str(sale_order_invoice_lines))

                                                    invoice_existente_en_tarea_de_proyecto.write({'invoice_line_ids': sale_order_invoice_lines})
                                                    
                                                    #Se establece el status en la factura unica o en las partes de las facturas por monto fijo o porcentaje.
                                                    tarea._set_status_in_task(invoice_existente_en_tarea_de_proyecto,item)

                                                    #Se términa el proceso para evitar agregar esta linea de factura en otra factura repitiendo el mismo registro sin necesidad.
                                                    break #--> Este break es del 'for invoice_existente_en_tarea_de_proyecto'
                                            else:
                                                _logger.warning("Se omite la linea de facturación porque ya se encuentra una linea igual en la factura, se debe revisar si se trata de un duplicado que no se debe agregar de nuevo a la factura.")

                                        else:
                                            _logger.warning("Factura con fecha de creación a la fecha estimada de facturación establecida.")

                                #¿Se debe crear una factura nueva o agregar una nueva linea a una factura existente?
                                if new_invoice:
                                    _logger.warning("Se crea la factura nueva y se inserta una linea de facturación asociada a esta linea de pago de la tarea.")

                                    #Se envían los datos para crear la factura nueva.                                    
                                    sale_order_invoice_lines = tarea.group_invoices_modified(item.estimated_payment_date, tarea.valid_agree_authorization_location)
                                    _logger.warning("Sale order invoice lines: "+str(sale_order_invoice_lines))

                                    #Antes de proceder con la facturación automática, se debe verificar que el Cliente al que se
                                    #le va a crear la factura tenga la contabilidad configurada (Ficha del contacto --> ficha de contabilidad)
                                    #Los campos a validar son:
                                    #1- Cuenta de cobro (Asiento contable)
                                    #2- Cuenta de pago (Asiento contable)
                                    #3- Diario de anticipos ventas
                                    #4- Diario de anticipos compras
                                    #5- Cuenta de anticipos ventas
                                    #6- Cuenta de anticipos compras

                                    partner_valido_para_invoice_automatica = True
                                    #if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.property_account_payable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.journal_advance_purchases_id or not tarea.project_id.partner_id.account_advance_sales_id or not tarea.project_id.partner_id.account_advance_purchases_id:
                                    if not tarea.project_id.partner_id.property_account_receivable_id or not tarea.project_id.partner_id.journal_advance_sales_id or not tarea.project_id.partner_id.account_payment_partial_sales_id:
                                        partner_valido_para_invoice_automatica = False

                                    if len(sale_order_invoice_lines) > 0 and partner_valido_para_invoice_automatica:

                                        #1- Se crea la factura y genera un move_id.
                                        #2- Este move_id se asigna al account.move.line.
                                        #3- Este account.move.line se asigna a la factura recien creada.
                                        vals = {
                                            'name': '/',
                                            'invoice_user_id': tarea.user_id.id,
                                            'type': 'out_invoice',
                                            'date': item.estimated_payment_date,
                                            'partner_id': tarea.partner_id.id,
                                            'partner_shipping_id': tarea.partner_id.id,
                                        }

                                        #Cuando se envía el item se trata de una tarifa única con pago en partes por % o fijo.
                                        #Al crearse la factura se establece el status con la parte o partes necesarias durante
                                        #la creación de dicha factura.
                                        tarea.create_invoice_tarifa_unica_recurrente(tarea,vals,sale_order_invoice_lines, item)
                                        
                                #else:
                                #    _logger.warning("Se agrega una linea de facturación a una factura existente y se asocia a esta tarea.")
                                #Solo debug
                                debug_count = 1000

                        else:
                            _logger.warning("Parte de la tarea sin fecha estimada de facturación establecida.")
                
                """

                """
                        date_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        start = datetime.strptime(date_now, "%Y-%m-%d %H:%M:%S")
                        context = self._context
                        current_uid = context.get('uid')
                        user = self.env['res.users'].browse(current_uid)
                        tz = pytz.timezone(user.tz) if user.tz else pytz.utc
                        start = pytz.utc.localize(start).astimezone(tz)
                        tz_date = start.strftime("%Y-%m-%d %H:%M:%S")

                        if tarea.valid_agree_estimated_payment_date and tarea.percent_sub >= 100.0 and (tarea.rate_type.tipo_tarifa == 'Recurrente' or tarea.rate_type.tipo_tarifa == 'Unica') and tarea.validate_finance:
                            tarea.sent_payment_date = tz_date
                            # Obtener la fecha en la zona horaria del usuario actual
                            current_uid = tarea._context.get('uid')
                            user = tarea.env['res.users'].browse(current_uid)

                            #Se envía a crear la factura por pago único.
                            #tarea.crear_factura_por_pago_unico(self.env, tarea, tarea.id)
                            #print(qwra)
                            invoice_lines = tarea.group_invoices_modified(
                            tarea.valid_agree_estimated_payment_date, tarea.valid_agree_authorization_location)

                            #invoice_lines_b = tarea.group_invoices(
                            #tarea.valid_agree_estimated_payment_date, tarea.valid_agree_authorization_location)

                            _logger.warning("Invoices lines: "+str(invoice_lines))
                            #_logger.warning("Invoice lines (old): "+str(invoice_lines_b))

                            #Verificar y crear factura.
                            if len(invoice_lines) == 1:
                                _logger.warning("Existe una sola linea de facturación relacionada.")
                                
                                vals = {
                                    'name': '/',
                                    'invoice_user_id': tarea.user_id.id,
                                    'type': 'out_invoice',
                                    'date': tarea.valid_agree_estimated_payment_date,
                                    'partner_id': tarea.partner_id.id,
                                    'partner_shipping_id': tarea.partner_id.id,
                                    'invoice_line_ids': invoice_lines,
                                }
                                tarea.add_line_to_invoice_modified(invoice_lines,vals)

                            else:
                                if tarea.rate_type.tipo_tarifa == 'Recurrente':
                                    _logger.warning("Tarea sin invoice lines y tarifa recurrente detectada.")
                                    _logger.warning("Task Maximum recurring lines: "+str(tarea.sale_line_id.order_id.maximum_recurring_lines))
                                    # Revisar si invoice_lines tiene mas de 12 elementos y de ser asi generar mas de una factura
                                    if len(invoice_lines) <= tarea.sale_line_id.order_id.maximum_recurring_lines:
                                        vals = {
                                            'name': '/',
                                            'invoice_user_id': tarea.user_id.id,
                                            'type': 'out_invoice',
                                            'date': tarea.valid_agree_estimated_payment_date,
                                            'partner_id': tarea.partner_id.id,
                                            'partner_shipping_id': tarea.partner_id.id,
                                            'invoice_line_ids': invoice_lines,
                                        }
                                        tarea.create_invoice_from_task_modified(vals)
                                    else:
                                        curr_inv = list()
                                        for line in invoice_lines:
                                            curr_inv.append(line)
                                            if len(curr_inv) == tarea.sale_line_id.order_id.maximum_recurring_lines:
                                                vals = {
                                                    'name': '/',
                                                    'invoice_user_id': tarea.user_id.id,
                                                    'type': 'out_invoice',
                                                    'date': tarea.valid_agree_estimated_payment_date,
                                                    'partner_id': tarea.partner_id.id,
                                                    'partner_shipping_id': tarea.partner_id.id,
                                                    'invoice_line_ids': curr_inv,
                                                }
                                                tarea.create_invoice_from_task_modified(vals)
                                                curr_inv.clear()
                                        if len(curr_inv):
                                            vals = {
                                                'name': '/',
                                                'invoice_user_id': tarea.user_id.id,
                                                'type': 'out_invoice',
                                                'date': tarea.valid_agree_estimated_payment_date,
                                                'partner_id': tarea.partner_id.id,
                                                'partner_shipping_id': tarea.partner_id.id,
                                                'invoice_line_ids': curr_inv,
                                            }
                                            tarea.create_invoice_from_task_modified(vals)
                                else:
                                    _logger.warning("Maximun unique lines (sale line id): "+str(tarea.sale_line_id.order_id.maximum_unique_lines))
                                    if len(invoice_lines) <= tarea.sale_line_id.order_id.maximum_unique_lines:
                                        vals = {
                                            'name': '/',
                                            'invoice_user_id': tarea.user_id.id,
                                            'type': 'out_invoice',
                                            'date': tarea.valid_agree_estimated_payment_date,
                                            'partner_id': tarea.partner_id.id,
                                            'partner_shipping_id': tarea.partner_id.id,
                                            'invoice_line_ids': invoice_lines,
                                        }
                                        tarea.create_invoice_from_task_modified(vals)
                                    else:
                                        curr_inv = list()
                                        for line in invoice_lines:
                                            curr_inv.append(line)
                                            if len(curr_inv) == tarea.sale_line_id.order_id.maximum_unique_lines:
                                                vals = {
                                                    'name': '/',
                                                    'invoice_user_id': tarea.user_id.id,
                                                    'type': 'out_invoice',
                                                    'date': tarea.valid_agree_estimated_payment_date,
                                                    'partner_id': tarea.partner_id.id,
                                                    'partner_shipping_id': tarea.partner_id.id,
                                                    'invoice_line_ids': curr_inv,
                                                }
                                                tarea.create_invoice_from_task_modified(vals)
                                                curr_inv.clear()
                                        if len(curr_inv):
                                            vals = {
                                                'name': '/',
                                                'invoice_user_id': tarea.user_id.id,
                                                'type': 'out_invoice',
                                                'date': tarea.valid_agree_estimated_payment_date,
                                                'partner_id': tarea.partner_id.id,
                                                'partner_shipping_id': tarea.partner_id.id,
                                                'invoice_line_ids': curr_inv,
                                            }
                                            tarea.create_invoice_from_task_modified(vals)

                                tarea.update_subscription_lines_modified(part_payment=tarea.percent_sub)
            """

            """
            if tarea.valid_agree_payment_percentage:
                _logger.warning("Tipo de pago por porcentaje")
                #Se debe verificar cada una de las lineas de la tabla de pagos para comprobar los
                #siguientes casos:
                #1- Si el porcentaje de la linea de la tabla es igual o menor al porcentaje de la tarea
                #   y tiene una fecha estimada de facturación menor o igual a la fecha actual entonces
                #   se procede con la generación automatica de la factura y el establecimiento de la
                #   fecha de envío de facturación en el campo "sent_payment_date" de la linea del pago
                #   analizado.
                #2- Se debe generar una factura por cada una de las lineas de porcentaje analizadas en
                #   cada una de las tareas que tengan la condición de pago en partes.
                for item in tarea.payment_by_prencentage_ids:
                    _logger.warning("Fecha estimada del item (%): "+str(item.estimated_payment_date))
                    _logger.warning("Fecha de envío de facturación: "+str(item.sent_payment_date))
                    _logger.warning("(%) Avance de la linea: "+str(item.percentage_value))

                    #Para colocar fecha de envío de facturación y generar la respectiva factura en status borrador
                    #se deben cumplir las siguientes condiciones:

                    #1- Fecha estimada de facturación establecida, <= a la fecha actual en la que se ejecuta el cron.
                    #2- Checks de ventas en True
                    #3- Checks de finanzas en True
                    #4- Porcentaje de la parte de la tarea >= al porcentaje de la tarea completa.

                    #Una vez se cumplan dichos parámetros se procede a establecer la fecha de envío y generar
                    #la factura respectiva en estatus borrador de forma automática.
                    #Se debe comprobar si la fecha estimada de facturación de la parte existe.
                    if item.estimated_payment_date:
                        if item.estimated_payment_date <= datetime.now().date() and not item.sent_payment_date and tarea.validate_so and tarea.validate_finance and item.percentage_value >= tarea.percent_sub:
                            _logger.warning("Tarea "+str(tarea.name)+" (Porcentaje %) cumple con los requisitos de la facturación automática.")
                            _logger.warning("Proyecto asociado: "+str(tarea.project_id.name))
                        
                    else:
                        _logger.warning("Parte de la tarea sin fecha estimada de facturación establecida.")

            if tarea.valid_agree_fixed_amount_payment:
                _logger.warning("Tipo de pago por monto fijo")
                #Se debe verificar cada una de las lineas de la tabla de pagos para comprobar los
                #siguientes casos:
                #1- Si el porcentaje de la linea de la tabla es igual o menor al porcentaje de la tarea
                #   y tiene una fecha estimada de facturación menor o igual a la fecha actual entonces
                #   se procede con la generación automatica de la factura y el establecimiento de la
                #   fecha de envío de facturación en el campo "sent_payment_date" de la linea del pago
                #   analizado.
                #2- Se debe generar una factura por cada una de las lineas de porcentaje analizadas en
                #   cada una de las tareas que tengan la condición de pago en partes.
                for item in tarea.part_payments_fixed_amounts_ids:
                    _logger.warning("Fecha estimada del item (%): "+str(item.estimated_payment_date))
                    _logger.warning("Fecha de envío de facturación: "+str(item.sent_payment_date))
                    _logger.warning("(%) Avance de la linea: "+str(item.invoiced_progress_percentage))

                    #Para colocar fecha de envío de facturación y generar la respectiva factura en status borrador
                    #se deben cumplir las siguientes condiciones:

                    #1- Fecha estimada de facturación establecida, <= a la fecha actual en la que se ejecuta el cron.
                    #2- Checks de ventas en True
                    #3- Checks de finanzas en True
                    #4- Porcentaje de la parte de la tarea >= al porcentaje de la tarea completa.

                    #Una vez se cumplan dichos parámetros se procede a establecer la fecha de envío y generar
                    #la factura respectiva en estatus borrador de forma automática.
                    #Se debe comprobar si la fecha estimada de facturación de la parte existe.
                    if item.estimated_payment_date:
                        if item.estimated_payment_date <= datetime.now().date() and not item.sent_payment_date and tarea.validate_so and tarea.validate_finance and item.invoiced_progress_percentage >= tarea.percent_sub:
                            _logger.warning("Tarea: "+str(tarea.name)+" (Monto fijo) cumple con los requisitos de la facturación automática.")
                            _logger.warning("Proyecto asociado: "+str(tarea.project_id.name))
                            _logger.warning("Tarea tarifa: "+str(tarea.rate_type.name))
                            _logger.warning("Tarea monto total: "+str(tarea.valid_agree_sales_order_line_amount))
                            _logger.warning("Tarea monto parte a facturar: "+str(item.amount))
                            _logger.warning("Tarea parte: "+str(item.number_of_parts))

                            #Se envía a crear la factura por pago único.
                            
                            _logger.warning("Estimated payment date: "+str(item.estimated_payment_date))
                            _logger.warning("Valid agree autorization location: "+str(tarea.valid_agree_authorization_location))
                            _logger.warning("ID de la tarea a buscar: "+str(tarea.id))

                            invoice_lines = tarea.group_invoices_modified(
                            item.estimated_payment_date, tarea.valid_agree_authorization_location)

                            _logger.warning("Invoices lines (Monto fijo): "+str(invoice_lines))

                            if len(invoice_lines) == 1:
                                _logger.warning("Existe una sola linea de facturación relacionada.")
                                
                                vals = {
                                    'name': '/',
                                    'invoice_user_id': tarea.user_id.id,
                                    'type': 'out_invoice',
                                    'date': item.estimated_payment_date,
                                    'partner_id': tarea.partner_id.id,
                                    'partner_shipping_id': tarea.partner_id.id,
                                    'invoice_line_ids': invoice_lines,
                                }
                                tarea.add_line_to_invoice(invoice_lines,vals,payment_parts=item)

                            else:
                                if tarea.rate_type.tipo_tarifa == 'Recurrente':
                                    _logger.warning("Tarea sin invoice lines y tarifa recurrente detectada.")
                                    _logger.warning("Task Maximum recurring lines: "+str(tarea.sale_line_id.order_id.maximum_recurring_lines))
                                    # Revisar si invoice_lines tiene mas de 12 elementos y de ser asi generar mas de una factura
                                    if len(invoice_lines) <= tarea.sale_line_id.order_id.maximum_recurring_lines:
                                        vals = {
                                            'name': '/',
                                            'invoice_user_id': tarea.user_id.id,
                                            'type': 'out_invoice',
                                            'date': item.estimated_payment_date,
                                            'partner_id': tarea.partner_id.id,
                                            'partner_shipping_id': tarea.partner_id.id,
                                            'invoice_line_ids': invoice_lines,
                                        }
                                        tarea.create_invoice_from_task_modified(vals)
                                    else:
                                        curr_inv = list()
                                        for line in invoice_lines:
                                            curr_inv.append(line)
                                            if len(curr_inv) == tarea.sale_line_id.order_id.maximum_recurring_lines:
                                                vals = {
                                                    'name': '/',
                                                    'invoice_user_id': tarea.user_id.id,
                                                    'type': 'out_invoice',
                                                    'date': item.estimated_payment_date,
                                                    'partner_id': tarea.partner_id.id,
                                                    'partner_shipping_id': tarea.partner_id.id,
                                                    'invoice_line_ids': curr_inv,
                                                }
                                                tarea.create_invoice_from_task_modified(vals)
                                                curr_inv.clear()
                                        if len(curr_inv):
                                            vals = {
                                                'name': '/',
                                                'invoice_user_id': tarea.user_id.id,
                                                'type': 'out_invoice',
                                                'date': item.estimated_payment_date,
                                                'partner_id': tarea.partner_id.id,
                                                'partner_shipping_id': tarea.partner_id.id,
                                                'invoice_line_ids': curr_inv,
                                            }
                                            tarea.create_invoice_from_task_modified(vals)
                                else:
                                    _logger.warning("Maximun unique lines (sale line id): "+str(tarea.sale_line_id.order_id.maximum_unique_lines))
                                    if len(invoice_lines) <= tarea.sale_line_id.order_id.maximum_unique_lines:
                                        vals = {
                                            'name': '/',
                                            'invoice_user_id': tarea.user_id.id,
                                            'type': 'out_invoice',
                                            'date': item.estimated_payment_date,
                                            'partner_id': tarea.partner_id.id,
                                            'partner_shipping_id': tarea.partner_id.id,
                                            'invoice_line_ids': invoice_lines,
                                        }
                                        tarea.create_invoice_from_task_modified(vals)
                                    else:
                                        curr_inv = list()
                                        for line in invoice_lines:
                                            curr_inv.append(line)
                                            if len(curr_inv) == tarea.sale_line_id.order_id.maximum_unique_lines:
                                                vals = {
                                                    'name': '/',
                                                    'invoice_user_id': tarea.user_id.id,
                                                    'type': 'out_invoice',
                                                    'date': item.estimated_payment_date,
                                                    'partner_id': tarea.partner_id.id,
                                                    'partner_shipping_id': tarea.partner_id.id,
                                                    'invoice_line_ids': curr_inv,
                                                }
                                                tarea.create_invoice_from_task_modified(vals)
                                                curr_inv.clear()
                                        if len(curr_inv):
                                            vals = {
                                                'name': '/',
                                                'invoice_user_id': tarea.user_id.id,
                                                'type': 'out_invoice',
                                                'date': item.estimated_payment_date,
                                                'partner_id': tarea.partner_id.id,
                                                'partner_shipping_id': tarea.partner_id.id,
                                                'invoice_line_ids': curr_inv,
                                            }
                                            tarea.create_invoice_from_task_modified(vals)

                            #Se envía el porcentaje de la linea de ta bla de partes de pago por monto fijo
                            tarea.update_subscription_lines_modified(part_payment=item.invoiced_progress_percentage)
                            
                            #debug_count = 100
                            #break

                    else:
                        _logger.warning("Parte de la tarea sin fecha estimada de facturación establecida.")
            """

            debug_count += 1
            
            #Solo debug
            if debug_count > 999:
                break
    
    def add_line_to_invoice_modified(self, inv_line, vals, payment_percent=None, payment_parts=None):
        _logger.warning("Inv_line: "+str(inv_line))
        _logger.warning("Vals: "+str(vals))
        _logger.warning("Payment_percent: "+str(payment_percent))
        _logger.warning("Payment_parts: "+str(payment_parts))
        _logger.warning("Sale order order line: "+str(self.sale_line_id.order_id.order_line))
        _logger.warning("Sale order lines (old): "+str(self.sale_line_id.order_id.order_line.invoice_lines))
        _logger.warning("Invoice_lines_ids relacionadas con la linea de pedido: "+str(self.sale_line_id.order_id.invoice_ids.invoice_line_ids))
        _logger.warning("Inv line location: "+str(inv_line[0][2].get('location')))
        _logger.warning("Concept id: "+str(inv_line[0][2].get('concept_id','X')))

        #Fix concept_id
        #if str(inv_line[0][2].get('concept_id','X')) == "X":
        #    inv_line[0][2]['concept_id'] = 33
        
        #for line in [line for line in self.sale_line_id.order_id.order_line if line.invoice_lines and line.invoice_lines[0].location == inv_line[0][2]['location']]:
        for line in [line for line in self.sale_line_id.order_id.order_line if self.sale_line_id.order_id.invoice_ids.invoice_line_ids and self.sale_line_id.order_id.invoice_ids.invoice_line_ids[0].location == inv_line[0][2]['location']]:
            inv_flag = False
            task = line.task_id
            _logger.warning("Add line (Line): "+str(line))

            if line.product_id.unique_invoicing and inv_line[0][2]['unique_invoicing'] or not line.product_id.unique_invoicing and not inv_line[0][2]['unique_invoicing']:
                if task.valid_agree_single_payment and task.valid_agree_estimated_payment_date == vals['date']:
                    if task.rate_type.tipo_tarifa == 'Recurrente':
                        if len(self.sale_line_id.order_id.invoice_ids.invoice_line_ids.move_id.invoice_line_ids) < task.sale_line_id.order_id.maximum_recurring_lines and self.sale_line_id.order_id.invoice_ids.invoice_line_ids.move_id.state == 'draft':
                            self.invoice_line_and_mark(inv_line,line)
                            inv_flag = True
                    else:
                        if len(self.sale_line_id.order_id.invoice_ids.invoice_line_ids.move_id.invoice_line_ids) < task.sale_line_id.order_id.maximum_unique_lines and self.sale_line_id.order_id.invoice_ids.invoice_line_ids.move_id.state == 'draft':
                            self.invoice_line_and_mark(inv_line,line)
                            inv_flag = True
                    if inv_flag:
                        #Si se ha añadido la línea a una factura, se le asigna esta factura a la línea
                        if payment_percent:
                            payment_percent.write({'factura_por_porcentaje': inv_line[0][2]['move_id']})
                        elif payment_parts:
                            payment_parts.write({'factura_por_monto_fijo': inv_line[0][2]['move_id']})
                        elif self.valid_agree_single_payment:
                            self.write({'factura_pago_unico': inv_line[0][2]['move_id']})
                        break

                elif task.valid_agree_payment_percentage:
                    filered_payments = [payment for payment in task.payment_by_prencentage_ids
                                    if payment.estimated_payment_date == vals['date']
                                    and payment.factura_por_porcentaje
                                    and payment.factura_por_porcentaje.state == 'draft']
                    for payment in filered_payments:
                        if task.rate_type.tipo_tarifa == 'Recurrente':
                            if len(payment.factura_por_porcentaje.invoice_line_ids) < task.sale_line_id.order_id.maximum_recurring_lines:
                                self.invoice_line_and_mark(inv_line,line,payment.factura_por_porcentaje.id)
                                inv_flag = True
                        else:
                            if len(payment.factura_por_porcentaje.invoice_line_ids) < task.sale_line_id.order_id.maximum_unique_lines:
                                self.invoice_line_and_mark(inv_line,line,payment.factura_por_porcentaje.id)
                                inv_flag = True
                        if inv_flag:
                            if payment_percent:
                                payment_percent.write({'factura_por_porcentaje': payment.factura_por_porcentaje.id})
                            elif payment_parts:
                                payment_parts.write({'factura_por_monto_fijo': payment.factura_por_porcentaje.id})
                            elif self.valid_agree_single_payment:
                                self.write({'factura_pago_unico': payment.factura_por_porcentaje.id})
                            break

                elif task.valid_agree_fixed_amount_payment:
                    filtered_payments = [payment for payment in task.part_payments_fixed_amounts_ids
                                        if payment.estimated_payment_date == vals['date']
                                        and payment.factura_por_monto_fijo
                                        and payment.factura_por_monto_fijo.state == 'draft']
                    for payment in filtered_payments:
                        if task.rate_type.tipo_tarifa == 'Recurrente':
                            if len(payment.factura_por_monto_fijo.invoice_line_ids) < task.sale_line_id.order_id.maximum_recurring_lines:
                                self.invoice_line_and_mark(inv_line,line,payment.factura_por_monto_fijo.id)
                                inv_flag = True
                        else:
                            if len(payment.factura_por_monto_fijo.invoice_line_ids) < task.sale_line_id.order_id.maximum_unique_lines:
                                self.invoice_line_and_mark(inv_line,line,payment.factura_por_monto_fijo.id)
                                inv_flag = True
                        if inv_flag:
                            if payment_percent:
                                payment_percent.write({'factura_por_porcentaje': payment.factura_por_monto_fijo.id})
                            elif payment_parts:
                                payment_parts.write({'factura_por_monto_fijo': payment.factura_por_monto_fijo.id})
                            elif self.valid_agree_single_payment:
                                self.write({'factura_pago_unico': payment.factura_por_monto_fijo.id})
                            break
                if inv_flag:
                    break

        if self.valid_agree_single_payment and not self.factura_pago_unico:
            self.create_invoice_from_task_modified(vals)
        elif payment_percent and not payment_percent.factura_por_porcentaje:
            self.create_invoice_from_task_modified(vals)
        elif payment_parts and not payment_parts.factura_por_monto_fijo:
            self.create_invoice_from_task_modified(vals)

    def update_subscription_lines_modified(self,percentage_payment = None, part_payment = None):
        if self.percent_sub >= 100.0 or self.valid_agree_payment_percentage or self.valid_agree_fixed_amount_payment:
            
            if self.percent_sub:
                _logger.warning("Se ha detectado una tarea con pago único")
                _logger.warning("Percent: "+str(self.percent_sub))

            if self.valid_agree_payment_percentage:
                _logger.warning("Se ha detectado una tarea con pagos por porcentaje")
                _logger.warning("Percent: "+str(self.valid_agree_payment_percentage))

            if self.valid_agree_fixed_amount_payment:
                _logger.warning("Se ha detectado una tarea con pagos por monto fijo")
                _logger.warning("Percent: "+str(self.valid_agree_fixed_amount_payment))

            self.send_email_and_notify()
            progress_stage = self.env['sale.subscription.stage'].search([('fold', '=', False),('in_progress', '=', True)], limit=1)
            #for line in [line for line in self.sale_line_id.order_id.order_line if line.invoice_lines and line.subscription_id]:
                #for sub_line in [sub_line for sub_line in line.subscription_id.recurring_invoice_line_ids if line.subscription_line_id.id == sub_line.id]:
            _logger.warning("Porgress stage: "+str(progress_stage))

            line = self.sale_line_id
            _logger.warning("Sale line ID: "+str(line))
            _logger.warning("Sale line Subscription ID: "+str(line.subscription_id))

            #Asignar la linea de suscripción a su respectiva linea de pedido de venta
            #puede llegar a ser una solución para aquellas tareas que aún no tienen
            #establecido este campo.

            for item_sub in line.subscription_id.recurring_invoice_line_ids:
                _logger.warning("Nombre de la linea de la suscripción asociada a la linea del pedido de venta asociada a la tarea: "+str(item_sub.name))

                #Se puede comparar la linea de suscripción con la linea de pedido de venta para
                #saber de la manera mas exacta a que linea de suscripción pertenece cada linea de
                #pedido de venta asociada a cada tarea de cada proyecto.
                _logger.warning("Nombre item_sub: "+str(item_sub.name))
                _logger.warning("Nombre sale_line: "+str(line.name))

                _logger.warning("Cantidad item_sub: "+str(item_sub.quantity))
                _logger.warning("Cantidad sale_line: "+str(line.product_uom_qty))

                _logger.warning("Unidad item_sub: "+str(item_sub.uom_id))
                _logger.warning("Unidad sale_line: "+str(line.product_uom))

                _logger.warning("Precio/unidad item_sub: "+str(item_sub.unit_price))
                _logger.warning("Precio/unidad sale_line: "+str(line.price_unit))

                _logger.warning("Descuento item_sub: "+str(item_sub.discount))
                _logger.warning("Descuento sale_line: "+str(line.discount))

                _logger.warning("Localidad item_sub: "+str(item_sub.locality))
                _logger.warning("Localidad sale_line (from task): "+str(self.valid_agree_authorization_location))

            sub_line = line.subscription_line_id
            _logger.warning("Sale subline ID: "+str(sub_line))

            if sub_line:
                _logger.warning("Nombre de la linea de suscripción: "+str(sub_line.name))
                _logger.warning("Nombre de la plantilla de la linea de suscripción: "+str(sub_line.template_name))

                sub_line.ready_to_invoice = True
                sub_line.locality = self.valid_agree_authorization_location.upper()
                sub_line.unique_invoicing = line.product_id.unique_invoicing
                analytic_account = line._get_analytic_account()
                sub_line.analytic_account = analytic_account.id
                sub_line.account_id = line._get_income_account(analytic_account)
                line.subscription_id.stage_id = progress_stage.id

                _logger.warning("Sub line quantity: "+str(sub_line.quantity))
                _logger.warning("Sub line locality: "+str(sub_line.locality))
                _logger.warning("Sub line unique_invoicing: "+str(sub_line.unique_invoicing))
                _logger.warning("Sub line analytic_account: "+str(sub_line.analytic_account))
                _logger.warning("Sub line account_id: "+str(sub_line.account_id))
                _logger.warning("Line subscription stage: "+str(line.subscription_id.stage_id))

                if sub_line.quantity >= 1:
                    if percentage_payment:
                        new_price = sub_line.price_unit + (line.price_unit * percentage_payment.percentage_value)/100
                        if new_price > line.price_unit:
                            sub_line.price_unit = (line.price_unit * percentage_payment.percentage_value)/100
                        else:
                            sub_line.price_unit = new_price

                    elif part_payment:
                        new_price = sub_line.price_unit + part_payment.amount
                        if new_price > line.price_unit:
                            sub_line.price_unit = part_payment.amount
                        else:
                            sub_line.price_unit = new_price

                    sub_line.unit_price = sub_line.price_unit

                if sub_line.quantity > 1:
                    sub_line.unit_price = line.price_unit
                    
                sub_line.invoice_percentage = self.percent_sub
                #if line.order_id.subscription_management == 'upsell':
                    #Si el pedido de venta viene de un upsell,
                    #se debe eliminar la línea vieja
                old_line_to_delete = None
                for old_line in line.subscription_id.recurring_invoice_line_ids:
                    if sub_line.product_id.id == old_line.product_id.id:
                        if math.isclose(100.0,old_line.invoice_percentage,rel_tol=0.01):
                            if sub_line.price_unit == old_line.price_unit and math.isclose(100.0,sub_line.invoice_percentage,rel_tol=0.01):
                                if sub_line.locality == old_line.locality:
                                    if sub_line.id != old_line.id:
                                        sub_line.quantity += old_line.quantity
                                        old_line_to_delete = old_line
                                        break
                if old_line_to_delete:
                    old_line_to_delete.unlink()

    def create_invoice_tarifa_unica_recurrente(self, tarea, vals, sale_order_invoice_lines, item=None):
        _logger.warning("Valores a revisar para facturación: "+str(vals))

        if tarea.rate_type and tarea.rate_type.currency_id:
            vals['currency_id'] = tarea.rate_type.currency_id.id
            
        journal_id = self.env['account.journal'].search(
            [('type', '=', 'sale'),
            ('company_id', '=', self.env.company.id),
            ('is_sale_journal', '=', True)], limit=1)

        vals['journal_id'] = journal_id.id
        vals['come_from_task'] = True
        vals['rate_type_id'] = tarea.rate_type.id
        narration = None
        period = None
        date_to = None

        narration = _("Instalación de Servicios")
        vals['narration'] = narration
        vals['state'] = 'draft'
        if date_to:
            vals['date_from'] = vals['date']
            vals['date_to'] = date_to
        if tarea.project_id.partner_id.islr_concept_id:
            vals['concept_id'] = tarea.project_id.partner_id.islr_concept_id.id
        else:
            _logger.warning("Factura se va a crear sin concepto de ISLR, revise los ajustes del Cliente asociado a la factura.")

        #Valores a enviar para la creación de la factura
        _logger.warning("Valores a insertar en modelo move.id: "+str(vals))
        
        move_obj = self.env['account.move']
        invoice = move_obj.create(vals)

        #Se inserta el move_id en las invoice_line_ids
        sale_order_invoice_lines[0][2]['move_id'] = invoice.id

        _logger.warning("Invoice lines ids a insertar: "+str(sale_order_invoice_lines))

        #self.env['account.move.line'].write(sale_order_invoice_lines[0][2])
        invoice.write({'invoice_line_ids': sale_order_invoice_lines})

        #Se establece el status en la factura unica o en las partes de las facturas por monto fijo o porcentaje.
        tarea._set_status_in_task(invoice,item)

    def _set_status_in_task(self, invoice, item = None):
        for line in invoice.invoice_line_ids:
            task = line.sale_line_ids.task_id
            if task.valid_agree_single_payment:
                task.write({
                    'factura_pago_unico': invoice.id,
                })
            elif task.valid_agree_payment_percentage:
                invoiced_amount = 0.0
                if not item.sent_payment_date:
                    invoiced_amount += item.percentage_value
                    if not item.estatus_factura:
                        item.write({
                            'factura_por_porcentaje': invoice.id,
                        })
            elif task.valid_agree_fixed_amount_payment:
                invoiced_amount = 0.0
                if not item.sent_payment_date:
                    invoiced_amount += item.invoiced_progress_percentage
                    if invoice.date == item.estimated_payment_date and task.percent_sub >= item.invoiced_progress_percentage and task.percent_sub >= invoiced_amount and not item.estatus_factura:
                        item.write({
                            'factura_por_monto_fijo': invoice.id,
                        })

    #(23/03/2023)--> Agregando validaciones sobre formatos de fecha en el proceso de creación
    #automático de facturas desde tareas de proeyctos.
    def create_invoice_from_task(self, vals):
        if self.rate_type and self.rate_type.currency_id:
            vals['currency_id'] = self.rate_type.currency_id.id
            
        journal_id = self.env['account.journal'].search(
            [('type', '=', 'sale'),
            ('company_id', '=', self.env.company.id),
            ('is_sale_journal', '=', True)], limit=1)

        vals['journal_id'] = journal_id.id
        vals['come_from_task'] = True
        vals['rate_type_id'] = self.rate_type.id
        narration = None
        period = None
        date_to = None
        if self.rate_type.tipo_tarifa == 'Recurrente':

            #Validaciones solo en tarifa recurrente.
            try:
                if self.valid_agree_single_payment:
                    if datetime.strptime(str(self.valid_agree_estimated_payment_date), '%Y-%m-%d').strftime('%m') == fields.Date.from_string(self.sent_payment_date).strftime('%m'):
                        narration = _("Esta factura cubre el siguiente periodo:  %s - %s") % (format_date(
                            self.env, vals['date']), format_date(self.env, self.last_day_of_month(vals['date'])))
                        date_to = self.last_day_of_month(vals['date'])
                    else:
                        narration = _("Esta factura cubre el siguiente periodo:  %s - %s") % (format_date(
                            self.env, vals['date']), format_date(self.env, self.last_day_of_month(vals['date'] + relativedelta(months=1))))
                        date_to = self.last_day_of_month(vals['date'] + relativedelta(months=1))
                elif self.valid_agree_payment_percentage:
                    for payment in self.payment_by_prencentage_ids:
                        if payment.sent_payment_date:
                            if datetime.strptime(str(payment.estimated_payment_date), '%Y-%m-%d').strftime('%m') == fields.Date.from_string(payment.sent_payment_date).strftime('%m'):
                                narration = _("Esta factura cubre el siguiente periodo:  %s - %s") % (format_date(
                                    self.env, vals['date']), format_date(self.env, self.last_day_of_month(vals['date'])))
                                date_to = self.last_day_of_month(vals['date'])
                                break
                            else:
                                narration = _("Esta factura cubre el siguiente periodo:  %s - %s") % (format_date(
                                    self.env, vals['date']), format_date(self.env, self.last_day_of_month(vals['date'] + relativedelta(months=1))))
                                date_to = self.last_day_of_month(vals['date'] + relativedelta(months=1))
                                break
                elif self.valid_agree_fixed_amount_payment:
                    for payment in self.part_payments_fixed_amounts_ids:
                        if payment.sent_payment_date:
                            if datetime.strptime(str(payment.estimated_payment_date), '%Y-%m-%d').strftime('%m') == fields.Date.from_string(payment.sent_payment_date).strftime('%m'):
                                narration = _("Esta factura cubre el siguiente periodo:  %s - %s") % (format_date(
                                    self.env, vals['date']), format_date(self.env, self.last_day_of_month(vals['date'])))
                                date_to = self.last_day_of_month(vals['date'])
                                break
                            else:
                                narration = _("Esta factura cubre el siguiente periodo:  %s - %s") % (format_date(
                                    self.env, vals['date']), format_date(self.env, self.last_day_of_month(vals['date'] + relativedelta(months=1))))
                                date_to = self.last_day_of_month(vals['date'] + relativedelta(months=1))
                                break
            except:
                raise ValidationError(_("""Error al procesar el cambio en la tarea, por favor, verifique los formatos de la fecha introducidos e intente nuevamente."""))
        else:
            narration = _("Instalación de Servicios")
        vals['narration'] = narration
        if date_to:
            vals['date_from'] = vals['date']
            vals['date_to'] = date_to
        if self.partner_id.islr_concept_id:
            vals['concept_id'] = self.partner_id.islr_concept_id.id
        invoice = self.env['account.move'].create(vals)
        for line in invoice.invoice_line_ids:
            task = line.sale_line_ids.task_id
            if task.valid_agree_single_payment:
                task.write({
                    'factura_pago_unico': invoice.id,
                })
            elif task.valid_agree_payment_percentage:
                invoiced_amount = 0.0
                for payment in task.payment_by_prencentage_ids:
                    if not payment.sent_payment_date:
                        continue
                    invoiced_amount += payment.percentage_value
                    if invoice.date == payment.estimated_payment_date and task.percent_sub >= payment.percentage_value and task.percent_sub >= invoiced_amount and not payment.estatus_factura:
                        payment.write({
                            'factura_por_porcentaje': invoice.id,
                        })
            elif task.valid_agree_fixed_amount_payment:
                invoiced_amount = 0.0
                for payment in task.part_payments_fixed_amounts_ids:
                    if not payment.sent_payment_date:
                        continue
                    invoiced_amount += payment.invoiced_progress_percentage
                    if invoice.date == payment.estimated_payment_date and task.percent_sub >= payment.invoiced_progress_percentage and task.percent_sub >= invoiced_amount and not payment.estatus_factura:
                        payment.write({
                            'factura_por_monto_fijo': invoice.id,
                        })

    """
    def create_invoice_from_task_modified(self, tarea, vals):
        _logger.warning("Valores a revisar para facturación: "+str(vals))

        if tarea.rate_type and tarea.rate_type.currency_id:
            vals['currency_id'] = tarea.rate_type.currency_id.id
            
        journal_id = self.env['account.journal'].search(
            [('type', '=', 'sale'),
            ('company_id', '=', self.env.company.id),
            ('is_sale_journal', '=', True)], limit=1)

        vals['journal_id'] = journal_id.id
        vals['come_from_task'] = True
        vals['rate_type_id'] = tarea.rate_type.id
        narration = None
        period = None
        date_to = None
        if self.rate_type.tipo_tarifa == 'Recurrente':
            if self.valid_agree_single_payment:
                if datetime.strptime(str(self.valid_agree_estimated_payment_date), '%Y-%m-%d').strftime('%m') == fields.Date.from_string(self.sent_payment_date).strftime('%m'):
                    narration = _("Esta factura cubre el siguiente periodo:  %s - %s") % (format_date(
                        self.env, vals['date']), format_date(self.env, self.last_day_of_month(vals['date'])))
                    date_to = self.last_day_of_month(vals['date'])
                else:
                    narration = _("Esta factura cubre el siguiente periodo:  %s - %s") % (format_date(
                        self.env, vals['date']), format_date(self.env, self.last_day_of_month(vals['date'] + relativedelta(months=1))))
                    date_to = self.last_day_of_month(vals['date'] + relativedelta(months=1))
            elif self.valid_agree_payment_percentage:
                for payment in self.payment_by_prencentage_ids:
                    if payment.sent_payment_date:
                        if datetime.strptime(str(payment.estimated_payment_date), '%Y-%m-%d').strftime('%m') == fields.Date.from_string(payment.sent_payment_date).strftime('%m'):
                            narration = _("Esta factura cubre el siguiente periodo:  %s - %s") % (format_date(
                                self.env, vals['date']), format_date(self.env, self.last_day_of_month(vals['date'])))
                            date_to = self.last_day_of_month(vals['date'])
                            break
                        else:
                            narration = _("Esta factura cubre el siguiente periodo:  %s - %s") % (format_date(
                                self.env, vals['date']), format_date(self.env, self.last_day_of_month(vals['date'] + relativedelta(months=1))))
                            date_to = self.last_day_of_month(vals['date'] + relativedelta(months=1))
                            break
            elif self.valid_agree_fixed_amount_payment:
                for payment in self.part_payments_fixed_amounts_ids:
                    if payment.sent_payment_date:
                        if datetime.strptime(str(payment.estimated_payment_date), '%Y-%m-%d').strftime('%m') == fields.Date.from_string(payment.sent_payment_date).strftime('%m'):
                            narration = _("Esta factura cubre el siguiente periodo:  %s - %s") % (format_date(
                                self.env, vals['date']), format_date(self.env, self.last_day_of_month(vals['date'])))
                            date_to = self.last_day_of_month(vals['date'])
                            break
                        else:
                            narration = _("Esta factura cubre el siguiente periodo:  %s - %s") % (format_date(
                                self.env, vals['date']), format_date(self.env, self.last_day_of_month(vals['date'] + relativedelta(months=1))))
                            date_to = self.last_day_of_month(vals['date'] + relativedelta(months=1))
                            break
        else:
            _logger.warning("Tarea con tarifa Única.")

        narration = _("Instalación de Servicios")
        vals['narration'] = narration
        if date_to:
            vals['date_from'] = vals['date']
            vals['date_to'] = date_to
        if tarea.project_id.partner_id.islr_concept_id:
            vals['concept_id'] = tarea.project_id.partner_id.islr_concept_id.id
        else:
            _logger.warning("Factura creada sin concepto de ISLR, revise los ajustes del Cliente asociado a la factura.")

        #Valores a enviar para la creación de la factura
        _logger.warning("Valores a insertar en modelo move.id: "+str(vals))

        invoice = self.env['account.move'].create(vals)
        for line in invoice.invoice_line_ids:
            task = line.sale_line_ids.task_id
            if task.valid_agree_single_payment:
                task.write({
                    'factura_pago_unico': invoice.id,
                })
            elif task.valid_agree_payment_percentage:
                invoiced_amount = 0.0
                for payment in task.payment_by_prencentage_ids:
                    if not payment.sent_payment_date:
                        continue
                    invoiced_amount += payment.percentage_value
                    if invoice.date == payment.estimated_payment_date and task.percent_sub >= payment.percentage_value and task.percent_sub >= invoiced_amount and not payment.estatus_factura:
                        payment.write({
                            'factura_por_porcentaje': invoice.id,
                        })
            elif task.valid_agree_fixed_amount_payment:
                invoiced_amount = 0.0
                for payment in task.part_payments_fixed_amounts_ids:
                    if not payment.sent_payment_date:
                        continue
                    invoiced_amount += payment.invoiced_progress_percentage
                    if invoice.date == payment.estimated_payment_date and task.percent_sub >= payment.invoiced_progress_percentage and task.percent_sub >= invoiced_amount and not payment.estatus_factura:
                        payment.write({
                            'factura_por_monto_fijo': invoice.id,
                        })
    """
    
    def group_invoices_modified(self, payment_date, location):

        invoice_lines = list()

        _logger.warning("Lineas: "+str(self.sale_line_id.order_id.order_line))
        _logger.warning("Nombre de la tarea a buscar en las lineas: "+str(self.name))

        for line in self.sale_line_id.order_id.order_line:
            _logger.warning("Linea de pedido: "+str(line.name))
            _logger.warning("Linea de pedido (task id): "+str(line.task_id))

            #Solo se devuelven las lineas de factura correspondientes a la tarea o segmento particular.
            if line.name == self.name:

                task = line.task_id
                task.invoiced_porcentage = 0
                if not task.prorate_amount:
                    task.calculate_prorate_amount()

                _logger.warning("Unico: "+str(task.valid_agree_single_payment))
                _logger.warning("Porcentaje: "+str(task.valid_agree_payment_percentage))
                _logger.warning("Monto fijo: "+str(task.valid_agree_fixed_amount_payment))

                _logger.warning("Payment date enviada a análisis: "+str(payment_date))
                _logger.warning(task.valid_agree_authorization_location)
                _logger.warning(location)
                _logger.warning(task.percent_sub)
                _logger.warning(task.rate_type.tipo_tarifa)
                _logger.warning(task.validate_so)
                _logger.warning(task.validate_finance)

                #if task.valid_agree_single_payment and task.valid_agree_estimated_payment_date == payment_date and task.valid_agree_authorization_location == location and not task.estatus_factura and task.percent_sub >= 100.0 and (task.rate_type.tipo_tarifa == 'Recurrente' or task.rate_type.tipo_tarifa == 'Unica') and task.validate_so and self.validate_finance:
                if task.valid_agree_single_payment and task.valid_agree_estimated_payment_date == payment_date and task.valid_agree_authorization_location == location and not task.estatus_factura and task.percent_sub >= 100.0 and (task.rate_type.tipo_tarifa == 'Recurrente' or task.rate_type.tipo_tarifa == 'Unica') and self.validate_finance:
                    
                    _logger.warning("Fecha de la tarea con pago único: "+str(task.valid_agree_estimated_payment_date))
                    _logger.warning(task.estatus_factura)
                    
                    #Se debe agregar la localización del producto.
                    invoice_lines.append((0, 0, line.custom_prepare_invoice_line_modified(task.prorate_amount or task.valid_agree_sales_order_line_amount,
                                                                                    task.sale_line_id.product_uom_qty, "Pago Único", " 100 %", location)))
                    #Solo debe encontrar la linea de facturación que se va a registrar.
                    break

                elif task.valid_agree_payment_percentage:
                    lines = self.env['project_sub_task.payment_by_prencentage'].search(
                        [('projectsubtask_payment_by_prencentage_id', '=', task.id)], order='sent_payment_date desc')
                    for payment in lines:
                        _logger.warning("Fecha estimada de facturación de la linea por porcentaje a analizar: "+str(payment.estimated_payment_date))
                        
                        #if not payment.sent_payment_date:
                        #    continue
                        if not payment.estatus_factura:
                            task.invoiced_porcentage += payment.percentage_value
                        if payment.estimated_payment_date == payment_date and task.valid_agree_authorization_location == location and not payment.estatus_factura and task.percent_sub >= payment.percentage_value and task.percent_sub >= task.invoiced_porcentage and (task.rate_type.tipo_tarifa == 'Recurrente' or task.rate_type.tipo_tarifa == 'Unica') and self.validate_finance:
                            invoice_lines.append((0, 0, line.custom_prepare_invoice_line_modified(payment.amount,task.sale_line_id.product_uom_qty / len(task.payment_by_prencentage_ids),
                                                                                            "Pago por Porcentaje", "{} %".format(payment.percentage_value), location)))
                            #Solo debe encontrar la linea de facturación que se va a registrar.
                            break

                elif task.valid_agree_fixed_amount_payment:
                    #Por monto fijo
                    lines = self.env['project_sub_task.part_payments_fixed_amounts'].search(
                        [('projectsubtask_part_payments_fixed_amounts_id', '=', task.id)], order='sent_payment_date desc')
                    
                    _logger.warning("Lineas encontradas en la tarea: "+str(lines))
                    for payment in lines:

                        _logger.warning("Sent_payment_date: "+str(payment.sent_payment_date))
                        _logger.warning("Status factura: "+str(payment.estatus_factura))
                        _logger.warning("invoiced_porcentage: "+str(task.invoiced_porcentage))
                        _logger.warning("estimated_payment_date: "+str(payment.estimated_payment_date))
                        _logger.warning("payment_date: "+str(payment_date))
                        _logger.warning("valid_agree_authorization_location: "+str(task.valid_agree_authorization_location))
                        _logger.warning("location: "+str(location))
                        _logger.warning("Porcentaje de la tarea: "+str(task.percent_sub))
                        _logger.warning("Invoiced_progress_percentage: "+str(payment.invoiced_progress_percentage))
                        _logger.warning("Tarifa: "+str(task.rate_type.tipo_tarifa))
                        
                        #if not payment.sent_payment_date:
                        #    continue
                        if not payment.estatus_factura:
                            _logger.warning("Sin estatus de factura.")
                            task.invoiced_porcentage += payment.invoiced_progress_percentage
                        if payment.estimated_payment_date == payment_date and task.valid_agree_authorization_location == location and not payment.estatus_factura and task.percent_sub >= payment.invoiced_progress_percentage and task.percent_sub >= task.invoiced_porcentage and (task.rate_type.tipo_tarifa == 'Recurrente' or task.rate_type.tipo_tarifa == 'Unica') and self.validate_finance:
                            _logger.warning("Llegó al llegadero!!")
                            invoice_lines.append((0, 0, line.custom_prepare_invoice_line_modified(payment.amount,task.sale_line_id.product_uom_qty / len(task.part_payments_fixed_amounts_ids),
                                                                                            "Pago por Partes", "{} %".format(payment.invoiced_progress_percentage), location)))

        return invoice_lines

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # Reescribir metodo que prepara las lineas de factura para reemplazar 'Invoicing period' de la descripcion, por 'Periodo de facturación'.
    def custom_prepare_invoice_line_modified(self, price_unit, quantity, payment_type, payment_amount, location, price_unit_prorate = None):
        """
        Prepare the dict of values to create the new invoice line for a sales order line.

        :param qty: float quantity to invoice
        """
        analytic_account = self._get_analytic_account()
        income_account = self._get_income_account(analytic_account)

        _logger.warning("Analityc_account: "+str(analytic_account))
        _logger.warning("Income_account: "+str(income_account))

        tax_amount = self.tax_id.amount / 100 * price_unit
        unit_price = abs(self.task_id.prorate_amount)/quantity or abs(self.task_id.valid_agree_sales_order_line_amount) / quantity
        if self.discount:
            unit_price = price_unit = self.task_id.prorated_price_unit() or 0.0
        if price_unit_prorate:
            price_unit = price_unit_prorate
            unit_price = abs(price_unit) or abs(self.task_id.valid_agree_sales_order_line_amount) / quantity

        self.ensure_one()
        res = {
            'display_type': self.display_type,
            'sequence': self.sequence,
            'name': self.name,
            'product_id': self.product_id.id,
            'account_id': int(income_account.id),
            'task_invoice_payment_type': payment_type,
            'task_invoice_payment_amount': payment_amount,
            'location': location.upper(),
            'product_uom_id': self.product_uom.id,
            'quantity': quantity,
            'discount': self.discount,
            'price_unit': price_unit if self.discount or price_unit_prorate else price_unit/quantity,
            'unit_price': unit_price,
            'tax_amount': tax_amount,
            'tax_ids': [(6, 0, self.tax_id.ids)],
            'analytic_account_id': int(analytic_account.id),
            'analytic_tag_ids': [(6, 0, self.analytic_tag_ids.ids)],
            'sale_line_ids': [(4, self.id)],
            'currency_id': self.order_id.currency_id.id,
            'unique_invoicing': self.product_id.unique_invoicing,
        }
        if self.order_id.partner_id.islr_concept_id:
            res['concept_id'] = self.order_id.partner_id.islr_concept_id.id

        if self.display_type:
            res['account_id'] = False

        if self.subscription_id:
            name = res['name']
            name = name.replace("Invoicing period", "Periodo de facturación")
            res.update({
                'name': name,
            })
        return res