# -*- coding: utf-8 -*-
import base64
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TextileRoll(models.Model):
    _name = 'textile.roll'
    _description = 'Physical Fabric Roll'
    _order = 'id desc'

    name = fields.Char(
        string="Roll Number",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('textile.roll') or 'New'
    )
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string="Stock Lot",
        required=True,
        copy=False,
        readonly=True,
        ondelete='restrict',
        index=True,
        help="Unique stock lot associated 1-to-1 with this physical roll."
    )
    product_id = fields.Many2one(
        'product.product',
        string="Product",
        required=True,
        index=True,
        domain="[('is_textile_product', '=', True)]"
    )
    production_id = fields.Many2one(
        'mrp.production',
        string="Manufacturing Order",
        required=True,
        ondelete='restrict',
        index=True
    )
    length_m = fields.Float(
        string="Length (m)",
        required=True,
        digits=(10, 2),
        help="Physical length of the fabric roll in meters."
    )
    weight_kg = fields.Float(
        string="Weight (kg)",
        digits=(10, 2),
        default=0.0,
        help="Physical weight of the roll in kilograms (operational/informational)."
    )
    grade = fields.Selection(
        selection=[
            ('A', 'Grade A'),
            ('B', 'Grade B'),
            ('C', 'Grade C'),
        ],
        string="Grade",
        help="Textile quality grade (A, B, C)."
    )
    qc_state = fields.Selection(
        selection=[
            ('pending', 'Pending QC'),
            ('passed', 'Passed'),
            ('rework', 'Rework'),
            ('rejected', 'Rejected'),
        ],
        string="QC Status",
        default='pending',
        required=True,
        readonly=True,
        copy=False,
        index=True
    )
    production_date = fields.Date(
        string="Production Date",
        default=fields.Date.context_today,
        required=True
    )
    notes = fields.Text(string="Notes")

    current_location_id = fields.Many2one(
        'stock.location',
        string="Current Location",
        compute='_compute_current_location_id',
        store=True,
        readonly=True,
        help="Physical stock location of this roll/lot derived from stock inventory records."
    )

    qr_payload = fields.Char(
        string="QR Payload",
        compute='_compute_qr_payload',
        readonly=True,
        help="Deterministic URL or reference encoded in the roll QR code."
    )
    qr_code_image = fields.Binary(
        string="QR Code Preview",
        compute='_compute_qr_code_image',
        store=False,
        help="Dynamic QR code preview generated on the fly without database storage."
    )

    _check_positive_length = models.Constraint(
        'CHECK(length_m > 0)',
        'The roll length must be strictly greater than 0.'
    )
    _check_positive_weight = models.Constraint(
        'CHECK(weight_kg >= 0)',
        'The roll weight cannot be negative.'
    )
    _unique_lot = models.Constraint(
        'UNIQUE(lot_id)',
        'Each fabric roll must correspond to a unique stock lot (1 roll = 1 lot).'
    )
    _unique_name = models.Constraint(
        'UNIQUE(name)',
        'The Roll Number must be unique.'
    )

    @api.depends('name')
    def _compute_qr_payload(self):
        for roll in self:
            if roll.id and isinstance(roll.id, int):
                base_url = roll.get_base_url().rstrip('/')
                roll.qr_payload = f"{base_url}/textile/roll/{roll.id}"
            elif roll.name:
                roll.qr_payload = roll.name
            else:
                roll.qr_payload = ''

    @api.depends('qr_payload')
    def _compute_qr_code_image(self):
        for roll in self:
            payload = roll.qr_payload
            if payload:
                try:
                    barcode_png = self.env['ir.actions.report'].barcode(
                        'QR',
                        payload,
                        width=250,
                        height=250
                    )
                    roll.qr_code_image = base64.b64encode(barcode_png)
                except Exception:
                    roll.qr_code_image = False
            else:
                roll.qr_code_image = False

    def _get_report_base_filename(self):
        self.ensure_one()
        return f"Roll_Label_{self.name}"

    def action_print_label(self):
        """Action button to print the fabric roll label report."""
        return self.env.ref('textile_inventory.action_report_textile_roll').report_action(self)

    @api.constrains('length_m', 'weight_kg', 'product_id', 'lot_id', 'production_id')
    def _check_roll_validity(self):
        for roll in self:
            if not roll.product_id:
                raise ValidationError(_("A product is required for the roll."))
            if not roll.production_id:
                raise ValidationError(_("A manufacturing order origin is required for the roll."))
            if not roll.lot_id:
                raise ValidationError(_("A stock lot is required for the roll."))
            if roll.length_m <= 0:
                raise ValidationError(_("Roll length must be strictly greater than 0."))
            if roll.weight_kg < 0:
                raise ValidationError(_("Roll weight cannot be negative."))

    def write(self, vals):
        if 'name' in vals:
            for roll in self:
                if vals['name'] != roll.name:
                    raise ValidationError(_("Roll Number %(roll)s is immutable and cannot be changed.", roll=roll.name))
        if 'lot_id' in vals:
            for roll in self:
                if vals['lot_id'] != roll.lot_id.id:
                    raise ValidationError(_("Stock Lot for roll %(roll)s is immutable and cannot be changed.", roll=roll.name))
        return super().write(vals)

    def copy(self, default=None):
        raise ValidationError(_("Duplicating fabric rolls is forbidden. Each physical roll must be registered via production."))

    def unlink(self):
        for roll in self:
            if roll.qc_state != 'pending':
                raise ValidationError(_(
                    "Cannot delete roll %(roll)s: only rolls in 'Pending QC' status can be deleted.",
                    roll=roll.name
                ))
            if hasattr(roll, 'inspection_ids') and roll.inspection_ids:
                raise ValidationError(_(
                    "Cannot delete roll %(roll)s: inspection history exists.",
                    roll=roll.name
                ))
        return super().unlink()

    @api.depends('lot_id', 'lot_id.quant_ids', 'lot_id.quant_ids.location_id', 'lot_id.quant_ids.quantity')
    def _compute_current_location_id(self):
        for roll in self:
            if not roll.lot_id:
                roll.current_location_id = False
                continue
            # Search quant with positive quantity
            quant = self.env['stock.quant'].search([
                ('lot_id', '=', roll.lot_id.id),
                ('quantity', '>', 0),
            ], order='id desc', limit=1)
            if quant:
                roll.current_location_id = quant.location_id
            else:
                # Fallback to the latest stock move line
                move_line = self.env['stock.move.line'].search([
                    ('lot_id', '=', roll.lot_id.id),
                    ('state', '=', 'done')
                ], order='date desc, id desc', limit=1)
                roll.current_location_id = move_line.location_dest_id if move_line else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('textile.roll') or 'New'
        return super().create(vals_list)

    @api.model
    def get_or_create_location(self, loc_name, usage='internal', xml_id=None):
        """Helper to get or create textile stock locations under the main warehouse."""
        warehouse = self.env['stock.warehouse'].search([], limit=1)
        parent_loc = warehouse.view_location_id if warehouse else self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        loc = self.env['stock.location'].search([
            ('name', '=', loc_name),
            ('location_id', '=', parent_loc.id if parent_loc else False)
        ], limit=1)
        if not loc:
            loc = self.env['stock.location'].create({
                'name': loc_name,
                'location_id': parent_loc.id if parent_loc else False,
                'usage': usage,
            })
        if xml_id:
            mod_data = self.env['ir.model.data'].search([
                ('module', '=', 'textile_inventory'),
                ('name', '=', xml_id)
            ], limit=1)
            if not mod_data:
                self.env['ir.model.data'].create({
                    'module': 'textile_inventory',
                    'name': xml_id,
                    'model': 'stock.location',
                    'res_id': loc.id,
                    'noupdate': True,
                })
        return loc

    @api.model
    def init_textile_locations(self):
        self.get_or_create_location('QC-Hold', usage='internal', xml_id='location_qc_hold')
        self.get_or_create_location('Rework', usage='internal', xml_id='location_rework')
        self.get_or_create_location('Scrap', usage='inventory', xml_id='location_scrap')
