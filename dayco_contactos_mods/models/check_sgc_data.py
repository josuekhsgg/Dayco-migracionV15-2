# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging
import pymssql
#import pyodbc #Librería de conexión a bases de datos SQL.
import string
from datetime import date, datetime, timedelta
from odoo.exceptions import UserError, ValidationError
import re
from . import chequeos

_logger = logging.getLogger(__name__)

########## - Verificación de data de clientes SGC - ##########
########## - Verificación de data de clientes SGC - ##########
########## - Verificación de data de clientes SGC - ##########

class CheckClientsData():
    def CheckClients_SGC_to_Odoo(self, rowall, cnxn, tipo_sync):
        _logger.warning("Data a analizar (Clientes): "+str(rowall))
        _logger.warning("Número de muestra (Clientes): "+str(len(rowall)))

        lista_clientes_base_instalada = list()
        lista_clientes_sharehosting = list()

        contador_clientes_odoo = 0
        contador_clientes_odoo_sharehosting = 0
        contador_clientes_odoo_base_instalada = 0
        contador_registros_analizados = 0

        for row in rowall: 
            #De la data obtenida en la primera sincronización, se deben cumplir los siguientes
            #preceptos para poder obtener la data desde SGC a Odoo

            #Obtener el rif de cada Cliente del SGC y buscarlo por el rif en Odoo, si lo encuentra
            #se debe ir contando para saber cuantos Clientes de odoo realmente se encuentran en SGC.

            #Para afinar un poco mejor el filtro, se debe tener en cuenta que el rif debe tener un guión
            #para poder ser encontrado correctamente en Odoo.

            #Solo aplicar esta modificación en caso de no encontrar el guion.
            if str(row.get('rif')).find("-") == -1:
                primera_letra_rif_sgc = str(row.get('rif'))[:1]
                #_logger.warning(primera_letra_rif_sgc)

                resto_rif = str(row.get('rif'))[1:]
                #_logger.warning(resto_rif)

                row['rif'] = primera_letra_rif_sgc+'-'+resto_rif
            #else:
            #    _logger.warning("Rif con guion encontrado!")

            #_logger.warning("Data a análizar: "+str(row))
            errores = list()
            registro_tecnico = list()

            #Verificar si el Cliente de SGC existe en Odoo y que cumpla que tenga la categoría
            #1- Base instalada en campo "Categorías"
            #2- Carrier en campo "Categorías"
            #3- Sharehosting en campo "Tipo de Cliente"
            #4- Puede ser un registro de tipo "Individual", sin embargo, si tiene marcado el check
            #   "Facturable" y en el campo "Tipo de cliente" tiene el valor "Sharehosting" se debe
            #   tomar en cuenta como un Cliente y así asignar el respectivo ID del Cliente desde
            #   la base de datos del SGC.

            #Comprobar información del Cliente a analizar (Debug)
            _logger.warning("Cliente: "+str(row.get('nombre')))
            _logger.warning("RIF: "+str(row.get('rif')))

            clientes_solo_rif = self.env['res.partner'].search(['|',('vat', 'in', [str(row.get('rif'))]),('identification_id', 'in', [str(row.get('rif'))]),('parent_id', '=', False),('active', 'in', [False,True])])

            _logger.warning("Registros encontrados en Odoo: "+str(clientes_solo_rif))

            #En caso de haber encontrado dos clientes con el mismo RIF
            #Si no encuentra el Cliente se debe solo actualizar la fecha de sincronización.
            for cliente in clientes_solo_rif:
                _logger.warning("Tipo de Cliente: "+str(cliente.partner_type_id.name))
                _logger.warning("Tipo de registro: "+str(cliente.company_type_stored))
                _logger.warning("Es facturable?: "+str(cliente.facturable))
                 
                if tipo_sync == 'Primera_sync':
                    if cliente.partner_type_id.name == "Sharehosting" and cliente.facturable and not cliente.parent_id:
                        _logger.warning("Cliente sharehosting valido encontrado!")

                        contador_clientes_odoo += 1
                        contador_clientes_odoo_sharehosting += 1

                        #En caso de no tener ID de Cliente establecido en Odoo, se asigna este ID Cliente desde el SGC.
                        if not cliente.id_cliente:
                            _logger.warning("ID Cliente actualizado correctamente!")
                            cliente.id_cliente = row.get("id_cliente")

                        registro_tecnico.append("""
                                    <p><h2>Se encontró al Cliente Sharehosting registrado en Odoo de forma correcta</h2></p>
                                    <p>El tipo de registro en Odoo es: """+str(cliente.company_type_stored)+"""</p>
                                    <p>
                                        Se ha registrado la información correspondiente al Cliente: </p>
                                    <p>
                                        <strong>
                                            """+str(row.get('nombre'))+"""
                                        </strong>
                                    </p>
                                    <p>
                                        Relacionado en Odoo con el ID del Cliente:
                                        <strong>
                                            """+str(row.get('id_cliente'))+"""
                                        </strong>
                                    </p>
                                    """)

                        self.env['sgc.odoo.history'].create({
                            'name': str(row.get('nombre')),
                            'fecha_registro': datetime.now(),
                            'tipo_error': 'Sync SGC --> Odoo (Cliente) Tipo: '+str(cliente.company_type_stored),
                            'registro_operacion': ''.join(registro_tecnico),
                            'registro_tecnico': ''.join(errores),
                            'category': '<p style="color:blue;">Actualización</p>',
                        })

                        #Se agrega al listado para visualizar en detalle los resultados
                        lista_clientes_sharehosting.append(cliente.name)

                    for category in cliente.category_id:
                        if category.name == "Base Instalada" or category.name == "Aliados para el Servicio":
                            _logger.warning("Cliente base instalada/Aliados para el Servicio encontrado!")

                            #En caso de no tener ID de Cliente establecido en Odoo, se asigna este ID Cliente desde el SGC.
                            if not cliente.id_cliente:
                                _logger.warning("ID Cliente actualizado correctamente!")
                                cliente.id_cliente = row.get("id_cliente")

                            registro_tecnico.append("""
                                    <p><h2>Se encontró al Cliente """+str(category.name)+""" registrado en Odoo de forma correcta</h2></p>
                                    <p>El tipo de registro en Odoo es: """+str(cliente.company_type_stored)+"""</p>
                                    <p>
                                        Se ha registrado la información correspondiente al Cliente: </p>
                                    <p>
                                        <strong>
                                            """+str(row.get('nombre'))+"""
                                        </strong>
                                    </p>
                                    <p>
                                        Relacionado en Odoo con el ID del Cliente:
                                        <strong>
                                            """+str(row.get('id_cliente'))+"""
                                        </strong>
                                    </p>
                                    """)

                            self.env['sgc.odoo.history'].create({
                                'name': str(row.get('nombre')),
                                'fecha_registro': datetime.now(),
                                'tipo_error': 'Sync SGC --> Odoo (Cliente) Tipo: '+str(cliente.company_type_stored),
                                'registro_operacion': ''.join(registro_tecnico),
                                'registro_tecnico': ''.join(errores),
                                'category': '<p style="color:blue;">Actualización</p>',
                            })

                            contador_clientes_odoo += 1
                            contador_clientes_odoo_base_instalada += 1

                            #Se agrega al listado para visualizar en detalle los resultados
                            lista_clientes_base_instalada.append(cliente.name)

                            #En caso de que exista dos etiquetas iguales se debe romper el ciclo al detectar la primera válida
                            break
                    
                #En caso de que la fecha de sincronización sea menor a la fecha de modificación se debe actualizar la data
                #desde el SGC hacía Odoo.

                elif row.get("DateModified") and tipo_sync == 'Sync_recurrente':
                    _logger.warning("DateModified SGC: "+str(row.get("DateModified")))
                    _logger.warning("DateSincronyzed SGC: "+str(row.get("DateSincronyzed")))

                    #Considerar el caso en el que la fecha de sincronización sea NULL, en ese caso se
                    #debe actualizar el Cliente
                    #Se descarta el valor "DateModified" en la pestaña "Información del SGC" para hacer
                    #que el Cliente actualice su id_sgc o no.

                    #if cliente.client_date_modified:
                    if row.get("DateSincronyzed") and row.get("DateModified"):
                        if row.get("DateSincronyzed") < row.get("DateModified"):
                            
                            if not cliente.id_cliente:
                                _logger.warning("ID Cliente actualizado correctamente!")
                                cliente.id_cliente = row.get("id_cliente")

                            #Entonces se debe hacer la modificación desde SGC a Odoo
                            _logger.warning("Actualizando desde SGC a Odoo")
                            
                            """
                            cliente.company_type = 'company' #Se establece a company por ser Clientes del SGC
                            cliente.id_cliente = row.get("id_cliente")
                            cliente.name = row.get("nombre")
                            cliente.direccion_facturacion = row.get("direccionFacturacion")
                            cliente.street = row.get("direccion")
                            cliente.vat = row.get("rif")
                            cliente.rif_cliente = row.get("rif")
                            cliente.phone = row.get("telefono")
                            cliente.mobile = row.get("telefono2")
                            cliente.fax_cliente = row.get("fax")
                            cliente.city = row.get("ciudad")
                            cliente.zip = row.get("codigoPostal")
                            cliente.tipo_negocio_cliente = int(row.get("fk_id_tipo_negocio"))
                            cliente.categoria_cliente = str(row.get("fk_id_categoria"))
                            cliente.tipo_cliente = str(row.get("fk_id_tipo_cliente"))
                            cliente.unidad_negocio_cliente = str(row.get("fk_id_unidad_negocio"))
                            cliente.tipo_cliente_corporativo = str(row.get("fk_id_tipo_clienteCorp"))
                            cliente.municipio_cliente = str(row.get("fk_id_municipio"))
                            cliente.cliente_activo = row.get("activo")
                            cliente.client_date_modified = row.get("DateModified")
                            cliente.account_management_id_sgc = str(row.get("AccountManagementId"))
                            """
                            #Para evitar que se rechequee y reinserte la data en la bd.
                            cliente.revisar_id_cliente_sgc = False
                            cliente.revisar_id_contacto_sgc = False

                            #Se archiva o desarchiva automáticamente 
                            #según el valor del campo "Activo" en SGC.

                            #Solo se debe archivar/desarchivar el contacto cuando el contacto no
                            #tenga un Usuario en la instancia Odoo (Validación nativa).
                            odoo_users = self.env['res.users'].search([('partner_id', '=', cliente.id)])
                            _logger.warning("Usuario asociado al contacto/cliente en Odoo: "+str(odoo_users))

                            if not odoo_users:
                                if int(row.get("activo")) == 0:
                                    cliente.active = False
                                else:
                                    cliente.active = True
                            else:
                                registro_tecnico.append("No se Archivan/desarchivan clientes que tengan Usuario en Odoo")


                            self.env['sgc.odoo.history'].create({
                                                                'name': str(row.get('nombre')),
                                                                'fecha_registro': datetime.now(),
                                                                'tipo_error': 'Sync SGC --> Odoo (Cliente) Tipo: '+str(cliente.company_type_stored),
                                                                'registro_operacion': 'Se ha actualizado correctamente la data desde el SGC hacía Odoo.',
                                                                'registro_tecnico': 'Actualización Recurrente',
                                                                'category': '<p style="color:blue;">Actualización</p>',
                                                            })

                    elif row.get("DateModified") and row.get("DateSincronyzed") == None:
                        _logger.warning("Actualización de Cliente que no se había sincronizado antes, posiblemente un Cliente nuevo.")
                        
                        if not cliente.id_cliente:
                            _logger.warning("ID Cliente actualizado correctamente!")
                            cliente.id_cliente = row.get("id_cliente")

                        #Entonces se debe hacer la modificación desde SGC a Odoo
                        """
                        _logger.warning("Actualizando desde SGC a Odoo")
                        cliente.company_type = 'company' #Se establece a company por ser Clientes del SGC
                        cliente.id_cliente = row.get("id_cliente")
                        cliente.name = row.get("nombre")
                        cliente.direccion_facturacion = row.get("direccionFacturacion")
                        cliente.street = row.get("direccion")
                        cliente.vat = row.get("rif")
                        cliente.rif_cliente = row.get("rif")
                        cliente.phone = row.get("telefono")
                        cliente.mobile = row.get("telefono2")
                        cliente.fax_cliente = row.get("fax")
                        cliente.city = row.get("ciudad")
                        cliente.zip = row.get("codigoPostal")
                        cliente.tipo_negocio_cliente = int(row.get("fk_id_tipo_negocio"))
                        cliente.categoria_cliente = str(row.get("fk_id_categoria"))
                        cliente.tipo_cliente = str(row.get("fk_id_tipo_cliente"))
                        cliente.unidad_negocio_cliente = str(row.get("fk_id_unidad_negocio"))
                        cliente.tipo_cliente_corporativo = str(row.get("fk_id_tipo_clienteCorp"))
                        cliente.municipio_cliente = str(row.get("fk_id_municipio"))
                        cliente.cliente_activo = row.get("activo")
                        cliente.client_date_modified = row.get("DateModified")
                        cliente.account_management_id_sgc = str(row.get("AccountManagementId"))
                        """
                        #Para evitar que se rechequee y reinserte la data en la bd.
                        cliente.revisar_id_cliente_sgc = False
                        cliente.revisar_id_contacto_sgc = False

                        #Se archiva o desarchiva automáticamente 
                        #según el valor del campo "Activo" en SGC.

                        #Solo se debe archivar/desarchivar el contacto cuando el contacto no
                        #tenga un Usuario en la instancia Odoo (Validación nativa).
                        odoo_users = self.env['res.users'].search([('partner_id', '=', cliente.id)])
                        _logger.warning("Usuario asociado al contacto/cliente en Odoo: "+str(odoo_users))

                        if not odoo_users:
                            if int(row.get("activo")) == 0:
                                cliente.active = False
                            else:
                                cliente.active = True
                        else:
                            registro_tecnico.append("No se Archivan/desarchivan clientes que tengan Usuario en Odoo")


                        self.env['sgc.odoo.history'].create({
                                                            'name': str(row.get('nombre')),
                                                            'fecha_registro': datetime.now(),
                                                            'tipo_error': 'Sync SGC --> Odoo (Cliente) Tipo: '+str(cliente.company_type_stored),
                                                            'registro_operacion': 'Se ha actualizado correctamente la data desde el SGC hacía Odoo.',
                                                            'registro_tecnico': 'Actualización por primera vez',
                                                            'category': '<p style="color:blue;">Actualización</p>',
                                                        })

                #Sea que se haya creado o no el registro desde Odoo hacia SGC se debe modificar el campo 'DateModified'
                #en SGC para saber cuando fue la última vez que paso por allí.
                #_logger.warning("Última fecha de modificación / revisión del Cliente en SGC: "+str(row.get("DateModified")))
                #_logger.warning("Fecha a establecer en el registro: "+str(datetime.now()))

                cursor_b = cnxn.cursor(as_dict=True)

                #En caso de que la fecha de modificación no exista, se debe establecer esta fecha en la base de
                #datos del SGC cuando sea creado o editado el contacto en el proceso de sincronización.
                stored_proc = """UPDATE [Cliente] SET DateSincronyzed = %s WHERE id_cliente = %s;"""
                params = (datetime.now() - timedelta(hours=4),int(row.get("id_cliente")))

                cursor_b.execute(stored_proc, params)
                cnxn.commit()
                cursor_b.close()

                #Se contabiliza cada registro analizado
                contador_registros_analizados += 1
                _logger.warning("Cliente #: "+str(contador_registros_analizados))
            
            if not clientes_solo_rif:
                _logger.warning("Cliente no encontrado en Odoo, solo se actualiza la fecha de sincronización.")
                cursor_b = cnxn.cursor(as_dict=True)

                #En caso de que la fecha de modificación no exista, se debe establecer esta fecha en la base de
                #datos del SGC cuando sea creado o editado el contacto en el proceso de sincronización.
                stored_proc = """UPDATE [Cliente] SET DateSincronyzed = %s WHERE id_cliente = %s;"""
                params = (datetime.now() - timedelta(hours=4),int(row.get("id_cliente")))

                cursor_b.execute(stored_proc, params)
                cnxn.commit()
                cursor_b.close()

                #Se contabiliza cada registro analizado
                contador_registros_analizados += 1
                _logger.warning("Cliente #: "+str(contador_registros_analizados))

        _logger.warning("Total de Clientes del SGC encontrados en Odoo: "+str(contador_clientes_odoo))
        _logger.warning("Total Base Instalada: "+str(contador_clientes_odoo_base_instalada))
        _logger.warning("Total Sharehosting: "+str(contador_clientes_odoo_sharehosting))

        for item_sharehosting in lista_clientes_sharehosting:
            _logger.warning("Cliente Sharehosting: "+str(item_sharehosting))
            
        for item_base_instalada in lista_clientes_base_instalada:
            _logger.warning("Cliente Base Instalada: "+str(item_base_instalada))

        #Ubicar los Clientes en Odoo que no hayan sido encontrados en SGC por algún error desconocido
        no_encontrados_total = self.env['res.partner'].search([('name','not in',lista_clientes_base_instalada),('category_id.name', 'in', ['Base Instalada', 'Aliados para el Servicio']),('company_type_stored','=','company')])

        no_encontrados_total_individuos = self.env['res.partner'].search([('name','not in',lista_clientes_base_instalada),('name','not in',lista_clientes_sharehosting),('facturable', '=', True),('partner_type_id.name', '=', 'Sharehosting'),('company_type_stored','=','person'),('parent_id', '=', False)])

        total_clientes_compania = 0
        total_clientes_individual = 0

        for contacto in no_encontrados_total:
            _logger.warning("Cliente tipo compañía en Odoo: "+str(contacto.name))
            total_clientes_compania+=1

        _logger.warning("Total clientes base instalada: "+str(total_clientes_compania))

        for contacto_b in no_encontrados_total_individuos:
            _logger.warning("Cliente tipo individual en Odoo: "+str(contacto_b.name))
            total_clientes_individual+=1

        _logger.warning("Total clientes sharehosting: "+str(total_clientes_individual))

        #Se deben registrar estos totales en el registro de operaciones de la interfaz SGC - Odoo
        self.env['sgc.odoo.history'].create({
                                            'name': 'Sincronización finalizada',
                                            'fecha_registro': datetime.now(),
                                            'tipo_error': 'Sync SGC --> Odoo (Cliente)',
                                            'registro_operacion': """
                                                                    <p><h2>Finalizada la sincronización de Clientes desde SGC --> Odoo</h2></p>
                                                                    <p>"Total clientes base instalada: """+str(total_clientes_compania)+"""</p>
                                                                    <p>"Total clientes sharehosting: """+str(total_clientes_individual)+"""</p>
                                                                    <p>...</p>
                                                                    <p>...</p>
                                                                        <p><h2>Listado de Clientes Base instalada no sincronizados desde Odoo hacia SGC (Existen en Odoo mas no en SGC) </h2></p>
                                                                    <p>...</p>
                                                                    <p>...</p>
                                                                    <p>
                                                                        <strong>
                                                                            """+str(no_encontrados_total)+"""
                                                                        </strong>
                                                                    </p>
                                                                    <p>...</p>
                                                                    <p>...</p>
                                                                        <p><h2>Listado de Clientes Sharehosting no sincronizados desde Odoo hacia SGC (Existen en Odoo mas no en SGC) </h2></p>
                                                                    <p>...</p>
                                                                    <p>...</p>
                                                                    <p>
                                                                        <strong>
                                                                            """+str(no_encontrados_total_individuos)+"""
                                                                        </strong>
                                                                    </p>
                                                                    """,
                                            'registro_tecnico': 'Totales',
                                            'category': '<p style="color:yellow;">Sincronización</p>',
                                        })

        return True
    
    def CheckClients_Odoo_to_SGC(self,cnxn):
        _logger.warning("########## - Se va a verificar la data desde Odoo a SGC - ##########")
        _logger.warning("########## - Se va a verificar la data desde Odoo a SGC - ##########")
        
        #Se obtienen todos los datos a verificar desde Odoo
        contactos_odoo = self.env['res.partner'].search([])

        #Se crea el cursor para verificar la data en SGC.
        cursor = cnxn.cursor()

        #Se debe obtener el último ID de Dayco para poder asignar en caso de no obtener dicho ID.
        #Si dicho ID no existe entonces se debe agregar dicho contacto al SGC.
        new_id = 0
        last_contacts = self.env['res.partner'].search([], order='id_cliente asc')
        for contact in last_contacts:
            _logger.warning("Contacto encontrado: "+str(contact.name))
            _logger.warning("Contacto ID SGC: "+str(contact.id_cliente))
            if new_id < contact.id_cliente:
                new_id = contact.id_cliente

        for contacto in contactos_odoo:
            _logger.warning("Contacto: "+str(contacto.name))
            _logger.warning("ID dayco: "+str(contacto.id_cliente))
            _logger.warning("Categoría: "+str(contacto.cliente_partner_category))
            _logger.warning("VAT/RIF: "+str(contacto.vat))

            #Solo se toman en cuenta los Clientes (contactos tipo compañía) que tengan el VAT (Campo RIF)
            #y tambien que sean del tipo indicado en el campo cliente_partner_category.
            if contacto.id_cliente == 0 and contacto.vat and contacto.cliente_partner_category:
                #Se debe agregar este contacto con su respectivo nuevo ID de Dayco SGC
                new_id += 1 #Sumar uno para no repetir el mismo ID de Dayco SGC.
                contacto.id_cliente = new_id

                #Se debe agregar este contacto a la base de datos del SGC.
                stored_proc = """ exec [dbo].[AgregarCliente]
                                                            @nombre = ?,
                                                            @rif = ?,
                                                            @direccion = ?,
                                                            @unidadNegocios = ?,
                                                            @telefono = ?,
                                                            @fax = ?,
                                                            @ciudad = ?,
                                                            @codigoPostal = ?,
                                                            @tipoCliente = ?,
                                                            @idClienteCorp = ?,
                                                            @idTipoNegocio = ?,
                                                            @idCategoria = ?,
                                                            @idMunicipio = ?,
                                                            @direccion2 = ?,
                                                            @telefono2 = ?,
                                                            @AccountManagementId = ?"""
                #Se debe eliminar el '-' del rif si este lo posee.
                characters = '-'
                if contacto.vat:
                    for x in range(len(characters)):
                        contacto.vat = contacto.vat.replace(characters[x],"")
                
                params = (str(contacto.name),str(contacto.vat),str(contacto.street),contacto.unidad_negocio_cliente,str(contacto.phone),str(contacto.fax_cliente),str(contacto.city),str(contacto.zip),contacto.cliente_partner_category,int(contacto.tipo_cliente_corporativo),int(contacto.tipo_negocio_cliente),int(contacto.categoria_cliente),int(contacto.municipio_cliente),str(contacto.direccion_facturacion),str(contacto.mobile),int(contacto.account_management_id_sgc))
            
                #Se ejecuta el stored procedure con el cursor
                cursor.execute(stored_proc, params)
                cursor.commit()
        
        return True

########## - Verificación de data de clientes SGC - ##########
########## - Verificación de data de clientes SGC - ##########
########## - Verificación de data de clientes SGC - ##########

########## - Verificación de data de contactos SGC - ##########
########## - Verificación de data de contactos SGC - ##########
########## - Verificación de data de contactos SGC - ##########

class CheckContactsData():
    def CheckContacts_SGC_to_Odoo(self, rowall, cnxn, tipo_sync):
        _logger.warning("Data a analizar (Contactos): "+str(rowall))
        _logger.warning("Número de muestra (Contactos): "+str(len(rowall)))
        contador_contactos_relacionados = 0
        contador_contacto_encontrado = 0
        letra_documento_identidad = ''
        documento_identidad = int()
        contador_contactos_clientes_creados = 0
        contador_registros_analizados = 0

        for row in rowall: 
            #Se debe insertar cada contacto en la instancia Odoo al cumplirse algunas condiciones
            #1- Que el ID (row.get("id_contacto")) no esté repetido (Procede a partir de aquí a realizar otras validaciones)
            #2- Que el contacto se encuentre relacionado debidamente con al menos un Cliente validado
            #previamente en el query de los Clientes y se encuentre registrado en Odoo.

            #print("Data a análizar: "+str(row))
            errores = list()
            registro_tecnico = list()

            #Se debe analizar esta data antes de realizar el proceso de registro respectivo, si se cumplen
            #los filtros necesarios si se debe ejecutar el proceso, si no se debe ignorar el registro, y de
            #ser posible se deben registrar los movimientos o registros realizados entre SGC y Odoo.

            contador_contactos_relacionados += 1
            procede_reg_or_edit = True

            #Se debe acomodar el número de cédula proveniente del SGC para poder encontrar la mayor cantidad
            #de coincidencias con los registros existentes en Odoo.
            
            #if tipo_sync == 'Primera_sync':
            #1- Si tiene letra se debe quitar.
            #Se debe considerar un rango de cedula de entre 6 y 10 caracteres de longitud!
            #Se debe considerar que pueda existir un registro en Odoo sin cédula y que este se encuentre
            #en SGC de la misma manera, por lo que si encuentra el registro por su ID_Cliente+ID_Contacto
            #Entonces si debe permitir actualizar, solo actualizar.
            if len(str(row.get('cedula'))) > 5 and len(str(row.get('cedula'))) < 10:

                #Array con la siguiente información a enviar:
                #1- Letra del documento de identidad.
                #2- Documento de identidad.
                #3- Cédula proveniente del SGC (Enviada dentro de la variable row).
                #4- Variable de control que permite el registro o edición de contactos o clientes desde SGC hacia Odoo.
                #5- Variable que contiene los errores que se generen durante los analísis.

                data_res = chequeos.MaestroChequeos.check_contact_data_cedula(self, row, procede_reg_or_edit, errores, registro_tecnico)

                #Se obtiene la data posterior al chequeo.
                row = data_res[0]
                procede_reg_or_edit = data_res[1]
                errores = data_res[2]
                letra_documento_identidad = data_res[3]
                documento_identidad = data_res[4]
                registro_tecnico = data_res[5]

                registro_tecnico.append("Cédula del contacto a analizar: "+str(letra_documento_identidad)+str(documento_identidad))
                #Se agrega condición maestra que establece que si la cédula está vacía entonces
                #No se crea el contacto con la cédula vacía.
                
                if procede_reg_or_edit:
                    #Se debe averiguar si ya existe este contacto del SGC registrado en Odoo.
                    #En caso de ser positivo, solo se debe actualizar el nivel de escalabilidad y sus privilegios.
                    contactos_del_cliente_encontrado = ''
                    registro_tecnico.append("Documento de identidad valido.")
                    #Buscar por el numero de cedula o el correo electrónico.
                    #Cada contacto valido en Odoo se busca con el siguiente criterio de filtrado:
                    #1- Que tenga empresa relacionada con el mismo id_cliente del SGC
                    #2- Que no tenga marcada la casilla de "Facturable"
                    #3- Que sea tipo "Individual"
                    #4- Que no tenga nada en el campo "Tipo de Cliente"

                    if len(str(row.get('cedula'))) > 5 and len(str(row.get('cedula'))) < 10:
                        _logger.warning('Se va a buscar por cédula de identidad!!: '+str(documento_identidad)+', id cliente asociado: '+str(row.get('fk_id_cliente')))
                        contactos_del_cliente_encontrado = self.env['res.partner'].search([('identification_id', '=', str(documento_identidad)),('parent_id.id_cliente', '=', row.get("fk_id_cliente")),('active', 'in', [False,True])], limit = 1)
                        
                        #Considerar el caso en el que la cédula haya cambiado y se mantengan los id_contacto y id_cliente iguales.
                        #if not contactos_del_cliente_encontrado:
                        #    _logger.warning("Se busca por la segunda posibilidad, ID_Contacto + ID_Cliente")
                        #    contactos_del_cliente_encontrado = self.env['res.partner'].search([('id_contacto', '=', row.get('id_contacto')),('parent_id.id_cliente', '=', row.get("fk_id_cliente")),('active', 'in', [False,True])])

                        _logger.warning("Contactos encontrados: "+str(contactos_del_cliente_encontrado))
                        registro_tecnico.append("Contactos encontrados en Odoo: "+str(contactos_del_cliente_encontrado))

                        if contactos_del_cliente_encontrado:                          
                            for contacto in contactos_del_cliente_encontrado:
                                _logger.warning("Contacto del Cliente encontrado en Odoo")

                                #Se debe verificar si este contacto encontrado en Odoo cumple con las siguientes características
                                #1- Que posea como compañía padre al Cliente con el mismo fk_id_cliente del SGC.
                                #2- Que posea una cédula valida.
                                #3- Que no esté repetido (Consultar detalles a revisar)

                                data_res = chequeos.MaestroChequeos.check_contact_data_contacto_cliente_encontrado(self, contacto, procede_reg_or_edit, errores, registro_tecnico)

                                #Lista negra de Clientes que no deben tomarse en cuenta para sincronizar sus contactos
                                #Se agregan los rif para evitar errores al momento de comparar.
                                #Se debe crear una funcionalidad que permita indicar desde Odoo cuales son los Clientes
                                #en lista negra, para así evitar sincronizaciones indeseadas.
                                black_list_clientes = ['305027498']

                                data_res = chequeos.MaestroChequeos.check_contact_data_contacto_cliente_blacklist(self, contacto, black_list_clientes, procede_reg_or_edit, errores, registro_tecnico)

                                #Se obtiene la data posterior al chequeo.
                                procede_reg_or_edit = data_res[0]
                                errores = data_res[1]
                                registro_tecnico = data_res[2]

                                if procede_reg_or_edit:
                                    _logger.warning("Nombre del contacto SGC: "+str(row.get('nombre'))+" - "+str(row.get('apellido')))
                                    _logger.warning("Cédula del contacto SGC: "+str(row.get('cedula')))
                                    _logger.warning("Nombre del contacto Odoo: "+str(contacto.name))
                                    _logger.warning("Cédula del contacto Odoo: "+str(contacto.identification_id))
                                    _logger.warning("Correo del contacto SGC: "+str(row.get('email')))
                                    _logger.warning("Correo del contacto Odoo: "+str(contacto.email))
                                    _logger.warning("Id Cliente de la Compañía padre asociada: "+str(contacto.parent_id.id_cliente))
                                    _logger.warning("fk_id_cliente de este contacto: "+str(row.get('fk_id_cliente')))
                        
                                    if not row.get("DateModified"):
                                        row['DateModified'] = datetime.now()

                                    try:
                                        #Se deben buscar los privilegios en la tabla de privilegios del SGC para
                                        #sincronizarlos correctamente con la instancia Odoo.
                                        cursor_b = cnxn.cursor(as_dict=True)

                                        stored_proc = """SELECT fk_id_privilegio FROM [Privilegio_Contacto] WHERE fk_id_contacto = """+str(row.get("id_contacto"))
                                        cursor_b.execute(stored_proc)
                                        privilegios = cursor_b.fetchall()

                                        _logger.warning("Resultado: "+str(privilegios))

                                        all_privilegios = [(5,0,0)]

                                        for item in privilegios:
                                            _logger.warning("Privilegio asociado al contacto: "+str(item.get('fk_id_privilegio')))

                                            all_privilegios.append((0, 0, {
                                                                    'name': str(item.get('fk_id_privilegio')),
                                            }))

                                        #Se asignan los privilegios nuevos
                                        contacto.privilegio_ids = all_privilegios

                                    except pymssql.Error as e:
                                        _logger.warning("No se pudieron adquirir los privilegios de este contacto desde el SGC.")
                                        _logger.warning("Error: "+str(e))

                                    contador_contacto_encontrado += 1

                                    #En caso de que el nivel de escalabilidad venga n null se coloca por defecto en 1.
                                    if not row.get("ScalabilityLevelId"):
                                        row['ScalabilityLevelId'] = 1

                                    #Se asigna la escalabilidad
                                    contacto.ScalabilityLevel = str(row.get("ScalabilityLevelId"))

                                    #En caso de no poseer, se debe asignar el id del contacto asociado y el id cliente relacionado
                                    #if not contacto.id_contacto > 0:
                                    contacto.id_contacto = row.get('id_contacto')
                                    #if not contacto.id_cliente > 0:
                                    contacto.id_cliente = row.get('fk_id_cliente')

                                    #Fecha de modificacion desde el SGC.
                                    contacto.contacto_date_modified = row.get("DateModified")

                                    #Cédula contacto para posteriores ediciones y sincronizaciones.
                                    contacto.cedula_contacto = str(letra_documento_identidad)+str(documento_identidad)

                                    #Para evitar que se rechequee y reinserte la data en la bd.
                                    contacto.revisar_id_cliente_sgc = False
                                    contacto.revisar_id_contacto_sgc = False

                                    ########## - ACTUALIZACIÓN RECURRENTE - ##########
                                    ########## - ACTUALIZACIÓN RECURRENTE - ##########

                                    #Solo en el caso de que la sincronización sea recurrente se debe actualizar
                                    #toda la data del contacto desde el SGC hacia Odoo
                                    if tipo_sync == 'Sync_recurrente':
                                        registro_tecnico.append("Actualización recurrente.")

                                        #Por ahora se descarta la edición del nombre por incompatibilidad de campos
                                        #entre SGC y Odoo, se debe realizar una modificación al SGC para poder llegar
                                        #al resultado deseado (Que en SGC se escriba nombre y apellido en el mismo campo)

                                        #Hotfix #11 (Solo se coloca el nombre desde SGC hacia Odoo cuando el apellido contenga un asterisco)
                                        if not str(row.get('apellido')) == '*':
                                            _logger.warning("Se establece nombre del contacto desde SGC a Odoo por sincronización recurrente.")
                                            contacto.name = row.get("nombre")+" "+row.get("apellido")
                                        
                                        contacto.apellido_contacto = '' #row.get("apellido")
                                        contacto.nationality = letra_documento_identidad
                                        contacto.cedula_contacto = str(letra_documento_identidad)+str(documento_identidad)
                                        contacto.identification_id = documento_identidad
                                        contacto.phone = row.get("telefono")
                                        contacto.mobile = row.get("celular")
                                        contacto.email = row.get("email")
                                        contacto.cargo_contacto = row.get("cargo")
                                        contacto.x_studio_cargo = row.get("cargo")
                                        contacto.prioridad_contacto = row.get("prioridad")
                                        contacto.habilitado_contacto = row.get("habilitado")
                                        contacto.id_cliente = row.get("fk_id_cliente")
                                        contacto.tipo_contacto = str(row.get("fk_id_tipo_contacto"))

                                        id_rol = 1
                                        #Detectar el rol en Odoo
                                        if row.get("fk_id_tipo_contacto") == 1:
                                            id_rol = self.env['x_rol'].search([('x_name', '=', 'Técnico')])
                                            _logger.warning("Rol en Odoo: "+str(id_rol))
                                        if row.get("fk_id_tipo_contacto") == 2:
                                            id_rol = self.env['x_rol'].search([('x_name', '=', 'Administrativo')])
                                            _logger.warning("Rol en Odoo: "+str(id_rol))
                                        if row.get("fk_id_tipo_contacto") == 3:
                                            id_rol = self.env['x_rol'].search([('x_name', '=', 'Ejecutivo')])
                                            _logger.warning("Rol en Odoo: "+str(id_rol))

                                        contacto.rol = id_rol #row.get("fk_id_tipo_contacto")
                                        contacto.contacto_activo = row.get("activo")

                                        #Se archiva o desarchiva automáticamente 
                                        #según el valor del campo "Activo" en SGC.

                                        #Solo se debe archivar/desarchivar el contacto cuando el contacto no
                                        #tenga un Usuario en la instancia Odoo (Validación nativa).
                                        odoo_users = self.env['res.users'].search([('partner_id', '=', contacto.id)])
                                        _logger.warning("Usuario asociado al contacto/cliente en Odoo: "+str(odoo_users))

                                        if not odoo_users:
                                            if int(row.get("activo")) == 0:
                                                contacto.active = False
                                            else:
                                                contacto.active = True
                                        else:
                                            registro_tecnico.append("No se Archivan/desarchivan contactos que tengan Usuario en Odoo")

                                    ########## - ACTUALIZACIÓN RECURRENTE - ##########
                                    ########## - ACTUALIZACIÓN RECURRENTE - ##########

                                    registro_tecnico.append("""<p>Se encontró en Odoo un registro de nombre: """+str(contacto.name)+"""</p>
                                                            <p>Con la siguiente compañía relacionada: """+str(contacto.parent_id)+"""</p>
                                                            <p>fk_id_cliente de la compañía relacionada en Odoo: """+str(contacto.parent_id.id_cliente)+"""</p>
                                                            <p>Se le actualiza el nivel de escalabilidad a: """+str(row.get('ScalabilityLevelId'))+"""</p>
                                                            <p>Se actualizan sus privilegios a: """+str(all_privilegios)+"""</p>""")

                                    chequeos.MaestroChequeos.check_contact_data_generador_historico(self, errores, False, row, registro_tecnico, 'Actualización registro existente', 'orange')

                                else:
                                    chequeos.MaestroChequeos.check_contact_data_generador_historico(self, errores, False, row, registro_tecnico, 'error', 'red')

                        #Si no encuentra el contacto poe cédula se busca por combinación de ID Cliente + ID Contacto
                        else:
                            _logger.warning('Se va a buscar por combinación del ID Contacto + ID Cliente: '+str(documento_identidad)+', id cliente asociado: '+str(row.get('fk_id_cliente')))
                            contactos_del_cliente_encontrado = self.env['res.partner'].search([('id_contacto', '=', row.get('id_contacto')),('parent_id.id_cliente', '=', row.get("fk_id_cliente")),('active', 'in', [False,True])])

                            if contactos_del_cliente_encontrado:
                                for contacto in contactos_del_cliente_encontrado:
                                    _logger.warning("Contacto del Cliente encontrado en Odoo")

                                    #Se debe verificar si este contacto encontrado en Odoo cumple con las siguientes características
                                    #1- Que posea como compañía padre al Cliente con el mismo fk_id_cliente del SGC.
                                    #2- Que posea una cédula valida.
                                    #3- Que no esté repetido (Consultar detalles a revisar)

                                    data_res = chequeos.MaestroChequeos.check_contact_data_contacto_cliente_encontrado(self, contacto, procede_reg_or_edit, errores, registro_tecnico)

                                    #Se obtiene la data posterior al chequeo.
                                    procede_reg_or_edit = data_res[0]
                                    errores = data_res[1]
                                    registro_tecnico = data_res[2]

                                    if procede_reg_or_edit:
                                        _logger.warning("Nombre del contacto SGC: "+str(row.get('nombre'))+" - "+str(row.get('apellido')))
                                        _logger.warning("Cédula del contacto SGC: "+str(row.get('cedula')))
                                        _logger.warning("Nombre del contacto Odoo: "+str(contacto.name))
                                        _logger.warning("Cédula del contacto Odoo: "+str(contacto.identification_id))
                                        _logger.warning("Correo del contacto SGC: "+str(row.get('email')))
                                        _logger.warning("Correo del contacto Odoo: "+str(contacto.email))
                                        _logger.warning("Id Cliente de la Compañía padre asociada: "+str(contacto.parent_id.id_cliente))
                                        _logger.warning("fk_id_cliente de este contacto: "+str(row.get('fk_id_cliente')))
                            
                                        if not row.get("DateModified"):
                                            row['DateModified'] = datetime.now()

                                        try:
                                            #Se deben buscar los privilegios en la tabla de privilegios del SGC para
                                            #sincronizarlos correctamente con la instancia Odoo.
                                            cursor_b = cnxn.cursor(as_dict=True)

                                            stored_proc = """SELECT fk_id_privilegio FROM [Privilegio_Contacto] WHERE fk_id_contacto = """+str(row.get("id_contacto"))
                                            cursor_b.execute(stored_proc)
                                            privilegios = cursor_b.fetchall()

                                            _logger.warning("Resultado: "+str(privilegios))

                                            all_privilegios = [(5,0,0)]

                                            for item in privilegios:
                                                _logger.warning("Privilegio asociado al contacto: "+str(item.get('fk_id_privilegio')))

                                                all_privilegios.append((0, 0, {
                                                                        'name': str(item.get('fk_id_privilegio')),
                                                }))

                                            #Se asignan los privilegios nuevos
                                            contacto.privilegio_ids = all_privilegios

                                        except pymssql.Error as e:
                                            _logger.warning("No se pudieron adquirir los privilegios de este contacto desde el SGC.")
                                            _logger.warning("Error: "+str(e))

                                        contador_contacto_encontrado += 1

                                        #En caso de que el nivel de escalabilidad venga n null se coloca por defecto en 1.
                                        if not row.get("ScalabilityLevelId"):
                                            row['ScalabilityLevelId'] = 1

                                        #Se asigna la escalabilidad
                                        contacto.ScalabilityLevel = str(row.get("ScalabilityLevelId"))

                                        #En caso de no poseer, se debe asignar el id del contacto asociado y el id cliente relacionado
                                        #if not contacto.id_contacto > 0:
                                        contacto.id_contacto = row.get('id_contacto')
                                        #if not contacto.id_cliente > 0:
                                        contacto.id_cliente = row.get('fk_id_cliente')

                                        #Fecha de modificacion desde el SGC.
                                        contacto.contacto_date_modified = row.get("DateModified")

                                        #Cédula contacto para posteriores ediciones y sincronizaciones.
                                        contacto.cedula_contacto = str(letra_documento_identidad)+str(documento_identidad)

                                        #Para evitar que se rechequee y reinserte la data en la bd.
                                        contacto.revisar_id_cliente_sgc = False
                                        contacto.revisar_id_contacto_sgc = False

                                        ########## - ACTUALIZACIÓN RECURRENTE - ##########
                                        ########## - ACTUALIZACIÓN RECURRENTE - ##########

                                        #Solo en el caso de que la sincronización sea recurrente se debe actualizar
                                        #toda la data del contacto desde el SGC hacia Odoo
                                        if tipo_sync == 'Sync_recurrente':
                                            registro_tecnico.append("Actualización recurrente.")

                                            #Por ahora se descarta la edición del nombre por incompatibilidad de campos
                                            #entre SGC y Odoo, se debe realizar una modificación al SGC para poder llegar
                                            #al resultado deseado (Que en SGC se escriba nombre y apellido en el mismo campo)

                                            contacto.name = row.get("nombre")+" "+row.get("apellido")#row.get("nombre")
                                            contacto.apellido_contacto = '' #row.get("apellido")
                                            contacto.nationality = letra_documento_identidad
                                            contacto.cedula_contacto = str(letra_documento_identidad)+str(documento_identidad)
                                            contacto.identification_id = documento_identidad
                                            contacto.phone = row.get("telefono")
                                            contacto.mobile = row.get("celular")
                                            contacto.email = row.get("email")
                                            contacto.cargo_contacto = row.get("cargo")
                                            contacto.x_studio_cargo = row.get("cargo")
                                            contacto.prioridad_contacto = row.get("prioridad")
                                            contacto.habilitado_contacto = row.get("habilitado")
                                            contacto.id_cliente = row.get("fk_id_cliente")
                                            contacto.tipo_contacto = str(row.get("fk_id_tipo_contacto"))

                                            id_rol = 1
                                            #Detectar el rol en Odoo
                                            if row.get("fk_id_tipo_contacto") == 1:
                                                id_rol = self.env['x_rol'].search([('x_name', '=', 'Técnico')])
                                                _logger.warning("Rol en Odoo: "+str(id_rol))
                                            if row.get("fk_id_tipo_contacto") == 2:
                                                id_rol = self.env['x_rol'].search([('x_name', '=', 'Administrativo')])
                                                _logger.warning("Rol en Odoo: "+str(id_rol))
                                            if row.get("fk_id_tipo_contacto") == 3:
                                                id_rol = self.env['x_rol'].search([('x_name', '=', 'Ejecutivo')])
                                                _logger.warning("Rol en Odoo: "+str(id_rol))

                                            contacto.rol = id_rol #row.get("fk_id_tipo_contacto")
                                            contacto.contacto_activo = row.get("activo")

                                            #Se archiva o desarchiva automáticamente 
                                            #según el valor del campo "Activo" en SGC.

                                            #Solo se debe archivar/desarchivar el contacto cuando el contacto no
                                            #tenga un Usuario en la instancia Odoo (Validación nativa).
                                            odoo_users = self.env['res.users'].search([('partner_id', '=', contacto.id)])
                                            _logger.warning("Usuario asociado al contacto/cliente en Odoo: "+str(odoo_users))
                                            
                                            if not odoo_users:
                                                if int(row.get("activo")) == 0:
                                                    contacto.active = False
                                                else:
                                                    contacto.active = True
                                            else:
                                                registro_tecnico.append("No se Archivan/desarchivan contactos que tengan Usuario en Odoo")


                                        ########## - ACTUALIZACIÓN RECURRENTE - ##########
                                        ########## - ACTUALIZACIÓN RECURRENTE - ##########

                                        registro_tecnico.append("""<p>Se encontró en Odoo un registro de nombre: """+str(contacto.name)+"""</p>
                                                                <p>Con la siguiente compañía relacionada: """+str(contacto.parent_id)+"""</p>
                                                                <p>fk_id_cliente de la compañía relacionada en Odoo: """+str(contacto.parent_id.id_cliente)+"""</p>
                                                                <p>Se le actualiza el nivel de escalabilidad a: """+str(row.get('ScalabilityLevelId'))+"""</p>
                                                                <p>Se actualizan sus privilegios a: """+str(all_privilegios)+"""</p>""")

                                        chequeos.MaestroChequeos.check_contact_data_generador_historico(self, errores, False, row, registro_tecnico, 'Actualización registro existente', 'orange')

                                    else:
                                        chequeos.MaestroChequeos.check_contact_data_generador_historico(self, errores, False, row, registro_tecnico, 'error', 'red')
                            else:
                                #Si no encuentra el contacto y si valida la data correctamente entonces se registra el Contacto

                                _logger.warning("Se va a registrar un contacto nuevo desde SGC hacia Odoo.")

                                #Solo permitir la creación del contacto nuevo si se encuentra al menos la cédula de identidad o el correo electrónico.
                                cliente_asociado_sgc_odoo = self.env['res.partner'].search(['|',('id_cliente', '=', row.get("fk_id_cliente")),('company_type_stored', '=', 'company'),('id_cliente', '=', row.get("fk_id_cliente")),('parent_id', '=', False)], limit=1)

                                #Verificación del parámetro "activo" desde SGC.
                                #Se archiva o desarchiva automáticamente 
                                #según el valor del campo "Activo" en SGC.

                                registro_tecnico.append("Cliente SGC asociado al contacto que se pretende crear: "+str(cliente_asociado_sgc_odoo))

                                if cliente_asociado_sgc_odoo:
                                    #Lista negra de Clientes que no deben tomarse en cuenta para sincronizar sus contactos
                                    #Se agregan los rif para evitar errores al momento de comparar.
                                    #Se debe crear una funcionalidad que permita indicar desde Odoo cuales son los Clientes
                                    #en lista negra, para así evitar sincronizaciones indeseadas.
                                    black_list_clientes = ['305027498']

                                    data_res = chequeos.MaestroChequeos.check_contact_data_contacto_cliente_blacklist(self, cliente_asociado_sgc_odoo, black_list_clientes, procede_reg_or_edit, errores, registro_tecnico)
                                    
                                    #Se obtiene la data posterior al chequeo.
                                    procede_reg_or_edit = data_res[0]
                                    errores = data_res[1]
                                    registro_tecnico = data_res[2]

                                    #Se aplica esta nueva condicional para el caso de haber encontrado contactos asociados
                                    #a Clientes en lista negra.

                                    #Se verifica si el contacto que en teoría no existe en Odoo esta asociado a un Cliente
                                    #que aun no ha sido sincronizado, de esta manera evitamos la duplicidad.
                                    _logger.warning("Documento de identidad a revisar: "+str(documento_identidad))
                                    data_res = chequeos.MaestroChequeos.check_contact_data_contacto_repetido_sin_cliente_sincronizado(self, documento_identidad, procede_reg_or_edit, errores, registro_tecnico)
                                    
                                    #Se obtiene la data posterior al chequeo.
                                    procede_reg_or_edit = data_res[0]
                                    errores = data_res[1]
                                    registro_tecnico = data_res[2]

                                    if procede_reg_or_edit:
                                        activo = True
                                        #Solo se debe archivar/desarchivar el contacto cuando el contacto no
                                        #tenga un Usuario en la instancia Odoo (Validación nativa).

                                        #Hotfix #25 (Lineas descartadas ya que se ttrata de contactos nuevos sin data en Odoo.)
                                        #odoo_users = self.env['res.users'].search([('partner_id', '=', contacto.id)])
                                        #_logger.warning("Usuario asociado al contacto/cliente en Odoo: "+str(odoo_users))

                                        #if not odoo_users:
                                        #    if int(row.get("activo")) == 0:
                                        #        contacto.active = False
                                        #    else:
                                        #        contacto.active = True
                                        #else:
                                        #    registro_tecnico.append("No se Archivan/desarchivan contactos que tengan Usuario en Odoo")

                                        #Se deben buscar los privilegios en la tabla de privilegios del SGC para
                                        #sincronizarlos correctamente con la instancia Odoo.
                                        try:
                                            cursor_b = cnxn.cursor(as_dict=True)

                                            stored_proc = """SELECT fk_id_privilegio FROM [Privilegio_Contacto] WHERE fk_id_contacto = """+str(row.get("id_contacto"))
                                            cursor_b.execute(stored_proc)
                                            privilegios = cursor_b.fetchall()

                                            _logger.warning("Resultado: "+str(privilegios))

                                            all_privilegios = [(5,0,0)]

                                            for item in privilegios:
                                                _logger.warning("Privilegio asociado al contacto: "+str(item.get('fk_id_privilegio')))

                                                all_privilegios.append((0, 0, {
                                                                        'name': str(item.get('fk_id_privilegio')),
                                                }))

                                        except pymssql.Error as e:
                                            _logger.warning("No se pudieron adquirir los privilegios de este contacto desde el SGC.")
                                            _logger.warning("Error: "+str(e))

                                        _logger.warning("Privilegios totales: "+str(all_privilegios))

                                        #Se cuenta una nueva creación exitosa!
                                        contador_contactos_clientes_creados += 1

                                        id_rol = 1
                                        #Detectar el rol en Odoo
                                        if row.get("fk_id_tipo_contacto") == 1:
                                            id_rol = self.env['x_rol'].search([('x_name', '=', 'Técnico')])
                                            _logger.warning("Rol en Odoo: "+str(id_rol))
                                        if row.get("fk_id_tipo_contacto") == 2:
                                            id_rol = self.env['x_rol'].search([('x_name', '=', 'Administrativo')])
                                            _logger.warning("Rol en Odoo: "+str(id_rol))
                                        if row.get("fk_id_tipo_contacto") == 3:
                                            id_rol = self.env['x_rol'].search([('x_name', '=', 'Ejecutivo')])
                                            _logger.warning("Rol en Odoo: "+str(id_rol))
                                        
                                        #Fix #12: en la creación (SGC --> Odoo) se establece nombre y apellido concatenados.
                                        self.env['res.partner'].create({
                                                                        'company_type': 'person',
                                                                        'id_contacto': row.get("id_contacto"),
                                                                        'name': row.get("nombre")+" "+row.get("apellido"),
                                                                        'parent_id': cliente_asociado_sgc_odoo.id,
                                                                        'apellido_contacto': '',#row.get("apellido"), --> A la espera por el fix del nombre y el apellido.
                                                                        'nationality': letra_documento_identidad,
                                                                        'cedula_contacto': letra_documento_identidad+documento_identidad,
                                                                        'identification_id': documento_identidad,
                                                                        'phone': row.get("telefono"),
                                                                        'mobile': row.get("celular"),
                                                                        'email': row.get("email"),
                                                                        'cargo_contacto': row.get("cargo"),
                                                                        'x_studio_cargo': row.get("cargo"),
                                                                        'prioridad_contacto': row.get("prioridad"),
                                                                        'habilitado_contacto': row.get("habilitado"),
                                                                        'id_cliente': row.get("fk_id_cliente"),
                                                                        'tipo_contacto': str(row.get("fk_id_tipo_contacto")),
                                                                        'rol': id_rol.id, #row.get("fk_id_tipo_contacto"),
                                                                        'contacto_activo': row.get("activo"),
                                                                        'contacto_date_modified': row.get("DateModified"),
                                                                        'client_date_modified': False,
                                                                        'ScalabilityLevel': str(row.get("ScalabilityLevelId")),
                                                                        'revisar_id_cliente_sgc': False,
                                                                        'revisar_id_contacto_sgc': False,
                                                                        'create_from_sync': True,
                                                                        'active': activo,
                                                                        'privilegio_ids': all_privilegios,
                                        
                                                                        #Campos de la instancia productivo Dayco
                                                                        'partner_category': '1',
                                                                        'wh_iva_rate': 0,
                                        
                                                                        #Se deben asignar de ser necesarios los campos
                                                                        #- property_account_payable_id
                                                                        #- property_account_receivable_id
                                                                    })
                                        
                                        registro_tecnico.append('Se ha creado correctamente el Contacto')
                                        chequeos.MaestroChequeos.check_contact_data_generador_historico(self, errores, False, row, registro_tecnico, 'Creación', 'green')
                                    else:
                                        chequeos.MaestroChequeos.check_contact_data_generador_historico(self, errores, False, row, registro_tecnico, 'error', 'red')
                                else:
                                    errores.append("""
                                                    <p><h2>Contacto en Odoo repetido sin compañía previamente sincronizada</h2></p>
                                                    <p>
                                                        Debe verificar y registrar primero al Cliente en SGC para que se sincronize correctamente antes de registrar este contacto.
                                                    </p>
                                                    """)
                                    chequeos.MaestroChequeos.check_contact_data_generador_historico(self, errores, False, row, registro_tecnico, 'error', 'red')
                else:
                    errores.append("""
                                    <p><h2>Contacto desde el SGC sin cédula de identidad / cédula invalida </h2></p>
                                    <p>
                                        Tambien se puede tratar de un error en el formato de los datos ingresados, revise el teléfono, cédula o celular. </p>
                                    <p>
                                    """)
                    chequeos.MaestroChequeos.check_contact_data_generador_historico(self, errores, False, row, registro_tecnico, 'error', 'red')
            else:
                #Buscar editar por la combinación de id_cliente+id_contacto ya que pueden borrar la cédula en cualquiera de los dos lados.

                contactos_con_id_cliente_y_id_contacto = self.env['res.partner'].search([('id_contacto', '=', row.get('id_contacto')),('parent_id.id_cliente', '=', row.get("fk_id_cliente")),('active', 'in', [False,True])])

                if contactos_con_id_cliente_y_id_contacto:
                    for contacto in contactos_con_id_cliente_y_id_contacto:
                        _logger.warning("Contacto encontrado en Odoo con ID Cliente y ID Contacto.")

                        #Se encontró un contacto para actualizar
                        contador_contacto_encontrado += 1

                        #Sincronización recurrente de manera obligatoria.
                        _logger.warning("Nombre del contacto SGC: "+str(row.get('nombre'))+" - "+str(row.get('apellido')))
                        _logger.warning("Cédula del contacto SGC: "+str(row.get('cedula')))
                        _logger.warning("Nombre del contacto Odoo: "+str(contacto.name))
                        _logger.warning("Cédula del contacto Odoo: "+str(contacto.identification_id))
                        _logger.warning("Correo del contacto SGC: "+str(row.get('email')))
                        _logger.warning("Correo del contacto Odoo: "+str(contacto.email))
                        _logger.warning("Id Cliente de la Compañía padre asociada: "+str(contacto.parent_id.id_cliente))
                        _logger.warning("fk_id_cliente de este contacto: "+str(row.get('fk_id_cliente')))
            
                        if not row.get("DateModified"):
                            row['DateModified'] = datetime.now()

                        try:
                            #Se deben buscar los privilegios en la tabla de privilegios del SGC para
                            #sincronizarlos correctamente con la instancia Odoo.
                            cursor_b = cnxn.cursor(as_dict=True)

                            stored_proc = """SELECT fk_id_privilegio FROM [Privilegio_Contacto] WHERE fk_id_contacto = """+str(row.get("id_contacto"))
                            cursor_b.execute(stored_proc)
                            privilegios = cursor_b.fetchall()

                            _logger.warning("Resultado: "+str(privilegios))

                            all_privilegios = [(5,0,0)]

                            for item in privilegios:
                                _logger.warning("Privilegio asociado al contacto: "+str(item.get('fk_id_privilegio')))

                                all_privilegios.append((0, 0, {
                                                        'name': str(item.get('fk_id_privilegio')),
                                }))

                            #Se asignan los privilegios nuevos
                            contacto.privilegio_ids = all_privilegios

                        except pymssql.Error as e:
                            _logger.warning("No se pudieron adquirir los privilegios de este contacto desde el SGC.")
                            _logger.warning("Error: "+str(e))

                        contador_contacto_encontrado += 1

                        #En caso de que el nivel de escalabilidad venga n null se coloca por defecto en 1.
                        if not row.get("ScalabilityLevelId"):
                            row['ScalabilityLevelId'] = 1

                        #Se asigna la escalabilidad
                        contacto.ScalabilityLevel = str(row.get("ScalabilityLevelId"))

                        #En caso de no poseer, se debe asignar el id del contacto asociado y el id cliente relacionado
                        #if not contacto.id_contacto > 0:
                        contacto.id_contacto = row.get('id_contacto')
                        #if not contacto.id_cliente > 0:
                        contacto.id_cliente = row.get('fk_id_cliente')

                        #Fecha de modificacion desde el SGC.
                        contacto.contacto_date_modified = row.get("DateModified")

                        #Cédula contacto para posteriores ediciones y sincronizaciones.
                        contacto.cedula_contacto = str(letra_documento_identidad)+str(documento_identidad)

                        #Para evitar que se rechequee y reinserte la data en la bd.
                        contacto.revisar_id_cliente_sgc = False
                        contacto.revisar_id_contacto_sgc = False

                        ########## - ACTUALIZACIÓN RECURRENTE - ##########
                        ########## - ACTUALIZACIÓN RECURRENTE - ##########

                        #Solo en el caso de que la sincronización sea recurrente se debe actualizar
                        #toda la data del contacto desde el SGC hacia Odoo
                        if tipo_sync == 'Sync_recurrente':
                            registro_tecnico.append("Actualización recurrente.")

                            #Por ahora se descarta la edición del nombre por incompatibilidad de campos
                            #entre SGC y Odoo, se debe realizar una modificación al SGC para poder llegar
                            #al resultado deseado (Que en SGC se escriba nombre y apellido en el mismo campo)

                            contacto.name = row.get("nombre")+" "+row.get("apellido") #row.get("nombre")
                            contacto.apellido_contacto = row.get("apellido")
                            contacto.nationality = letra_documento_identidad
                            contacto.cedula_contacto = str(letra_documento_identidad)+str(documento_identidad)
                            contacto.identification_id = documento_identidad
                            contacto.phone = row.get("telefono")
                            contacto.mobile = row.get("celular")
                            contacto.email = row.get("email")
                            contacto.cargo_contacto = row.get("cargo")
                            contacto.x_studio_cargo = row.get("cargo")
                            contacto.prioridad_contacto = row.get("prioridad")
                            contacto.habilitado_contacto = row.get("habilitado")
                            contacto.id_cliente = row.get("fk_id_cliente")
                            contacto.tipo_contacto = str(row.get("fk_id_tipo_contacto"))

                            id_rol = 1
                            #Detectar el rol en Odoo
                            if row.get("fk_id_tipo_contacto") == 1:
                                id_rol = self.env['x_rol'].search([('x_name', '=', 'Técnico')])
                                _logger.warning("Rol en Odoo: "+str(id_rol))
                            if row.get("fk_id_tipo_contacto") == 2:
                                id_rol = self.env['x_rol'].search([('x_name', '=', 'Administrativo')])
                                _logger.warning("Rol en Odoo: "+str(id_rol))
                            if row.get("fk_id_tipo_contacto") == 3:
                                id_rol = self.env['x_rol'].search([('x_name', '=', 'Ejecutivo')])
                                _logger.warning("Rol en Odoo: "+str(id_rol))

                            contacto.rol = id_rol #row.get("fk_id_tipo_contacto")
                            contacto.contacto_activo = row.get("activo")

                            #Se archiva o desarchiva automáticamente 
                            #según el valor del campo "Activo" en SGC.

                            #Solo se debe archivar/desarchivar el contacto cuando el contacto no
                            #tenga un Usuario en la instancia Odoo (Validación nativa).
                            odoo_users = self.env['res.users'].search([('partner_id', '=', contacto.id)])
                            _logger.warning("Usuario asociado al contacto/cliente en Odoo: "+str(odoo_users))

                            if not odoo_users:
                                if int(row.get("activo")) == 0:
                                    contacto.active = False
                                else:
                                    contacto.active = True
                            else:
                                registro_tecnico.append("No se Archivan/desarchivan contactos que tengan Usuario en Odoo")


                        ########## - ACTUALIZACIÓN RECURRENTE - ##########
                        ########## - ACTUALIZACIÓN RECURRENTE - ##########

                        registro_tecnico.append("""<p>Se encontró en Odoo un registro de nombre: """+str(contacto.name)+"""</p>
                                                <p>Con la siguiente compañía relacionada: """+str(contacto.parent_id)+"""</p>
                                                <p>fk_id_cliente de la compañía relacionada en Odoo: """+str(contacto.parent_id.id_cliente)+"""</p>
                                                <p>Se le actualiza el nivel de escalabilidad a: """+str(row.get('ScalabilityLevelId'))+"""</p>
                                                <p>Se actualizan sus privilegios a: """+str(all_privilegios)+"""</p>""")

                        chequeos.MaestroChequeos.check_contact_data_generador_historico(self, errores, False, row, registro_tecnico, 'Actualización registro existente', 'orange')
                else:
                    errores.append("""
                                        <p><h2>Contacto desde el SGC sin cédula de identidad / cédula invalida </h2></p>
                                        <p>
                                            Tambien se puede tratar de un error en el formato de los datos ingresados, revise el teléfono, cédula o celular. </p>
                                        <p>
                                        """)
                    chequeos.MaestroChequeos.check_contact_data_generador_historico(self, errores, False, row, registro_tecnico, 'error', 'red')

            #Sea que se haya creado o no el registro desde Odoo hacia SGC se debe modificar el campo 'DateModified'
            #en SGC para saber cuando fue la última vez que paso por allí.
            _logger.warning("Última fecha de modificación / revisión del Contacto en SGC: "+str(row.get("DateModified")))
            _logger.warning("Fecha de sincronización a establecer en el registro: "+str(datetime.now()))

            cursor_b = cnxn.cursor(as_dict=True)

            #En caso de que la fecha de modificación no exista, se debe establecer esta fecha en la base de
            #datos del SGC cuando sea creado o editado el contacto en el proceso de sincronización.
            stored_proc = """UPDATE [Contacto] SET DateSincronyzed = %s WHERE id_contacto = %s;"""
            params = (datetime.now() - timedelta(hours=4),int(row.get("id_contacto")))

            cursor_b.execute(stored_proc, params)
            cnxn.commit()
            cursor_b.close()

            #Se contabiliza cada registro analizado
            contador_registros_analizados += 1
            _logger.warning("Cliente/Contacto #: "+str(contador_registros_analizados))
            _logger.warning("Contactos creados #: "+str(contador_contactos_clientes_creados))

            if contador_contactos_clientes_creados > 900 or contador_registros_analizados > 900:
                #Tomar de 900 en 900 para no saturar la base de datos
                break

        _logger.warning("Total de registros analizados del SGC: "+str(contador_contactos_relacionados))
        _logger.warning("Total de registros encontrados en Odoo: "+str(contador_contacto_encontrado))
        _logger.warning("Total de registros creados en Odoo: "+str(contador_contactos_clientes_creados))

        return True

########## - Verificación de data de contactos SGC - ##########
########## - Verificación de data de contactos SGC - ##########
########## - Verificación de data de contactos SGC - ##########

########## - Verificación de datos activación / desactivación SGC - Odoo - ##########

    def CheckContactsChangesSGCtoOdoo(self, contactos_sgc, cnxn):
        _logger.warning("Se va a revisar la data de activación / desactivación de los contactos almacenados en Odoo en la base de datos del SGC")

        for contacto in contactos_sgc:

            #Solo verificar contactos que tengan id_contacto valido del SGC.
            if contacto.id_contacto > 0:
                #_logger.warning("Contacto a revisar: "+str(contacto.name))
                #_logger.warning("ID de contacto del SGC: "+str(contacto.id_contacto))

                cursor_b = cnxn.cursor(as_dict=True)

                stored_proc = """SELECT nombre, activo FROM [Contacto] WHERE id_contacto = """+str(contacto.id_contacto)
                cursor_b.execute(stored_proc)
                resultado = cursor_b.fetchall()

                #_logger.warning("Resultado: "+str(resultado))

                activo_int = 0
                if contacto.active:
                    activo_int = 1
                
                if not activo_int == int(resultado[0].get("activo")):
                    contacto.revisar_id_cliente_sgc = False
                    contacto.revisar_id_contacto_sgc = False

                    if int(resultado[0].get("activo")) == 0:
                        contacto.active = False
                        #Se registra la activación /desactivación de datos entre el sgc y Odoo
                        self.env['sgc.odoo.history'].create({
                            'name': str(contacto.name),
                            'fecha_registro': datetime.now(),
                            'tipo_error': 'Sync SGC --> Odoo ('+str(contacto.company_type_stored)+')',
                            'registro_operacion': 'Se ha desactivado correctamente el registro',
                            'registro_tecnico': 'None',
                            'category': '<p style="color:green;">Desactivación</p>',
                        })
                    else:
                        contacto.active = True
                        self.env['sgc.odoo.history'].create({
                            'name': str(contacto.name),
                            'fecha_registro': datetime.now(),
                            'tipo_error': 'Sync SGC --> Odoo ('+str(contacto.company_type_stored)+')',
                            'registro_operacion': 'Se ha activado correctamente el registro',
                            'registro_tecnico': 'None',
                            'category': '<p style="color:green;">Activación</p>',
                        })
                #else:
                #    _logger.warning("No se ha cambiado el status del contacto, sin cambios.")
