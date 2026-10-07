# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    roll_ids = fields.One2many(
        'textile.roll',
        'lot_id',
        string="Textile Rolls"
    )
    roll_id = fields.Many2one(
        'textile.roll',
        string="Physical Roll",
        compute='_compute_roll_id',
        store=False
    )
    is_textile_roll = fields.Boolean(
        string="Is Textile Roll",
        compute='_compute_roll_id',
        store=False
    )

    @api.depends('roll_ids')
    def _compute_roll_id(self):
        for lot in self:
            roll = lot.roll_ids[:1]
            lot.roll_id = roll
            lot.is_textile_roll = bool(roll)

