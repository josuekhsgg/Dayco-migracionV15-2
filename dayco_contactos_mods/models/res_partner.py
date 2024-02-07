# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging
#import pyodbc #Librería de conexión a bases de datos SQL.
import pymssql
import string
from datetime import date, datetime, timedelta
from odoo.exceptions import UserError, ValidationError
from . import check_sgc_data
from . import bd_connector
from time import time
import re

_logger = logging.getLogger(__name__)

class DaycoExtrasContactos(models.Model):
    _inherit = 'res.partner'
    _description = 'Modificaciones del módulo de contactos para integración con SGC.'

    id_cliente = fields.Integer("ID cliente SGC", store=True) #default=lambda self: self._revisar_id_sgc())
    direccion_facturacion = fields.Char("Dirección de facturación", related="street")
    rif_cliente = fields.Char("RIF", store=True, related="vat")
    fax_cliente= fields.Char("FAX", default="-")
    tipo_negocio_cliente = fields.Integer('Tipo de negocio', default=38)
    categoria_cliente = fields.Selection([('5', 'P1'),('7', 'P2'),('8', 'P3'),('10', 'P4')], 'Categoría', default='10')
    tipo_cliente = fields.Selection([('1', 'Cliente de Valor'), ('2', 'Cliente de Alto Valor'), ('3','Prospecto'), ('4','Vip')], 'Tipo de Cliente', default='1')
    unidad_negocio_cliente = fields.Selection([('1', 'Masivo'), ('2', 'Corporativo'), ('3', 'Masivo/Corporativo'), ('4', 'Otro')], 'Unidad de negocio', default='2')
    tipo_cliente_corporativo = fields.Selection([('1', 'Dedicado'), ('2', 'Colocado'), ('3', 'Dedicado/Colocado'), ('4', 'Otro')], 'Tipo de Cliente corporativo', default='4')
    municipio_cliente = fields.Integer('Municipio Cliente', default=1)
    cliente_activo = fields.Integer("Cliente Activo", default=1)
    client_date_modified = fields.Datetime("Última fecha de modificación (Cliente)", default=fields.Datetime.now(), store=True)
    account_management_id_sgc = fields.Char("Gerente de cuenta")
    revisar_id_cliente_sgc = fields.Boolean("Revisar ID SGC - Cliente", default=True, store=True)
    cliente_partner_category = fields.Selection([('1', 'Cliente'), ('2', 'Cliente / Proveedor'), ('3','Proveedor'), ('4','Empleado'), ('5', 'Otros')], 'Categoría del Cliente')
    
    #Campos direccionados a los contactos
    id_contacto = fields.Integer("ID contacto SGC", store=True)#, default=lambda self: self._revisar_id_contacto_sgc())
    apellido_contacto = fields.Char("Apellido contacto", default='*')
    cedula_contacto = fields.Char("Cédula contacto", store=True)
    cargo_contacto = fields.Char("Cargo contacto", related="function")
    ciudad_contacto = fields.Char("Ciudad contacto")
    prioridad_contacto = fields.Integer("Prioridad contacto", default=1)
    habilitado_contacto = fields.Integer("Contacto Habilitado", default=1)
    tipo_contacto = fields.Selection([('1', 'Ejecutivo'), ('2', 'Dayco'), ('3','Administrativo')], 'Tipo contacto')
    contacto_activo = fields.Integer("Contacto Activo", default=1)
    contacto_date_modified = fields.Datetime("Última fecha de modificación (Contacto)", default=fields.Datetime.now(), store=True)
    ScalabilityLevel = fields.Selection([('1', '1'), ('2', '2'), ('3','3'), ('4','No aplica')], 'Scalability Level', default='1') #No puede ser cero.
    privilegio_ids = fields.One2many('privilegios.contactos.sgc', 'privilegio_id', string="", readonly=False, store=True)
    check_privilegios_label = fields.Text("Log", compute='_check_privilegios')
    revisar_id_contacto_sgc = fields.Boolean("Revisar ID SGC - Contactos", default=True, store=True)
    #criterio_ordenamiento_nombre_sgc = fields.Selection([('1', 'Nombre(s) + apellido(s)'), ('2', 'Nombre + apellido(s)')], 'Criterio de ordenamiento del nombre', default='1')

    #Campos de control de procesos y funciones
    create_from_sync = fields.Boolean("Desde sincronización", default=False, store=True)
    company_type_stored = fields.Selection("Tipo de contacto", related="company_type", store=True)
    #Se debe asegurar que cuando se modifique algún dato de manera efectiva entonces se proceda
    #a cambiar la fecha de escritura en la ficha del contacto

    def _check_privilegios(self):
        if self.privilegio_ids:
            for privilegio in self.privilegio_ids:
                _logger.warning("Privilegio: "+str(privilegio.name))

                #Buscar coincidencias en la misma tabla de privilegios.
                count = 0
                for item in self.privilegio_ids:
                    if item.name == privilegio.name:
                        count+=1
                
                if count > 1:
                    self.privilegio_ids = False
                    self.check_privilegios_label = "Privilegios repetidos, por favor verifique"
                else:
                    self.check_privilegios_label = "Privilegios establecidos"
        else:
            self.check_privilegios_label = "Sin privilegios"

    #Correcciones en caso de valores incoherentes en los privilegios
    @api.onchange('privilegio_ids')
    def check_privilegios(self):
        if self.privilegio_ids:
            for privilegio in self.privilegio_ids:
                _logger.warning("Privilegio: "+str(privilegio.name))

                #Buscar coincidencias en la misma tabla de privilegios.
                count = 0
                for item in self.privilegio_ids:
                    if item.name == privilegio.name:
                        count+=1
                
                if count > 1:
                    self.privilegio_ids = False
                    self.check_privilegios_label = "No se puede establecer privilegios repetidos, por favor, verifique."
                else:
                    self.check_privilegios_label = "Privilegios establecidos"
        else:
            self.check_privilegios_label = "Sin privilegios"
            
    #Asignaciones automáticas en campos irregulares
    @api.onchange('user_id')
    def check_gerente_de_cuenta_to_sgc(self):
        _logger.warning("########## - Inicio chequeo user_id - ##########")
        _logger.warning("########## - Inicio chequeo user_id - ##########")

        _logger.warning("Partner_id: "+str(self.user_id.partner_id))
        _logger.warning("Id_contacto SGC: "+str(self.user_id.partner_id.id_contacto))

        #Reiniciar igualando a cero primero para garantizar que no quede un ID anterior.
        self.account_management_id_sgc = False
        if self.user_id.partner_id.id_contacto > 0:
            self.account_management_id_sgc = str(self.user_id.partner_id.id_contacto)

        _logger.warning("########## - Fin chequeo user_id - ##########")
        _logger.warning("########## - Fin chequeo user_id - ##########")

    @api.onchange('partner_type_id')
    def check_partner_type_id_to_sgc(self):
        _logger.warning("########## - Inicio chequeo partner_type_id - ##########")
        _logger.warning("########## - Inicio chequeo partner_type_id - ##########")

        self.unidad_negocio_cliente = False

        if str(self.partner_type_id.name) == "Corporativo":
            self.unidad_negocio_cliente = "2"
        elif str(self.partner_type_id.name) == "Sharehosting":
            self.unidad_negocio_cliente = "1"

        _logger.warning("########## - Fin chequeo partner_type_id - ##########")
        _logger.warning("########## - Fin chequeo partner_type_id - ##########")

    @api.onchange('partner_category')
    def check_partner_category_to_sgc(self):
        _logger.warning("########## - Inicio chequeo partner_category Odoo - ##########")
        _logger.warning("########## - Inicio chequeo partner_category Odoo - ##########")

        self.cliente_partner_category = False

        if str(self.partner_category) == "1":
            self.cliente_partner_category = "1"
        elif str(self.partner_category) == "2":
            self.cliente_partner_category = "2"
        elif str(self.partner_category) == "3":
            self.cliente_partner_category = "3"
        elif str(self.partner_category) == "4":
            self.cliente_partner_category = "4"
        elif str(self.partner_category) == "5":
            self.cliente_partner_category = "5"

        _logger.warning("########## - Fin chequeo partner_category Odoo - ##########")
        _logger.warning("########## - Fin chequeo partner_category Odoo - ##########")

    @api.onchange('category_id')
    def check_categorias_to_sgc(self):
        _logger.warning("########## - Inicio chequeo de categorías hacia SGC - ##########")
        _logger.warning("########## - Inicio chequeo de categorías hacia SGC - ##########")

        self.tipo_cliente = False

        for category in self.category_id:
            _logger.info("Categoría: "+str(category.name))
            if str(category.name) == "Cliente de Valor":
                self.tipo_cliente = '1'
                break
            elif str(category.name) == "Cliente Alto Valor":
                self.tipo_cliente = '2'
                break
            elif str(category.name) == "Prospecto":
                self.tipo_cliente = '3'
                break
            elif str(category.name) == "VIP":
                self.tipo_cliente = '4'
                break
            elif str(category.name) == "Base Instalada":
                self.tipo_cliente = '1'
                break
            elif str(category.name) == "Aliados para el Servicio" or str(category.name) == "Aliado para el Servicio":
                self.tipo_cliente = '1'
                break

        _logger.warning("########## - Fin chequeo de categorías hacia SGC - ##########")
        _logger.warning("########## - Fin chequeo de categorías hacia SGC - ##########")

    #Al desactivar un contacto en Odoo, se debe desactivar en SGC al instante sin esperar por la sincronización.
    def desactivate_record(self):
        _logger.warning("Se va a desactivar el contacto (Compañía / Individual / Individual - Cliente): "+str(self.name))

        #Primero se desactiva en el SGC, si todo sale OK entonces si se desactiva en Odoo,
        #en caso de presentarse algún error entonces se debe emitir la alerta adecuada.
        #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.

        try:
            if str(self.partner_category) == '1' or str(self.partner_category) == '2' or str(self.partner_category) == '3':
                #Una vez modificada la fecha se procede a insertar la nueva data en el SGC.
                ip = self.env.company.ip_conexion_sgc
                port = self.env.company.puerto_conexion_sgc
                bd = self.env.company.bd_conexion_sgc
                user = self.env.company.user_conexion_sgc
                password = self.env.company.pass_conexion_sgc

                # ENCRYPT defaults to yes starting in ODBC Driver 18. Its good to always specify ENCRYPT=yes on the client side to avoid MITM attacks.
                cnxn = bd_connector.BdConnections.connect_to_bd(self,ip,port,bd,user,password)
                #cnxn = bd_connector.BdConnections.connect_to_bd(self,'200.74.215.68','4022','Dayco_SGC','Odoo','Dayco2022$')

                if not cnxn:
                    _logger.warning("No se pudo conectar a la base de datos, verifique los errores de conexión en el log.")
                else:
                    cursor_b = cnxn.cursor(as_dict=True)
                    _logger.warning("Actualizando desde Odoo a SGC")

                    rows = ''
                    #Para el caso de activar o desactivar el valor a enviar es el mismo (ID del SGC)
                    if self.company_type_stored == 'person' and self.parent_id:
                        params = int(self.id_contacto)
                        rows = cursor_b.callproc('EliminarContacto', [params])
                    elif self.company_type_stored == 'person' and not self.parent_id and self.facturable and str(self.partner_type_id.name) == "Sharehosting":
                        params = int(self.id_cliente)
                        rows = cursor_b.callproc('EliminarCliente', [params])
                    else:
                        params = int(self.id_cliente)
                        rows = cursor_b.callproc('EliminarCliente', [params])
                    
                    cnxn.commit() 
                    
                    sgc_sucessfully_commit = False
                    for row in rows:
                        _logger.warning("Numero de filas afectadas: "+str(row))
                        sgc_sucessfully_commit = True
                        #Con solo el primer valor es suficiente :)
                        break

                    #Si la consulta afecto al menos a una fila entonces todo OK, si no lanza la alerta
                    if not sgc_sucessfully_commit:
                        cnxn.close()
                        raise ValidationError(_("Ninguna fila ha sido afectada, verifique con el Administrador del SGC sobre el 'archivado/desarchivado' de este registro."))
                    
                    #Se hace falso para que al crear por si+ncronización no se haga un rechequeo innecesario.
                    self.revisar_id_cliente_sgc = False
                    self.revisar_id_contacto_sgc = False
                    
                    #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.
                    if self.company_type_stored == 'person' and self.parent_id:
                        self.contacto_date_modified = datetime.now() + timedelta(minutes=1)
                        self.contacto_activo = 0
                    elif self.company_type_stored == 'person' and not self.parent_id and self.facturable:
                        self.client_date_modified = datetime.now() + timedelta(minutes=1)
                        self.cliente_activo = 0
                    else:
                        self.client_date_modified = datetime.now() + timedelta(minutes=1)
                        self.cliente_activo = 0

                    self.active = False
                    cnxn.close()
            else:
                raise ValidationError(_("""Las funcionalidades de la interfaz SGC-Odoo han sido habilitadas
                                           solo a los registros que contengan en su campo 'Categoría' los valores:
                                           1- Cliente
                                           2- Cliente/Proveedor """))

        except pymssql.Error as e:
                cursor_b.close()
                cnxn.close()

                raise ValidationError(_("""Error al activar este Contacto/Cliente, por favor, verifique e intente nuevamente.
                                            Registro del error: 

                                            """+str(e)+"""."""))
    def activate_record(self):
        _logger.warning("Se va a activar el contacto (Compañía / Individual):: "+str(self.name))

        #Primero se activa en el SGC, si todo sale OK entonces si se desactiva en Odoo,
        #en caso de presentarse algún error entonces se debe emitir la alerta adecuada.
        #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.

        try:
            if str(self.partner_category) == '1' or str(self.partner_category) == '2' or str(self.partner_category) == '3':
                #Una vez modificada la fecha se procede a insertar la nueva data en el SGC.
                ip = self.env.company.ip_conexion_sgc
                port = self.env.company.puerto_conexion_sgc
                bd = self.env.company.bd_conexion_sgc
                user = self.env.company.user_conexion_sgc
                password = self.env.company.pass_conexion_sgc

                # ENCRYPT defaults to yes starting in ODBC Driver 18. It's good to always specify ENCRYPT=yes on the client side to avoid MITM attacks.
                cnxn = bd_connector.BdConnections.connect_to_bd(self,ip,port,bd,user,password)

                #Debug only--> #cnxn = bd_connector.BdConnections.connect_to_bd(self,'10.0.1.168','Dayco_SGC','Odoo','Dayco2022$')
                #cnxn = bd_connector.BdConnections.connect_to_bd(self,'200.74.215.68','4022','Dayco_SGC','Odoo','Dayco2022$')

                if not cnxn:
                    _logger.warning("No se pudo conectar a la base de datos, verifique los errores de conexión en el log.")
                else:
                    cursor_b = cnxn.cursor(as_dict=True)
                    _logger.warning("Actualizando desde Odoo a SGC")

                    if self.company_type_stored == 'person' and self.parent_id:
                        _logger.warning("Se va a activar un registro tipo individual.")
                        stored_proc = """ UPDATE [Contacto] SET activo = 1 WHERE id_contacto = """+str(self.id_contacto)
                    elif self.company_type_stored == 'person' and not self.parent_id and self.facturable and str(self.partner_type_id.name) == "Sharehosting":
                        _logger.warning("Se va a activar un registro tipo Individuo sin compañía.")
                        #Se crea el procedimiento almacenado que se va a ejecutar
                        stored_proc = """ UPDATE [Cliente] SET activo = 1 WHERE id_cliente = """+str(self.id_cliente)
                    else:
                        _logger.warning("Se va a activar un registro tipo compañía.")
                        #Se crea el procedimiento almacenado que se va a ejecutar
                        stored_proc = """ UPDATE [Cliente] SET activo = 1 WHERE id_cliente = """+str(self.id_cliente)

                    #Se ejecuta el stored procedure con el cursor
                    cursor_b.execute(stored_proc)

                    #Con pymssql el commit se hace directamente sobre el objeto que crea la conexión con la base de datos.
                    cnxn.commit()

                    _logger.warning("Numero de filas afectadas: "+str(cursor_b.rowcount))

                    #Si la consulta afecto al menos a una fila entonces todo OK, si no lanza la alerta
                    if not cursor_b.rowcount > 0:
                        cnxn.close()
                        raise ValidationError(_("Ninguna fila ha sido afectada, verifique con el Administrador del SGC sobre el 'archivado/desarchivado' de este registro."))

                    #Se hace falso para que al crear por sincronización no se haga un rechequeo innecesario.
                    self.revisar_id_cliente_sgc = False
                    self.revisar_id_contacto_sgc = False

                    #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.
                    if self.company_type_stored == 'person' and self.parent_id:
                        self.contacto_date_modified = datetime.now() + timedelta(minutes=1)
                        self.contacto_activo = 1
                    elif self.company_type_stored == 'person' and not self.parent_id and self.facturable:
                        self.client_date_modified = datetime.now() + timedelta(minutes=1)
                        self.cliente_activo = 1
                    else:
                        self.client_date_modified = datetime.now() + timedelta(minutes=1)
                        self.cliente_activo = 1

                    self.active = True
                    cursor_b.close()
                    cnxn.close()   
            else:
                raise ValidationError(_("""Las funcionalidades de la interfaz SGC-Odoo han sido habilitadas
                                           solo a los registros que contengan en su campo 'Categoría' los valores:
                                           1- Cliente
                                           2- Cliente/Proveedor """))
        except pymssql.Error as e:
                cursor_b.close()
                cnxn.close()

                raise ValidationError(_("""Error al desactivar este Contacto/Cliente, por favor, verifique e intente nuevamente.
                                            Registro del error: 

                                            """+str(e)+"""."""))

    #Cuando se cambie el campo de la compañia relacionada, se debe obtener el ID de la compañía y
    #asignarlo al campo correspondiente.
    @api.onchange('parent_id')
    def check_id_sgc_parent_id(self):
        _logger.warning("Reflect ID SGC company in ID SGC contact.")
        #Se debe validar que la compañía que se va a asociar tenga un ID SGC valido o en caso
        #de no tener ID Cliente SGC verificar que contenga una categoría valida para no
        #sincronizar o que se encuentre en la lista negra de Clientes (Por construir).

        if self.company_type_stored == 'person' and not (str(self.parent_id.partner_category) == '2' or str(self.parent_id.partner_category) == '4' or str(self.parent_id.partner_category) == '5'):
            if self.parent_id:
                if self.parent_id.id_cliente > 0:
                    self.id_cliente = self.parent_id.id_cliente
                else:
                    raise ValidationError(_("""Debe seleccionar una compañía con ID de Cliente SGC valido si la va a asociar a un contacto nuevo, por favor, verifique e intente nuevamente.
                                                ID SGC de la compañía seleccionada: """+str(self.parent_id.id_cliente)))
        #Nueva condición agregada por el tema de poder registrar contactos asociados a proveedores que no se
        #sincronizan con el SGC, esto se debe a que los proveedores no se sincronizan con el SGC y al mismo
        #tiempo se pueden convertir en la empresa relacionada de un contacto en Odoo.
        elif self.company_type_stored == 'person' and (str(self.parent_id.partner_category) == '2' or str(self.parent_id.partner_category) == '4' or str(self.parent_id.partner_category) == '5'):
            _logger.warning("Contacto tipo proveedor, no se sincroniza el contacto nuevo.")


    #@api.onchange('vat')
    #def reflect_vat(self):
    #    _logger.warning("Reflect del VAT en RIF Cliente.")
    #    #Se debe verificar si ya existe un rif igual ya sincronizado o creado en la data de Odoo para evitar
    #    #errores al registrar en la bse de datos del SGC.
    #    error = False
    #    
    #    if self.vat:
    #        contactos = self.env['res.partner'].search([('id_cliente', '!=', self.id_cliente),('vat', '=', self.vat)])
#
    #        _logger.warning("Registros encontrados: "+str(contactos))
#
    #        if contactos:
    #            #Reiniciamos los campos para prevenir que se registre información duplicada en la base de datos.
    #            self.rif_cliente = False
    #            self.vat = False
    #            error = True
#
    #            _logger.warning("Rif actual: "+str(self.vat))
#
    #        else:
    #            #self.revisar_id_cliente_sgc = True
    #            self.rif_cliente = self.vat
    #            self.create_from_sync = False
#
    #    if error:
    #        self.vat = "Rif ya registrado, por favor verifique."

    #Aca se establecen los campos que se deben tomar en cuenta para el proceso de edición desde Odoo a SGC
    #Una vez se edite alguno de estos campos, se actualizará la información desde Odoo a SGC.
    @api.onchange('id_cliente','vat','email','name','rif_cliente','direccion_facturacion','unidad_negocio_cliente','phone','fax_cliente','city','zip','tipo_cliente','tipo_negocio_cliente','categoria_cliente','tipo_cliente_corporativo','municipio_cliente','street2','mobile','account_management_id_sgc')
    def _activar_chequeo_por_edicion_cliente(self):
        if self.company_type_stored == 'company' and self.rif_cliente:
            _logger.warning("Se ha editado un Cliente (contacto tipo compañía) efectivamente, se procede a sincronizar por edición")
            if self.company_type_stored == "company":
                self.revisar_id_cliente_sgc = True

    def validate_rif_before_sgc(self, field_value):
        if 'creating_company' in self._context:
            # Skip vat validation when creating the company
            return True

        rif_obj = re.compile(r"^[V|E|J|G]+[-][\d]{9}", re.X)
        if field_value:
            if rif_obj.search(field_value.upper()):
                if len(field_value) == 11:
                    return True
                else:
                    return False
        else:
            return False

    @api.constrains('revisar_id_cliente_sgc')
    def _check_contact_company_data(self):
        
        #Hot fix #29: Verificación personalizada del RIF para ajustes en procesos de registros antes de
                    #que se registre data en SGC.
        
        if self.company_type_stored == 'company':
            if self.validate_rif_before_sgc(self.vat) is False:
                #En la edición se cancela el check para evitar errores de redundancia.
                #self.revisar_id_cliente_sgc = False
                raise ValidationError(_("""El rif tiene un formato incorrecto.\n\t""" 
"""Los formatos permitidos son los siguientes:\n\t"""
"""V-012345678, E-012345678, J-012345678, G-012345678\n\t"""
"""Por favor verifique el formato y si posee los 9 digitos e intente de nuevo\n\t"""))
        
        #Fix #38: Buscar y asignar "id_cliente" en caso de no encontrarse "id_cliente" en Odoo.
        if self.id_cliente > 0:
            if str(self.partner_category) == '1' or str(self.partner_category) == '2' or str(self.partner_category) == '3':

                #Solo ejecutar estas instrucciones cuando se haya editado alguno de los campos indicados arriba
                if self.revisar_id_cliente_sgc and self.company_type_stored == 'company' and not self.create_from_sync:
                    _logger.warning("########## - INICIO chequeo de la data modificada en contacto tipo Compañía - ##########")
                    _logger.warning("########## - INICIO chequeo de la data modificada en contacto tipo Compañía - ##########")

                    #Se deben agregar las validaciones necesarias para garantizar que la data que viajará al SGC sea la
                    #mas integra y autentica posible, si todo esta bien se actualiza la fecha de modificación.

                    #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.
                    #self.client_date_modified = datetime.now()

                    #try:
                    #Una vez modificada la fecha se procede a insertar la nueva data en el SGC.
                    ip = self.env.company.ip_conexion_sgc
                    port = self.env.company.puerto_conexion_sgc
                    bd = self.env.company.bd_conexion_sgc
                    user = self.env.company.user_conexion_sgc
                    password = self.env.company.pass_conexion_sgc

                    try:
                        # ENCRYPT defaults to yes starting in ODBC Driver 18. It's good to always specify ENCRYPT=yes on the client side to avoid MITM attacks.
                        cnxn = bd_connector.BdConnections.connect_to_bd(self,ip,port,bd,user,password)
                        #cnxn = bd_connector.BdConnections.connect_to_bd(self,'200.74.215.68','4022','Dayco_SGC','Odoo','Dayco2022$')

                        if not cnxn:
                            if self.revisar_id_cliente_sgc:
                                self.revisar_id_cliente_sgc = False
                            _logger.warning("No se pudo conectar a la base de datos, verifique los errores de conexión en el log.")
                        else:
                            cursor_b = cnxn.cursor(as_dict=True)
                            _logger.warning("Actualizando desde Odoo a SGC")

                            categoria_encontrada = False
                            #Para poder editar nuevamente se debe verificar la data del Cliente a envíar al SGC.
                            for category in self.category_id:
                                
                                _logger.info("Categoría: "+str(category.name))
                                if str(category.name) == "Cliente de Valor":
                                    categoria_encontrada = True
                                    self.tipo_cliente = '1'
                                    break
                                elif str(category.name) == "Cliente Alto Valor":
                                    categoria_encontrada = True
                                    self.tipo_cliente = '2'
                                    break
                                elif str(category.name) == "Prospecto":
                                    categoria_encontrada = True
                                    self.tipo_cliente = '3'
                                    break
                                elif str(category.name) == "VIP":
                                    categoria_encontrada = True
                                    self.tipo_cliente = '4'
                                    break
                                elif str(category.name) == "Base Instalada":
                                    categoria_encontrada = True
                                    self.tipo_cliente = '1'
                                    break
                                elif str(category.name) == "Aliados para el Servicio" or str(category.name) == "Aliado para el Servicio":
                                    categoria_encontrada = True
                                    self.tipo_cliente = '1'
                                    break
                            
                            #Condición valida solo para Clientes Sharehosting sin etiquetas en el campo Categorías
                            if not self.category_id and self.company_type == "company" and str(self.partner_type_id.name) == "Sharehosting":
                                _logger.warning("Cliente tipo Sharehosting detectado, se establece etiqueta para el SGC: Cliente de valor.")
                                self.tipo_cliente = '1'
                                categoria_encontrada = True

                            if not categoria_encontrada:
                                #Se debe registrar un error indicando porque no se editó el Cliente desde Odoo a SGC.
                                raise ValidationError(_("Por favor, verifique la data a envíar a SGC antes de editar este Cliente, categoría no establecida."))

                            #Se debe eliminar el '-' del rif si este lo posee.
                            characters = '-'
                            vat_cliente = self.vat
                            if self.vat:
                                for x in range(len(characters)):
                                    vat_cliente = vat_cliente.replace(characters[x],"")
                                    
                            _logger.warning("Nuevo VAT procesado: "+str(vat_cliente))
                            self.rif_cliente = vat_cliente
                            
                            #Se debe crear una validación adicional que envíe valores vacíos en vez de la palabra false cuando
                            #cree o modifique desde Odoo hacía SGC.

                            if not self.phone:
                                #Se envía vacío.
                                self.phone = ''
                            if not self.mobile:
                                #Se envía vacío.
                                self.mobile = ''
                            if not self.fax_cliente:
                                #Se envía vacío.
                                self.fax_cliente = ''
                            if not self.city:
                                #Se envía vacío.
                                self.city = ''
                            if not self.zip:
                                #Se envía vacío.
                                self.zip = ''

                            params = (int(self.id_cliente),str(self.name),self.rif_cliente,str(self.street),str(self.unidad_negocio_cliente),str(self.phone),str(self.fax_cliente),str(self.city),str(self.zip),int(self.tipo_cliente),int(self.tipo_negocio_cliente),int(self.categoria_cliente),int(self.tipo_cliente_corporativo),self.municipio_cliente,self.street,self.mobile,int(self.account_management_id_sgc))

                            sgc_sucessfully_commit = False
                            #Se ejecuta el stored procedure con el cursor
                            rows = cursor_b.callproc('ModificarCliente', params)
                            cnxn.commit()

                            for row in rows:
                                _logger.warning("Numero de filas afectadas en SGC: "+str(row))
                                sgc_sucessfully_commit = True
                                #Con solo el primer valor es suficiente :)
                                break

                            #Si la consulta afecto al menos a una fila entonces todo OK, si no lanza la alerta
                            if not sgc_sucessfully_commit and not self.create_from_sync:
                                if self.revisar_id_cliente_sgc:
                                    self.revisar_id_cliente_sgc = False
                                cnxn.close()
                                raise ValidationError(_("Ninguna fila ha sido afectada, verifique con el Administrador del SGC sobre el proceso de modificación de este registro."))

                            #Se hace falso para que al crear por sincronización no se haga un rechequeo innecesario.
                            if self.revisar_id_cliente_sgc:
                                self.revisar_id_cliente_sgc = False

                            #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.
                            self.client_date_modified = datetime.now() - timedelta(hours=4)

                            #La fecha de sincronización debe ser mayor que la fecha de modifcación del Contacto para evitar ejecutar una sincronización innecesaria.
                            #Monitorear posible diferencia en segundos entre las fechas.
                            stored_proc = """UPDATE [Cliente] SET DateSincronyzed = %s WHERE id_cliente = %s;"""
                            params = (datetime.now() - timedelta(hours=4) + timedelta(minutes=1),int(self.id_cliente))

                            cursor_b.execute(stored_proc, params)
                            cnxn.commit()

                            #Luego de ejecutar se debe cerrar para estar seguros :)
                            cursor_b.close()
                            cnxn.close()

                            self.env['sgc.odoo.history'].create({
                                'name': str(self.name),
                                'fecha_registro': datetime.now(),
                                'tipo_error': 'Sync Odoo --> SGC ('+str(self.company_type_stored)+')',
                                'registro_operacion': 'Se ha editado correctamente el registro',
                                'registro_tecnico': 'None',
                                'category': '<p style="color:orange;">Edición de Cliente existente</p>',
                            })

                    except pymssql.Error as e:

                        if self.revisar_id_cliente_sgc:
                            self.revisar_id_cliente_sgc = False
                        cursor_b.close()
                        cnxn.close()

                        _logger.warning("########## - FIN chequeo de la data modificada en contacto tipo Compañía - ##########")
                        _logger.warning("########## - FIN chequeo de la data modificada en contacto tipo Compañía - ##########")

                        raise ValidationError(_("""Error al registrar la data del nuevo Cliente, por favor, verifique e intente nuevamente.
                                                    Registro del error: 

                                                    """+str(e)+"""."""))
                    
                else:
                    if self.revisar_id_cliente_sgc:
                        self.revisar_id_cliente_sgc = False
                    _logger.warning("No se modifica la data de Clientes en el SGC.")
            else:
                if self.revisar_id_cliente_sgc:
                    self.revisar_id_cliente_sgc = False
                _logger.warning(_("""Las funcionalidades de la interfaz SGC-Odoo han sido habilitadas
                                            solo a los registros que contengan en su campo 'Categoría' los valores:
                                            1- Cliente
                                            2- Cliente/Proveedor """))
        else:
            #Verificar si existe el id_cliente en la base de datos del SGC, en caso positivo asignarlo al Cliente con el RIF asociado.
            #Se presenta el caso #2
            #Solo editar desde Odoo hacía SGC si tiene la categoría correcta
            #durante la primera sincronización.
            #Pendiente completar el caso del Cliente Proveedor con etiqueta "Aliados para el servicio".

            self.cliente_partner_category = False

            if str(self.partner_category) == "1":
                self.cliente_partner_category = "1"
            elif str(self.partner_category) == "2":
                self.cliente_partner_category = "2"
            elif str(self.partner_category) == "3":
                self.cliente_partner_category = "3"
            elif str(self.partner_category) == "4":
                self.cliente_partner_category = "4"
            elif str(self.partner_category) == "5":
                self.cliente_partner_category = "5"

            if self.cliente_partner_category == "1" or self.cliente_partner_category == "3":
                _logger.warning("Se busca el id Cliente SGC antes de editar, si lo encuentra edita el Cliente, si no, emite alerta de edición.")

                #Se debe verificar si existe un cliente en SGC con el ID Cliente asociado y el RIF del cliente de Odoo
                #Si se encuentra el cliente en la BD, se debe obtener su id_cliente, modificar en sgc y guardar
                #en Odoo con el id_cliente recien adquirido.
                #Se debe eliminar el '-' del RIF si este lo posee.
                #Solo en caso de no haberse editado el RIF, se reconfirma el campo "rif_cliente" con el campo VAT.
                self.rif_cliente = self.vat

                characters = '-'
                rif_cliente_sgc = self.rif_cliente
                if self.rif_cliente:
                    for x in range(len(characters)):
                        rif_cliente_sgc = rif_cliente_sgc.replace(characters[x],"")
                self.rif_cliente = rif_cliente_sgc

                rif_cliente_odoo = self.rif_cliente
                #_logger.warning("RIF a buscar en SGC: "+str(rif_cliente_odoo))

                ip = self.env.company.ip_conexion_sgc
                port = self.env.company.puerto_conexion_sgc
                bd = self.env.company.bd_conexion_sgc
                user = self.env.company.user_conexion_sgc
                password = self.env.company.pass_conexion_sgc
                
                try:
                    # ENCRYPT defaults to yes starting in ODBC Driver 18. It's good to always specify ENCRYPT=yes on the client side to avoid MITM attacks.
                    cnxn = bd_connector.BdConnections.connect_to_bd(self,ip,port,bd,user,password)
                    #cnxn = bd_connector.BdConnections.connect_to_bd(self,'200.74.215.68','4022','Dayco_SGC','Odoo','Dayco2022$')

                    if not cnxn:
                        _logger.warning("No se pudo conectar a la base de datos, verifique los errores de conexión en el log.")
                        if self.revisar_id_contacto_sgc:
                            self.revisar_id_contacto_sgc = False
                    else:
                        cursor_b = cnxn.cursor(as_dict=True)
                        _logger.warning("Actualizando desde Odoo a SGC")
                        
                        #Select a la bd buscando el posible contacto relacionado
                        #En caso de encontrarlo, procede_creacion_nueva = False
                        #Si no lo encuentra, procede_creacion_nueva = True

                        _logger.warning("RIF a buscar en SGC: "+str(rif_cliente_odoo))

                        stored_proc = """SELECT id_cliente FROM [Cliente] WHERE rif = %s;"""
                        params = (rif_cliente_odoo)

                        cursor_b.execute(stored_proc, params)
                        var_a = cursor_b.fetchall()
                        cnxn.commit()
                        
                        if var_a:
                            #Si se detectó registro existente en el SGC se debe actualizar
                            _logger.warning("Var_a: "+str(var_a[0].get("id_cliente")))

                            #Se obtiene el id cliente encontrado en la bd
                            self.id_cliente = var_a[0].get("id_cliente")

                            categoria_encontrada = False
                            #Para poder editar nuevamente se debe verificar la data del Cliente a envíar al SGC.
                            for category in self.category_id:
                                
                                _logger.info("Categoría: "+str(category.name))
                                if str(category.name) == "Cliente de Valor":
                                    categoria_encontrada = True
                                    self.tipo_cliente = '1'
                                    break
                                elif str(category.name) == "Cliente Alto Valor":
                                    categoria_encontrada = True
                                    self.tipo_cliente = '2'
                                    break
                                elif str(category.name) == "Prospecto":
                                    categoria_encontrada = True
                                    self.tipo_cliente = '3'
                                    break
                                elif str(category.name) == "VIP":
                                    categoria_encontrada = True
                                    self.tipo_cliente = '4'
                                    break
                                elif str(category.name) == "Base Instalada":
                                    categoria_encontrada = True
                                    self.tipo_cliente = '1'
                                    break
                                elif str(category.name) == "Aliados para el Servicio" or str(category.name) == "Aliado para el Servicio":
                                    categoria_encontrada = True
                                    self.tipo_cliente = '1'
                                    break
                            
                            #Condición valida solo para Clientes Sharehosting sin etiquetas en el campo Categorías
                            if not self.category_id and self.company_type == "company" and str(self.partner_type_id.name) == "Sharehosting":
                                _logger.warning("Cliente tipo Sharehosting detectado, se establece etiqueta para el SGC: Cliente de valor.")
                                self.tipo_cliente = '1'
                                categoria_encontrada = True

                            if not categoria_encontrada:
                                #Se debe registrar un error indicando porque no se editó el Cliente desde Odoo a SGC.
                                raise ValidationError(_("Por favor, verifique la data a envíar a SGC antes de editar este Cliente, categoría no establecida."))

                            self.unidad_negocio_cliente = False

                            if str(self.partner_type_id.name) == "Corporativo":
                                self.unidad_negocio_cliente = "2"
                            elif str(self.partner_type_id.name) == "Sharehosting":
                                self.unidad_negocio_cliente = "1"

                            #Se debe eliminar el '-' del RIF si este lo posee.
                            characters = '-'
                            rif_cliente_sgc = self.rif_cliente
                            if self.rif_cliente:
                                for x in range(len(characters)):
                                    rif_cliente_sgc = rif_cliente_sgc.replace(characters[x],"")
                            self.rif_cliente = rif_cliente_sgc

                            #Se debe validar que campo cambió realmente antes de enviar la data
                            #para mejorar la eficiencia del proceso de edición.
                            _logger.warning("RIF a buscar: "+str(rif_cliente_sgc))
                            _logger.warning("ID Cliente a buscar: "+str(self.id_cliente))
                            
                            _logger.warning("Data a comparar: "+str(var_a))

                            #Si el nombre y apellido en el SGC se encuentran en el nombre de Odoo no se modifica
                            #el nombre ni el apellido en SGC.
                            for item_sgc in var_a:
                            #Se debe crear una validación adicional que envíe valores vacíos en vez de la palabra false cuando
                            #cree o modifique desde Odoo hacía SGC.
                                _logger.warning("Actualizando desde Odoo a SGC")

                                #Se debe eliminar el '-' del rif si este lo posee.
                                characters = '-'
                                vat_cliente = self.vat
                                if self.vat:
                                    for x in range(len(characters)):
                                        vat_cliente = vat_cliente.replace(characters[x],"")
                                self.rif_cliente = vat_cliente
                                
                                #Se debe crear una validación adicional que envíe valores vacíos en vez de la palabra false cuando
                                #cree o modifique desde Odoo hacía SGC.

                                if not self.phone:
                                    #Se envía vacío.
                                    self.phone = ''
                                if not self.mobile:
                                    #Se envía vacío.
                                    self.mobile = ''
                                if not self.fax_cliente:
                                    #Se envía vacío.
                                    self.fax_cliente = ''
                                if not self.city:
                                    #Se envía vacío.
                                    self.city = ''
                                if not self.zip:
                                    #Se envía vacío.
                                    self.zip = ''

                                params = (int(self.id_cliente),str(self.name),self.rif_cliente,str(self.street),str(self.unidad_negocio_cliente),str(self.phone),str(self.fax_cliente),str(self.city),str(self.zip),int(self.tipo_cliente),int(self.tipo_negocio_cliente),int(self.categoria_cliente),int(self.tipo_cliente_corporativo),self.municipio_cliente,self.street,self.mobile,int(self.account_management_id_sgc))

                                sgc_sucessfully_commit = False
                                #Se ejecuta el stored procedure con el cursor
                                rows = cursor_b.callproc('ModificarCliente', params)
                                cnxn.commit()

                                for row in rows:
                                    _logger.warning("Numero de filas afectadas en SGC: "+str(row))
                                    sgc_sucessfully_commit = True
                                    #Con solo el primer valor es suficiente :)
                                    break

                                #Si la consulta afecto al menos a una fila entonces todo OK, si no lanza la alerta
                                if not sgc_sucessfully_commit and not self.create_from_sync:
                                    if self.revisar_id_cliente_sgc:
                                        self.revisar_id_cliente_sgc = False
                                    cnxn.close()
                                    raise ValidationError(_("Ninguna fila ha sido afectada, verifique con el Administrador del SGC sobre el proceso de modificación de este registro."))

                                #Se hace falso para que al crear por sincronización no se haga un rechequeo innecesario.
                                #self.revisar_id_cliente_sgc = False
                                if self.revisar_id_cliente_sgc:
                                    self.revisar_id_cliente_sgc = False

                                #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.
                                self.client_date_modified = datetime.now() + timedelta(minutes=1) - timedelta(hours=4)

                                cursor_b.close()
                                cnxn.close()

                                self.env['sgc.odoo.history'].create({
                                    'name': str(self.name),
                                    'fecha_registro': datetime.now(),
                                    'tipo_error': 'Sync SGC --> Odoo ('+str(self.company_type_stored)+')',
                                    'registro_operacion': 'Se ha editado correctamente el registro',
                                    'registro_tecnico': 'None',
                                    'category': '<p style="color:orange;">Edición de Cliente '+str(self.tipo_cliente_corporativo)+' existente.</p>',
                                })
                        else:
                            _logger.warning("Se considerar la posibilidad de crear el Cliente en SGC si cumple con algunos parámetros.")
                            #Se verifican los campos del contacto (Individual) antes de insertar.
                            procede_registro_por_edicion = True

                            #Condición valida solo para Clientes Sharehosting sin etiquetas en el campo Categorías
                            if not self.category_id and self.company_type == "company" and str(self.partner_type_id.name) == "Sharehosting":
                                _logger.warning("Cliente tipo Sharehosting detectado, se establece etiqueta para el SGC: Cliente de valor.")
                                self.tipo_cliente = '1'
                                categoria_encontrada = True

                            if self.direccion_facturacion:
                                _logger.warning("Se ha establecido una dirección de facturación")

                                if self.street:
                                    _logger.warning("Se ha establecido una dirección secundaria")

                                    if self.vat:
                                        _logger.warning("Se ha establecido un RIF correctamente")

                                        if self.phone or self.mobile:
                                            _logger.warning("Se ha establecido un telefono principal")

                                            if self.partner_type_id:
                                                _logger.warning("Se ha establecido una categoría de Cliente valida.")

                                                if self.fax_cliente:
                                                    _logger.warning("Se ha establecido un fax del Cliente")

                                                    if self.city:
                                                        _logger.warning("Se ha establecido una ciudad")

                                                        #Descartado por no ser necesario en todos los casos existentes.
                                                        #if vals.get("zip"):
                                                        #    _logger.warning("Se ha establecido un código postal")

                                                        if self.tipo_negocio_cliente:
                                                            _logger.warning("Se ha establecido un tipo de negocio de cliente")

                                                            if self.categoria_cliente:
                                                                _logger.warning("Se ha establecido una categoría de Cliente")

                                                                if self.tipo_cliente:
                                                                    _logger.warning("Se ha establecido un tipo de Cliente")

                                                                    if self.unidad_negocio_cliente:
                                                                        _logger.warning("Se ha establecido una unidad de negocio de Cliente")

                                                                        if self.tipo_cliente_corporativo:
                                                                            _logger.warning("Se ha establecido un tipo de Cliente corporativo")

                                                                            if self.municipio_cliente:
                                                                                _logger.warning("Se ha establecido un municipio")

                                                                                if self.cliente_activo:
                                                                                    _logger.warning("Se ha activado al cliente")
                                                                                    
                                                                                    #if vals.get("account_management_id_sgc"):
                                                                                    #    _logger.warning("Se ha establecido un accountmanagementid")

                                                                                    #Se procede una vez pasadas todas las validaciones necesarias
                                                                                    #a registrar al cliente nuevo.

                                                                                    #Una vez se cumplen todas las verificaciones se procede con el envío
                                                                                    #de datos hacía el SGC.

                                                                                    #Una vez modificada la fecha se procede a insertar la nueva data en el SGC.
                                                                                    ip = self.env.company.ip_conexion_sgc
                                                                                    port = self.env.company.puerto_conexion_sgc
                                                                                    bd = self.env.company.bd_conexion_sgc
                                                                                    user = self.env.company.user_conexion_sgc
                                                                                    password = self.env.company.pass_conexion_sgc

                                                                                    try:
                                                                                        # ENCRYPT defaults to yes starting in ODBC Driver 18. It's good to always specify ENCRYPT=yes on the client side to avoid MITM attacks.
                                                                                        cnxn = bd_connector.BdConnections.connect_to_bd(self,ip,port,bd,user,password)
                                                                                        #cnxn = bd_connector.BdConnections.connect_to_bd(self,'200.74.215.68','4022','Dayco_SGC','Odoo','Dayco2022$')
                                                                                        #--> Solo debug, sin clave ni puerto definido: bd_connector.BdConnections.connect_to_bd(None,'10.0.1.168','Dayco_SGC','Odoo','Dayco2022$')

                                                                                        #Se debe establecer el parámetro SET NOCOUNT ON para que funcione correctamente
                                                                                        #https://stackoverflow.com/questions/7753830/mssql2008-pyodbc-previous-sql-was-not-a-query

                                                                                        cursor_b = cnxn.cursor(as_dict=True)
                                                                                        _logger.warning("Registrando desde Odoo a SGC")
                                                                                                                                    
                                                                                        stored_proc = """ SET NOCOUNT ON exec [dbo].[AgregarCliente]
                                                                                                                                    @nombre = %s,
                                                                                                                                    @rif = %s,
                                                                                                                                    @direccion = %s,
                                                                                                                                    @unidadNegocios = %s,
                                                                                                                                    @telefono = %s,
                                                                                                                                    @fax = %s,
                                                                                                                                    @ciudad = %s,
                                                                                                                                    @codigoPostal = %s,
                                                                                                                                    @tipoCliente = %s,
                                                                                                                                    @idClienteCorp = %s,
                                                                                                                                    @idTipoNegocio = %s,
                                                                                                                                    @idCategoria = %s,
                                                                                                                                    @idMunicipio = %s,
                                                                                                                                    @direccion2 = %s,
                                                                                                                                    @telefono2 = %s,
                                                                                                                                    @AccountManagementId = %s"""

                                                                                        #Se debe eliminar el '-' del rif si este lo posee.
                                                                                        characters = '-'
                                                                                        if self.rif_cliente:
                                                                                            for x in range(len(characters)):
                                                                                                self.rif_cliente =self.rif_cliente.replace(characters[x],"")
                                                                                        
                                                                                        if self.cedula_contacto:
                                                                                            for x in range(len(characters)):
                                                                                                self.cedula_contacto = self.cedula_contacto.replace(characters[x],"")

                                                                                        #Se debe convertir el tipo de cliente a un entero aceptable para el SGC
                                                                                        if self.tipo_contacto == 1:
                                                                                            _logger.warning("Cambiar por el status correcto en SGC")

                                                                                        _logger.warning("Gerente de cuenta: "+str(int(self.account_management_id_sgc)))
                                                                                        
                                                                                        #Se debe crear una validación adicional que envíe valores vacíos en vez de la palabra false cuando
                                                                                        #cree o modifique desde Odoo hacía SGC.

                                                                                        if not self.phone:
                                                                                            #Se envía vacío.
                                                                                            self.phone = ''
                                                                                        if not self.mobile:
                                                                                            #Se envía vacío.
                                                                                            self.mobile = ''
                                                                                        if not self.fax_cliente:
                                                                                            #Se envía vacío.
                                                                                            self.fax_cliente = ''
                                                                                        if not self.city:
                                                                                            #Se envía vacío.
                                                                                            self.city = ''
                                                                                        if not self.zip:
                                                                                            #Se envía vacío.
                                                                                            self.zip = ''

                                                                                        params = ''
                                                                                        #Si retorna cero es porque se le pasó una cadena vacía o un cero en efecto, si no entonces si pasas el número.
                                                                                        if int(self.account_management_id_sgc) > 0:
                                                                                            params = (str(self.name),str(self.rif_cliente),str(self.street),int(self.unidad_negocio_cliente),str(self.phone),str(self.fax_cliente),self.city,str(self.zip),int(self.tipo_cliente),int(self.tipo_cliente_corporativo),int(self.tipo_negocio_cliente),int(self.categoria_cliente),int(self.municipio_cliente),self.direccion_facturacion,self.mobile,int(self.account_management_id_sgc))
                                                                                        else:
                                                                                            _logger.warning("Se envía NULL")
                                                                                            params = (str(self.name),str(self.rif_cliente),str(self.street),int(self.unidad_negocio_cliente),str(self.phone),str(self.fax_cliente),self.city,str(self.zip),int(self.tipo_cliente),int(self.tipo_cliente_corporativo),int(self.tipo_negocio_cliente),int(self.categoria_cliente),int(self.municipio_cliente),self.direccion_facturacion,self.mobile,None)
                                                                                
                                                                                        #Se ejecuta el stored procedure con el cursor
                                                                                        cursor_b.execute(stored_proc, params)
                                                                                        var_a = cursor_b.fetchone()
                                                                                        cnxn.commit()

                                                                                        _logger.warning("Var_a: "+str(var_a))
                                                                                        
                                                                                        #Si se creó correctamente el registro en la BD se procede a salvar el Cliente en Odoo
                                                                                        if not var_a.get("ReturnId") > 0:
                                                                                            cnxn.close()
                                                                                            raise ValidationError(_("Ninguna fila ha sido afectada/insertada, verifique con el Administrador del SGC sobre el proceso de modificación/creación de registros."))
                                                                                        else:
                                                                                            _logger.warning("Contacto (Compañía) registrado con exito!")
                                                                                            
                                                                                            #Fix tipo de contacto en caso de registrarse un Cliente
                                                                                            self.tipo_contacto = str(1)

                                                                                            #La fecha de sincronización debe ser mayor que la fecha de modifcación del Contacto para evitar ejecutar una sincronización innecesaria.
                                                                                            #Monitorear posible diferencia en segundos entre las fechas.
                                                                                            stored_proc = """UPDATE [Cliente] SET DateSincronyzed = %s WHERE id_cliente = %s;"""
                                                                                            params = (datetime.now() - timedelta(hours=4),int(var_a.get("ReturnId")))

                                                                                            cursor_b.execute(stored_proc, params)
                                                                                            cnxn.commit()

                                                                                            #Se hace falso para que al crear por sincronización no se haga un rechequeo innecesario.
                                                                                            self.revisar_id_cliente_sgc = False

                                                                                            #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.
                                                                                            self.client_date_modified = datetime.now() + timedelta(minutes=1)

                                                                                            #Una vez creado el contacto, procedemos a establecer el id que retorna el SGC.
                                                                                            self.id_cliente = var_a.get("ReturnId")

                                                                                            #Solo debe proceder la creación del contacto si se cumplen las condiciones en Odoo,
                                                                                            #y al mismo tiempo se cumple el registro en la BD del SGC.
                                                                                            #procede = True
                                                                                            cursor_b.close()
                                                                                            cnxn.close()

                                                                                            self.env['sgc.odoo.history'].create({
                                                                                                        'name': str(self.name),
                                                                                                        'fecha_registro': datetime.now(),
                                                                                                        'tipo_error': 'Sync Odoo --> SGC ('+str(self.company_type_stored)+')',
                                                                                                        'registro_operacion': 'Se ha creado correctamente el registro.',
                                                                                                        'registro_tecnico': 'None',
                                                                                                        'category': '<p style="color:green;">Creación de Cliente tipo compañía</p>',
                                                                                                    })

                                                                                        #else:
                                                                                        #    _logger.warning("No se ha establecido un accountmanagementid")
                                                                                    except pymssql.Error as e:
                                                                                        cursor_b.close()
                                                                                        cnxn.close()

                                                                                        raise ValidationError(_("""Error al registrar la data del nuevo Cliente, por favor, verifique e intente nuevamente.
                                                                                                                    Registro del error: 

                                                                                                                    """+str(e)+"""."""))

                                                                                else:
                                                                                    _logger.warning("No se ha activado al cliente")
                                                                                    procede_registro_por_edicion = False
                                                                            else:
                                                                                _logger.warning("No se ha establecido un municipio")
                                                                                procede_registro_por_edicion = False
                                                                        else:
                                                                            _logger.warning("No se ha establecido un tipo de Cliente corporativo")
                                                                            procede_registro_por_edicion = False
                                                                    else:
                                                                        _logger.warning("No se ha establecido una unidad de negocio de Cliente")
                                                                        procede_registro_por_edicion = False
                                                                else:
                                                                    _logger.warning("No se ha establecido un tipo de Cliente")
                                                                    procede_registro_por_edicion = False
                                                            else:
                                                                _logger.warning("No se ha establecido una categoría de Cliente")
                                                                procede_registro_por_edicion = False
                                                        else:
                                                            _logger.warning("No se ha establecido un tipo de negocio de cliente")
                                                            procede_registro_por_edicion = False
                                                        #else:
                                                        #    _logger.warning("No se ha establecido un código postal")
                                                    else:
                                                        _logger.warning("No se ha establecido una ciudad")
                                                        procede_registro_por_edicion = False
                                                else:
                                                    _logger.warning("No se ha establecido un fax del Cliente")
                                                    procede_registro_por_edicion = False
                                            else:
                                                _logger.warning("No se ha establecido una categoría de Cliente valida.")
                                                procede_registro_por_edicion = False
                                        else:
                                            _logger.warning("No se ha establecido un teléfono principal ni uno secundario correctamente")
                                            procede_registro_por_edicion = False
                                    else:
                                        _logger.warning("No se ha establecido un RIF correctamente")
                                        procede_registro_por_edicion = False
                                else:
                                    _logger.warning("No se ha establecido una dirección secundaria")
                                    procede_registro_por_edicion = False
                            else:
                                _logger.warning("No se ha establecido una dirección de facturación")
                                procede_registro_por_edicion = False

                            #Si no se cumple algunas de las condiciones se registra error al momento de crear.
                            if not procede_registro_por_edicion:
                                self.env['sgc.odoo.history'].create({
                                    'name': str(self.name),
                                    'fecha_registro': datetime.now(),
                                    'tipo_error': 'Sync Odoo --> SGC ('+str(self.company_type_stored)+')',
                                    'registro_operacion': 'Se ha encontrado un registro en SGC relacionado con el registro que se está intentado editar en Odoo, Nombre: '+str(self.name)+', ID_Cliente: '+str(self.id_cliente)+', RIF '+str(self.rif_cliente)+', sin embargo, no cumple con los requerimientos del SGC para poder ser registrados, por favor verifique e intente nuevamente.',
                                    'registro_tecnico': 'None',
                                    'category': '<p style="color:red;">Error</p>',
                                })

                except pymssql.Error as e:

                    if self.revisar_id_cliente_sgc:
                        self.revisar_id_cliente_sgc = False
                    cursor_b.close()
                    cnxn.close()

                    _logger.warning("########## - FIN chequeo de la data modificada en cliente - ##########")
                    _logger.warning("########## - FIN chequeo de la data modificada en cliente - ##########")
            
                    raise ValidationError(_("""Error al editar la data del nuevo Contacto, por favor, verifique e intente nuevamente.
                                                Registro del error: 

                                                """+str(e)+"""."""))
            else:
                _logger.warning("No se sincroniza con el SGC por tener la categoría: "+str(self.partner_category))

        #Validación adicional por si no se cumple alguna de las condiciones anteriores.
        if self.revisar_id_cliente_sgc:
            self.revisar_id_cliente_sgc = False
        _logger.warning("No se edita el Cliente porque aun no se ha sincronizado con el SGC, verifique porque no se ha sincronizado e intente nuevamente.")

    @api.onchange('function')
    def reflect_function(self):
        _logger.warning("Reflect del cargo en el SGC.")
        #self.revisar_id_contacto_sgc = True
        self.cargo_contacto = self.function
        self.create_from_sync = False
        _logger.warning("Creado por sincronización: "+str(self.create_from_sync))

    @api.onchange('rol')
    def reflect_x_studio_rol(self):
        _logger.warning("Reflect del tipo de cliente SGC")
        #self.revisar_id_contacto_sgc = True
        self.tipo_contacto = False

        if str(self.rol.display_name) == "Ejecutivo":
            self.tipo_contacto = "3"
        elif str(self.rol.display_name) == "Administrativo":
            self.tipo_contacto = "2"
        elif str(self.rol.display_name) == "Dayco":
            self.tipo_contacto = "1"
        elif str(self.rol.display_name) == "Técnico":
            self.tipo_contacto = "1"
        else:
            self.tipo_contacto = "1"

        #elif str(self.rol.display_name) == "Contacto comercial":
        #    self.tipo_contacto = "1"
        #elif str(self.rol.display_name) == "Técnico":
        #    self.tipo_contacto = "1"

        self.create_from_sync = False
        _logger.warning("Creado por sincronización: "+str(self.create_from_sync))

    @api.onchange('city')
    def reflect_city_contacto(self):
        _logger.warning("Reflect de la ciudad en el SGC.")
        #self.revisar_id_contacto_sgc = True
        self.ciudad_contacto = self.city
        self.create_from_sync = False
        _logger.warning("Creado por sincronización: "+str(self.create_from_sync))

    @api.onchange('identification_id')
    def reflect_identification_id(self):
        _logger.warning("Reflect de cedula en cedula_contacto contacto SGC.")
        #self.revisar_id_contacto_sgc = True
        if self.nationality and self.identification_id:
            self.cedula_contacto = self.nationality+self.identification_id
        self.create_from_sync = False
        _logger.warning("Creado por sincronización: "+str(self.create_from_sync))

    #Aca se establecen los campos que se deben tomar en cuenta para el proceso de edición desde Odoo a SGC
    #Una vez se edite alguno de estos campos, se actualizará la información desde Odoo a SGC.
    @api.onchange('id_contacto','email','phone','mobile','name','apellido_contacto','identification_id','cedula_contacto','cargo_contacto','ciudad_contacto','prioridad_contacto','habilitado_contacto','tipo_contacto','contacto_activo','ScalabilityLevel','privilegio_ids')
    def _activar_chequeo_por_edicion_contacto(self):
        if self.company_type_stored == 'person': #and self.cedula_contacto:
            _logger.warning("Se ha editado un Contacto (contacto tipo individual) efectivamente, se procede a sincronizar por edición")
            if self.company_type_stored == "person":
                self.revisar_id_contacto_sgc = True

            _logger.warning("Revisar Contacto desde Odoo a SGC: "+str(self.revisar_id_contacto_sgc))

    @api.constrains('revisar_id_contacto_sgc')
    def _check_contact_individual_data(self):
        
        _logger.warning(self.revisar_id_contacto_sgc)
        _logger.warning(self.company_type_stored)
        #_logger.warning(self.create_from_sync)
        #_logger.warning(self.parent_id)
        #_logger.warning(self.facturable)
        #_logger.warning(self.partner_type_id)
        
        #if self.parent_id:
        #    _logger.warning("Encontro parent id fantasma")
        #elif not self.parent_id:
        #    _logger.warning("No encontro parent id fantasma")

        #Solo ejecutar estas instrucciones cuando se haya editado alguno de los campos indicados arriba
        #Se cosideran dos casos:
        #1- Se edita un contacto tipo Individual con compañía establecida
        #2- Se edita un contacto tipo Individual sin compañía establecida
        #3- Fix self.revisar_id_contacto_sgc = False en cada nivel de verificación para evitar fallo de sincronización al editar.
        #4- Fix #2, se agrega verificación por id_cliente o id_contacto según el caso para asegurar que solo se actualicen los
        #contactos o clientes que ya se encuentren debidamente sincronizados.
        #5- Fix #3, se debe establecer en False la variable de control "revivar_id_x_sgc" solo cuando este en true, para evitar
        #errores de recursión maxima o bucles infinitos.

        #Dichos fixs se generan por la necesidad de actualizar desde Odoo contactos que ya existían antes de instalar la interfaz
        #en la instancia, por lo que deben establecerse los campos necesarios antes de verificar y editar desde Odoo
        #hacia SGC.

        #Fix cédula contacto
        if self.nationality and self.identification_id:
            self.cedula_contacto = self.nationality+self.identification_id
        #Fix tipo contacto
        if self.rol:
            #self.tipo_contacto = str(self.rol.id)
            if str(self.rol.display_name) == "Ejecutivo":
                self.tipo_contacto = "3"
            elif str(self.rol.display_name) == "Administrativo":
                self.tipo_contacto = "2"
            elif str(self.rol.display_name) == "Dayco":
                self.tipo_contacto = "1"
            elif str(self.rol.display_name) == "Contacto comercial":
                self.tipo_contacto = "1"
            elif str(self.rol.display_name) == "Técnico":
                self.tipo_contacto = "1"
        #Fix cargo contacto
        self.cargo_contacto = str(self.function)
        #Fix cliente partner category
        if self.parent_id:
            _logger.warning("Se actualiza la categoría del contacto asociado al Cliente sincronizado al SGC.")
            self.partner_category = str(self.parent_id.partner_category)
            self.cliente_partner_category = str(self.partner_category)

        #Fix #12: Actualización de ID Contacto previo a la edición de datos desde Odoo a SGC.
        #Solo valido para contactos individuales relacionados con empresas, no se considera por el
        #momento el Cliente Sharehosting que no se haya sincronizado.
        if self.id_cliente and self.cedula_contacto and not self.id_contacto:
            #Se presenta el caso #2
            _logger.warning("Se busca el id contacto SGC antes de editar, si lo encuentra edita el contacto, si no, emite alerta de edición.")

            #Se debe verificar si existe un contacto en SGC con el ID Cliente asociado y la cedula del contacto
            #Si se encuentra el contacto en la BD, se debe obtener su id contacto, modificar en sgc y guardar
            #en Odoo con el ID Contacto recien adquirido.
            cedula_contacto = self.cedula_contacto
            
            ip = self.env.company.ip_conexion_sgc
            port = self.env.company.puerto_conexion_sgc
            bd = self.env.company.bd_conexion_sgc
            user = self.env.company.user_conexion_sgc
            password = self.env.company.pass_conexion_sgc
            
            try:
                # ENCRYPT defaults to yes starting in ODBC Driver 18. It's good to always specify ENCRYPT=yes on the client side to avoid MITM attacks.
                cnxn = bd_connector.BdConnections.connect_to_bd(self,ip,port,bd,user,password)
                #cnxn = bd_connector.BdConnections.connect_to_bd(self,'200.74.215.68','4022','Dayco_SGC','Odoo','Dayco2022$')

                if not cnxn:
                    _logger.warning("No se pudo conectar a la base de datos, verifique los errores de conexión en el log.")
                    if self.revisar_id_contacto_sgc:
                        self.revisar_id_contacto_sgc = False
                else:
                    cursor_b = cnxn.cursor(as_dict=True)
                    _logger.warning("Actualizando desde Odoo a SGC")
                    
                    #Select a la bd buscando el posible contacto relacionado
                    #En caso de encontrarlo, procede_creacion_nueva = False
                    #Si no lo encuentra, procede_creacion_nueva = True

                    _logger.warning("Cédula a buscar: "+str(cedula_contacto))
                    _logger.warning("ID Cliente a buscar: "+str(self.id_cliente))

                    stored_proc = """SELECT id_contacto, nombre, apellido FROM [Contacto] WHERE fk_id_cliente = %s and cedula = %s;"""
                    params = (int(self.id_cliente),cedula_contacto)

                    cursor_b.execute(stored_proc, params)
                    var_a = cursor_b.fetchall()
                    cnxn.commit()
                    
                    if var_a:
                        #Si se detectó registro existente en el SGC se debe actualizar
                        _logger.warning("Var_a: "+str(var_a[0].get("id_contacto")))

                        #Se obtiene el id contacto encontrado en la bd
                        self.id_contacto = var_a[0].get("id_contacto")

                        #Fix del tipo de contacto por importación
                        #Fix del campo 'Tipo contacto'
                        #vals['tipo_contacto'] = str(vals.get('rol'))

                        #Se debe eliminar el '-' de la cédula si este lo posee.
                        characters = '-'
                        cedula_contacto = self.cedula_contacto
                        if self.cedula_contacto:
                            for x in range(len(characters)):
                                cedula_contacto = cedula_contacto.replace(characters[x],"")
                        self.cedula_contacto = cedula_contacto

                        #Se debe validar que campo cambió realmente antes de enviar la data
                        #para mejorar la eficiencia del proceso de edición.
                        _logger.warning("Cédula a buscar: "+str(cedula_contacto))
                        _logger.warning("ID Cliente a buscar: "+str(self.id_cliente))
                        
                        name_odoo_temp = self.name
                        name_a = False
                        name_b = False
                        ape_a = False
                        ape_b = False

                        _logger.warning("Verificar la data del Contacto a editar desde Odoo a SGC")
                        _logger.warning("Data a comparar: "+str(var_a))
                        procede_edicion_sgc = False

                        #Si el nombre y apellido en el SGC se encuentran en el nombre de Odoo no se modifica
                        #el nombre ni el apellido en SGC.
                        for item_sgc in var_a:
                            nombres_sgc = item_sgc.get('nombre').split(" ")
                            apellidos_sgc = item_sgc.get('apellido').split(" ")

                            _logger.warning("Nombres SGC A: "+str(nombres_sgc))
                            _logger.warning("Apellidos SGC A: "+str(apellidos_sgc))
                            _logger.warning("Nombre Odoo: "+str(self.name))
                            name_aa, name_bb, ape_aa, ape_bb = check_sgc_data.chequeos.MaestroChequeos.SplitNombres(self.name,"1")

                            for item in nombres_sgc:
                                #Verificar si existen los nombres en Odoo exactamente iguales.
                                if item:
                                    #Verificar si existen los nombres en Odoo exactamente iguales.
                                    if not str(name_aa).find(str(item)) == -1 or not str(name_bb).find(str(item)) == -1:
                                        _logger.warning("Nombre: "+str(item)+" encontrado en SGC!")
                                    else:
                                        #Se procede con la nueva edición del nombre desde Odoo hacia SGC.
                                        procede_edicion_sgc = True
                                else:
                                    #Se procede con la nueva edición del nombre desde Odoo hacia SGC.
                                    procede_edicion_sgc = True
                            
                            #Solo si pasó la verificación de los nombres es que verifica los apellidos.
                            if not procede_edicion_sgc:
                                for item in apellidos_sgc:
                                    #Verificar si existen los nombres en Odoo exactamente iguales.
                                    if item:
                                        #Verificar si existen los nombres en Odoo exactamente iguales.
                                        if not str(ape_aa).find(str(item)) == -1 or not str(ape_bb).find(str(item)) == -1:
                                            _logger.warning("Apellido: "+str(item)+" encontrado en SGC!")
                                        else:
                                            #Se procede con la nueva edición del nombre desde Odoo hacia SGC.
                                            procede_edicion_sgc = True
                                    else:
                                        #Se procede con la nueva edición del nombre desde Odoo hacia SGC.
                                        procede_edicion_sgc = True

                        if not procede_edicion_sgc:
                            #De forma temporal se envía nombre y apellido segmentados a SGC
                            #y luego se recupera su forma original antes de ser escritos en Odoo.
                            self.name = item_sgc['nombre']
                            self.apellido_contacto = item_sgc['apellido']
                            
                        else:
                            _logger.warning("Procede la edición del nombre desde Odoo hacia SGC.")
                            name_a, name_b, ape_a, ape_b = check_sgc_data.chequeos.MaestroChequeos.SplitNombres(self.name,"1")

                            self.name = name_a + " " + name_b
                            self.apellido_contacto = ape_a + " " + ape_b

                        #Se debe crear una validación adicional que envíe valores vacíos en vez de la palabra false cuando
                        #cree o modifique desde Odoo hacía SGC.

                        if not self.cedula_contacto:
                            #Se envía vacío.
                            self.cedula_contacto = ''
                        if not self.phone:
                            #Se envía vacío.
                            self.phone = ''
                        if not self.mobile:
                            #Se envía vacío.
                            self.mobile = ''
                        if not self.email:
                            #Se envía vacío.
                            self.email = ''
                        if not self.function:
                            #Se envía vacío.
                            self.function = ''

                        params = (self.id_contacto,str(self.name),str(self.apellido_contacto),str(self.cedula_contacto),str(self.phone),str(self.email),str(self.cargo_contacto),self.id_cliente,int(self.tipo_contacto),self.mobile,self.prioridad_contacto,int(self.ScalabilityLevel))

                        sgc_sucessfully_commit = False

                        #Se ejecuta el stored procedure con el cursor
                        rows = cursor_b.callproc('ModificarContacto', params)
                        cnxn.commit()

                        #Fix #11, Apellido del contacto repetido (Descartado por verificación de edición por campo)
                        if name_a and ape_a:
                            self.name = name_a + " " + name_b + " " + ape_a + " " + ape_b
                            self.apellido_contacto = ape_a + " " + ape_b

                        for row in rows:
                            _logger.warning("Numero de filas afectadas: "+str(row))
                            sgc_sucessfully_commit = True
                            #Con solo el primer valor es suficiente :)
                            break

                        #Si la consulta afecto al menos a una fila entonces todo OK, si no lanza la alerta
                        if not sgc_sucessfully_commit and not self.create_from_sync:
                            if self.revisar_id_contacto_sgc:
                                self.revisar_id_contacto_sgc = False
                            cnxn.close()
                            raise ValidationError(_("Ninguna fila ha sido afectada, verifique con el Administrador del SGC sobre el proceso de modificación de este registro."))

                        #Se hace falso para que al crear por sincronización no se haga un rechequeo innecesario.
                        if self.revisar_id_contacto_sgc:
                            self.revisar_id_contacto_sgc = False

                        #Si la edición resultó exitosa entonces se procede a recuperar el nombre original antes de guardar el contacto nuevo.
                        self.name = name_odoo_temp

                        #Al editarse un contacto se debe reestablecer la data de los privilegios para garantizar que se mnatienen
                        #siempre lo mas actualizado posible.
                        #Se deben registrar tantos privilegios como se hayan establecido al momento de crear.
                        stored_proc = """DELETE FROM Privilegio_Contacto WHERE fk_id_contacto = %s"""
                
                        params = (int(self.id_contacto))

                        cursor_b.execute(stored_proc, params)
                        #Se confirma la transacción desde Odoo hacia SGC.
                        cnxn.commit()
                        #cnxn.close()
                        
                        #Luego de eliminarse se vuelven a registrar en la tabla de privilegios.
                        if self.privilegio_ids:

                            for privilegio in self.privilegio_ids:
                                _logger.warning("Privilegio: "+str(privilegio[2]))  
                                
                                #Se debe verificar qie el privilegio sea el correcto
                                #antes de permitir registrarlo en la tabla de privilegios.

                                #Se deben registrar tantos privilegios como se hayan establecido al momento de crear.
                                stored_proc = """SET NOCOUNT ON exec [dbo].[AgregarPrivilegioContacto]
                                                                            @privilegio = %s,
                                                                            @contacto = %s"""
                        
                                params = (int(privilegio[2].get('name')),int(self.id_contacto))

                                cursor_b.execute(stored_proc, params)
                                #Se confirma la transacción desde Odoo hacia SGC.
                                cnxn.commit()
                                #cnxn.close()

                        else:
                            _logger.warning("Sin Privilegios")  
                            
                            #Se debe verificar qie el privilegio sea el correcto
                            #antes de permitir registrarlo en la tabla de privilegios.

                            #Se deben registrar tantos privilegios como se hayan establecido al momento de crear.
                            stored_proc = """SET NOCOUNT ON exec [dbo].[AgregarPrivilegioContacto]
                                                                        @privilegio = %s,
                                                                        @contacto = %s"""
                    
                            params = (int('5'),int(self.id_contacto))

                            cursor_b.execute(stored_proc, params)
                            #Se confirma la transacción desde Odoo hacia SGC.
                            cnxn.commit()
                            #cnxn.close()

                        #La fecha de sincronización debe ser mayor que la fecha de modifcación del Contacto para evitar ejecutar una sincronización innecesaria.
                        #Monitorear posible diferencia en segundos entre las fechas.
                        stored_proc = """UPDATE [Contacto] SET DateSincronyzed = %s WHERE id_contacto = %s;"""
                        params = (datetime.now() - timedelta(hours=4) + timedelta(minutes=1),int(self.id_contacto))

                        cursor_b.execute(stored_proc, params)
                        cnxn.commit()

                        #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.
                        self.contacto_date_modified = datetime.now() + timedelta(minutes=1)

                        #Se cierra la conexión para evitar congestiones por manejo automatico tarío o deficiente
                        cursor_b.close()
                        #cnxn.close()

                        self.env['sgc.odoo.history'].create({
                            'name': str(self.name),
                            'fecha_registro': datetime.now(),
                            'tipo_error': 'Sync Odoo --> SGC ('+str(self.company_type_stored)+')',
                            'registro_operacion': 'Se ha editado correctamente el registro en SGC durante la edición de un contacto en Odoo.',
                            'registro_tecnico': 'None',
                            'category': '<p style="color:orange;">Edición de Contacto existente</p>',
                        })

                    else:
                        self.env['sgc.odoo.history'].create({
                            'name': str(self.name),
                            'fecha_registro': datetime.now(),
                            'tipo_error': 'Sync Odoo --> SGC ('+str(self.company_type_stored)+')',
                            'registro_operacion': 'No se ha encontrado un registro en SGC relacionado con el registro que se está intentado editar en Odoo, Nombre: '+str(self.name)+', ID_Cliente: '+str(self.id_cliente)+', Documento de identidad: '+str(self.cedula_contacto),
                            'registro_tecnico': 'None',
                            'category': '<p style="color:red;">Error</p>',
                        })

            except pymssql.Error as e:

                if self.revisar_id_contacto_sgc:
                    self.revisar_id_contacto_sgc = False
                cursor_b.close()
                cnxn.close()

                _logger.warning("########## - FIN chequeo de la data modificada en contacto tipo Individual - ##########")
                _logger.warning("########## - FIN chequeo de la data modificada en contacto tipo Individual - ##########")
        
                raise ValidationError(_("""Error al editar la data del nuevo Contacto, por favor, verifique e intente nuevamente.
                                            Registro del error: 

                                            """+str(e)+"""."""))

        elif (self.id_cliente > 0 and self.id_contacto > 0) or (self.id_cliente > 0 and str(self.partner_type_id.name) == "Sharehosting" and not self.parent_id and self.facturable):
            if str(self.partner_category) == '1' or str(self.partner_category) == '2' or str(self.partner_category) == '3':

                if self.revisar_id_contacto_sgc and self.company_type_stored == 'person' and self.parent_id: #and not self.create_from_sync:
                    _logger.warning("########## - INICIO chequeo de la data modificada en contacto tipo Individual - ##########")
                    _logger.warning("########## - INICIO chequeo de la data modificada en contacto tipo Individual - ##########")
                    
                    #Se deben agregar las validaciones necesarias para garantizar que la data que viajará al SGC sea la
                    #mas integra y autentica posible, si todo esta bien se actualiza la fecha de modificación.

                    #try:
                        #Una vez modificada la fecha se procede a insertar la nueva data en el SGC.

                    ip = self.env.company.ip_conexion_sgc
                    port = self.env.company.puerto_conexion_sgc
                    bd = self.env.company.bd_conexion_sgc
                    user = self.env.company.user_conexion_sgc
                    password = self.env.company.pass_conexion_sgc
                    
                    try:
                        # ENCRYPT defaults to yes starting in ODBC Driver 18. It's good to always specify ENCRYPT=yes on the client side to avoid MITM attacks.
                        cnxn = bd_connector.BdConnections.connect_to_bd(self,ip,port,bd,user,password)
                        #cnxn = bd_connector.BdConnections.connect_to_bd(self,'200.74.215.68','4022','Dayco_SGC','Odoo','Dayco2022$')

                        if not cnxn:
                            _logger.warning("No se pudo conectar a la base de datos, verifique los errores de conexión en el log.")
                            if self.revisar_id_contacto_sgc:
                                self.revisar_id_contacto_sgc = False
                        else:
                            cursor_b = cnxn.cursor(as_dict=True)
                            _logger.warning("Actualizando desde Odoo a SGC!!")

                            #Se debe eliminar el '-' de la cédula si este lo posee.
                            characters = '-'
                            cedula_contacto = self.cedula_contacto
                            if self.cedula_contacto:
                                for x in range(len(characters)):
                                    cedula_contacto = cedula_contacto.replace(characters[x],"")
                            self.cedula_contacto = cedula_contacto

                            #Se debe validar que campo cambió realmente antes de enviar la data
                            #para mejorar la eficiencia del proceso de edición.
                            _logger.warning("ID Contacto a buscar: "+str(self.id_contacto))
                            _logger.warning("ID Cliente a buscar: "+str(self.id_cliente))

                            stored_proc = """SELECT id_contacto, nombre, apellido FROM [Contacto] WHERE fk_id_cliente = %s and id_contacto = %s;"""
                            params = (int(self.id_cliente),int(self.id_contacto))

                            cursor_b.execute(stored_proc, params)
                            contacto_sgc = cursor_b.fetchall()
                            cnxn.commit()
                            
                            name_odoo_temp = self.name
                            name_a = False
                            name_b = False
                            ape_a = False
                            ape_b = False

                            if contacto_sgc:
                                _logger.warning("Verificar la data del Contacto a editar desde Odoo a SGC")
                                _logger.warning("Data a comparar: "+str(contacto_sgc))
                                procede_edicion_sgc = False

                                #Si el nombre y apellido en el SGC se encuentran en el nombre de Odoo no se modifica
                                #el nombre ni el apellido en SGC.
                                for item_sgc in contacto_sgc:
                                    nombres_sgc = item_sgc.get('nombre').split(" ")
                                    apellidos_sgc = item_sgc.get('apellido').split(" ")

                                    _logger.warning("Nombres SGC B: "+str(nombres_sgc))
                                    _logger.warning("Apellidos SGC B: "+str(apellidos_sgc))
                                    _logger.warning("Nombre Odoo: "+str(self.name))
                                    name_aa, name_bb, ape_aa, ape_bb = check_sgc_data.chequeos.MaestroChequeos.SplitNombres(self.name,"1")

                                    for item in nombres_sgc:
                                        #Verificar si existen los nombres en Odoo exactamente iguales.
                                        if item:
                                            if not str(name_aa).find(str(item)) == -1 or not str(name_bb).find(str(item)) == -1:
                                                _logger.warning("Nombre: "+str(item)+" encontrado en SGC!")
                                            else:
                                                #Se procede con la nueva edición del nombre desde Odoo hacia SGC.
                                                procede_edicion_sgc = True
                                        else:
                                            #Se procede con la nueva edición del nombre desde Odoo hacia SGC.
                                            procede_edicion_sgc = True
                                    
                                    #Solo si pasó la verificación de los nombres es que verifica los apellidos.
                                    if not procede_edicion_sgc:
                                        for item in apellidos_sgc:
                                            #Verificar si existen los nombres en Odoo exactamente iguales.
                                            if item:
                                                if not str(ape_aa).find(str(item)) == -1 or not str(ape_bb).find(str(item)) == -1:
                                                    _logger.warning("Apellido: "+str(item)+" encontrado en SGC!")
                                                else:
                                                    #Se procede con la nueva edición del nombre desde Odoo hacia SGC.
                                                    procede_edicion_sgc = True
                                            else:
                                                #Se procede con la nueva edición del nombre desde Odoo hacia SGC.
                                                procede_edicion_sgc = True

                                if not procede_edicion_sgc:
                                    #De forma temporal se envía nombre y apellido segmentados a SGC
                                    #y luego se recupera su forma original antes de ser escritos en Odoo.
                                    self.name = item_sgc['nombre']
                                    self.apellido_contacto = item_sgc['apellido']
                                    
                                else:
                                    _logger.warning("Procede la edición del nombre desde Odoo hacia SGC.")
                                    name_a, name_b, ape_a, ape_b = check_sgc_data.chequeos.MaestroChequeos.SplitNombres(self.name,"1")

                                    self.name = name_a + " " + name_b
                                    self.apellido_contacto = ape_a + " " + ape_b

                            #Se debe crear una validación adicional que envíe valores vacíos en vez de la palabra false cuando
                            #cree o modifique desde Odoo hacía SGC.

                            if not self.cedula_contacto:
                                #Se envía vacío.
                                self.cedula_contacto = ''
                            if not self.phone:
                                #Se envía vacío.
                                self.phone = ''
                            if not self.mobile:
                                #Se envía vacío.
                                self.mobile = ''
                            if not self.email:
                                #Se envía vacío.
                                self.email = ''
                            if not self.function:
                                #Se envía vacío.
                                self.function = ''

                            params = (self.id_contacto,str(self.name),str(self.apellido_contacto),str(self.cedula_contacto),str(self.phone),str(self.email),str(self.cargo_contacto),self.id_cliente,int(self.tipo_contacto),self.mobile,self.prioridad_contacto,int(self.ScalabilityLevel))

                            sgc_sucessfully_commit = False

                            #Se ejecuta el stored procedure con el cursor
                            rows = cursor_b.callproc('ModificarContacto', params)
                            cnxn.commit()

                            #Fix #11, Apellido del contacto repetido
                            if name_a and ape_a:
                                self.name = name_a + " " + name_b + " " + ape_a + " " + ape_b
                                self.apellido_contacto = ape_a + " " + ape_b

                            for row in rows:
                                _logger.warning("Numero de filas afectadas: "+str(row))
                                sgc_sucessfully_commit = True
                                #Con solo el primer valor es suficiente :)
                                break

                            #Si la consulta afecto al menos a una fila entonces todo OK, si no lanza la alerta
                            if not sgc_sucessfully_commit and not self.create_from_sync:
                                if self.revisar_id_contacto_sgc:
                                    self.revisar_id_contacto_sgc = False
                                cnxn.close()
                                raise ValidationError(_("Ninguna fila ha sido afectada, verifique con el Administrador del SGC sobre el proceso de modificación de este registro."))

                            #Se hace falso para que al crear por sincronización no se haga un rechequeo innecesario.
                            if self.revisar_id_contacto_sgc:
                                self.revisar_id_contacto_sgc = False

                            #Si la edición resultó exitosa entonces se procede a recuperar el nombre original antes de guardar el contacto nuevo.
                            self.name = name_odoo_temp
                            
                            #Al editarse un contacto se debe reestablecer la data de los privilegios para garantizar que se mnatienen
                            #siempre lo mas actualizado posible.
                            #Se deben registrar tantos privilegios como se hayan establecido al momento de crear.
                            stored_proc = """DELETE FROM Privilegio_Contacto WHERE fk_id_contacto = %s"""
                    
                            params = (int(self.id_contacto))

                            cursor_b.execute(stored_proc, params)
                            #Se confirma la transacción desde Odoo hacia SGC.
                            cnxn.commit()
                            #cnxn.close()
                            
                            #Luego de eliminarse se vuelven a registrar en la tabla de privilegios.
                            if self.privilegio_ids:

                                for privilegio in self.privilegio_ids:
                                    _logger.warning("Privilegio: "+str(privilegio.name))  
                                    
                                    #Se debe verificar qie el privilegio sea el correcto
                                    #antes de permitir registrarlo en la tabla de privilegios.

                                    #Se deben registrar tantos privilegios como se hayan establecido al momento de crear.
                                    stored_proc = """SET NOCOUNT ON exec [dbo].[AgregarPrivilegioContacto]
                                                                                @privilegio = %s,
                                                                                @contacto = %s"""
                            
                                    params = (int(privilegio.name),int(self.id_contacto))

                                    cursor_b.execute(stored_proc, params)
                                    #Se confirma la transacción desde Odoo hacia SGC.
                                    cnxn.commit()
                                    #cnxn.close()

                            else:
                                _logger.warning("Sin Privilegios")  
                                
                                #Se debe verificar qie el privilegio sea el correcto
                                #antes de permitir registrarlo en la tabla de privilegios.

                                #Se deben registrar tantos privilegios como se hayan establecido al momento de crear.
                                stored_proc = """SET NOCOUNT ON exec [dbo].[AgregarPrivilegioContacto]
                                                                            @privilegio = %s,
                                                                            @contacto = %s"""
                        
                                params = (int('5'),int(self.id_contacto))

                                cursor_b.execute(stored_proc, params)
                                #Se confirma la transacción desde Odoo hacia SGC.
                                cnxn.commit()
                                #cnxn.close()

                            #La fecha de sincronización debe ser mayor que la fecha de modifcación del Contacto para evitar ejecutar una sincronización innecesaria.
                            #Monitorear posible diferencia en segundos entre las fechas.
                            stored_proc = """UPDATE [Contacto] SET DateSincronyzed = %s WHERE id_contacto = %s;"""
                            params = (datetime.now() - timedelta(hours=4) + timedelta(minutes=1),int(self.id_contacto))

                            cursor_b.execute(stored_proc, params)
                            cnxn.commit()

                            #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.
                            self.contacto_date_modified = datetime.now() + timedelta(minutes=1)

                            #Se cierra la conexión para evitar congestiones por manejo automatico tarío o deficiente
                            cursor_b.close()
                            cnxn.close()

                            self.env['sgc.odoo.history'].create({
                                'name': str(self.name),
                                'fecha_registro': datetime.now(),
                                'tipo_error': 'Sync Odoo --> SGC ('+str(self.company_type_stored)+')',
                                'registro_operacion': 'Se ha editado correctamente el registro en SGC durante la edición de un contacto en Odoo.',
                                'registro_tecnico': 'None',
                                'category': '<p style="color:orange;">Edición de Contacto existente</p>',
                            })

                    except pymssql.Error as e:

                        if self.revisar_id_contacto_sgc:
                            self.revisar_id_contacto_sgc = False
                        cursor_b.close()
                        cnxn.close()

                        _logger.warning("########## - FIN chequeo de la data modificada en contacto tipo Individual - ##########")
                        _logger.warning("########## - FIN chequeo de la data modificada en contacto tipo Individual - ##########")
                
                        raise ValidationError(_("""Error al editar la data del nuevo Contacto, por favor, verifique e intente nuevamente.
                                                    Registro del error: 

                                                    """+str(e)+"""."""))

                elif self.revisar_id_contacto_sgc and self.company_type_stored == 'person' and not self.parent_id and self.facturable and str(self.partner_type_id.name) == "Sharehosting":
                    _logger.warning("########## - INICIO chequeo de data Contacto Individual sin compañía - ##########")
                    _logger.warning("########## - INICIO chequeo de data Contacto Individual sin compañía - ##########")

                    ip = self.env.company.ip_conexion_sgc
                    port = self.env.company.puerto_conexion_sgc
                    bd = self.env.company.bd_conexion_sgc
                    user = self.env.company.user_conexion_sgc
                    password = self.env.company.pass_conexion_sgc
                    
                    try:
                        # ENCRYPT defaults to yes starting in ODBC Driver 18. It's good to always specify ENCRYPT=yes on the client side to avoid MITM attacks.
                        cnxn = bd_connector.BdConnections.connect_to_bd(self,ip,port,bd,user,password)
                        #cnxn = bd_connector.BdConnections.connect_to_bd(self,'200.74.215.68','4022','Dayco_SGC','Odoo','Dayco2022$')

                        if not cnxn:
                            if self.revisar_id_contacto_sgc:
                                self.revisar_id_contacto_sgc = False
                            _logger.warning("No se pudo conectar a la base de datos, verifique los errores de conexión en el log.")
                        else:
                            cursor_b = cnxn.cursor(as_dict=True)
                            _logger.warning("Actualizando desde Odoo a SGC")

                            #Se debe eliminar el '-' del rif si este lo posee.
                            characters = '-'
                            vat_cliente = self.vat
                            if self.vat:
                                for x in range(len(characters)):
                                    vat_cliente = vat_cliente.replace(characters[x],"")
                            self.rif_cliente = vat_cliente
                            
                            #Se debe crear una validación adicional que envíe valores vacíos en vez de la palabra false cuando
                            #cree o modifique desde Odoo hacía SGC.

                            if not self.phone:
                                #Se envía vacío.
                                self.phone = ''
                            if not self.mobile:
                                #Se envía vacío.
                                self.mobile = ''
                            if not self.fax_cliente:
                                #Se envía vacío.
                                self.fax_cliente = ''
                            if not self.city:
                                #Se envía vacío.
                                self.city = ''
                            if not self.zip:
                                #Se envía vacío.
                                self.zip = ''

                            params = (int(self.id_cliente),str(self.name),self.rif_cliente,str(self.street),str(self.unidad_negocio_cliente),str(self.phone),str(self.fax_cliente),str(self.city),str(self.zip),int(self.tipo_cliente),int(self.tipo_negocio_cliente),int(self.categoria_cliente),int(self.tipo_cliente_corporativo),self.municipio_cliente,self.street,self.mobile,int(self.account_management_id_sgc))

                            sgc_sucessfully_commit = False
                            #Se ejecuta el stored procedure con el cursor
                            rows = cursor_b.callproc('ModificarCliente', params)
                            cnxn.commit()

                            for row in rows:
                                _logger.warning("Numero de filas afectadas en SGC: "+str(row))
                                sgc_sucessfully_commit = True
                                #Con solo el primer valor es suficiente :)
                                break

                            #Si la consulta afecto al menos a una fila entonces todo OK, si no lanza la alerta
                            if not sgc_sucessfully_commit and not self.create_from_sync:
                                if self.revisar_id_contacto_sgc:
                                    self.revisar_id_contacto_sgc = False
                                cnxn.close()
                                raise ValidationError(_("Ninguna fila ha sido afectada, verifique con el Administrador del SGC sobre el proceso de modificación de este registro."))

                            #Se hace falso para que al crear por sincronización no se haga un rechequeo innecesario.
                            #self.revisar_id_cliente_sgc = False
                            if self.revisar_id_contacto_sgc:
                                self.revisar_id_contacto_sgc = False

                            #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.
                            self.client_date_modified = datetime.now() + timedelta(minutes=1) - timedelta(hours=4)

                            cursor_b.close()
                            cnxn.close()

                            self.env['sgc.odoo.history'].create({
                                'name': str(self.name),
                                'fecha_registro': datetime.now(),
                                'tipo_error': 'Sync SGC --> Odoo ('+str(self.company_type_stored)+')',
                                'registro_operacion': 'Se ha editado correctamente el registro',
                                'registro_tecnico': 'None',
                                'category': '<p style="color:orange;">Edición de Cliente Sharehosting existente.</p>',
                            })

                    except pymssql.Error as e:

                        if self.revisar_id_contacto_sgc:
                            self.revisar_id_contacto_sgc = False
                        cursor_b.close()
                        cnxn.close()
                        
                        _logger.warning("########## - FIN chequeo de data Contacto Individual sin compañía - ##########")
                        _logger.warning("########## - FIN chequeo de data Contacto Individual sin compañía - ##########")

                        raise ValidationError(_("""Error al editar la data del nuevo Contacto, por favor, verifique e intente nuevamente.
                                                    Registro del error: 

                                                    """+str(e)+"""."""))

                else:
                    _logger.warning("No se modifica la data de contactos en el SGC.")
                    if self.revisar_id_contacto_sgc:
                        self.revisar_id_contacto_sgc = False
            else:
                if self.revisar_id_contacto_sgc:
                    self.revisar_id_contacto_sgc = False
                _logger.warning(_("""Las funcionalidades de la interfaz SGC-Odoo han sido habilitadas
                                            solo a los registros que contengan en su campo 'Categoría' los valores:
                                            1- Cliente
                                            2- Cliente/Proveedor """))
        else:
            if self.revisar_id_contacto_sgc:
                self.revisar_id_contacto_sgc = False
            _logger.warning("No se edita el contacto porque aun no se ha sincronizado con el SGC, verifique porque no se ha sincronizado e intente nuevamente.")

    @api.model
    def create(self, vals):
        #_logger.warning("########## INICIO VERIFICACIÓN POR CREATE ##########")
        #_logger.warning("########## INICIO VERIFICACIÓN POR CREATE ##########")

        _logger.warning("Nombre: "+str(vals.get("name")))
        _logger.warning("Cédula: "+str(vals.get("identification_id")))
        _logger.warning("Rif: "+str(vals.get("vat")))
        _logger.warning("Tipo de compañía (stored): "+str(vals.get("company_type_stored")))
        _logger.warning("Tipo de compañía: "+str(vals.get("company_type")))

        #Hot fix #29: Verificación personalizada del RIF para ajustes en procesos de registros antes de
                    #que se registre data en SGC.
        
        if not vals.get("company_type") is None and vals.get("company_type") == 'company':
            if self.validate_rif_before_sgc(vals.get('vat')) is False:
                raise ValidationError(_("""El rif tiene un formato incorrecto.\n\t""" 
"""Los formatos permitidos son los siguientes:\n\t"""
"""V-012345678, E-012345678, J-012345678, G-012345678\n\t"""
"""Por favor verifique el formato y si posee los 9 digitos e intente de nuevo\n\t"""))

        #_logger.warning("Email: "+str(vals.get("email")))
        #_logger.warning("Tipo de contacto desde Odoo: "+str(vals.get("company_type")))

        #Se debe colocar en false los campos "revisar_id_contacto_sgc" y "revisar_id_cliente_sgc".
        vals['revisar_id_contacto_sgc'] = False
        vals['revisar_id_cliente_sgc'] = False

        #Se debe ejecutar el stored procedure desde Odoo y retornar el ID del SGC recien creado cuando se
        #inserte el nuevo registro en la data del SGC.

        #Dependiendo de si son Clientes (Compañías) o Contactos (Individuales) las validaciones de los
        #campos cambian.
        
        #Cuando la cédula llega al método de creación desde el sincronizador
        #se debe asegurar de que ya tenga el formato correcto.
        cedres = vals.get('identification_id')

        #if str(vals.get('identification_id')).find("-") == -1:
            #Se debe asignar el - despues de la primera letra del RIF.
        #    letra_ced = str(vals.get('identification_id'))[:1]
        #    numero_ced = str(vals.get('identification_id'))[1:]
        #    cedres = numero_ced

        #    _logger.warning("Cedula resultante (cedres): "+str(cedres))

        #_logger.warning("Valores: "+str(vals)) #Solo debug.

        #Fix #22: Se coloca validación usando método GET y en caso de no encontrar False para prevenir error
        #al crear Usuario directamente desde la sección de Usuarios nativa.

        #Fix tipo contacto
        if vals.get('rol',False):
            vals['tipo_contacto'] = str(vals['rol'])
        #Fix cargo contacto
        if vals.get('function',False):
            vals['cargo_contacto'] = str(vals['function'])

        #Se agrega validación adicional en la que se debe prevenir que exista un contacto con el mismo id_contacto
        #o la misma cédula de identidad y así evitar duplicidades.
        registro_repetido = self.env['res.partner'].search(['|',('vat', '=', str(cedres)),('identification_id', '=', str(cedres))], limit=1)
        _logger.warning("Registros repetidos encontrados: "+str(registro_repetido))

        #Hot fix #33: Se puede registrar un contacto con cédula repetida como un proveedor, solo aplicar validación.
                    #a registros que sean Clientes o Clientes Proveedores o Proveedores con etiqueta "Aliados para el servicio."
        #23/01/2023
        #Categorías permitidas para sincronizar hasta la fecha:
        #1- Cliente
        #3- Cliente/proveedor

        if vals.get('cliente_partner_category') not in ['1', '3']:        
            registro_repetido = False

        if not registro_repetido:
            if not vals.get("create_from_sync"):

                #Se agrega el filtro global "Categoría" que solo permitirá la ejecución de las funcionalidades de
                #Creación/Edición/Activación/Desactivación a los registros que contengan en este campo los
                #valores:

                #1- Cliente
                #2- Proveedor
                #3- Cliente/Proveedor

                #Fix rif Cliente
                characters = '-'
                vals['rif_cliente'] = vals.get('vat')

                #Fix se agrega la variable procede en un nivel superior en caso de ser un contacto duplicado
                #se debe analizar que data se esta enviando y posterior realizar los arreglos necesarios
                #para que funcione correctamente la interfaz SGC --> Odoo
                procede = False

                _logger.warning("Valores: "+str(vals))
                #_logger.warning("Categoría del Cliente: "+str(vals.get('cliente_partner_category')))
                    
                #Solo se sincronizan los registros que contemplen el valor "Cliente" o "Cliente/Proveedor" en Odoo.
                #Los contactos heredan la categoría de la compañía relacionada, por lo que se cumple la validación.
                if str(vals.get('cliente_partner_category')) == '1' or str(vals.get('cliente_partner_category')) == '3':

                    if str(vals.get("company_type")) == "person":
                        _logger.warning("########## - Se va a crear un contacto (Individual) en SGC - ##########")
                        
                        #Se debe agregar validaciones adicionales para el vat y evitar registros indeseados :)
                        if str(vals.get('vat')).count("-") > 1:
                            _logger.warning("Se ha encontrado mas de un guion en el rif, debe verificar su formato.")
                            raise ValidationError(_("""Los formatos validos de RIF son los siguientes:
                                                        J-123456789
                                                        G-123456789
                                                        E-123456789
                                                        
                                                        Por favor verifique e intente nuevamente."""))

                        procede = False

                        #Se verifican los campos del contacto (Individual) antes de insertar.
                        if vals.get("apellido_contacto"):
                            _logger.warning("Se ha establecido un apellido")

                            #if vals.get("identification_id"):
                            #    _logger.warning("Se ha establecido una cédula")

                            if vals.get("phone") or vals.get("mobile"):
                                _logger.warning("Se ha establecido un telefono principal")

                                #if vals.get("mobile"):
                                #    _logger.warning("Se ha establecido un telefono secundario")

                                    #if vals.get("function"):
                                    #    _logger.warning("Se ha establecido un cargo")

                                if vals.get("habilitado_contacto"):
                                    _logger.warning("Se ha habilitado el contacto (individual)")

                                    if (vals.get("id_cliente") and vals.get("id_cliente") > 0) or not vals.get("parent_id"):
                                        _logger.warning("Se ha establecido un id_cliente valido de una compañía")

                                        if vals.get("tipo_contacto") or vals.get('rol'):
                                            _logger.warning("Se ha establecido un tipo de contacto correctamente")

                                            if int(vals.get("ScalabilityLevel")) > 0 or not vals.get("parent_id"):
                                                _logger.warning("Se ha establecido la escalabilidad")
                                                
                                                #Una vez se cumplen todas las verificaciones se procede con el envío
                                                #de datos hacía el SGC.
                                                
                                                ip = self.env.company.ip_conexion_sgc
                                                port = self.env.company.puerto_conexion_sgc
                                                bd = self.env.company.bd_conexion_sgc
                                                user = self.env.company.user_conexion_sgc
                                                password = self.env.company.pass_conexion_sgc

                                                try:
                                                    # ENCRYPT defaults to yes starting in ODBC Driver 18. It's good to always specify ENCRYPT=yes on the client side to avoid MITM attacks.
                                                    cnxn = bd_connector.BdConnections.connect_to_bd(self,ip,port,bd,user,password)
                                                    #cnxn = bd_connector.BdConnections.connect_to_bd(None,'10.0.1.168','Dayco_SGC','Odoo','Dayco2022$')

                                                    #Se debe establecer el parámetro SET NOCOUNT ON para que funcione correctamente
                                                    #https://stackoverflow.com/questions/7753830/mssql2008-pyodbc-previous-sql-was-not-a-query

                                                    cursor_b = cnxn.cursor(as_dict=True)
                                                    _logger.warning("Registrando desde Odoo a SGC")

                                                    #Se debe eliminar el '-' del rif si este lo posee.
                                                    characters = '-'
                                                    if vals['rif_cliente']:
                                                        for x in range(len(characters)):
                                                            vals['rif_cliente'] = vals['rif_cliente'].replace(characters[x],"")
                                                    
                                                    if vals['cedula_contacto']:
                                                        for x in range(len(characters)):
                                                            vals['cedula_contacto'] = vals['cedula_contacto'].replace(characters[x],"")
                                                    
                                                    #Se debe convertir el tipo de cliente a un entero aceptable para el SGC
                                                    if vals['tipo_contacto'] == 1:
                                                        _logger.warning("Cambiar por el status correcto en SGC")
                                                    
                                                    #Se deben cumplir dos casos:
                                                    #1- Se debe poder registrar un contacto con compañía asociada en la tabla Contactos
                                                    #2- Se debe poder registrar un contacto sin compañía asociada en la tbla Clientes

                                                    #Para el segundo caso se debe modificar un poco la data que se esta enviando para cumplir
                                                    #con los registros de la tabla Cliente del SGC, por ejemplo, la cédula es el rif en SGC.

                                                    #En caso de presentar inconvenientes con los procedimientos almacenados o consultas particulares
                                                    #y el envío de parámetros, se deben usar "bind variables" como '%s'.

                                                    #Referencia: https://stackoverflow.com/questions/23244450/cant-insert-tuple-to-mssql-db

                                                    #use bind variables. it is safer, it is kinder to the DB.
                                                    #cursor.execute('SELECT * FROM persons WHERE salesrep=%s', 'John Doe')
                                                    #your strings will be automatically and properly wrapped in quotes.

                                                    var_a = '' #Variable donde se almacena el ReturnId despues de registrar exitosamente un registro en SGC.
                                                    sharehosting_id = self.env['partner.type'].search([('name', '=', 'Sharehosting')], limit=1)
                                                    procede_registro_nuevo = True

                                                    if not vals['parent_id'] and vals['facturable'] and str(vals['partner_type_id']) == str(sharehosting_id.id):
                                                        #Descartado para prevenir inestabilidad en el sistema SGC, se pide ajuro asociar el contacto a un Cliente SGC valido.
                                                        
                                                        _logger.warning("Se acepta este tipo de registro por no tener una compañía asociada valida.")
                                                        #raise ValidationError(_("Debe asociar este contacto a un Cliente SGC valido, verifique e intente nuevamente."))
                                                
                                                        #Se deben agregar las condiciones de Clientes necesarias para registrar el contacto
                                                        #como si se tratase de un Cliente de manera segura.
                                                        if vals.get("unidad_negocio_cliente"):
                                                            _logger.warning("Se ha establecido una unidad de negocio de Cliente")
                                                        
                                                            if vals.get("street"):
                                                                _logger.warning("Se ha establecido una dirección")
                                                        
                                                                if vals.get("city"):
                                                                    _logger.warning("Se ha establecido una ciudad")

                                                                    #Descartado por no ser necesario en todos los casos existentes.
                                                                    #if vals.get("zip"):
                                                                    #    _logger.info("Se ha establecido un código postal")

                                                                    if vals.get("tipo_negocio_cliente"):
                                                                        _logger.warning("Se ha establecido un tipo de negocio de cliente")

                                                                        if vals.get("categoria_cliente"):
                                                                            _logger.warning("Se ha establecido una categoría de Cliente")

                                                                            #if vals.get("tipo_cliente"):
                                                                            #    _logger.warning("Se ha establecido un tipo de Cliente")

                                                                            if vals.get("tipo_cliente_corporativo"):
                                                                                _logger.warning("Se ha establecido un tipo de Cliente corporativo")

                                                                                if vals.get("municipio_cliente"):
                                                                                    _logger.warning("Se ha establecido un municipio")

                                                                                    if vals.get("cliente_activo"):
                                                                                        _logger.warning("Se ha activado al cliente")
                                                                                        
                                                                                        #if vals.get("account_management_id_sgc"):
                                                                                        #    _logger.warning("Se ha establecido un accountmanagementid")
                                                                                        try:
                                                                                            stored_proc = """ SET NOCOUNT ON exec [dbo].[AgregarCliente]
                                                                                                                                            @nombre = %s,
                                                                                                                                            @rif = %s,
                                                                                                                                            @direccion = %s,
                                                                                                                                            @unidadNegocios = %s,
                                                                                                                                            @telefono = %s,
                                                                                                                                            @fax = %s,
                                                                                                                                            @ciudad = %s,
                                                                                                                                            @codigoPostal = %s,
                                                                                                                                            @tipoCliente = %s,
                                                                                                                                            @idClienteCorp = %s,
                                                                                                                                            @idTipoNegocio = %s,
                                                                                                                                            @idCategoria = %s,
                                                                                                                                            @idMunicipio = %s,
                                                                                                                                            @direccion2 = %s,
                                                                                                                                            @telefono2 = %s,
                                                                                                                                            @AccountManagementId = %s"""
                                                                                            #Se debe eliminar el '-' del rif si este lo posee.
                                                                                            characters = '-'
                                                                                            if vals['rif_cliente']:
                                                                                                for x in range(len(characters)):
                                                                                                    vals['rif_cliente'] = vals['rif_cliente'].replace(characters[x],"")
                                                                                            
                                                                                            if vals['cedula_contacto']:
                                                                                                for x in range(len(characters)):
                                                                                                    vals['cedula_contacto'] = vals['cedula_contacto'].replace(characters[x],"")
                                                                                            #Se debe convertir el tipo de cliente a un entero aceptable para el SGC
                                                                                            if vals['tipo_contacto'] == 1:
                                                                                                _logger.warning("Cambiar por el status correcto en SGC")
                                                                                            
                                                                                            _logger.warning("Gerente de cuenta: "+str(int(vals['account_management_id_sgc'])))
                                                                                            
                                                                                            #Se debe crear una validación adicional que envíe valores vacíos en vez de la palabra false cuando
                                                                                            #cree o modifique desde Odoo hacía SGC.

                                                                                            if not vals['phone']:
                                                                                                #Se envía vacío.
                                                                                                vals['phone'] = ''
                                                                                            if not vals['mobile']:
                                                                                                #Se envía vacío.
                                                                                                vals['mobile'] = ''
                                                                                            if not vals['fax_cliente']:
                                                                                                #Se envía vacío.
                                                                                                vals['fax_cliente'] = ''
                                                                                            if not vals['city']:
                                                                                                #Se envía vacío.
                                                                                                vals['city'] = ''
                                                                                            if not vals['zip']:
                                                                                                #Se envía vacío.
                                                                                                vals['zip'] = ''

                                                                                            params = ''
                                                                                            #Si retorna cero es porque se le pasó una cadena vacía o un cero en efecto, si no entonces si pasas el número.
                                                                                            if int(vals['account_management_id_sgc']) > 0:
                                                                                                params = (str(vals['name']),str(vals['rif_cliente']),str(vals['street']),int(vals['unidad_negocio_cliente']),str(vals['phone']),str(vals['fax_cliente']),vals['city'],str(vals['zip']),int(vals['tipo_cliente']),int(vals['tipo_cliente_corporativo']),int(vals['tipo_negocio_cliente']),int(vals['categoria_cliente']),int(vals['municipio_cliente']),vals['direccion_facturacion'],vals['mobile'],int(vals['account_management_id_sgc']))
                                                                                            else:
                                                                                                _logger.warning("Se envía NULL")
                                                                                                params = (str(vals['name']),str(vals['rif_cliente']),str(vals['street']),int(vals['unidad_negocio_cliente']),str(vals['phone']),str(vals['fax_cliente']),vals['city'],str(vals['zip']),int(vals['tipo_cliente']),int(vals['tipo_cliente_corporativo']),int(vals['tipo_negocio_cliente']),int(vals['categoria_cliente']),int(vals['municipio_cliente']),vals['direccion_facturacion'],vals['mobile'],None)
                                                                                    
                                                                                            #Se ejecuta el stored procedure con el cursor
                                                                                            cursor_b.execute(stored_proc, params)
                                                                                            var_a = cursor_b.fetchone()
                                                                                            cnxn.commit()

                                                                                            procede_registro_nuevo = False
                                                                                            procede = True

                                                                                            #Fix tipo de contacto en Cliente sharehosting (06/01/2023)
                                                                                            vals['tipo_contacto'] = "1"
                                                                                            
                                                                                            #Fix Id_cliente SGC
                                                                                            vals['id_cliente'] = var_a.get("ReturnId")

                                                                                            #La fecha de sincronización debe ser mayor que la fecha de modifcación del Contacto para evitar ejecutar una sincronización innecesaria.
                                                                                            #Monitorear posible diferencia en segundos entre las fechas.
                                                                                            stored_proc = """UPDATE [Cliente] SET DateSincronyzed = %s WHERE id_cliente = %s;"""
                                                                                            params = (datetime.now() - timedelta(hours=4) + timedelta(minutes=1),int(vals.get('id_cliente')))

                                                                                            cursor_b.execute(stored_proc, params)
                                                                                            cnxn.commit()

                                                                                            #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.
                                                                                            vals['client_date_modified'] = datetime.now() + timedelta(minutes=1)

                                                                                        except pymssql.Error as e:
                                                                                            procede_registro_nuevo = False

                                                                                            cursor_b.close()
                                                                                            cnxn.close()

                                                                                            raise ValidationError(_("""Error al registrar la data del nuevo Contacto de tipo Cliente Sharehosting de SGC, por favor, verifique e intente nuevamente.
                                                                                                                        Registro del error: 

                                                                                                                        """+str(e)+"""."""))
                                                                                        #else:
                                                                                        #    _logger.warning("No se ha establecido un accountmanagementid valido")
                                                                                        #    cnxn.close()
                                                                                        #    raise ValidationError(_("Debe establecer un accountmanagementid valido para este Cliente (SGC) de tipo Individual (Odoo)"))
                                                                                    else:
                                                                                        _logger.warning("No se ha establecido el parámetro activo de Cliente valido")
                                                                                        cnxn.close()
                                                                                        cursor_b.close()
                                                                                        raise ValidationError(_("Debe establecer el parámetro activo de Cliente valido para este Cliente (SGC) de tipo Individual (Odoo)"))
                                                                                else:
                                                                                    _logger.warning("No se ha establecido un municipio de Cliente valido")
                                                                                    cnxn.close()
                                                                                    cursor_b.close()
                                                                                    raise ValidationError(_("Debe establecer un municipio de Cliente valido para este Cliente (SGC) de tipo Individual (Odoo)"))
                                                                            else:
                                                                                _logger.warning("No se ha establecido un tipo de Cliente Corporativo valido")
                                                                                cnxn.close()
                                                                                cursor_b.close()
                                                                                raise ValidationError(_("Debe establecer un tipo de Cliente Corporativo valido para este Cliente (SGC) de tipo Individual (Odoo)"))
                                                                            #else:
                                                                            #    _logger.warning("No se ha establecido un tipo de Cliente valido")
                                                                            #    cnxn.close()
                                                                            #    raise ValidationError(_("Debe establecer un tipo de Cliente valido para este Cliente (SGC) de tipo Individual (Odoo)"))
                                                                        else:
                                                                            _logger.warning("No se ha establecido una categoría de Cliente valida")
                                                                            cnxn.close()
                                                                            cursor_b.close()
                                                                            raise ValidationError(_("Debe establecer una categoría de Cliente valida para este Cliente (SGC) de tipo Individual (Odoo)"))
                                                                    else:
                                                                        _logger.warning("No se ha establecido un tipo de negocio de Cliente valido")
                                                                        cnxn.close()
                                                                        cursor_b.close()
                                                                        raise ValidationError(_("Debe establecer un tipo de Cliente valido para este Cliente (SGC) de tipo Individual (Odoo)"))
                                                                    #else:
                                                                    #    _logger.warning("No se ha establecido una código postal valido")
                                                                    #    cnxn.close()
                                                                    #    cursor_b.close()
                                                                    #    raise ValidationError(_("Debe establecer un código postal para este Cliente (SGC) de tipo Individual (Odoo)"))
                                                                else:
                                                                    _logger.warning("No se ha establecido una Ciudad valida")
                                                                    cnxn.close()
                                                                    cursor_b.close()
                                                                    raise ValidationError(_("Debe establecer una Ciudad para este Cliente (SGC) de tipo Individual (Odoo)"))
                                                            else:
                                                                _logger.warning("No se ha establecido una Dirección valida")
                                                                cnxn.close()
                                                                cursor_b.close()
                                                                raise ValidationError(_("Debe establecer una Dirección para este Cliente (SGC) de tipo Individual (Odoo)"))
                                                        else:
                                                            _logger.warning("No se ha establecido una unidad de negocio de Cliente")
                                                            cnxn.close()
                                                            cursor_b.close()
                                                            raise ValidationError(_("Debe establecer una unidad de negocio para este Cliente (SGC) de tipo Individual (Odoo)"))
                                                    else:
                                                        _logger.warning("Se registra un contacto de tipo individual en la tabla Contacto")
                                                        procede_registro_nuevo = True

                                                        #Se debe establecer si se va a modificar un contacto o si se va a crear nuevo.

                                                        #Verificar si existe en SGC un contacto como el que se está creando, en ese caso, se debe
                                                        #editar el contacto con el fin de no duplicar data desde Odoo hacia SGC.
                                                        #Se pueden presentar tres casos:
                                                        #1- Tiene ID Contacto y ID Cliente (Proveniente de plantilla)
                                                        #2- Tiene ID Cliente y Cédula
                                                        #3- No tiene Cédula, no tiene ID Contacto y tiene ID Cliente (Creación manual sin plantilla)

                                                        if vals.get('id_contacto') and vals.get('id_cliente'):
                                                            #Si existen estos dos valores se encuentra el caso #1, se debe buscar en SGC la data para actualizar.
                                                            _logger.warning("Caso #1 de edición durante la creación")

                                                            ip = self.env.company.ip_conexion_sgc
                                                            port = self.env.company.puerto_conexion_sgc
                                                            bd = self.env.company.bd_conexion_sgc
                                                            user = self.env.company.user_conexion_sgc
                                                            password = self.env.company.pass_conexion_sgc
                                                            
                                                            try:
                                                                # ENCRYPT defaults to yes starting in ODBC Driver 18. It's good to always specify ENCRYPT=yes on the client side to avoid MITM attacks.
                                                                cnxn = bd_connector.BdConnections.connect_to_bd(self,ip,port,bd,user,password)
                                                                #cnxn = bd_connector.BdConnections.connect_to_bd(self,'200.74.215.68','4022','Dayco_SGC','Odoo','Dayco2022$')

                                                                if not cnxn:
                                                                    _logger.warning("No se pudo conectar a la base de datos, verifique los errores de conexión en el log.")
                                                                    procede_registro_nuevo = False
                                                                    if vals.get('revisar_id_contacto_sgc'):
                                                                        vals['revisar_id_contacto_sgc'] = False
                                                                else:
                                                                    cursor_b = cnxn.cursor(as_dict=True)
                                                                    _logger.warning("Actualizando desde Odoo a SGC")
                                                                    #Fix del tipo de contacto por importación
                                                                    #Fix del campo 'Tipo contacto'
                                                                    #vals['tipo_contacto'] = str(vals.get('rol'))
                                                                    if str(vals['tipo_contacto']) == "1":
                                                                        vals['tipo_contacto'] = "3"
                                                                    elif str(vals['tipo_contacto']) == "2":
                                                                        vals['tipo_contacto'] = "2"
                                                                    elif str(vals['tipo_contacto']) == "3":
                                                                        vals['tipo_contacto'] = "1"
                                                                    else:
                                                                        vals['tipo_contacto'] = "1"

                                                                    #Se debe eliminar el '-' de la cédula si este lo posee.
                                                                    characters = '-'
                                                                    cedula_contacto = vals.get('cedula_contacto')
                                                                    if vals.get('cedula_contacto'):
                                                                        for x in range(len(characters)):
                                                                            cedula_contacto = cedula_contacto.replace(characters[x],"")
                                                                    vals['cedula_contacto'] = cedula_contacto
                                                                    
                                                                    #Se debe validar que campo cambió realmente antes de enviar la data
                                                                    #para mejorar la eficiencia del proceso de edición.
                                                                    _logger.warning("ID Contacto a buscar: "+str(vals.get('id_contacto')))
                                                                    _logger.warning("ID Cliente a buscar: "+str(vals.get('id_cliente')))

                                                                    stored_proc = """SELECT id_contacto, nombre, apellido FROM [Contacto] WHERE fk_id_cliente = %s and id_contacto = %s;"""
                                                                    params = (int(vals.get('id_cliente')),int(vals.get('id_contacto')))

                                                                    cursor_b.execute(stored_proc, params)
                                                                    contacto_sgc = cursor_b.fetchall()
                                                                    cnxn.commit()
                                                                    
                                                                    name_odoo_temp = vals.get('name')
                                                                    name_a = False
                                                                    name_b = False
                                                                    ape_a = False
                                                                    ape_b = False

                                                                    if contacto_sgc:
                                                                        _logger.warning("Verificar la data del Contacto a editar desde Odoo a SGC")
                                                                        _logger.warning("Data a comparar: "+str(contacto_sgc))
                                                                        procede_edicion_sgc = False

                                                                        #Si el nombre y apellido en el SGC se encuentran en el nombre de Odoo no se modifica
                                                                        #el nombre ni el apellido en SGC.
                                                                        for item_sgc in contacto_sgc:
                                                                            nombres_sgc = item_sgc.get('nombre').split(" ")
                                                                            apellidos_sgc = item_sgc.get('apellido').split(" ")

                                                                            _logger.warning("Nombres SGC C: "+str(nombres_sgc))
                                                                            _logger.warning("Apellidos SGC C: "+str(apellidos_sgc))
                                                                            _logger.warning("Nombre Odoo: "+str(vals.get('name')))
                                                                            name_aa, name_bb, ape_aa, ape_bb = check_sgc_data.chequeos.MaestroChequeos.SplitNombres(vals['name'],"1")

                                                                            for item in nombres_sgc:
                                                                                #Verificar si existen los nombres en Odoo exactamente iguales.
                                                                                if item:
                                                                                    #Verificar si existen los nombres en Odoo exactamente iguales.
                                                                                    if not str(name_aa).find(str(item)) == -1 or not str(name_bb).find(str(item)) == -1:
                                                                                        _logger.warning("Nombre: "+str(item)+" encontrado en SGC!")
                                                                                    else:
                                                                                        #Se procede con la nueva edición del nombre desde Odoo hacia SGC.
                                                                                        procede_edicion_sgc = True
                                                                                else:
                                                                                    #Se procede con la nueva edición del nombre desde Odoo hacia SGC.
                                                                                    procede_edicion_sgc = True
                                                                            
                                                                            #Solo si pasó la verificación de los nombres es que verifica los apellidos.
                                                                            if not procede_edicion_sgc:
                                                                                for item in apellidos_sgc:
                                                                                    #Verificar si existen los nombres en Odoo exactamente iguales.
                                                                                    if item:
                                                                                        #Verificar si existen los nombres en Odoo exactamente iguales.
                                                                                        if not str(ape_aa).find(str(item)) == -1 or not str(ape_bb).find(str(item)) == -1:
                                                                                            _logger.warning("Apellido: "+str(item)+" encontrado en SGC!")
                                                                                        else:
                                                                                            #Se procede con la nueva edición del nombre desde Odoo hacia SGC.
                                                                                            procede_edicion_sgc = True
                                                                                    else:
                                                                                        #Se procede con la nueva edición del nombre desde Odoo hacia SGC.
                                                                                        procede_edicion_sgc = True

                                                                        if not procede_edicion_sgc:
                                                                            #De forma temporal se envía nombre y apellido segmentados a SGC
                                                                            #y luego se recupera su forma original antes de ser escritos en Odoo.
                                                                            vals['name'] = item_sgc['nombre']
                                                                            vals['apellido_contacto'] = item_sgc['apellido']
                                                                            
                                                                        else:
                                                                            _logger.warning("Procede la edición del nombre desde Odoo hacia SGC.")
                                                                            name_a, name_b, ape_a, ape_b = check_sgc_data.chequeos.MaestroChequeos.SplitNombres(self.name, "1")

                                                                            vals['name'] = name_a + " " + name_b
                                                                            vals['apellido_contacto'] = ape_a + " " + ape_b

                                                                    #Se debe crear una validación adicional que envíe valores vacíos en vez de la palabra false cuando
                                                                    #cree o modifique desde Odoo hacía SGC.

                                                                    if not vals['cedula_contacto']:
                                                                        #Se envía vacío.
                                                                        vals['cedula_contacto'] = ''
                                                                    if not vals['phone']:
                                                                        #Se envía vacío.
                                                                        vals['phone'] = ''
                                                                    if not vals['mobile']:
                                                                        #Se envía vacío.
                                                                        vals['mobile'] = ''
                                                                    if not vals['email']:
                                                                        #Se envía vacío.
                                                                        vals['email'] = ''
                                                                    if not vals['function']:
                                                                        #Se envía vacío.
                                                                        vals['function'] = ''

                                                                    params = (vals.get('id_contacto'),str(vals.get('name')),str(vals.get('apellido_contacto')),str(vals.get('cedula_contacto')),str(vals.get('phone')),str(vals.get('email')),str(vals.get('cargo_contacto')),vals.get('id_cliente'),int(vals.get('tipo_contacto')),vals.get('mobile'),vals.get('prioridad_contacto'),int(vals.get('ScalabilityLevel')))
                                                                    
                                                                    sgc_sucessfully_commit = False
                                                                    #Se ejecuta el stored procedure con el cursor
                                                                    rows = cursor_b.callproc('ModificarContacto', params)
                                                                    cnxn.commit()
                                                                    
                                                                    #Fix #11, Apellido del contacto repetido
                                                                    if name_a and ape_a:
                                                                        vals['name'] = name_a + " " + name_b + " " + ape_a + " " + ape_b
                                                                        vals['apellido_contacto'] = ape_a + " " + ape_b

                                                                    for row in rows:
                                                                        _logger.warning("Numero de filas afectadas: "+str(row))
                                                                        sgc_sucessfully_commit = True
                                                                        #Con solo el primer valor es suficiente :)
                                                                        break

                                                                    #Si la consulta afecto al menos a una fila entonces todo OK, si no lanza la alerta
                                                                    if not sgc_sucessfully_commit and not vals.get('create_from_sync'):
                                                                        if vals.get('revisar_id_contacto_sgc'):
                                                                            vals['revisar_id_contacto_sgc'] = False
                                                                        cnxn.close()
                                                                        raise ValidationError(_("Ninguna fila ha sido afectada, verifique con el Administrador del SGC sobre el proceso de modificación de este registro."))

                                                                    #Se hace falso para que al crear por sincronización no se haga un rechequeo innecesario.
                                                                    if vals.get('revisar_id_contacto_sgc'):
                                                                        vals['revisar_id_contacto_sgc'] = False
                                                                    
                                                                    #Si la edición resultó exitosa entonces se procede a recuperar el nombre original antes de guardar el contacto nuevo.
                                                                    vals['name'] = name_odoo_temp

                                                                    #Al editarse un contacto se debe reestablecer la data de los privilegios para garantizar que se mnatienen
                                                                    #siempre lo mas actualizado posible.
                                                                    #Se deben registrar tantos privilegios como se hayan establecido al momento de crear.
                                                                    stored_proc = """DELETE FROM Privilegio_Contacto WHERE fk_id_contacto = %s"""
                                                            
                                                                    params = (int(vals.get('id_contacto')))

                                                                    cursor_b.execute(stored_proc, params)
                                                                    #Se confirma la transacción desde Odoo hacia SGC.
                                                                    cnxn.commit()
                                                                    #cnxn.close()
                                                                    
                                                                    #Luego de eliminarse se vuelven a registrar en la tabla de privilegios.
                                                                    if vals.get('privilegio_ids'):

                                                                        for privilegio in vals['privilegio_ids']:
                                                                            _logger.warning("Privilegio: "+str(privilegio[2]))  
                                                                            
                                                                            #Se debe verificar qie el privilegio sea el correcto
                                                                            #antes de permitir registrarlo en la tabla de privilegios.

                                                                            #Se deben registrar tantos privilegios como se hayan establecido al momento de crear.
                                                                            stored_proc = """SET NOCOUNT ON exec [dbo].[AgregarPrivilegioContacto]
                                                                                                                        @privilegio = %s,
                                                                                                                        @contacto = %s"""
                                                                    
                                                                            params = (int(privilegio[2].get('name')),int(vals.get('id_contacto')))

                                                                            cursor_b.execute(stored_proc, params)
                                                                            #Se confirma la transacción desde Odoo hacia SGC.
                                                                            cnxn.commit()
                                                                            #cnxn.close()

                                                                    else:
                                                                        _logger.warning("Sin Privilegios")  
                                                                        
                                                                        #Se debe verificar qie el privilegio sea el correcto
                                                                        #antes de permitir registrarlo en la tabla de privilegios.

                                                                        #Se deben registrar tantos privilegios como se hayan establecido al momento de crear.
                                                                        stored_proc = """SET NOCOUNT ON exec [dbo].[AgregarPrivilegioContacto]
                                                                                                                    @privilegio = %s,
                                                                                                                    @contacto = %s"""
                                                                
                                                                        params = (int('5'),int(vals.get('id_contacto')))

                                                                        cursor_b.execute(stored_proc, params)
                                                                        #Se confirma la transacción desde Odoo hacia SGC.
                                                                        cnxn.commit()
                                                                        #cnxn.close()

                                                                    #La fecha de sincronización debe ser mayor que la fecha de modifcación del Contacto para evitar ejecutar una sincronización innecesaria.
                                                                    #Monitorear posible diferencia en segundos entre las fechas.
                                                                    stored_proc = """UPDATE [Contacto] SET DateSincronyzed = %s WHERE id_contacto = %s;"""
                                                                    params = (datetime.now() - timedelta(hours=4) + timedelta(minutes=1),int(vals.get('id_contacto')))

                                                                    cursor_b.execute(stored_proc, params)
                                                                    cnxn.commit()

                                                                    #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.
                                                                    vals['contacto_date_modified'] = datetime.now() + timedelta(minutes=1)

                                                                    #Se cierra la conexión para evitar congestiones por manejo automatico tarío o deficiente
                                                                    cursor_b.close()
                                                                    #cnxn.close()

                                                                    self.env['sgc.odoo.history'].create({
                                                                        'name': str(vals.get('name')),
                                                                        'fecha_registro': datetime.now(),
                                                                        'tipo_error': 'Sync Odoo --> SGC ('+str(vals.get('company_type_stored'))+')',
                                                                        'registro_operacion': 'Se ha editado correctamente el registro en SGC durante la creación de un contacto nuevo en Odoo.',
                                                                        'registro_tecnico': 'None',
                                                                        'category': '<p style="color:orange;">Edición de Contacto existente</p>',
                                                                    })

                                                                    _logger.warning("Se crea el registro en Odoo editando hacia SGC.")
                                                                    rec = super(DaycoExtrasContactos, self).create(vals)
                                                                    return rec

                                                            except pymssql.Error as e:
                                                                
                                                                procede_registro_nuevo = False
                                                                if vals.get('revisar_id_contacto_sgc'):
                                                                    vals['revisar_id_contacto_sgc'] = False
                                                                cursor_b.close()
                                                                cnxn.close()

                                                                _logger.warning("########## - FIN chequeo de la data modificada en contacto tipo Individual - ##########")
                                                                _logger.warning("########## - FIN chequeo de la data modificada en contacto tipo Individual - ##########")
                                                        
                                                                raise ValidationError(_("""Error al editar la data del nuevo Contacto, por favor, verifique e intente nuevamente.
                                                                                            Registro del error: 

                                                                                            """+str(e)+"""."""))

                                                        elif vals.get('id_cliente') and vals.get('cedula_contacto'):
                                                            #Se presenta el caso #2
                                                            _logger.warning("Caso #2 de edición durante la creación")

                                                            #Se debe verificar si existe un contacto en SGC con el ID Cliente asociado y la cedula del contacto
                                                            #Si se encuentra el contacto en la BD, se debe obtener su id contacto, modificar en sgc y guardar
                                                            #en Odoo con el ID Contacto recien adquirido.
                                                            cedula_contacto = vals.get('cedula_contacto')
                                                            
                                                            ip = self.env.company.ip_conexion_sgc
                                                            port = self.env.company.puerto_conexion_sgc
                                                            bd = self.env.company.bd_conexion_sgc
                                                            user = self.env.company.user_conexion_sgc
                                                            password = self.env.company.pass_conexion_sgc
                                                            
                                                            try:
                                                                # ENCRYPT defaults to yes starting in ODBC Driver 18. It's good to always specify ENCRYPT=yes on the client side to avoid MITM attacks.
                                                                cnxn = bd_connector.BdConnections.connect_to_bd(self,ip,port,bd,user,password)
                                                                #cnxn = bd_connector.BdConnections.connect_to_bd(self,'200.74.215.68','4022','Dayco_SGC','Odoo','Dayco2022$')

                                                                if not cnxn:
                                                                    _logger.warning("No se pudo conectar a la base de datos, verifique los errores de conexión en el log.")
                                                                    procede_registro_nuevo = False
                                                                    if vals.get('revisar_id_contacto_sgc'):
                                                                        vals['revisar_id_contacto_sgc'] = False
                                                                else:
                                                                    cursor_b = cnxn.cursor(as_dict=True)
                                                                    _logger.warning("Actualizando desde Odoo a SGC")
                                                                    
                                                                    #Select a la bd buscando el posible contacto relacionado
                                                                    #En caso de encontrarlo, procede_creacion_nueva = False
                                                                    #Si no lo encuentra, procede_creacion_nueva = True

                                                                    _logger.warning("Cédula a buscar: "+str(cedula_contacto))
                                                                    _logger.warning("ID Cliente a buscar: "+str(vals.get('id_cliente')))

                                                                    stored_proc = """SELECT id_contacto FROM [Contacto] WHERE fk_id_cliente = %s and cedula = %s;"""
                                                                    params = (int(vals.get('id_cliente')),cedula_contacto)

                                                                    cursor_b.execute(stored_proc, params)
                                                                    var_a = cursor_b.fetchone()
                                                                    cnxn.commit()
                                                                    
                                                                    if var_a:
                                                                        #Si se detectó registro existente en el SGC se debe actualizar
                                                                        _logger.warning("Var_a: "+str(var_a.get("id_contacto")))
                                                                        procede_registro_nuevo = False

                                                                        #Se obtiene el id contacto encontrado en la bd
                                                                        vals['id_contacto'] = var_a.get("id_contacto")

                                                                        #Fix del tipo de contacto por importación
                                                                        #Fix del campo 'Tipo contacto'
                                                                        #vals['tipo_contacto'] = str(vals.get('rol'))
                                                                        if str(vals['tipo_contacto']) == "1":
                                                                            vals['tipo_contacto'] = "3"
                                                                        elif str(vals['tipo_contacto']) == "2":
                                                                            vals['tipo_contacto'] = "2"
                                                                        elif str(vals['tipo_contacto']) == "3":
                                                                            vals['tipo_contacto'] = "1"
                                                                        else:
                                                                            vals['tipo_contacto'] = "1"

                                                                        #Se debe eliminar el '-' de la cédula si este lo posee.
                                                                        characters = '-'
                                                                        cedula_contacto = vals.get('cedula_contacto')
                                                                        if vals.get('cedula_contacto'):
                                                                            for x in range(len(characters)):
                                                                                cedula_contacto = cedula_contacto.replace(characters[x],"")
                                                                        vals['cedula_contacto'] = cedula_contacto

                                                                        #Se debe validar que campo cambió realmente antes de enviar la data
                                                                        #para mejorar la eficiencia del proceso de edición.
                                                                        _logger.warning("Cédula a buscar: "+str(cedula_contacto))
                                                                        _logger.warning("ID Cliente a buscar: "+str(vals.get('id_cliente')))

                                                                        stored_proc = """SELECT id_contacto, nombre, apellido FROM [Contacto] WHERE fk_id_cliente = %s and cedula = %s;"""
                                                                        params = (int(vals.get('id_cliente')),cedula_contacto)

                                                                        cursor_b.execute(stored_proc, params)
                                                                        contacto_sgc = cursor_b.fetchall()
                                                                        cnxn.commit()
                                                                        
                                                                        name_odoo_temp = vals.get('name')
                                                                        name_a = False
                                                                        name_b = False
                                                                        ape_a = False
                                                                        ape_b = False
                                                                        
                                                                        if contacto_sgc:
                                                                            _logger.warning("Verificar la data del Contacto a editar desde Odoo a SGC")
                                                                            _logger.warning("Data a comparar: "+str(contacto_sgc))
                                                                            procede_edicion_sgc = False

                                                                            #Si el nombre y apellido en el SGC se encuentran en el nombre de Odoo no se modifica
                                                                            #el nombre ni el apellido en SGC.
                                                                            for item_sgc in contacto_sgc:
                                                                                nombres_sgc = item_sgc.get('nombre').split(" ")
                                                                                apellidos_sgc = item_sgc.get('apellido').split(" ")

                                                                                _logger.warning("Nombres SGC D: "+str(nombres_sgc))
                                                                                _logger.warning("Apellidos SGC D: "+str(apellidos_sgc))
                                                                                _logger.warning("Nombre Odoo: "+str(vals.get('name')))
                                                                                name_aa, name_bb, ape_aa, ape_bb = check_sgc_data.chequeos.MaestroChequeos.SplitNombres(vals['name'],"1")

                                                                                for item in nombres_sgc:
                                                                                    #Verificar si existen los nombres en Odoo exactamente iguales.
                                                                                    if item:
                                                                                        #Verificar si existen los nombres en Odoo exactamente iguales.
                                                                                        if not str(name_aa).find(str(item)) == -1 or not str(name_bb).find(str(item)) == -1:
                                                                                            _logger.warning("Nombre: "+str(item)+" encontrado en SGC!")
                                                                                        else:
                                                                                            #Se procede con la nueva edición del nombre desde Odoo hacia SGC.
                                                                                            procede_edicion_sgc = True
                                                                                    else:
                                                                                        #Se procede con la nueva edición del nombre desde Odoo hacia SGC.
                                                                                        procede_edicion_sgc = True
                                                                                
                                                                                #Solo si pasó la verificación de los nombres es que verifica los apellidos.
                                                                                if not procede_edicion_sgc:
                                                                                    for item in apellidos_sgc:
                                                                                        #Verificar si existen los nombres en Odoo exactamente iguales.
                                                                                        if item:
                                                                                            #Verificar si existen los nombres en Odoo exactamente iguales.
                                                                                            if not str(ape_aa).find(str(item)) == -1 or not str(ape_bb).find(str(item)) == -1:
                                                                                                _logger.warning("Apellido: "+str(item)+" encontrado en SGC!")
                                                                                            else:
                                                                                                #Se procede con la nueva edición del nombre desde Odoo hacia SGC.
                                                                                                procede_edicion_sgc = True
                                                                                        else:
                                                                                            #Se procede con la nueva edición del nombre desde Odoo hacia SGC.
                                                                                            procede_edicion_sgc = True

                                                                            if not procede_edicion_sgc:
                                                                                #De forma temporal se envía nombre y apellido segmentados a SGC
                                                                                #y luego se recupera su forma original antes de ser escritos en Odoo.
                                                                                vals['name'] = item_sgc['nombre']
                                                                                vals['apellido_contacto'] = item_sgc['apellido']
                                                                                
                                                                            else:
                                                                                _logger.warning("Procede la edición del nombre desde Odoo hacia SGC.")
                                                                                name_a, name_b, ape_a, ape_b = check_sgc_data.chequeos.MaestroChequeos.SplitNombres(vals['name'],"1")

                                                                                vals['name'] = name_a + " " + name_b
                                                                                vals['apellido_contacto'] = ape_a + " " + ape_b

                                                                        #Se debe crear una validación adicional que envíe valores vacíos en vez de la palabra false cuando
                                                                        #cree o modifique desde Odoo hacía SGC.

                                                                        if not vals['cedula_contacto']:
                                                                            #Se envía vacío.
                                                                            vals['cedula_contacto'] = ''
                                                                        if not vals['phone']:
                                                                            #Se envía vacío.
                                                                            vals['phone'] = ''
                                                                        if not vals['mobile']:
                                                                            #Se envía vacío.
                                                                            vals['mobile'] = ''
                                                                        if not vals['email']:
                                                                            #Se envía vacío.
                                                                            vals['email'] = ''
                                                                        if not vals['function']:
                                                                            #Se envía vacío.
                                                                            vals['function'] = ''

                                                                        params = (vals.get('id_contacto'),str(vals.get('name')),str(vals.get('apellido_contacto')),str(vals.get('cedula_contacto')),str(vals.get('phone')),str(vals.get('email')),str(vals.get('cargo_contacto')),vals.get('id_cliente'),int(vals.get('tipo_contacto')),vals.get('mobile'),vals.get('prioridad_contacto'),int(vals.get('ScalabilityLevel')))

                                                                        sgc_sucessfully_commit = False

                                                                        #Se ejecuta el stored procedure con el cursor
                                                                        rows = cursor_b.callproc('ModificarContacto', params)
                                                                        cnxn.commit()

                                                                        #Fix #11, Apellido del contacto repetido
                                                                        if name_a and ape_a:
                                                                            vals['name'] = name_a + " " + name_b + " " + ape_a + " " + ape_b
                                                                            vals['apellido_contacto'] = ape_a + " " + ape_b

                                                                        for row in rows:
                                                                            _logger.warning("Numero de filas afectadas: "+str(row))
                                                                            sgc_sucessfully_commit = True
                                                                            #Con solo el primer valor es suficiente :)
                                                                            break

                                                                        #Si la consulta afecto al menos a una fila entonces todo OK, si no lanza la alerta
                                                                        if not sgc_sucessfully_commit and not vals.get('create_from_sync'):
                                                                            if vals.get('revisar_id_contacto_sgc'):
                                                                                vals['revisar_id_contacto_sgc'] = False
                                                                            cnxn.close()
                                                                            raise ValidationError(_("Ninguna fila ha sido afectada, verifique con el Administrador del SGC sobre el proceso de modificación de este registro."))

                                                                        #Se hace falso para que al crear por sincronización no se haga un rechequeo innecesario.
                                                                        if vals.get('revisar_id_contacto_sgc'):
                                                                            vals['revisar_id_contacto_sgc'] = False
                                                                        
                                                                        #Si la edición resultó exitosa entonces se procede a recuperar el nombre original antes de guardar el contacto nuevo.
                                                                        vals['name'] = name_odoo_temp
                                                                        
                                                                        #Al editarse un contacto se debe reestablecer la data de los privilegios para garantizar que se mnatienen
                                                                        #siempre lo mas actualizado posible.
                                                                        #Se deben registrar tantos privilegios como se hayan establecido al momento de crear.
                                                                        stored_proc = """DELETE FROM Privilegio_Contacto WHERE fk_id_contacto = %s"""
                                                                
                                                                        params = (int(vals.get('id_contacto')))

                                                                        cursor_b.execute(stored_proc, params)
                                                                        #Se confirma la transacción desde Odoo hacia SGC.
                                                                        cnxn.commit()
                                                                        #cnxn.close()
                                                                        
                                                                        #Luego de eliminarse se vuelven a registrar en la tabla de privilegios.
                                                                        if vals.get('privilegio_ids'):

                                                                            for privilegio in vals['privilegio_ids']:
                                                                                _logger.warning("Privilegio: "+str(privilegio[2]))  
                                                                                
                                                                                #Se debe verificar qie el privilegio sea el correcto
                                                                                #antes de permitir registrarlo en la tabla de privilegios.

                                                                                #Se deben registrar tantos privilegios como se hayan establecido al momento de crear.
                                                                                stored_proc = """SET NOCOUNT ON exec [dbo].[AgregarPrivilegioContacto]
                                                                                                                            @privilegio = %s,
                                                                                                                            @contacto = %s"""
                                                                        
                                                                                params = (int(privilegio[2].get('name')),int(vals.get('id_contacto')))

                                                                                cursor_b.execute(stored_proc, params)
                                                                                #Se confirma la transacción desde Odoo hacia SGC.
                                                                                cnxn.commit()
                                                                                #cnxn.close()

                                                                        else:
                                                                            _logger.warning("Sin Privilegios")  
                                                                            
                                                                            #Se debe verificar qie el privilegio sea el correcto
                                                                            #antes de permitir registrarlo en la tabla de privilegios.

                                                                            #Se deben registrar tantos privilegios como se hayan establecido al momento de crear.
                                                                            stored_proc = """SET NOCOUNT ON exec [dbo].[AgregarPrivilegioContacto]
                                                                                                                        @privilegio = %s,
                                                                                                                        @contacto = %s"""
                                                                    
                                                                            params = (int('5'),int(vals.get('id_contacto')))

                                                                            cursor_b.execute(stored_proc, params)
                                                                            #Se confirma la transacción desde Odoo hacia SGC.
                                                                            cnxn.commit()
                                                                            #cnxn.close()

                                                                        #La fecha de sincronización debe ser mayor que la fecha de modifcación del Contacto para evitar ejecutar una sincronización innecesaria.
                                                                        #Monitorear posible diferencia en segundos entre las fechas.
                                                                        stored_proc = """UPDATE [Contacto] SET DateSincronyzed = %s WHERE id_contacto = %s;"""
                                                                        params = (datetime.now() - timedelta(hours=4) + timedelta(minutes=1),int(vals.get('id_contacto')))

                                                                        cursor_b.execute(stored_proc, params)
                                                                        cnxn.commit()

                                                                        #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.
                                                                        vals['contacto_date_modified'] = datetime.now() + timedelta(minutes=1)

                                                                        #Se cierra la conexión para evitar congestiones por manejo automatico tarío o deficiente
                                                                        cursor_b.close()
                                                                        #cnxn.close()

                                                                        self.env['sgc.odoo.history'].create({
                                                                            'name': str(vals.get('name')),
                                                                            'fecha_registro': datetime.now(),
                                                                            'tipo_error': 'Sync Odoo --> SGC ('+str(vals.get('company_type_stored'))+')',
                                                                            'registro_operacion': 'Se ha editado correctamente el registro en SGC durante la creación de un contacto nuevo en Odoo.',
                                                                            'registro_tecnico': 'None',
                                                                            'category': '<p style="color:orange;">Edición de Contacto existente</p>',
                                                                        })

                                                                        _logger.warning("Se crea el registro en Odoo editando hacia SGC.")
                                                                        rec = super(DaycoExtrasContactos, self).create(vals)
                                                                        return rec
                                                                    else:
                                                                        _logger.warning("No se ha encontrado un contacto en SGC que contenga la cédula y ID Cliente indicados al momento de hacer el registro, se procede a registrar un nuevo contacto tanto en SGC como en Odoo.")
                                                                        procede_registro_nuevo = True
                                                                    #print(asdaqw)

                                                            except pymssql.Error as e:
                                                                
                                                                procede_registro_nuevo = False
                                                                if vals.get('revisar_id_contacto_sgc'):
                                                                    vals['revisar_id_contacto_sgc'] = False
                                                                cursor_b.close()
                                                                cnxn.close()

                                                                _logger.warning("########## - FIN chequeo de la data modificada en contacto tipo Individual - ##########")
                                                                _logger.warning("########## - FIN chequeo de la data modificada en contacto tipo Individual - ##########")
                                                        
                                                                raise ValidationError(_("""Error al editar la data del nuevo Contacto, por favor, verifique e intente nuevamente.
                                                                                            Registro del error: 

                                                                                            """+str(e)+"""."""))

                                                    if procede_registro_nuevo:
                                                        #Caso #3, creación manual sin plantilla
                                                        _logger.warning("Caso #3, Creacion manual sin plantilla.")
                                                        
                                                        stored_proc = """SET NOCOUNT ON exec [dbo].[AgregarContacto]
                                                                                                        @nombre = %s,
                                                                                                        @apellido = %s,
                                                                                                        @cedula = %s,
                                                                                                        @telefono = %s,
                                                                                                        @email = %s,
                                                                                                        @cargo = %s,
                                                                                                        @id_cliente = %s,
                                                                                                        @id_tipo = %s,
                                                                                                        @celular = %s,
                                                                                                        @prioridad = %s,
                                                                                                        @ScalabilityLevelId = %s"""

                                                        #Fix #11, Apellido del contacto repetido
                                                        #vals['apellido_contacto'] = '*'
                                                        name_a, name_b, ape_a, ape_b = check_sgc_data.chequeos.MaestroChequeos.SplitNombres(vals['name'],"1")

                                                        vals['name'] = name_a + " " + name_b
                                                        vals['apellido_contacto'] = ape_a + " " + ape_b
                                                        
                                                        #Se debe crear una validación adicional que envíe valores vacíos en vez de la palabra false cuando
                                                        #cree o modifique desde Odoo hacía SGC.

                                                        if not vals['cedula_contacto']:
                                                            #Se envía vacío.
                                                            vals['cedula_contacto'] = ''
                                                        if not vals['phone']:
                                                            #Se envía vacío.
                                                            vals['phone'] = ''
                                                        if not vals['mobile']:
                                                            #Se envía vacío.
                                                            vals['mobile'] = ''
                                                        if not vals['email']:
                                                            #Se envía vacío.
                                                            vals['email'] = ''
                                                        if not vals['function']:
                                                            #Se envía vacío.
                                                            vals['function'] = ''

                                                        #Hotfix #26: Ajuste del rol desde Odoo hacia SGC.
                                                        if str(vals['tipo_contacto']) == "1":
                                                            vals['tipo_contacto'] = "3"
                                                        elif str(vals['tipo_contacto']) == "2":
                                                            vals['tipo_contacto'] = "2"
                                                        elif str(vals['tipo_contacto']) == "3":
                                                            vals['tipo_contacto'] = "1"
                                                        else:
                                                            vals['tipo_contacto'] = "1"

                                                        params = (str(vals['name']),str(vals['apellido_contacto']),str(vals['cedula_contacto']),str(vals['phone']),str(vals['email']),str(vals['function']),int(vals['id_cliente']),int(vals['tipo_contacto']),str(vals['mobile']),int(vals['prioridad_contacto']),int(vals['ScalabilityLevel']))
                                                    
                                                        #Se ejecuta el stored procedure con el cursor
                                                        cursor_b.execute(stored_proc, params)
                                                        var_a = cursor_b.fetchone()
                                                        cnxn.commit()
                                                        #cnxn.close()

                                                        _logger.warning("Var_a: "+str(var_a.get("ReturnId")))
                                                        
                                                        #Despues de ejecutar se establece el nombre correcto en Odoo
                                                        vals['name'] = name_a + " " + name_b + " " + ape_a + " " + ape_b
                                                        vals['apellido_contacto'] = ape_a + " " + ape_b

                                                        #Si se creó correctamente el registro en la BD se procede a salvar el contacto en Odoo
                                                        if not var_a.get("ReturnId") > 0:
                                                            cursor_b.close()
                                                            cnxn.close()
                                                            raise ValidationError(_("Ninguna fila ha sido afectada/insertada, verifique con el Administrador del SGC sobre el proceso de modificación/creación de registros."))
                                                        else:
                                                            _logger.warning("Contacto (Individual) registrado con exito!")
                                                    
                                                            #La fecha de sincronización debe ser mayor que la fecha de modifcación del Contacto para evitar ejecutar una sincronización innecesaria.
                                                            #Monitorear posible diferencia en segundos entre las fechas.

                                                            #Se debe agregar la condición para el datesincronyzed y los privilegios.

                                                        if not vals['parent_id'] and vals['facturable'] and str(vals['partner_type_id']) == str(sharehosting_id.id):
                                                            _logger.warning("Se actualiza fecha en tabla Cliente y no se actualizan privilegios.")
                                                            #La fecha de sincronización debe ser mayor que la fecha de modifcación del Contacto para evitar ejecutar una sincronización innecesaria.
                                                            #Monitorear posible diferencia en segundos entre las fechas.
                                                            stored_proc = """UPDATE [Cliente] SET DateSincronyzed = %s WHERE id_cliente = %s;"""
                                                            params = (datetime.now() - timedelta(hours=4),int(var_a.get("ReturnId")))

                                                            cursor_b.execute(stored_proc, params)
                                                            cnxn.commit()

                                                        else:
                                                            stored_proc = """UPDATE [Contacto] SET DateSincronyzed = %s WHERE id_contacto = %s;"""
                                                            params = (datetime.now() - timedelta(hours=4),int(var_a.get("ReturnId")))

                                                            cursor_b.execute(stored_proc, params)
                                                            cnxn.commit()

                                                            #Se debe registrar el contacto con los privilegios indicados por el Usuario al crear el contacto.
                                                            _logger.warning(vals)
                                                            if not vals['check_privilegios_label'] == "Sin privilegios":
                                                            #if vals['privilegio_ids']:

                                                                try:
                                                                    for privilegio in vals['privilegio_ids']:
                                                                        _logger.warning("Privilegio: "+str(privilegio[2].get("name"))) 
                                                                        #_logger.warning("Privilegio: "+str(privilegio.name))  
                                                                    
                                                                        #Se debe verificar qie el privilegio sea el correcto
                                                                        #antes de permitir registrarlo en la tabla de privilegios.

                                                                        #Se deben registrar tantos privilegios como se hayan establecido al momento de crear.
                                                                        stored_proc = """SET NOCOUNT ON exec [dbo].[AgregarPrivilegioContacto]
                                                                                                                    @privilegio = %s,
                                                                                                                    @contacto = %s"""
                                                            
                                                                        params = (int(privilegio[2].get("name")),int(var_a.get("ReturnId")))

                                                                        cursor_b.execute(stored_proc, params)
                                                                        #Se confirma la transacción desde Odoo hacia SGC.
                                                                        cnxn.commit()
                                                                        #cnxn.close()
                                                                except pymssql.Error as e:
                                                                    cursor_b.close()
                                                                    cnxn.close()

                                                                    raise ValidationError(_("""Error al registrar la data del nuevo Contacto, por favor, verifique e intente nuevamente.
                                                                                                Registro del error: 

                                                                                                """+str(e)+"""."""))

                                                            else:
                                                                _logger.warning("Sin Privilegios")  
                                                            
                                                                #Se debe verificar qie el privilegio sea el correcto
                                                                #antes de permitir registrarlo en la tabla de privilegios.
                                                            
                                                                try:
                                                                    #Se deben registrar tantos privilegios como se hayan establecido al momento de crear.
                                                                    stored_proc = """SET NOCOUNT ON exec [dbo].[AgregarPrivilegioContacto]
                                                                                                                @privilegio = %s,
                                                                                                                @contacto = %s"""
                                                        
                                                                    params = (int('5'),int(var_a.get("ReturnId")))

                                                                    cursor_b.execute(stored_proc, params)
                                                                    #Se confirma la transacción desde Odoo hacia SGC.
                                                                    cnxn.commit()
                                                                    #cnxn.close()
                                                                except pymssql.Error as e:
                                                                    cursor_b.close()
                                                                    cnxn.close()

                                                                    raise ValidationError(_("""Error al registrar la data del nuevo Contacto, por favor, verifique e intente nuevamente.
                                                                                                Registro del error: 

                                                                                                """+str(e)+"""."""))

                                                        #Se hace falso para que al crear por sincronización no se haga un rechequeo innecesario.
                                                        if vals['parent_id']:
                                                            vals['revisar_id_contacto_sgc'] = False

                                                            #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.
                                                            vals['contacto_date_modified'] = datetime.now() + timedelta(minutes=1)

                                                            #Una vez creado el contacto, procedemos a establecer el id que retorna el SGC.
                                                            vals['id_contacto'] = var_a.get("ReturnId")
                                                            
                                                            self.env['sgc.odoo.history'].create({
                                                                                                'name': str(vals['name']),
                                                                                                'fecha_registro': datetime.now(),
                                                                                                'tipo_error': 'Sync Odoo --> SGC ('+str(vals.get("company_type_stored"))+')',
                                                                                                'registro_operacion': 'Se ha creado correctamente el registro.',
                                                                                                'registro_tecnico': 'None',
                                                                                                'category': '<p style="color:green;">Creación de Contacto</p>',
                                                                                            })

                                                        elif not vals['parent_id'] and vals['facturable'] and str(vals['partner_type_id']) == str(sharehosting_id.id):
                                                            vals['revisar_id_cliente_sgc'] = False

                                                            #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.
                                                            vals['client_date_modified'] = datetime.now() + timedelta(minutes=1)

                                                            #Una vez creado el contacto, procedemos a establecer el id que retorna el SGC.
                                                            vals['id_cliente'] = var_a.get("ReturnId")

                                                            self.env['sgc.odoo.history'].create({
                                                                                                'name': str(vals['name']),
                                                                                                'fecha_registro': datetime.now(),
                                                                                                'tipo_error': 'Sync Odoo --> SGC ('+str(vals.get("company_type_stored"))+')',
                                                                                                'registro_operacion': 'Se ha creado correctamente el registro.',
                                                                                                'registro_tecnico': 'None',
                                                                                                'category': '<p style="color:green;">Creación de Cliente Sharehosting</p>',
                                                                                            })

                                                        #Solo debe proceder la creación del contacto si se cumplen las condiciones en Odoo,
                                                        #y al mismo tiempo se cumple el registro en la BD del SGC.
                                                        procede = True
                                                        cnxn.close()
                                                        cursor_b.close()
                                                
                                                except pymssql.Error as e:
                                                    cursor_b.close()
                                                    cnxn.close()

                                                    raise ValidationError(_("""Error al registrar la data del nuevo Contacto, por favor, verifique e intente nuevamente.
                                                                                Registro del error: 

                                                                                """+str(e)+"""."""))

                                            else:
                                                _logger.warning("No se ha establecido la escalabilidad")
                                        else:
                                            _logger.warning("No se ha establecido un tipo de contacto correctamente")
                                    else:
                                        _logger.warning("No se ha establecido un id_cliente valido de una compañía")
                                else:
                                    _logger.warning("No se ha habilitado el contacto (individual)")
                                    #else:
                                    #    _logger.warning("No se ha establecido un cargo")

                                #else:
                                #    _logger.warning("No se ha establecido un telefono secundario")
                            else:
                                _logger.warning("No se ha establecido un telefono principal ni uno secundario.")
                            #else:
                            #    _logger.warning("No se ha establecido una cédula")
                        else:
                            _logger.warning("No se ha establecido un apellido")
                    
                    elif str(vals.get("company_type")) == "company":
                        _logger.warning("########## - Se va a crear un Cliente (Compañía) en SGC - ##########")

                        procede = False

                        #Validaciones prioritarias
                        #1- RIF repetido en caso de ser un registro tipo compañía.

                        contactos_rif_repetido = self.env['res.partner'].search([('vat', '=', vals.get('vat')),('company_type_stored', '!=', 'person')])

                        if contactos_rif_repetido:
                            for contacto in contactos_rif_repetido:
                                _logger.warning("Registro con rif repetido, no procede el registro.")
                                raise ValidationError(_("""Ya existe un registro con el mismo RIF o Cédula de identidad: 
                                                            """+str(contacto.name)+"""
                                                            """+str(contacto.vat)+"""
                                                            """+str(contacto.email)+"""
                                                            """+str(contacto.identification_id)+"""
                                                            Por favor, verifique e intente nuevamente."""))

                        #Se debe agregar validaciones adicionales para el vat y evitar registros indeseados :)
                        if str(vals.get('vat')).count("-") > 1:
                            _logger.warning("Se ha encontrado mas de un guion en el rif, debe verificar su formato.")
                            raise ValidationError(_("""Los formatos validos de RIF son los siguientes:
                                                        J-123456789
                                                        G-123456789
                                                        E-123456789
                                                        
                                                        Por favor verifique e intente nuevamente."""))

                        sharehosting_id = self.env['partner.type'].search([('name', '=', 'Sharehosting')], limit=1)

                        #Condición valida solo para Clientes Sharehosting sin etiquetas en el campo Categorías
                        if not vals.get('tipo_cliente') and vals.get('company_type') == "company" and str(vals.get('partner_type_id')) == str(sharehosting_id.id):
                            _logger.warning("Cliente tipo Sharehosting detectado, se establece etiqueta para el SGC: Cliente de valor.")
                            vals['tipo_cliente'] = '1'

                        #Se verifican los campos del contacto (Individual) antes de insertar.
                        if vals.get("direccion_facturacion"):
                            _logger.warning("Se ha establecido una dirección de facturación")

                            if vals.get("street"):
                                _logger.warning("Se ha establecido una dirección secundaria")

                                if vals.get("vat"):
                                    _logger.warning("Se ha establecido un RIF correctamente")

                                    if vals.get("phone") or vals.get("mobile"):
                                        _logger.warning("Se ha establecido un telefono principal")

                                        #if vals.get("mobile"):
                                        #    _logger.warning("Se ha establecido un telefono secundario")

                                        if vals.get("fax_cliente"):
                                            _logger.warning("Se ha establecido un fax del Cliente")

                                            if vals.get("city"):
                                                _logger.warning("Se ha establecido una ciudad")

                                                #Descartado por no ser necesario en todos los casos existentes.
                                                #if vals.get("zip"):
                                                #    _logger.warning("Se ha establecido un código postal")

                                                if vals.get("tipo_negocio_cliente"):
                                                    _logger.warning("Se ha establecido un tipo de negocio de cliente")

                                                    if vals.get("categoria_cliente"):
                                                        _logger.warning("Se ha establecido una categoría de Cliente")

                                                        if vals.get("tipo_cliente"):
                                                            _logger.warning("Se ha establecido un tipo de Cliente")

                                                            if vals.get("unidad_negocio_cliente"):
                                                                _logger.warning("Se ha establecido una unidad de negocio de Cliente")

                                                                if vals.get("tipo_cliente_corporativo"):
                                                                    _logger.warning("Se ha establecido un tipo de Cliente corporativo")

                                                                    if vals.get("municipio_cliente"):
                                                                        _logger.warning("Se ha establecido un municipio")

                                                                        if vals.get("cliente_activo"):
                                                                            _logger.warning("Se ha activado al cliente")
                                                                            
                                                                            #if vals.get("account_management_id_sgc"):
                                                                            #    _logger.warning("Se ha establecido un accountmanagementid")

                                                                            #Se procede una vez pasadas todas las validaciones necesarias
                                                                            #a registrar al cliente nuevo.

                                                                            #Una vez se cumplen todas las verificaciones se procede con el envío
                                                                            #de datos hacía el SGC.

                                                                            #Una vez modificada la fecha se procede a insertar la nueva data en el SGC.
                                                                            ip = self.env.company.ip_conexion_sgc
                                                                            port = self.env.company.puerto_conexion_sgc
                                                                            bd = self.env.company.bd_conexion_sgc
                                                                            user = self.env.company.user_conexion_sgc
                                                                            password = self.env.company.pass_conexion_sgc

                                                                            try:
                                                                                # ENCRYPT defaults to yes starting in ODBC Driver 18. It's good to always specify ENCRYPT=yes on the client side to avoid MITM attacks.
                                                                                cnxn = bd_connector.BdConnections.connect_to_bd(self,ip,port,bd,user,password)
                                                                                #cnxn = bd_connector.BdConnections.connect_to_bd(self,'200.74.215.68','4022','Dayco_SGC','Odoo','Dayco2022$')
                                                                                #--> Solo debug, sin clave ni puerto definido: bd_connector.BdConnections.connect_to_bd(None,'10.0.1.168','Dayco_SGC','Odoo','Dayco2022$')

                                                                                #Se debe establecer el parámetro SET NOCOUNT ON para que funcione correctamente
                                                                                #https://stackoverflow.com/questions/7753830/mssql2008-pyodbc-previous-sql-was-not-a-query

                                                                                cursor_b = cnxn.cursor(as_dict=True)
                                                                                _logger.warning("Registrando desde Odoo a SGC")
                                                                                                                            
                                                                                stored_proc = """ SET NOCOUNT ON exec [dbo].[AgregarCliente]
                                                                                                                            @nombre = %s,
                                                                                                                            @rif = %s,
                                                                                                                            @direccion = %s,
                                                                                                                            @unidadNegocios = %s,
                                                                                                                            @telefono = %s,
                                                                                                                            @fax = %s,
                                                                                                                            @ciudad = %s,
                                                                                                                            @codigoPostal = %s,
                                                                                                                            @tipoCliente = %s,
                                                                                                                            @idClienteCorp = %s,
                                                                                                                            @idTipoNegocio = %s,
                                                                                                                            @idCategoria = %s,
                                                                                                                            @idMunicipio = %s,
                                                                                                                            @direccion2 = %s,
                                                                                                                            @telefono2 = %s,
                                                                                                                            @AccountManagementId = %s"""

                                                                                #Se debe eliminar el '-' del rif si este lo posee.
                                                                                characters = '-'
                                                                                if vals['rif_cliente']:
                                                                                    for x in range(len(characters)):
                                                                                        vals['rif_cliente'] = vals['rif_cliente'].replace(characters[x],"")
                                                                                
                                                                                if vals['cedula_contacto']:
                                                                                    for x in range(len(characters)):
                                                                                        vals['cedula_contacto'] = vals['cedula_contacto'].replace(characters[x],"")
                                                                                
                                                                                #if not vals['contacto_date_modified']:
                                                                                #    vals['contacto_date_modified'] = datetime.now()

                                                                                #Se debe convertir el tipo de cliente a un entero aceptable para el SGC
                                                                                if vals['tipo_contacto'] == 1:
                                                                                    _logger.warning("Cambiar por el status correcto en SGC")

                                                                                _logger.warning("Gerente de cuenta: "+str(int(vals['account_management_id_sgc'])))
                                                                                
                                                                                #Se debe crear una validación adicional que envíe valores vacíos en vez de la palabra false cuando
                                                                                #cree o modifique desde Odoo hacía SGC.

                                                                                if not vals['phone']:
                                                                                    #Se envía vacío.
                                                                                    vals['phone'] = ''
                                                                                if not vals['mobile']:
                                                                                    #Se envía vacío.
                                                                                    vals['mobile'] = ''
                                                                                if not vals['fax_cliente']:
                                                                                    #Se envía vacío.
                                                                                    vals['fax_cliente'] = ''
                                                                                if not vals['city']:
                                                                                    #Se envía vacío.
                                                                                    vals['city'] = ''
                                                                                if not vals['zip']:
                                                                                    #Se envía vacío.
                                                                                    vals['zip'] = ''

                                                                                params = ''
                                                                                #Si retorna cero es porque se le pasó una cadena vacía o un cero en efecto, si no entonces si pasas el número.
                                                                                if int(vals['account_management_id_sgc']) > 0:
                                                                                    params = (str(vals['name']),str(vals['rif_cliente']),str(vals['street']),int(vals['unidad_negocio_cliente']),str(vals['phone']),str(vals['fax_cliente']),vals['city'],str(vals['zip']),int(vals['tipo_cliente']),int(vals['tipo_cliente_corporativo']),int(vals['tipo_negocio_cliente']),int(vals['categoria_cliente']),int(vals['municipio_cliente']),vals['direccion_facturacion'],vals['mobile'],int(vals['account_management_id_sgc']))
                                                                                else:
                                                                                    _logger.warning("Se envía NULL")
                                                                                    params = (str(vals['name']),str(vals['rif_cliente']),str(vals['street']),int(vals['unidad_negocio_cliente']),str(vals['phone']),str(vals['fax_cliente']),vals['city'],str(vals['zip']),int(vals['tipo_cliente']),int(vals['tipo_cliente_corporativo']),int(vals['tipo_negocio_cliente']),int(vals['categoria_cliente']),int(vals['municipio_cliente']),vals['direccion_facturacion'],vals['mobile'],None)
                                                                        
                                                                                #Se ejecuta el stored procedure con el cursor
                                                                                cursor_b.execute(stored_proc, params)
                                                                                var_a = cursor_b.fetchone()
                                                                                cnxn.commit()

                                                                                _logger.warning("Var_a: "+str(var_a))
                                                                                
                                                                                #Si se creó correctamente el registro en la BD se procede a salvar el Cliente en Odoo
                                                                                if not var_a.get("ReturnId") > 0:
                                                                                    cnxn.close()
                                                                                    raise ValidationError(_("Ninguna fila ha sido afectada/insertada, verifique con el Administrador del SGC sobre el proceso de modificación/creación de registros."))
                                                                                else:
                                                                                    _logger.warning("Contacto (Compañía) registrado con exito!")
                                                                                    
                                                                                    #Fix tipo de contacto en caso de registrarse un Cliente
                                                                                    vals['tipo_contacto'] = str(1)

                                                                                    #La fecha de sincronización debe ser mayor que la fecha de modifcación del Contacto para evitar ejecutar una sincronización innecesaria.
                                                                                    #Monitorear posible diferencia en segundos entre las fechas.
                                                                                    stored_proc = """UPDATE [Cliente] SET DateSincronyzed = %s WHERE id_cliente = %s;"""
                                                                                    params = (datetime.now() - timedelta(hours=4),int(var_a.get("ReturnId")))

                                                                                    cursor_b.execute(stored_proc, params)
                                                                                    cnxn.commit()

                                                                                    #Se hace falso para que al crear por sincronización no se haga un rechequeo innecesario.
                                                                                    vals['revisar_id_cliente_sgc'] = False

                                                                                    #Se debe actualizar la fecha de edición del Cliente / Contacto para que funcione correctamente la sincronización.
                                                                                    vals['client_date_modified'] = datetime.now() + timedelta(minutes=1)

                                                                                    #Una vez creado el contacto, procedemos a establecer el id que retorna el SGC.
                                                                                    vals['id_cliente'] = var_a.get("ReturnId")

                                                                                    #Solo debe proceder la creación del contacto si se cumplen las condiciones en Odoo,
                                                                                    #y al mismo tiempo se cumple el registro en la BD del SGC.
                                                                                    procede = True
                                                                                    cursor_b.close()
                                                                                    cnxn.close()

                                                                                    self.env['sgc.odoo.history'].create({
                                                                                                'name': str(vals['name']),
                                                                                                'fecha_registro': datetime.now(),
                                                                                                'tipo_error': 'Sync Odoo --> SGC ('+str(vals.get("company_type_stored"))+')',
                                                                                                'registro_operacion': 'Se ha creado correctamente el registro.',
                                                                                                'registro_tecnico': 'None',
                                                                                                'category': '<p style="color:green;">Creación de Cliente tipo compañía</p>',
                                                                                            })

                                                                                #else:
                                                                                #    _logger.warning("No se ha establecido un accountmanagementid")
                                                                            except pymssql.Error as e:
                                                                                cursor_b.close()
                                                                                cnxn.close()

                                                                                raise ValidationError(_("""Error al registrar la data del nuevo Cliente, por favor, verifique e intente nuevamente.
                                                                                                            Registro del error: 

                                                                                                            """+str(e)+"""."""))

                                                                        else:
                                                                            _logger.warning("No se ha activado al cliente")
                                                                    else:
                                                                        _logger.warning("No se ha establecido un municipio")
                                                                else:
                                                                    _logger.warning("No se ha establecido un tipo de Cliente corporativo")
                                                            else:
                                                                _logger.warning("No se ha establecido una unidad de negocio de Cliente")
                                                        else:
                                                            _logger.warning("No se ha establecido un tipo de Cliente")
                                                    else:
                                                        _logger.warning("No se ha establecido una categoría de Cliente")
                                                else:
                                                    _logger.warning("No se ha establecido un tipo de negocio de cliente")
                                                #else:
                                                #    _logger.warning("No se ha establecido un código postal")
                                            else:
                                                _logger.warning("No se ha establecido una ciudad")
                                        else:
                                            _logger.warning("No se ha establecido un fax del Cliente")
                                        #else:
                                        #    _logger.warning("No se ha establecido un telefono secundario")
                                    else:
                                        _logger.warning("No se ha establecido un teléfono principal ni uno secundario correctamente")
                                else:
                                    _logger.warning("No se ha establecido un RIF correctamente")
                            else:
                                _logger.warning("No se ha establecido una dirección secundaria")
                        else:
                            _logger.warning("No se ha establecido una dirección de facturación")
                else:
                    #Hot fix #13: Se permite la creación sin sincronizar de Clientes y contactos con la
                    #categoría "Otros", "Empleados" y "Proveedor"
                    if str(vals.get('cliente_partner_category')) == '2' or str(vals.get('cliente_partner_category')) == '4' or str(vals.get('cliente_partner_category')) == '5':
                        _logger.warning("Registro tipo: "+str(vals.get('cliente_partner_category'))+" detectado, no se sincroniza hacia el SGC.")

                    _logger.warning("Se crea el registro en Odoo sin sincronización hacia SGC.")
                    rec = super(DaycoExtrasContactos, self).create(vals)
                    return rec
                    
                if procede:
                    rec = super(DaycoExtrasContactos, self).create(vals)
                else:
                    _logger.warning("Data errada: "+str(vals))
                    raise ValidationError(_("""Error al registrar la data, verifique e intente nuevamente.
                                            Para los Contactos nuevos se requiere la siguiente data:
                                                    Nombre(Obligatorio): """+str(vals.get('name'))+"""
                                                    Apellido: """+str(vals.get('apellido_contacto'))+"""
                                                    Nro. de documento de identidad (Obligatorio solo en caso Sharehosting): """+str(vals.get('cedula_contacto'))+"""
                                                    Telefono principal(Obligatorio): """+str(vals.get('phone'))+"""
                                                    Telefono secundario (Opcional): """+str(vals.get('mobile'))+"""
                                                    Cargo (Opcional): """+str(vals.get('function'))+"""
                                                    Contacto habilitado (Por defecto 1): """+str(vals.get('habilitado_contacto'))+"""
                                                    ID del Cliente SGC asociado: """+str(vals.get('id_cliente'))+"""
                                                    Tipo de contacto (x_studio_rol (Campo rol) --> Obligatorio): """+str(vals.get('tipo_contacto'))+"""
                                                    Scalability Level ID: """+str(vals.get('ScalabilityLevel'))+"""

                                                    Para los Clientes se requiere la siguiente data:
                                                    Nombre: """+str(vals.get('name'))+"""
                                                    RIF(Obligatorio): """+str(vals.get('vat'))+"""
                                                    Telefono principal(Obligatorio): """+str(vals.get('phone'))+"""
                                                    Telefono secundario (Opcional): """+str(vals.get('mobile'))+"""
                                                    Cargo (Opcional): """+str(vals.get('function'))+"""
                                                    Dirección de facturación(Obligatorio): """+str(vals.get('direccion_facturacion'))+"""
                                                    Calle (Obligatorio, igual a la dirección de facturación para SGC)
                                                    Ciudad (Obligatorio): """+str(vals.get('ciudad_contacto'))+"""
                                                    Tipo de negocio del Cliente: """+str(vals.get('tipo_negocio_cliente'))+"""
                                                    Categoría del Cliente: """+str(vals.get('categoria_cliente'))+"""
                                                    Tipo de Cliente: """+str(vals.get('tipo_cliente'))+""""""""+str(vals.get('category_id'))+""""
                                                    Unidad de negocio del Cliente: """+str(vals.get('unidad_negocio_cliente'))+"""
                                                    Tipo de Cliente corporativo: """+str(vals.get('tipo_cliente_corporativo'))+"""
                                                    Municipio del Cliente: """+str(vals.get('municipio_cliente'))+"""
                                                    Cliente activo: """+str(vals.get('cliente_activo'))+"""
                                                """))

                #_logger.warning("########## FIN VERIFICACIÓN POR CREATE ##########")
                #_logger.warning("########## FIN VERIFICACIÓN POR CREATE ##########")
                return rec
            
            else:
                #_logger.warning("########## FIN VERIFICACIÓN POR CREATE ##########")
                #_logger.warning("########## FIN VERIFICACIÓN POR CREATE ##########")
                #_logger.warning("Fecha desde SGC Cliente (Sincronización): "+str(vals['client_date_modified']))
                
                #En caso de que el nivel de escalabilidad venga n null se coloca por defecto en 1.
                if not vals['ScalabilityLevel'] or vals['ScalabilityLevel'] == None or vals['ScalabilityLevel'] == 'None':
                    vals['ScalabilityLevel'] = '1'

                #En caso de que la fecha desde el SGC provenga en NULL
                if not vals['contacto_date_modified'] or vals['contacto_date_modified'] == None:
                    vals['contacto_date_modified'] = datetime.now() - timedelta(hours=4)
                
                if not vals['client_date_modified'] or vals['client_date_modified'] == None:
                    vals['client_date_modified'] = datetime.now() - timedelta(hours=4)

                #_logger.warning("Fecha desde SGC Contacto (Sincronización): "+str(vals['contacto_date_modified']))
                return super(DaycoExtrasContactos, self).create(vals)
        else:
            _logger.warning("Registro ignorado, ya existe en la data de Odoo")
            raise ValidationError(_("""Ya existe un registro con el mismo RIF o Cédula de identidad: 
                                        """+str(registro_repetido.name)+"""
                                        """+str(registro_repetido.vat)+"""
                                        """+str(registro_repetido.email)+"""
                                        """+str(registro_repetido.identification_id)+"""
                                        Por favor, verifique e intente nuevamente."""))

    #@api.constrains('name')
    def check_contact_in_sgc(self):
        _logger.warning("########## - INICIO Revisión de registro nuevo en res.partner - ##########")
        _logger.warning("########## - INICIO Revisión de registro nuevo en res.partner - ##########")
        
        #Este contacto puede presentar los siguientes casos:
        #1- El contacto es tipo individuo y no tiene compañía relacionada
        #En ese caso se debe verificar solo la cédula del contacto tipo individuo

        #2- El contacto es tipo individuo y tiene compañia relacionada
        #En este caso se debe verificar la cédula del contacto tipo individuo y el rif de la compañía relacionada

        #3- El contacto es tipo compañía
        #En este caso se debe verificar el rif de la compañía

        #Se debe estudiar una condición especial que permita omitir esta verificación cuando se cree mediante el
        #método de sincronización.
        if self.create_from_sync:
            #No se ejecuta la revisión
            _logger.warning("Se esta creando por la sincronización, no es necesario verificar datos.")

        else:
            #Se deben verificar los distintos casos
            _logger.warning("Se verifican los distintos casos planteados.")


        _logger.warning("########## - FIN Revisión de contacto nuevo - ##########")
        _logger.warning("########## - FIN Revisión de contacto nuevo - ##########")

    #Función a ejecutar usando un cron job.
    @api.model
    def sync_clientes_contactos_cron(self):
        _logger.warning("########## - Ejecución cada 20 segundos - ##########")
        _logger.warning("########## - Ejecución cada 20 segundos - ##########")
        _logger.warning("########## - Ejecución cada 20 segundos - ##########")
        
        #Solo debug, se establece un tiempo inicial y se resta de otro definido al final de las funciones
        #aqui definidas para saber cual es el rendimiento de las mismas en entornos de prueba, qa y producción.

        start_time = time()
        
        #Se obtienen los datos de conexión SGC desde la ficha de la compañía.
        ip = self.env.company.ip_conexion_sgc
        port = self.env.company.puerto_conexion_sgc
        bd = self.env.company.bd_conexion_sgc
        user = self.env.company.user_conexion_sgc
        password = self.env.company.pass_conexion_sgc

        # ENCRYPT defaults to yes starting in ODBC Driver 18. It's good to always specify ENCRYPT=yes on the client side to avoid MITM attacks.
        cnxn = bd_connector.BdConnections.connect_to_bd(self,ip,port,bd,user,password)
        #cnxn = bd_connector.BdConnections.connect_to_bd(self,'200.74.215.68','4022','Dayco_SGC','Odoo','Dayco2022$')

        if not cnxn:
            _logger.warning("No se pudo conectar a la base de datos, verifique los errores de conexión en el log.")
        else:
            cursor = cnxn.cursor(as_dict=True)
            
            if self.env.company.fecha_ultima_sincronizacion:
                fecha_last_sync = self.env.company.fecha_ultima_sincronizacion - timedelta(hours=4)
                fecha_revision = fecha_last_sync.strftime("%Y-%m-%dT%H:%M:%SZ")

                #Se indica desde que fecha se va a verificar la data.
                _logger.warning("Se va a revisar la data registrada a partir de la fecha: "+str(fecha_revision))
                #_logger.warning("Un día anterior a la fecha de la última sincronización: "+str(fecha_revision))
            else:
                _logger.warning("Sin fecha de sincronización establecida, se va a ejecutar la primera sincronización.")

            if not self.env.company.fecha_ultima_sincronizacion:
                clientes_existentes_odoo = self.env['res.partner'].search([('active', 'in', [False,True])])

                lista_id_clientes_sgc_rif = list()

                for cliente in clientes_existentes_odoo:
                    if cliente.vat: #or cliente.identification_id:
                        characters = '-'
                        rif_cliente = cliente.vat
                        for x in range(len(characters)):
                            rif_cliente = rif_cliente.replace(characters[x],"")

                        p = re.compile('[^PVEGJ0-9]')
                        resultado = p.search(rif_cliente)
                        _logger.warning("Resultado del análisis de "+str(rif_cliente)+": "+str(resultado))

                        if resultado:
                            _logger.warning("Rif con formato desconocido: "+str(cliente.vat))
                        else:
                            #Se debe tratar el rif para quitarle el guión antes de ser analizado en la base de datos del SGC.

                            lista_id_clientes_sgc_rif.append("'"+str(rif_cliente)+"'")

                _logger.warning("Clientes validos a buscar en SGC: "+str(lista_id_clientes_sgc_rif))
                _logger.warning("Propiedades de la conexión: "+str(cursor.connection))
                
                cursor.execute("""SELECT id_cliente,
                                                    nombre,
                                                    direccionFacturacion,
                                                    direccion,
                                                    rif,
                                                    telefono,
                                                    telefono2,
                                                    fax,
                                                    ciudad,
                                                    codigoPostal,
                                                    fk_id_tipo_negocio,
                                                    fk_id_categoria,
                                                    fk_id_tipo_cliente,
                                                    fk_id_unidad_negocio,
                                                    fk_id_tipo_clienteCorp,
                                                    fk_id_municipio,
                                                    activo,
                                                    DateModified,
                                                    AccountManagementId FROM [Cliente] WHERE rif IN ("""+str(','.join(lista_id_clientes_sgc_rif))+""") AND activo=1;""")
                rowall = cursor.fetchall()

                #Se llama a la clase de chequeo de Clientes desde SGC a Odoo
                result_SGC_ODOO = check_sgc_data.CheckClientsData.CheckClients_SGC_to_Odoo(self,rowall,cnxn,'Primera_sync')

            else:
                clientes_existentes_odoo = self.env['res.partner'].search([('active', 'in', [False,True])])

                lista_id_clientes_sgc_rif = list()

                for cliente in clientes_existentes_odoo:
                    if cliente.vat: #or cliente.identification_id:
                        characters = '-'
                        rif_cliente = cliente.vat
                        for x in range(len(characters)):
                            rif_cliente = rif_cliente.replace(characters[x],"")

                        p = re.compile('[^PVEGJ0-9]')
                        resultado = p.search(rif_cliente)
                        _logger.warning("Resultado del análisis de "+str(rif_cliente)+": "+str(resultado))

                        if resultado:
                            _logger.warning("Rif con formato desconocido: "+str(cliente.vat))
                        else:
                            #Se debe tratar el rif para quitarle el guión antes de ser analizado en la base de datos del SGC.

                            lista_id_clientes_sgc_rif.append("'"+str(rif_cliente)+"'")
                
                _logger.warning("Clientes validos a buscar en SGC: "+str(lista_id_clientes_sgc_rif))
                _logger.warning("Propiedades de la conexión: "+str(cursor.connection))

                cursor.execute("""SELECT id_cliente,
                                                    nombre,
                                                    direccionFacturacion,
                                                    direccion,
                                                    rif,
                                                    telefono,
                                                    telefono2,
                                                    fax,
                                                    ciudad,
                                                    codigoPostal,
                                                    fk_id_tipo_negocio,
                                                    fk_id_categoria,
                                                    fk_id_tipo_cliente,
                                                    fk_id_unidad_negocio,
                                                    fk_id_tipo_clienteCorp,
                                                    fk_id_municipio,
                                                    activo,
                                                    DateModified,
                                                    DateSincronyzed,
                                                    AccountManagementId FROM [Cliente] WHERE rif IN ("""+str(','.join(lista_id_clientes_sgc_rif))+""") and ((cast(DateModified as smalldatetime) > cast(DateSincronyzed as smalldatetime)) or DateSincronyzed IS NULL);""") 

                rowall = cursor.fetchall()
            
                #Se llama a la clase de chequeo de Clientes desde SGC a Odoo
                result_SGC_ODOO = check_sgc_data.CheckClientsData.CheckClients_SGC_to_Odoo(self,rowall,cnxn,'Sync_recurrente')

            #Se llama a la clase de chequeo de Clientes desde Odoo a SGC
            #result_ODOO_SGC = check_sgc_data.CheckClientsData.CheckClients_Odoo_to_SGC(self,cnxn)
            
            #Se debe garantizar que el query de los registros de la tabla Contacto del SGC no se salga de
            #los registros de sus Clientes Asociados ya validados y registrados e Odoo, por lo que lo ideal
            #es atar el query de contactos del SGC a solo los ID Clientes existentes y ya sincronizados en
            #Odoo con el query anterior.
            clientes_existentes_odoo = self.env['res.partner'].search([('id_cliente', '>', 0)])

            lista_id_clientes_sgc = list()

            for cliente in clientes_existentes_odoo:
                lista_id_clientes_sgc.append(str(cliente.id_cliente))

            _logger.warning("Clientes del SGC activos en Odoo: "+str(lista_id_clientes_sgc))

            _logger.warning("Resultados SGC --> Odoo: "+str(result_SGC_ODOO))
            #_logger.warning("Resultados Odoo --> SGC: "+str(result_ODOO_SGC))
            #Para seccionar la selección se usa TOP seguido del número de registros a solicitar (SELECT TOP 100)
            if not self.env.company.fecha_ultima_sincronizacion:
                cursor.execute("""SELECT id_contacto,
                                                nombre,
                                                apellido,
                                                cedula,
                                                telefono,
                                                celular,
                                                email,
                                                cargo,
                                                prioridad,
                                                habilitado,
                                                fk_id_cliente,
                                                fk_id_tipo_contacto,
                                                activo,
                                                DateModified,
                                                ScalabilityLevelId FROM [Contacto] WHERE fk_id_cliente IN ("""+str(','.join(lista_id_clientes_sgc))+""") and (cedula<>'' or email<>'' or telefono<>'' or celular<>'') and ((LEN(telefono) > 9 and LEN(telefono) < 15) or (LEN(celular) > 9 and LEN(celular) < 15)) and activo=1;""")

                rowall = cursor.fetchall()

                result_SGC_ODOO = check_sgc_data.CheckContactsData.CheckContacts_SGC_to_Odoo(self,rowall,cnxn,'Primera_sync')

            else:
                cursor.execute("""SELECT id_contacto,
                                                    nombre,
                                                    apellido,
                                                    cedula,
                                                    telefono,
                                                    celular,
                                                    email,
                                                    cargo,
                                                    prioridad,
                                                    habilitado,
                                                    fk_id_cliente,
                                                    fk_id_tipo_contacto,
                                                    activo,
                                                    DateModified,
                                                    DateSincronyzed,
                                                    ScalabilityLevelId FROM [Contacto] WHERE fk_id_cliente IN ("""+str(','.join(lista_id_clientes_sgc))+""") and (cedula<>'' or email<>'' or telefono<>'' or celular<>'') and ((LEN(telefono) > 9 and LEN(telefono) < 19) or (LEN(celular) > 9 and LEN(celular) < 19)) and ((cast(DateModified as smalldatetime) > cast(DateSincronyzed as smalldatetime)) or DateSincronyzed IS NULL);""")
            
                rowall = cursor.fetchall()
                result_SGC_ODOO = check_sgc_data.CheckContactsData.CheckContacts_SGC_to_Odoo(self,rowall,cnxn,'Sync_recurrente')
            #Se debe realizar el procedimiento inverso para verificar los contactos desactivados del lado Cliente
            #Interfaz SGC Portal de Clientes.
            #contactos_sgc = self.env['res.partner'].search([('company_type_stored', '=', 'person')])

            #check_sgc_data.CheckContactsData.CheckContactsChangesSGCtoOdoo(self,contactos_sgc,cnxn)

            #Siempre recuerda cerrar para evitar inconvenientes :)
            cursor.close()
            cnxn.close()

            elapsed_time = time() - start_time

            #Al finalizar la sincronización, se debe actualizar la fecha de la última sincronización en la
            #compañía actual, para que cualquier Usuario pueda revisar esta fecha y revisar solo las
            #modificaciones que se efectuen despues de esta fecha.

            _logger.warning("Compañía del Usuario actual: "+str(self.env.company.name))

            self.env.company.fecha_ultima_sincronizacion = datetime.now()

            _logger.warning("Tiempo de ejecución total: "+str(elapsed_time))

    #Función a ejecutar usando un cron job.
    @api.model
    def sync_clientes_cron(self):
        _logger.warning("########## - Ejecución cada 20 segundos - ##########")
        _logger.warning("########## - Ejecución cada 20 segundos - ##########")
        _logger.warning("########## - Ejecución cada 20 segundos - ##########")
        
        #Solo debug, se establece un tiempo inicial y se resta de otro definido al final de las funciones
        #aqui definidas para saber cual es el rendimiento de las mismas en entornos de prueba, qa y producción.

        start_time = time()
        
        #Se obtienen los datos de conexión SGC desde la ficha de la compañía.
        ip = self.env.company.ip_conexion_sgc
        port = self.env.company.puerto_conexion_sgc
        bd = self.env.company.bd_conexion_sgc
        user = self.env.company.user_conexion_sgc
        password = self.env.company.pass_conexion_sgc

        # ENCRYPT defaults to yes starting in ODBC Driver 18. It's good to always specify ENCRYPT=yes on the client side to avoid MITM attacks.
        cnxn = bd_connector.BdConnections.connect_to_bd(self,ip,port,bd,user,password)
        #cnxn = bd_connector.BdConnections.connect_to_bd(self,'200.74.215.68','4022','Dayco_SGC','Odoo','Dayco2022$')

        try:
            if not cnxn:
                _logger.warning("No se pudo conectar a la base de datos, verifique los errores de conexión en el log.")
            else:
                cursor = cnxn.cursor(as_dict=True)
                
                if self.env.company.fecha_ultima_sincronizacion:
                    fecha_last_sync = self.env.company.fecha_ultima_sincronizacion - timedelta(hours=4)
                    fecha_revision = fecha_last_sync.strftime("%Y-%m-%dT%H:%M:%SZ")

                    #Se indica desde que fecha se va a verificar la data.
                    _logger.warning("Se va a revisar la data registrada a partir de la fecha: "+str(fecha_revision))
                    #_logger.warning("Un día anterior a la fecha de la última sincronización: "+str(fecha_revision))
                else:
                    _logger.warning("Sin fecha de sincronización establecida, se va a ejecutar la primera sincronización.")

                clientes_existentes_odoo = self.env['res.partner'].search([])
                
                lista_id_clientes_sgc_rif = list()

                for cliente in clientes_existentes_odoo:
                    if cliente.vat: #or cliente.identification_id:
                        characters = '-'
                        rif_cliente = cliente.vat
                        for x in range(len(characters)):
                            rif_cliente = rif_cliente.replace(characters[x],"")

                        p = re.compile('[^PVEGJ0-9]')
                        resultado = p.search(rif_cliente)
                        _logger.warning("Resultado del análisis de "+str(rif_cliente)+": "+str(resultado))

                        if resultado:
                            _logger.warning("Rif con formato desconocido: "+str(cliente.vat))
                        else:
                            #Se debe tratar el rif para quitarle el guión antes de ser analizado en la base de datos del SGC.

                            lista_id_clientes_sgc_rif.append("'"+str(rif_cliente)+"'")

                _logger.warning("Clientes validos a buscar en SGC: "+str(lista_id_clientes_sgc_rif))
                _logger.warning("Propiedades de la conexión: "+str(cursor.connection))

                _logger.warning("Sentencia SQL: "+str("""SELECT id_cliente,
                                                    nombre,
                                                    direccionFacturacion,
                                                    direccion,
                                                    rif,
                                                    telefono,
                                                    telefono2,
                                                    fax,
                                                    ciudad,
                                                    codigoPostal,
                                                    fk_id_tipo_negocio,
                                                    fk_id_categoria,
                                                    fk_id_tipo_cliente,
                                                    fk_id_unidad_negocio,
                                                    fk_id_tipo_clienteCorp,
                                                    fk_id_municipio,
                                                    activo,
                                                    DateModified,
                                                    AccountManagementId FROM [Cliente] WHERE rif IN ("""+str(','.join(lista_id_clientes_sgc_rif))+""") AND activo=1;"""))

                #_logger.warning("Propiedades de la conexión: "+str(cursor.connection))
                cursor.execute("""SELECT id_cliente,
                                                    nombre,
                                                    direccionFacturacion,
                                                    direccion,
                                                    rif,
                                                    telefono,
                                                    telefono2,
                                                    fax,
                                                    ciudad,
                                                    codigoPostal,
                                                    fk_id_tipo_negocio,
                                                    fk_id_categoria,
                                                    fk_id_tipo_cliente,
                                                    fk_id_unidad_negocio,
                                                    fk_id_tipo_clienteCorp,
                                                    fk_id_municipio,
                                                    activo,
                                                    DateModified,
                                                    AccountManagementId FROM [Cliente] WHERE rif IN ("""+str(','.join(lista_id_clientes_sgc_rif))+""") and ((cast(DateModified as smalldatetime) > cast(DateSincronyzed as smalldatetime)) or DateSincronyzed IS NULL);""")
                rowall = cursor.fetchall()

                #Se llama a la clase de chequeo de Clientes desde SGC a Odoo
                result_SGC_ODOO = check_sgc_data.CheckClientsData.CheckClients_SGC_to_Odoo(self,rowall,cnxn,'Primera_sync')
                
                #Siempre prevenir que lamentar :)
                cursor.close()
                cnxn.close()

                elapsed_time = time() - start_time

                _logger.warning("Compañía del Usuario actual: "+str(self.env.company.name))

                self.env.company.fecha_ultima_sincronizacion = datetime.now()

                _logger.warning("Tiempo de ejecución total: "+str(elapsed_time))
        
        except pymssql.Error as e:
                    #cursor_b.close()
                    cnxn.close()

                    raise ValidationError(_("""Error al activar este Contacto/Cliente, por favor, verifique e intente nuevamente.
                                                Registro del error: 

                                                """+str(e)+"""."""))

    #Función a ejecutar usando un cron job.
    @api.model
    def sync_contactos_cron(self):
        _logger.warning("########## - Ejecución cada 20 segundos - ##########")
        _logger.warning("########## - Ejecución cada 20 segundos - ##########")
        _logger.warning("########## - Ejecución cada 20 segundos - ##########")
        
        #Solo debug, se establece un tiempo inicial y se resta de otro definido al final de las funciones
        #aqui definidas para saber cual es el rendimiento de las mismas en entornos de prueba, qa y producción.

        start_time = time()
        
        #Se obtienen los datos de conexión SGC desde la ficha de la compañía.
        ip = self.env.company.ip_conexion_sgc
        port = self.env.company.puerto_conexion_sgc
        bd = self.env.company.bd_conexion_sgc
        user = self.env.company.user_conexion_sgc
        password = self.env.company.pass_conexion_sgc
        
        # ENCRYPT defaults to yes starting in ODBC Driver 18. It's good to always specify ENCRYPT=yes on the client side to avoid MITM attacks.
        cnxn = bd_connector.BdConnections.connect_to_bd(self,ip,port,bd,user,password)
        #cnxn = bd_connector.BdConnections.connect_to_bd(self,'200.74.215.68','4022','Dayco_SGC','Odoo','Dayco2022$')

        try:
            if not cnxn:
                _logger.warning("No se pudo conectar a la base de datos, verifique los errores de conexión en el log.")
            else:
                cursor = cnxn.cursor(as_dict=True)
                
                if self.env.company.fecha_ultima_sincronizacion:
                    fecha_last_sync = self.env.company.fecha_ultima_sincronizacion - timedelta(hours=4)
                    fecha_revision = fecha_last_sync.strftime("%Y-%m-%dT%H:%M:%SZ")

                    #Se indica desde que fecha se va a verificar la data.
                    _logger.warning("Se va a revisar la data registrada a partir de la fecha: "+str(fecha_revision))
                    #_logger.warning("Un día anterior a la fecha de la última sincronización: "+str(fecha_revision))
                else:
                    _logger.warning("Sin fecha de sincronización establecida, se va a ejecutar la primera sincronización.")

                #Se llama a la clase de chequeo de Clientes desde Odoo a SGC
                #result_ODOO_SGC = check_sgc_data.CheckClientsData.CheckClients_Odoo_to_SGC(self,cnxn)
                
                #Se debe garantizar que el query de los registros de la tabla Contacto del SGC no se salga de
                #los registros de sus Clientes Asociados ya validados y registrados e Odoo, por lo que lo ideal
                #es atar el query de contactos del SGC a solo los ID Clientes existentes y ya sincronizados en
                #Odoo con el query anterior.
                clientes_existentes_odoo = self.env['res.partner'].search([('id_cliente', '>', 0)])

                lista_id_clientes_sgc = list()

                for cliente in clientes_existentes_odoo:
                    lista_id_clientes_sgc.append(str(cliente.id_cliente))

                _logger.warning("Clientes del SGC activos en Odoo: "+str(lista_id_clientes_sgc))

                #_logger.warning("Resultados SGC --> Odoo: "+str(result_SGC_ODOO))
                #_logger.warning("Resultados Odoo --> SGC: "+str(result_ODOO_SGC))
                #Para seccionar la selección se usa TOP seguido del número de registros a solicitar (SELECT TOP 10)
                if len(lista_id_clientes_sgc) > 0:
                    cursor.execute("""SELECT id_contacto,
                                                    nombre,
                                                    apellido,
                                                    cedula,
                                                    telefono,
                                                    celular,
                                                    email,
                                                    cargo,
                                                    prioridad,
                                                    habilitado,
                                                    fk_id_cliente,
                                                    fk_id_tipo_contacto,
                                                    activo,
                                                    DateModified,
                                                    ScalabilityLevelId FROM [Contacto] WHERE fk_id_cliente IN ("""+str(','.join(lista_id_clientes_sgc))+""") and (cedula<>'' or email<>'' or telefono<>'' or celular<>'') and ((LEN(telefono) > 9 and LEN(telefono) < 19) or (LEN(celular) > 9 and LEN(celular) < 19)) and ((cast(DateModified as smalldatetime) > cast(DateSincronyzed as smalldatetime)) or DateSincronyzed IS NULL);""")

                    rowall = cursor.fetchall()

                    result_SGC_ODOO = check_sgc_data.CheckContactsData.CheckContacts_SGC_to_Odoo(self,rowall,cnxn,'Primera_sync')

                    #Se debe realizar el procedimiento inverso para verificar los contactos desactivados del lado Cliente
                    #Interfaz SGC Portal de Clientes.
                    #contactos_sgc = self.env['res.partner'].search([('company_type_stored', '=', 'person')])

                    #check_sgc_data.CheckContactsData.CheckContactsChangesSGCtoOdoo(self,contactos_sgc,cnxn)

                    #Siempre recuerda cerrar para evitar inconvenientes :)
                    cursor.close()
                    cnxn.close()

                    elapsed_time = time() - start_time

                    #Al finalizar la sincronización, se debe actualizar la fecha de la última sincronización en la
                    #compañía actual, para que cualquier Usuario pueda revisar esta fecha y revisar solo las
                    #modificaciones que se efectuen despues de esta fecha.

                    _logger.warning("Compañía del Usuario actual: "+str(self.env.company.name))

                    self.env.company.fecha_ultima_sincronizacion = datetime.now()

                    _logger.warning("Tiempo de ejecución total: "+str(elapsed_time))
                else:
                    raise ValidationError(_("""No hay Clientes con ID cliente validos, primero ejecute el sincronizador de clientes desde el SGC."""))
        
        except pymssql.Error as e:
                    #cursor_b.close()
                    cnxn.close()

                    raise ValidationError(_("""Error al activar este Contacto/Cliente, por favor, verifique e intente nuevamente.
                                                Registro del error: 

                                                """+str(e)+"""."""))

class PrivilegiosContactosSGC(models.Model):
    _name = 'privilegios.contactos.sgc'
    _description = 'Privilegios asignados a los contactos'

    privilegio_id = fields.Many2one('res.partner', string='Privilegio del contacto', ondelete='cascade')
    name = fields.Selection([('1', 'Reporte de Incidentes, Fallas y Requerimientos'), ('2', 'Solicitud de Permisos de Trabajo (PDT)'), ('3','Movilización de Equipos'), ('4','Remote Hands'), ('5','Sin privilegios')], 'Privilegio')