# -*- coding: utf-8 -*-
from odoo import fields, models


class TextileShift(models.Model):
    _name = 'textile.shift'
    _description = 'Textile Production Shift'
    _order = 'name'

    name = fields.Char(string="Shift Name", required=True)
    code = fields.Char(string="Shift Code", required=True, index=True)
    active = fields.Boolean(string="Active", default=True)

    _code_uniq = models.Constraint('UNIQUE(code)', 'The shift code must be unique!')
