from odoo import models, fields
from datetime import datetime, timedelta
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = "stock.picking"

    date_of_transfer = fields.Date(string="Effective Date", default=False, copy=False)

    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        #commmit
        self.env.cr.commit()

        if self.date_of_transfer != False:
            selected_date = self.date_of_transfer
            selected_datetime = datetime.strptime(str(selected_date) + " 05:00:00", "%Y-%m-%d %H:%M:%S")

            self.env.cr.execute("UPDATE stock_valuation_layer SET create_date = (%s) WHERE description LIKE (%s)",
                                [selected_datetime, str(self.name + "%")])


            self.env.cr.execute("UPDATE account_move_line SET date = (%s) WHERE ref SIMILAR TO %s",
                                [selected_date, str(self.name + "%")])

            self.env.cr.execute("UPDATE account_move set date = (%s) WHERE ref SIMILAR TO %s",
                                [selected_date, str(self.name + "%")])
            self.env.cr.commit()
            time = self.scheduled_date.time()

            self.date_done = (selected_date + timedelta(hours=4))
            self.env.cr.commit()
            #convertir la fecha a la zona horaria del usuario
            self.date_done = self.date_done + timedelta(hours=5)
            for stock_move_line in self.env['stock.move.line'].search([('reference', 'ilike', str(self.name + "%"))]):
                stock_move_line.date = selected_date

                stock_move_line.date = stock_move_line.date + timedelta(hours=5)
        return res