# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class TextileRoll(models.Model):
    _inherit = 'textile.roll'

    inspection_ids = fields.One2many(
        'textile.inspection',
        'roll_id',
        string="Inspections"
    )
    inspection_count = fields.Integer(
        string="Inspection Count",
        compute='_compute_inspection_count',
        store=True
    )

    @api.depends('inspection_ids')
    def _compute_inspection_count(self):
        for roll in self:
            roll.inspection_count = len(roll.inspection_ids)

    def action_view_inspections(self):
        self.ensure_one()
        return {
            'name': _('Inspections - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'textile.inspection',
            'view_mode': 'list,form',
            'domain': [('roll_id', '=', self.id)],
            'context': {
                'default_roll_id': self.id,
            }
        }
