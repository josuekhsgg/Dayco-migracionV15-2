# -*- coding: utf-8 -*-
{
    'name': "dayco_project_fixs",

    'summary': """
        Ajustes al automatismo realizado para Dayco en el módulo de proyectos y relacionados.""",

    'description': """
        En desarrollo
    """,

    'author': "Jhomson Arcas - Dayco",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','project_task_customization','project_sub_task','motives_proposal_dayco'],

    # always loaded
    'data': [
        #'security/ir.model.access.csv',
        'data/access.xml',
        'views/ir_cron.xml',
        'views/project_task.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
