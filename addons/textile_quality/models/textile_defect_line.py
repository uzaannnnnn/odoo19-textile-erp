# -*- coding: utf-8 -*-
from odoo import fields, models


class TextileDefectLine(models.Model):
    _name = 'textile.defect.line'
    _description = 'Textile Defect Line'
    _order = 'id'

    inspection_id = fields.Many2one(
        'textile.inspection',
        string="Inspection",
        required=True,
        ondelete='cascade',
        index=True
    )
    defect_type_id = fields.Many2one(
        'textile.defect.type',
        string="Defect Type",
        required=True
    )
    defect_count = fields.Integer(
        string="Defect Count",
        required=True,
        default=1
    )
    note = fields.Char(string="Note")

    _check_count = models.Constraint(
        'CHECK(defect_count >= 0)',
        'Defect count cannot be negative!'
    )
