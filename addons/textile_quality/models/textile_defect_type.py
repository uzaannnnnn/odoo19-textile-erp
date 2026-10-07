# -*- coding: utf-8 -*-
from odoo import fields, models


class TextileDefectType(models.Model):
    _name = 'textile.defect.type'
    _description = 'Textile Defect Type'
    _order = 'name'

    name = fields.Char(string="Defect Name", required=True)
    code = fields.Char(string="Defect Code", required=True, index=True)
    active = fields.Boolean(string="Active", default=True)
    description = fields.Text(string="Description")

    _code_uniq = models.Constraint(
        'UNIQUE(code)',
        'The defect type code must be unique!'
    )
