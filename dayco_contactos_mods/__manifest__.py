# -*- coding: utf-8 -*-
{
    'name': "dayco_contactos_mods",

    'summary': """
        Modificaciones del modulo de contactos""",

    'description': """
        Detalles sobre permisos y otros elementos relacionados con el manejo de la data 
        del modulo de conatctaos.
        Todo el código presente en este addon es Propiedad de Dayco Host, no se permite
        modificación, revisión, venta, o cualquier actividad afin sin previa consulta con
        el propietario del desarrollo. 
    """,

    'author': "Jhomson Arcas - DaycoHost",
    'website': "https://daycohost.com/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Administration',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','contacts'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/access.xml',
        'data/menu_items.xml',
        'views/res_partner.xml',
        'views/res_company.xml',
        'views/sgc_odoo_history.xml',
        'views/ir_cron.xml',
    ],
    # only loaded in demonstration mode

    #Siempre subir todo a desarrollo
    #Siempre hacer un respaldo de la instancia antes de subir o probar cualquier desarrollo.
    #Realizar el respaldo y hacer el montaje despues de la hora en la que se términen las actividades en la empresa.
    #Llevar registro de cambios y notificaciones que permita llevar un historico de los cambios que se vayan subiendo.
    
    'demo': [
        'demo/demo.xml',
    ],
}
