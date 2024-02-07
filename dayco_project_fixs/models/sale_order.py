# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging
#import pyodbc #Librería de conexión a bases de datos SQL.
import string
from datetime import date, datetime, timedelta
from odoo.exceptions import UserError, ValidationError
from time import time
import re
import json
import requests
from requests.auth import HTTPBasicAuth

_logger = logging.getLogger(__name__)

class DaycoExtrasSaleOrderProyectos(models.Model):
    _inherit = 'sale.order'
    _description = "Modificaciones de procesos automáticos entre pedidos de ventas y proyectos."

    #(12/04/2023) --> Agregar validación sobre lineas de pedido al guardar un pedido de venta.
    def write(self,vals):

        res = super(DaycoExtrasSaleOrderProyectos, self).write(vals)

        #Antes de escribir los cambios, se verifican cambios en las lineas de pedido de ventas.
        for line in self.order_line:
            _logger.warning("Nombre de la linea: "+str(line.name))
            _logger.warning("Nombre de la tarea: "+str(line.task_id.name))
            _logger.warning("Monto de la tarea asociada: "+str(line.task_id.valid_agree_sales_order_line_amount))
            _logger.warning("Monto de la linea del pedido de venta: "+str(line.price_subtotal))

            if line.task_id:
                #Actualizar el monto de la linea de pedido de venta en la tarea asociada.
                line.task_id.valid_agree_sales_order_line_amount = line.price_subtotal

        return res

class DaycoExtrasSaleOrderLineProyectos(models.Model):
    _inherit = 'sale.order.line'
    _description = 'Modificaciones del módulo de ventas para ajustar procesos varios.'

    def custom_prepare_invoice_line(self, price_unit, quantity, payment_type, payment_amount, location, price_unit_prorate = None):
        """
        Prepare the dict of values to create the new invoice line for a sales order line.

        :param qty: float quantity to invoice
        """
        analytic_account = self._get_analytic_account()
        income_account = self._get_income_account(analytic_account)
        
        facturacion_demo = False

        try:
            tax_amount = self.tax_id.amount / 100 * price_unit
            unit_price = abs(self.task_id.prorate_amount)/quantity or abs(self.task_id.valid_agree_sales_order_line_amount) / quantity
            if self.discount:
                unit_price = price_unit = self.task_id.prorated_price_unit() or 0.0
            if price_unit_prorate:
                price_unit = price_unit_prorate
                unit_price = abs(price_unit) or abs(self.task_id.valid_agree_sales_order_line_amount) / quantity
        except:
            if price_unit == 0 or quantity == 0:
                facturacion_demo = True
                _logger.warning("Cantidad: "+str(quantity))
                _logger.warning("Precio: "+str(price_unit))
                pass
            else:
                raise ValidationError(_("Error al cálcular el precio unitario, por favor verifique el monto y cantidad de los productos en el pedido de venta asociado e intente nuevamente."))
        
        #(13/06/2023) --> Función actual que genera las lineas desde el SO hacia la factura
                         #cuando se cumplen las condiciones del automatismo de la tarea.
        if not facturacion_demo:
            self.ensure_one()
            res = {
                'display_type': self.display_type,
                'sequence': self.sequence,
                'name': self.name,
                'product_id': self.product_id.id,
                'account_id': income_account.id or '',
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
                'analytic_account_id': analytic_account.id,
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
        else:
            self.ensure_one()
            res = {
                'display_type': self.display_type,
                'sequence': self.sequence,
                'name': self.name,
                'product_id': self.product_id.id,
                'account_id': income_account.id or '',
                'task_invoice_payment_type': payment_type,
                'task_invoice_payment_amount': payment_amount,
                'location': location.upper(),
                'product_uom_id': self.product_uom.id,
                'quantity': 0,
                'discount': self.discount,
                'price_unit': 0,
                'unit_price': 0,
                'tax_amount': 0,
                'tax_ids': False,
                'analytic_account_id': analytic_account.id,
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
    
    """
    def action_confirm(self):
        _logger.warning("########## INICIO VERIFICACIÓN DE PROYECTOS EN PEDIDOS DE VENTA ##########")
        _logger.warning("########## INICIO VERIFICACIÓN DE PROYECTOS EN PEDIDOS DE VENTA ##########")

        #Se ejecuta todo el proceso actual en la función action_confirm del pedido de venta.
        super(DaycoExtrasSaleOrderProyectos, self).action_confirm()

        #Se verifica que el proyecto asociado al pedido de venta (en caso de que aplique)
        #no se encuentre al 100% en sus tareas padre, en caso de ser asi, se debe recomendar
        #crear una oportunidad nueva.
        #Como se hace desde una venta adicional, se debe asignar primero el proyecto y luego
        #es que se verifican los porcentajes de las tareas padre del proyecto asignado.

        proyecto_admitido = False

        if self.project_id:
            _logger.warning("Proyecto asociado: "+str(self.project_id.name))

            #Se buscan las tareas padre del proyecto asociado.
            padre_tasks = self.env['project.task'].search([('project_id', '=', self.project_id.id),('parent_id', '=', False)])

            for task in padre_tasks:
                _logger.warning("% de avance de la tarea: "+str(task.name)+": "+str(task.percentage_progress))

                if task.percentage_progress == 100:
                    _logger.warning("Este Cliente no posee proyectos activos, por favor, gestione uno desde una nueva oportunidad.")
                else:
                    proyecto_admitido = True
                    break
            
            if not proyecto_admitido:
                raise ValidationError(_("Este Cliente no posee proyectos activos, por favor, gestione uno desde una nueva oportunidad."))
            else:
                self.domain_onchange()
                #super().action_confirm()
                ctx = self._context.copy()
                domain= [('type_motive', '=', 'awon')]
                search=self.env['motives.proposal'].search(domain)
                ctx['reason']=[x.id for x in search]
                ctx['type'] ='sale'
                ctx['type_motive'] ='awon'
                ctx['id_order'] =self.id

                return {
                    'name': _('Motive Proposal'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'motive.wizard',
                    'view_mode': 'form',
                    'context': ctx,
                    'target': 'new',
                }
        else:
            self.domain_onchange()
            #super().action_confirm()
            ctx = self._context.copy()
            domain= [('type_motive', '=', 'awon')]
            search=self.env['motives.proposal'].search(domain)
            ctx['reason']=[x.id for x in search]
            ctx['type'] ='sale'
            ctx['type_motive'] ='awon'
            ctx['id_order'] =self.id

            return {
                'name': _('Motive Proposal'),
                'type': 'ir.actions.act_window',
                'res_model': 'motive.wizard',
                'view_mode': 'form',
                'context': ctx,
                'target': 'new',
            }
    """