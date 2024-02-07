# -*- coding: utf-8 -*-
# from odoo import http


# class DaycoContactosMods(http.Controller):
#     @http.route('/dayco_contactos_mods/dayco_contactos_mods', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/dayco_contactos_mods/dayco_contactos_mods/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('dayco_contactos_mods.listing', {
#             'root': '/dayco_contactos_mods/dayco_contactos_mods',
#             'objects': http.request.env['dayco_contactos_mods.dayco_contactos_mods'].search([]),
#         })

#     @http.route('/dayco_contactos_mods/dayco_contactos_mods/objects/<model("dayco_contactos_mods.dayco_contactos_mods"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('dayco_contactos_mods.object', {
#             'object': obj
#         })
