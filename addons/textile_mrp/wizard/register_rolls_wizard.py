# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class TextileRegisterRollsWizard(models.TransientModel):
    _name = 'textile.register.rolls.wizard'
    _description = 'Register Fabric Output Rolls'

    production_id = fields.Many2one(
        'mrp.production',
        string="Manufacturing Order",
        required=True,
        readonly=True
    )
    product_id = fields.Many2one(
        'product.product',
        related='production_id.product_id',
        string="Finished Fabric",
        readonly=True
    )
    planned_qty = fields.Float(
        related='production_id.product_qty',
        string="Planned Quantity (m)",
        readonly=True
    )
    existing_good_qty = fields.Float(
        string="Already Registered (m)",
        compute='_compute_summary'
    )
    new_rolls_total_m = fields.Float(
        string="New Rolls Output (m)",
        compute='_compute_summary'
    )
    production_loss_m = fields.Float(
        string="Production Loss (m)",
        digits=(10, 2),
        default=0.0,
        help="Recorded manufacturing loss in meters."
    )
    line_ids = fields.One2many(
        'textile.register.rolls.line',
        'wizard_id',
        string="Output Rolls"
    )

    @api.depends('production_id.good_output_m', 'line_ids.length_m')
    def _compute_summary(self):
        for wiz in self:
            wiz.existing_good_qty = wiz.production_id.good_output_m
            wiz.new_rolls_total_m = sum(wiz.line_ids.mapped('length_m'))

    def action_register_rolls(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Please specify at least one roll to register."))
        if self.production_loss_m < 0:
            raise ValidationError(_("Production loss cannot be negative."))

        mo = self.production_id
        mo.production_loss_m = self.production_loss_m

        created_rolls = self.env['textile.roll']
        for line in self.line_ids:
            if line.length_m <= 0:
                raise ValidationError(_("Roll length must be strictly positive."))
            if line.weight_kg < 0:
                raise ValidationError(_("Roll weight cannot be negative."))

            roll_name = self.env['ir.sequence'].next_by_code('textile.roll') or 'New'
            lot = self.env['stock.lot'].create({
                'name': roll_name,
                'product_id': mo.product_id.id,
                'company_id': mo.company_id.id,
            })
            roll = self.env['textile.roll'].create({
                'name': roll_name,
                'lot_id': lot.id,
                'product_id': mo.product_id.id,
                'production_id': mo.id,
                'length_m': line.length_m,
                'weight_kg': line.weight_kg,
                'qc_state': 'pending',
                'production_date': fields.Date.context_today(self),
            })
            created_rolls |= roll

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rolls Registered Successfully'),
                'message': _('%(count)s fabric roll(s) registered for %(mo)s.', count=len(created_rolls), mo=mo.name),
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }


class TextileRegisterRollsLine(models.TransientModel):
    _name = 'textile.register.rolls.line'
    _description = 'Register Fabric Roll Line'

    wizard_id = fields.Many2one(
        'textile.register.rolls.wizard',
        string="Wizard",
        required=True,
        ondelete='cascade'
    )
    length_m = fields.Float(
        string="Length (m)",
        required=True,
        digits=(10, 2)
    )
    weight_kg = fields.Float(
        string="Weight (kg)",
        digits=(10, 2),
        default=0.0
    )

    @api.constrains('length_m', 'weight_kg')
    def _check_line_dimensions(self):
        for line in self:
            if line.length_m <= 0:
                raise ValidationError(_("Roll length must be strictly positive."))
            if line.weight_kg < 0:
                raise ValidationError(_("Roll weight cannot be negative."))
