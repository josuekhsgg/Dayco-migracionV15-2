# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging
#import pyodbc #Librería de conexión a bases de datos SQL.
import pymssql
#import string
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)

class BdConnections():
    def connect_to_bd(self,server,port,database,username,password):
        _logger.warning("BD a conectar: "+str(database))
        #_logger.warning("Server a conectar: "+str(server))
        #_logger.warning("Puerto: "+str(port))

        try:
            conn = pymssql.connect(server+":"+port, username, password, database, 30, 30)
            #cursor = conn.cursor(as_dict=True)

            # Some other example server values are
            # server = 'localhost\sqlexpress' # for a named instance
            # server = 'myserver,port' # to specify an alternate port
            #cnxn = pyodbc.connect('DRIVER={FreeTDS};SERVER='+server+';DATABASE='+database+';ENCRYPT=no;MARS_Connection=Yes;UID='+username+';PWD='+ password)

            #return cnxn
            return conn
        except pymssql.Error as e:
            _logger.warning("Error al crear conexión: "+str(e))
            return False