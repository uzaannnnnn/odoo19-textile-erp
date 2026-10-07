# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    textile_shift_id = fields.Many2one(
        'textile.shift',
        string="Shift",
        help="Production work shift"
    )
    operator_id = fields.Many2one(
        'res.users',
        string="Operator",
        help="Machine operator or production supervisor responsible for this run."
    )
    production_loss_m = fields.Float(
        string="Production Loss (m)",
        digits=(10, 2),
        default=0.0,
        help="Recorded manufacturing loss / scrap fabric in meters."
    )
    good_output_m = fields.Float(
        string="Good Output (m)",
        compute='_compute_textile_roll_stats',
        store=True,
        digits=(10, 2),
        help="Total usable fabric meters registered across output rolls."
    )
    roll_count = fields.Integer(
        string="Roll Count",
        compute='_compute_textile_roll_stats',
        store=True,
        help="Number of physical rolls registered for this manufacturing order."
    )
    roll_ids = fields.One2many(
        'textile.roll',
        'production_id',
        string="Textile Rolls"
    )
    is_textile_mo = fields.Boolean(
        string="Is Textile MO",
        compute='_compute_is_textile_mo',
        store=True
    )

    @api.depends('product_id', 'product_id.is_textile_product')
    def _compute_is_textile_mo(self):
        for mo in self:
            mo.is_textile_mo = bool(mo.product_id and mo.product_id.is_textile_product)

    @api.depends('roll_ids', 'roll_ids.length_m')
    def _compute_textile_roll_stats(self):
        for mo in self:
            mo.good_output_m = sum(mo.roll_ids.mapped('length_m'))
            mo.roll_count = len(mo.roll_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            product_id = vals.get('product_id')
            if product_id and not vals.get('location_dest_id'):
                product = self.env['product.product'].browse(product_id)
                if product.is_textile_product:
                    qc_loc = self.env['stock.location'].search([
                        ('name', '=', 'QC-Hold'),
                        ('usage', '=', 'internal')
                    ], limit=1)
                    if qc_loc:
                        vals['location_dest_id'] = qc_loc.id
        return super().create(vals_list)

    @api.onchange('product_id')
    def _onchange_product_id_textile_location(self):
        if self.product_id and self.product_id.is_textile_product:
            qc_loc = self.env['stock.location'].search([
                ('name', '=', 'QC-Hold'),
                ('usage', '=', 'internal')
            ], limit=1)
            if qc_loc:
                self.location_dest_id = qc_loc

    @api.constrains('production_loss_m')
    def _check_production_loss(self):
        for mo in self:
            if mo.production_loss_m < 0.0:
                raise ValidationError(_("Production loss cannot be negative."))

    def _button_mark_done_sanity_checks(self):
        super()._button_mark_done_sanity_checks()
        for production in self:
            if production.is_textile_mo:
                # 1. At least one roll must be registered
                if not production.roll_ids:
                    raise UserError(_(
                        "Cannot complete Textile Manufacturing Order %s: "
                        "At least one physical fabric roll must be registered before completion."
                    ) % production.name)

                # 2. Production balance invariant: Good Output + Production Loss == Planned Quantity
                total_accounted = production.good_output_m + production.production_loss_m
                rounding = production.product_uom_id.rounding or 0.01
                if float_compare(total_accounted, production.product_qty, precision_rounding=rounding) != 0:
                    raise UserError(_(
                        "Cannot complete Textile Manufacturing Order %(name)s: "
                        "Production balance does not match planned quantity!\n"
                        "- Planned Quantity: %(planned).2f m\n"
                        "- Good Output Rolls: %(good).2f m\n"
                        "- Production Loss: %(loss).2f m\n"
                        "- Total Accounted: %(total).2f m\n"
                        "Invariant requires: Good Output + Production Loss == Planned Quantity.",
                        name=production.name,
                        planned=production.product_qty,
                        good=production.good_output_m,
                        loss=production.production_loss_m,
                        total=total_accounted,
                    ))

    def _prepare_textile_finished_move_lines(self):
        """Prepare finished stock moves and stock move lines in WH/QC-Hold for each roll."""
        self.ensure_one()
        qc_loc = self.env['stock.location'].search([
            ('name', '=', 'QC-Hold'),
            ('usage', '=', 'internal')
        ], limit=1)
        if not qc_loc:
            qc_loc = self.location_dest_id

        finish_moves = self.move_finished_ids.filtered(
            lambda m: m.product_id == self.product_id and m.state not in ('done', 'cancel')
        )
        finish_moves.write({
            'location_dest_id': qc_loc.id,
            'quantity': self.good_output_m,
            'picked': False,
        })

        # Remove existing non-done move lines to avoid duplicates
        finish_moves.move_line_ids.filtered(lambda ml: ml.state != 'done').unlink()

        for move in finish_moves:
            for roll in self.roll_ids:
                self.env['stock.move.line'].create({
                    'move_id': move.id,
                    'product_id': self.product_id.id,
                    'product_uom_id': self.product_uom_id.id,
                    'location_id': move.location_id.id,
                    'location_dest_id': qc_loc.id,
                    'lot_id': roll.lot_id.id,
                    'quantity': roll.length_m,
                    'picked': False,
                })
        self.qty_producing = self.good_output_m
        # Mark raw component moves as picked if available
        self.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel')).picked = True

    def pre_button_mark_done(self):
        textile_mos = self.filtered(lambda p: p.is_textile_mo)
        for mo in textile_mos:
            mo._button_mark_done_sanity_checks()
            mo._prepare_textile_finished_move_lines()

        other_mos = self - textile_mos
        if other_mos:
            res = super(MrpProduction, other_mos).pre_button_mark_done()
            if res is not True:
                return res
        return True

    def button_mark_done(self):
        res = super().button_mark_done()
        for mo in self:
            if mo.is_textile_mo and mo.state == 'done':
                mo.roll_ids._compute_current_location_id()
        return res

    def action_register_rolls(self):
        self.ensure_one()
        return {
            'name': _('Register Fabric Rolls'),
            'type': 'ir.actions.act_window',
            'res_model': 'textile.register.rolls.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_production_id': self.id,
                'default_production_loss_m': self.production_loss_m,
            }
        }

    def action_view_textile_rolls(self):
        self.ensure_one()
        return {
            'name': _('Fabric Rolls - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'textile.roll',
            'view_mode': 'list,form',
            'domain': [('production_id', '=', self.id)],
            'context': {
                'default_production_id': self.id,
                'default_product_id': self.product_id.id,
            }
        }
