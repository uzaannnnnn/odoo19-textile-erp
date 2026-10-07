# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class TextileInspection(models.Model):
    _name = 'textile.inspection'
    _description = 'Textile Quality Inspection'
    _order = 'id desc'

    name = fields.Char(
        string="Inspection Reference",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('textile.inspection') or 'New'
    )
    roll_id = fields.Many2one(
        'textile.roll',
        string="Roll",
        required=True,
        ondelete='restrict',
        index=True
    )
    product_id = fields.Many2one(
        'product.product',
        string="Product",
        related='roll_id.product_id',
        store=True,
        readonly=True
    )
    inspector_id = fields.Many2one(
        'res.users',
        string="Inspector",
        required=True,
        default=lambda self: self.env.user
    )
    inspection_date = fields.Date(
        string="Inspection Date",
        required=True,
        default=fields.Date.context_today
    )
    actual_width_cm = fields.Float(
        string="Measured Width (cm)",
        digits=(6, 2),
        help="Physical width measured during inspection."
    )
    actual_gsm = fields.Float(
        string="Measured GSM",
        digits=(6, 2),
        help="Fabric weight measured during inspection."
    )
    grade = fields.Selection(
        selection=[
            ('A', 'Grade A'),
            ('B', 'Grade B'),
            ('C', 'Grade C'),
        ],
        string="Grade",
        required=True,
        help="Assigned textile quality grade."
    )
    result = fields.Selection(
        selection=[
            ('passed', 'Passed'),
            ('rework', 'Rework'),
            ('rejected', 'Rejected'),
        ],
        string="QC Result",
        readonly=True,
        copy=False,
        index=True,
        help="Outcome explicitly determined by the inspector."
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('done', 'Completed'),
        ],
        string="Status",
        default='draft',
        required=True,
        readonly=True,
        copy=False,
        index=True
    )
    notes = fields.Text(string="Inspection Notes")
    defect_line_ids = fields.One2many(
        'textile.defect.line',
        'inspection_id',
        string="Defect Lines"
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('textile.inspection') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        for insp in self:
            if insp.state == 'done' and not self.env.user.has_group('textile_core.group_textile_manager'):
                protected = {'roll_id', 'grade', 'result', 'actual_width_cm', 'actual_gsm', 'defect_line_ids'}
                if any(k in vals for k in protected):
                    raise UserError(_("Completed QC inspection %s cannot be modified.") % insp.name)
        return super().write(vals)

    def unlink(self):
        for insp in self:
            if insp.state == 'done':
                raise UserError(_("Completed QC inspections cannot be deleted (Inspection %s).") % insp.name)
        return super().unlink()

    def _move_roll_stock(self, dest_location):
        """Execute physical stock movement from current location to destination location."""
        self.ensure_one()
        roll = self.roll_id
        src_location = roll.current_location_id
        if not src_location:
            raise UserError(_("Cannot move roll %s: current stock location is unknown.") % roll.name)

        if src_location.id == dest_location.id:
            # Already at destination location
            return True

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal')
        ], limit=1)

        move = self.env['stock.move'].create({
            'description_picking': f"QC: {roll.name} -> {dest_location.name}",
            'origin': f"QC Inspection {self.name}",
            'product_id': roll.product_id.id,
            'product_uom': roll.product_id.uom_id.id,
            'product_uom_qty': roll.length_m,
            'location_id': src_location.id,
            'location_dest_id': dest_location.id,
            'picking_type_id': picking_type.id if picking_type else False,
            'picked': True,
            'move_line_ids': [(0, 0, {
                'product_id': roll.product_id.id,
                'product_uom_id': roll.product_id.uom_id.id,
                'location_id': src_location.id,
                'location_dest_id': dest_location.id,
                'lot_id': roll.lot_id.id,
                'quantity': roll.length_m,
                'picked': True,
            })],
        })
        move._action_confirm()
        move._action_done()
        return move

    def action_pass(self):
        """QC PASS workflow: Move to WH/Stock, mark passed."""
        self.ensure_one()
        if not (self.env.user.has_group('textile_core.group_textile_qc') or self.env.user.has_group('textile_core.group_textile_manager')):
            raise AccessError(_("Only QC Inspectors and Textile Managers can perform QC decisions."))
        if self.state == 'done':
            raise UserError(_("This inspection is already completed."))
        if self.roll_id.qc_state == 'rejected':
            raise UserError(_("Cannot PASS an already rejected roll (%s).") % self.roll_id.name)

        stock_loc = self.env.ref('stock.stock_location_stock')
        # Execute stock movement
        self._move_roll_stock(stock_loc)

        # Update roll status and grade
        self.roll_id.write({
            'qc_state': 'passed',
            'grade': self.grade,
        })
        self.roll_id._compute_current_location_id()
        self.write({
            'result': 'passed',
            'state': 'done',
        })
        return True

    def action_rework(self):
        """QC REWORK workflow: Move to WH/Rework, mark rework."""
        self.ensure_one()
        if not (self.env.user.has_group('textile_core.group_textile_qc') or self.env.user.has_group('textile_core.group_textile_manager')):
            raise AccessError(_("Only QC Inspectors and Textile Managers can perform QC decisions."))
        if self.state == 'done':
            raise UserError(_("This inspection is already completed."))
        if self.roll_id.qc_state == 'rejected':
            raise UserError(_("Cannot mark an already rejected roll (%s) for rework.") % self.roll_id.name)

        rework_loc = self.env['stock.location'].search([
            ('name', '=', 'Rework'),
            ('usage', '=', 'internal')
        ], limit=1)
        if not rework_loc:
            rework_loc = self.roll_id.get_or_create_location('Rework', usage='internal')

        # Execute stock movement
        self._move_roll_stock(rework_loc)

        # Update roll status and grade
        self.roll_id.write({
            'qc_state': 'rework',
            'grade': self.grade,
        })
        self.roll_id._compute_current_location_id()
        self.write({
            'result': 'rework',
            'state': 'done',
        })
        return True

    def action_reject(self):
        """QC REJECT workflow: Move to WH/Scrap, mark rejected."""
        self.ensure_one()
        if not (self.env.user.has_group('textile_core.group_textile_qc') or self.env.user.has_group('textile_core.group_textile_manager')):
            raise AccessError(_("Only QC Inspectors and Textile Managers can perform QC decisions."))
        if self.state == 'done':
            raise UserError(_("This inspection is already completed."))
        if self.roll_id.qc_state == 'rejected':
            raise UserError(_("Cannot perform QC operations on an already rejected/scrapped roll (%s).") % self.roll_id.name)

        scrap_loc = self.env['stock.location'].search([
            ('name', '=', 'Scrap'),
            ('usage', '=', 'inventory')
        ], limit=1)
        if not scrap_loc:
            scrap_loc = self.env.ref('stock.stock_location_scrapped')

        # Execute stock movement
        self._move_roll_stock(scrap_loc)

        # Update roll status and grade
        self.roll_id.write({
            'qc_state': 'rejected',
            'grade': self.grade,
        })
        self.roll_id._compute_current_location_id()
        self.write({
            'result': 'rejected',
            'state': 'done',
        })
        return True
