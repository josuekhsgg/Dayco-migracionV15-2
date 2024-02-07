# -*- coding: utf-8 -*-

from datetime import date, datetime, timedelta
from odoo import models, fields, api, _
import logging
import pymssql
#import pyodbc #Librería de conexión a bases de datos SQL.
import string
from datetime import date, datetime, timedelta
from odoo.exceptions import UserError, ValidationError
import re

_logger = logging.getLogger(__name__)

class MaestroChequeos():
    #Se verifica la cédula y otros valores proveninentes del registro del SGC.
    def check_contact_data_cedula(self,row,procede,errores,registro_tecnico):
        _logger.warning("Data a analizar: "+str(row))
        
        #Data que se envía de vuelta con los resultados obtenidos
        resultado = list()

        #Variable para controlar el registro/edición de los nuevos contactos o clientes desde SGC hacia Odoo.
        procede_reg_or_edit = procede

        #Dependiendo del tipo de verificación se procede con una verificación en especifico.
        #Solo se ejecuta si aún procede el registro o la edición del Contacto o Cliente desde el SGC hacia Odoo.
        if procede_reg_or_edit:

            if not row.get('cedula'):
                _logger.warning("Cedula en None")
                row['cedula'] = ''
            
            p = re.compile('[^VEP0-9]')
            resultado_search = p.search(row.get('cedula'))

            if row.get('cedula') and not resultado_search:
                letra_documento_identidad = ''
                documento_identidad = ''

                #Se agrega condición maestra que establece que si la cédula está vacía entonces
                #se crea el contacto con la cédula vacía.
                if not str(row.get('cedula')) == '':
                    _logger.warning("Cédula a analizar: "+str(row.get('cedula')))
                    #Dependiendo de si la cédula tiene letra o no, se acomoda desde SGC a Odoo.
                    if str(row.get('cedula')).find("V") == -1 and str(row.get('cedula')).find("E") == -1:
                        _logger.warning("Ajustando cédula sin letra desde SGC a Odoo.")

                        if int(row.get('cedula')) < 80000000:
                            letra_documento_identidad = 'V'
                            documento_identidad = str(row.get('cedula'))
                            row['cedula'] = 'V'+str(row.get('cedula'))
                        else:
                            letra_documento_identidad = 'E'
                            documento_identidad = str(row.get('cedula'))
                            row['cedula'] = 'E'+str(row.get('cedula'))

                    else:
                        _logger.warning("Detectando tipo de documento de identidad.")
                        _logger.warning(str(row.get('cedula')).find('V'))

                        if not str(row.get('cedula')).find("V") == -1:
                            _logger.warning("Cortando V!")
                            pos_letra = str(row.get('cedula')).find('V')
                            letra_documento_identidad = str(row.get('cedula'))[:pos_letra+1]
                            documento_identidad = str(row.get('cedula'))[pos_letra+1:]
                        elif not str(row.get('cedula')).find("E") == -1:
                            _logger.warning("Cortando E!")
                            pos_letra = str(row.get('cedula')).find('E')
                            letra_documento_identidad = str(row.get('cedula'))[:pos_letra+1]
                            documento_identidad = str(row.get('cedula'))[pos_letra+1:]
                        elif not str(row.get('cedula')).find("P") == -1:
                            _logger.warning("Cortando P!")
                            pos_letra = str(row.get('cedula')).find('P')
                            letra_documento_identidad = str(row.get('cedula'))[:pos_letra+1]
                            documento_identidad = str(row.get('cedula'))[pos_letra+1:]
                        else:
                            _logger.warning("Letra no reconocida, por favor verifique este registro.")
                else:
                    documento_identidad = False

                if str(documento_identidad).isdigit():
                    row['cedula'] = documento_identidad
                else:
                    _logger.warning("Cedula con inconsistencias, no se procede con el registro o edición de este registro desde el SGC.")
                    #Cedula con mas de una letra, posible error de tipeo.
                    procede_reg_or_edit = False
                    errores.append("""
                                    <p><h2>Contacto con mas de una letra en la cédula</h2></p>
                                    <p>
                                        Verifique el registro en el SGC e intente nuevamente. </p>
                                    <p>
                                    """)
            
                #Una vez completada la verificación se devuelve el array resultante
                resultado.append(row)
                resultado.append(procede_reg_or_edit)
                resultado.append(errores)
                resultado.append(letra_documento_identidad)
                resultado.append(documento_identidad)
                resultado.append(registro_tecnico)

                return resultado
            else:
                errores.append("""
                                    <p><h2>Contacto sin cédula/cédula invalida</h2></p>
                                    <p>
                                        Verifique el registro en el SGC e intente nuevamente. </p>
                                    <p>
                                    """)
                resultado.append(row)
                resultado.append(False)
                resultado.append(errores)
                resultado.append('')
                resultado.append('')
                resultado.append(registro_tecnico)

                return resultado
        
        else:
            errores.append("Pausada la sincronización de este contacto, revise el log.")

            resultado.append(False)
            resultado.append(False)
            resultado.append(errores)
            resultado.append('')
            resultado.append('')
            resultado.append(registro_tecnico)

            return False

    def check_contact_data_contacto_cliente_encontrado(self,contacto,procede,errores,registro_tecnico):
        _logger.warning("Data del contacto a analizar (CCE): "+str(contacto))
        
        #Data que se envía de vuelta con los resultados obtenidos
        resultado = list()

        #Variable para controlar el registro/edición de los nuevos contactos o clientes desde SGC hacia Odoo.
        procede_reg_or_edit = procede

        #Dependiendo del tipo de verificación se procede con una verificación en especifico.
        #Solo se ejecuta si aún procede el registro o la edición del Contacto o Cliente desde el SGC hacia Odoo.
        if procede_reg_or_edit:
            #Se verifica porque no se ha registrado el contacto
            if contacto.facturable:
                procede_reg_or_edit = False
                errores.append("""
                            <p><h2>Contacto con Check de facturable marcado</h2></p>
                            <p>
                                Solo los Clientes naturales tienen este check marcado </p>
                            <p>
                            """)
            if contacto.partner_type_id:
                procede_reg_or_edit = False
                errores.append("""
                            <p><h2>Contacto con campo "Tipo de Cliente" establecido</h2></p>
                            <p>
                                Solo los Clientes naturales o compañías tienen este Campo establecido </p>
                            <p>
                            """)
            if not contacto.parent_id:
                procede_reg_or_edit = False
                errores.append("""
                            <p><h2>Contacto sin compañía relacionada</h2></p>
                            <p>
                                Solo los Clientes naturales o compañías tienen este Campo vacío </p>
                            <p>
                            """)
            
            #Una vez completada la verificación se devuelve el array resultante
            resultado.append(procede_reg_or_edit)
            resultado.append(errores)
            resultado.append(registro_tecnico)

            return resultado

        else:
            #Se debe retornar un array en False para prevenir errores de verificación de datos.
            errores.append("Pausada la sincronización de este contacto, revise el log.")
            resultado.append(False)
            resultado.append(errores)
            resultado.append(registro_tecnico)

            return resultado
    
    def check_contact_data_contacto_cliente_blacklist(self,cliente_asociado_sgc_odoo,black_list_clientes,procede,errores,registro_tecnico):
        _logger.warning("Data del contacto(s) a analizar (Blacklist): "+str(cliente_asociado_sgc_odoo))
        _logger.warning("Contacto RIF (Odoo): "+str(cliente_asociado_sgc_odoo.vat))

        #Data que se envía de vuelta con los resultados obtenidos
        resultado = list()

        #Variable para controlar el registro/edición de los nuevos contactos o clientes desde SGC hacia Odoo.
        procede_reg_or_edit = procede

        #Dependiendo del tipo de verificación se procede con una verificación en especifico.
        #Solo se ejecuta si aún procede el registro o la edición del Contacto o Cliente desde el SGC hacia Odoo.
        if procede_reg_or_edit:
            for item in black_list_clientes:
                if item in cliente_asociado_sgc_odoo.vat:
                    _logger.warning("Cliente en lista negra, no se sincronizan sus contactos")
                    errores.append('Contacto relacionado con empresa en lista negra: '+str(cliente_asociado_sgc_odoo.name))

                    procede_reg_or_edit = False
                    
            #Una vez completada la verificación se devuelve el array resultante
            resultado.append(procede_reg_or_edit)
            resultado.append(errores)
            resultado.append(registro_tecnico)

            return resultado

        else:
            #Se debe retornar un array en False para prevenir errores de verificación de datos.
            errores.append("Pausada la sincronización de este contacto, revise el log.")
            resultado.append(False)
            resultado.append(errores)
            resultado.append(registro_tecnico)

            return resultado
    
    def check_contact_data_contacto_repetido_sin_cliente_sincronizado(self,documento_identidad,procede,errores,registro_tecnico):
        _logger.warning("Data del contacto a analizar (CRSCS): "+str(documento_identidad))

        #Data que se envía de vuelta con los resultados obtenidos
        resultado = list()

        #Variable para controlar el registro/edición de los nuevos contactos o clientes desde SGC hacia Odoo.
        procede_reg_or_edit = procede

        #Dependiendo del tipo de verificación se procede con una verificación en especifico.
        #Solo se ejecuta si aún procede el registro o la edición del Contacto o Cliente desde el SGC hacia Odoo.
        if procede_reg_or_edit:
            if documento_identidad:
                _logger.warning("Chequeando ocurrencias solo en documento de identidad!.")
                registro_tecnico.append("Chequeando ocurrencias solo en documento de identidad!.")

                registro_repetido = self.env['res.partner'].search(['|',('vat', '=', str(documento_identidad)),('identification_id', '=', str(documento_identidad))], limit=1)
                
                _logger.warning("Registros repetidos encontrados: "+str(registro_repetido))
                registro_tecnico.append("Registros repetidos encontrados: "+str(registro_repetido))

                if registro_repetido:
                    procede_reg_or_edit = False
                    errores.append("Se encontró un registro en Odoo asociado a un Cliente que no se ha sincronizado, por favor verifique la información del Cliente antes de sincronizar este contacto.")
                    
            #Una vez completada la verificación se devuelve el array resultante
            resultado.append(procede_reg_or_edit)
            resultado.append(errores)
            resultado.append(registro_tecnico)

            return resultado

        else:
            #Se debe retornar un array en False para prevenir errores de verificación de datos.
            errores.append("Pausada la sincronización de este contacto, revise el log.")
            resultado.append(False)
            resultado.append(errores)
            resultado.append(registro_tecnico)

            return resultado

    def check_contact_data_generador_historico(self,errores,contacto,row,registro_tecnico,tipo_msg,color):
        _logger.warning("Contacto a registrar en el historico: "+str(row)+" - "+str(contacto))

        #Cada item debe colocarse en una cadena formateada para su lectura comoda.
        registro_tecnico_formateado = ''
        for item in registro_tecnico:
            registro_tecnico_formateado = registro_tecnico_formateado+"<p>"+item+"</p>"

        if row:
            self.env['sgc.odoo.history'].create({
                                                'name': str(row.get('nombre'))+' '+str(row.get('apellido')),
                                                'fecha_registro': datetime.now(),
                                                'tipo_error': 'Sync SGC --> Odoo (Contacto)',
                                                'registro_operacion': errores,
                                                'registro_tecnico': registro_tecnico_formateado,
                                                'category': '<p style="color:'+str(color)+';">'+str(tipo_msg)+'</p>',
                                            })
        elif contacto:
            self.env['sgc.odoo.history'].create({
                                                'name': str(contacto.name), #Al realizar hotfix en SGC se debe agregar el apellido de ser necesario
                                                'fecha_registro': datetime.now(),
                                                'tipo_error': 'Sync SGC --> Odoo (Contacto)',
                                                'registro_operacion': errores,
                                                'registro_tecnico': registro_tecnico_formateado,
                                                'category': '<p style="color:'+str(color)+';">'+str(tipo_msg)+'</p>',
                                            })
    
    #Función de ordenamiento de los nombres
    #Función de ordenamiento de los nombres

    def SplitNombres(nombre_odoo,ordenamiento):
        """
        Autor original en código PHP: eduardoromero.
        https://gist.github.com/eduardoromero/8495437
        
        Separa los nombres y los apellidos y retorna una tupla de tres
        elementos (string) formateados para nombres con el primer caracter
        en mayuscula. Esto es suponiendo que en la cadena los nombres y 
        apellidos esten ordenados de la forma ideal:
    
        1- nombre o nombres.
        2- primer apellido.
        3- segundo apellido.

        *Modificación Jhomson Arcas (13/01/2022)
        *Se aceptan las siguientes combinaciones:

        *Ordenamiento #1
        *1- Nombre A + Apellido A
        *2- Nombre A + Nombre B + Apellido A
        *3- Nombre A + Nombre B + Apellido A + Apellido B

        *Ordenamiento #2
        *1- Nombre A + Apellido A + Apellido B

        *4- Se debe evitar colocar un solo nombre y dos apellidos!!
        *5- Se agrega campo que permite indicar cual es el ordenamiento de los nombres y apellidos
            cubriendo el 100% de los casos posibles.

        SplitNombres( '' )
        >>> ('Nombres', 'Primer Apellido', 'Segundo Apellido')
        """

        #debug (Pruebas con nombres aleatorios)
        #nombre = self.name

        #Se ubica el nombre de Odoo
        nombre = nombre_odoo

        # Separar el nombre completo en espacios.
        tokens = nombre.split(" ")
    
        # Lista donde se guarda las palabras del nombre.
        names = []
    
        # Palabras de apellidos y nombres compuestos.
        especial_tokens = ['the', 'da', 'de', 'di', 'do', 'del', 'la', 'las', 
        'le', 'los', 'mac', 'mc', 'van', 'von', 'y', 'i', 'san', 'santa']
    
        prev = ""
        for token in tokens:
            _token = token.lower()
    
            if _token in especial_tokens:
                prev += token + " "
    
            else:
                names.append(prev + token)
                prev = ""
    
        num_nombres = len(names)
        name_a, name_b, nombres, apellido1, apellido2 = "", "", "", "", ""
    
        # Cuando no existe nombre.
        if num_nombres == 0:
            name_a = ''
            name_b =''
            nombres = ""
    
        # Cuando el nombre consta de un solo elemento.
        elif num_nombres == 1:
            name_a = names[0]
            name_b =''
            nombres = names[0]
    
        # Cuando el nombre consta de dos elementos.
        elif num_nombres == 2:
            name_a = names[0]
            name_b =''
            nombres = names[0]
            apellido1 = names[1]
    
        # Cuando el nombre consta de tres elementos.
        elif num_nombres == 3:
            if str(ordenamiento)  == '1':
                name_a = names[0]
                name_b = names[1]
                nombres = names[0]
                apellido1 = names[2]
            elif str(ordenamiento)  == '2':
                name_a = names[0]
                apellido1 = names[1]
                nombres = names[0]
                apellido2 = names[2]

            #apellido2 = names[3]
    
        # Cuando el nombre consta de más de tres elementos.
        else:
            if str(ordenamiento) == '1':
                name_a = names[0]
                name_b = names[1]
                nombres = names[0]
                apellido1 = names[2]
                apellido2 = names[3]
            elif str(ordenamiento)  == '2':
                name_a = names[0]
                name_b = ""
                nombres = names[0]
                apellido1 = names[1]
                apellido2 = names[2] + " " + names[3]

            #nombres = names[0] + " " + names[1]
            #apellido1 = names[2]
            #apellido2 = names[3]
    
        # Establecemos las cadenas con el primer caracter en mayúscula.
        nombres = nombres.title()
        apellido1 = apellido1.title()
        apellido2 = apellido2.title()

        _logger.warning("Ordenamiento: "+str(ordenamiento))

        _logger.warning("Name A: "+str(name_a))
        _logger.warning("Name B: "+str(name_b))
        #_logger.warning("Nombres: "+str(nombres))
        _logger.warning("Apellido A: "+str(apellido1))
        _logger.warning("Apellido B: "+str(apellido2))

        return (name_a, name_b, apellido1, apellido2)

    #Función de ordenamiento de los nombres
    #Función de ordenamiento de los nombres