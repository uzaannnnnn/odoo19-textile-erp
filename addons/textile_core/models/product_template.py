# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_textile_product = fields.Boolean(
        string="Is Textile Product",
        default=False,
        index=True,
        help="Check this if the product is related to textile manufacturing."
    )
    textile_type = fields.Selection(
        selection=[
            ('raw_material', 'Raw Material'),
            ('fabric', 'Fabric'),
            ('other', 'Other'),
        ],
        string="Textile Type",
        help="Type of textile product (Raw Material, Fabric, etc.)"
    )
    fabric_type = fields.Selection(
        selection=[
            ('woven', 'Woven'),
            ('knitted', 'Knitted'),
            ('other', 'Other'),
        ],
        string="Fabric Type",
        help="Structure of fabric (Woven, Knitted, etc.)"
    )
    material = fields.Char(
        string="Material",
        help="Fiber or material type (e.g. Polyester, Cotton)"
    )
    composition = fields.Char(
        string="Composition",
        help="Fiber composition (e.g. 100% PES, 60/40 TC)"
    )
    color = fields.Char(
        string="Color",
        help="Color or shade name"
    )
    width_cm = fields.Float(
        string="Width (cm)",
        digits=(6, 2),
        help="Fabric width in centimeters"
    )
    gsm = fields.Float(
        string="GSM",
        digits=(6, 2),
        help="Grams per square meter (g/m²)"
    )

    @api.constrains('width_cm', 'gsm')
    def _check_textile_dimensions(self):
        for template in self:
            if template.width_cm < 0.0:
                raise ValidationError(_("Fabric width cannot be negative."))
            if template.gsm < 0.0:
                raise ValidationError(_("Fabric GSM cannot be negative."))

