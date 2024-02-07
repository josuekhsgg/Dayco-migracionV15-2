# -*- coding: utf-8 -*-
# from odoo import http


# class DaycoProjectFixs(http.Controller):
#     @http.route('/dayco_project_fixs/dayco_project_fixs/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/dayco_project_fixs/dayco_project_fixs/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('dayco_project_fixs.listing', {
#             'root': '/dayco_project_fixs/dayco_project_fixs',
#             'objects': http.request.env['dayco_project_fixs.dayco_project_fixs'].search([]),
#         })

#     @http.route('/dayco_project_fixs/dayco_project_fixs/objects/<model("dayco_project_fixs.dayco_project_fixs"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('dayco_project_fixs.object', {
#             'object': obj
#         })
