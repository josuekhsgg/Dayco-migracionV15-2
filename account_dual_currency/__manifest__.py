# -*- coding: utf-8 -*-
{
    'name': "Venezuela: Account Dual Currency",
    'version': '15.0.1.0.0',
    'category' : 'Account',
    'license': 'Other proprietary',
    'summary': """Esta aplicación permite manejar dualidad de moneda en Contabilidad.""",
    'author': 'José Luis Vizcaya López',
    'company': 'José Luis Vizcaya López',
    'maintainer': 'José Luis Vizcaya López',
    'website': 'https://github.com/birkot',
    'description': """
    
        - Mantener como moneda principal Bs y $ como secundaria.
        - Facturas en Bs pero manteniendo deuda en $.
        - Tasa individual para cada Factura de Cliente y Proveedor.
        - Tasa individual para Asientos contables.
        - Visualización de Débito y Crédito en ambas monedas en los apuntes contables.
        - Conciliación total o parcial de $ y Bs en facturas.
        - Registro de pagos en facturas con tasa diferente a la factura.
        - Registro de anticipos en el módulo de Pagos de Odoo, manteniendo saldo a favor en $ y Bs.
        - Informe de seguimiento en $ y Bs a la tasa actual.
        - Reportes contables en $ (Vencidas por Pagar, Vencidas por Cobrar y Libro mayor de empresas)
        - Valoración de inventario en $ y Bs a la tasa actual

    """,
    'depends': [
                'base','product','stock', 'sale','l10n_ve_full','account','account_reports','account_followup','web','stock_account','account_accountant','analytic','stock_landed_costs','account_debit_note','mail','account_asset'
                ],
    'data':[
        'views/account_move_view.xml',
        'views/res_currency.xml',
        'views/account_payment.xml',
        'data/decimal_precision.xml',
        'wizard/account_payment_register.xml',
        'views/product_templete.xml',
        'data/account_financial_report_data.xml',
        'security/ir.model.access.csv',
        'security/res_groups.xml',
        'views/account_journal_dashboard_view.xml',
        'views/search_template_view.xml',
        'views/stock_valuation_layer.xml',
        'views/res_company.xml',
        'views/account_bank_statement.xml',
        'views/stock_landed_cost.xml',
        'views/account_analytic_account.xml',
        'views/account_analytic_line.xml',
        'wizard/generar_retencion_igtf_wizard.xml',
        'report/sale_report_views.xml',
        'data/cron.xml',
        'data/channel.xml',
        'views/effective_date_change.xml',
        'views/account_asset.xml',
    ],
    'assets': {
        'web.assets_qweb': [
            'account_dual_currency/static/src/xml/**/*',
        ],
    },
    'images': [
        'static/description/thumbnail.png',
    ],
    'live_test_url': 'https://demo-venezuela.odoo.com/web/login',
    "price": 2990,
    "currency": "USD",
    'installable' : True,
    'application' : False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
