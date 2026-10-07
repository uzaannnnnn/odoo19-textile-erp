# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _sanity_check(self, separate_pickings=True):
        super()._sanity_check(separate_pickings=separate_pickings)
        self._check_textile_delivery_gate()

    def _check_textile_delivery_gate(self):
        """Enforce strict delivery quality gate and whole-roll delivery invariants."""
        for picking in self:
            is_delivery = picking.picking_type_code == 'outgoing' or (
                picking.location_dest_id and picking.location_dest_id.usage == 'customer'
            )
            if not is_delivery:
                continue

            move_lines = picking.move_line_ids | picking.move_ids.move_line_ids
            for ml in move_lines:
                if ml.product_id.is_textile_product and ml.product_id.textile_type == 'fabric':
                    if not ml.lot_id:
                        raise UserError(_(
                            "Delivery cannot be validated.\n\n"
                            "Fabric product %(product)s requires a fabric roll lot assignment.",
                            product=ml.product_id.display_name
                        ))
                    roll = self.env['textile.roll'].search([('lot_id', '=', ml.lot_id.id)], limit=1)
                    if not roll:
                        raise UserError(_(
                            "Delivery cannot be validated.\n\n"
                            "Lot %(lot)s for fabric %(product)s does not map to a registered fabric roll.",
                            lot=ml.lot_id.name,
                            product=ml.product_id.display_name
                        ))

                    # Invariant: Delivery Quality Gate
                    if roll.qc_state != 'passed':
                        raise UserError(_(
                            "Delivery cannot be validated.\n\n"
                            "Roll %(roll)s has not passed quality inspection.\n"
                            "Current QC status: %(status)s.",
                            roll=roll.name,
                            status=roll.qc_state.upper()
                        ))

                    # Invariant: Whole Roll Delivery
                    rounding = ml.product_uom_id.rounding or 0.01
                    if float_compare(ml.quantity, roll.length_m, precision_rounding=rounding) != 0:
                        raise UserError(_(
                            "Delivery cannot be validated.\n\n"
                            "Partial roll delivery is not supported for textile rolls.\n"
                            "Roll %(roll)s has length %(length).2f m, but %(qty).2f m was specified in delivery.",
                            roll=roll.name,
                            length=roll.length_m,
                            qty=ml.quantity
                        ))

    def _action_done(self):
        self._check_textile_delivery_gate()
        res = super()._action_done()
        for picking in self:
            is_delivery = picking.picking_type_code == 'outgoing' or (
                picking.location_dest_id and picking.location_dest_id.usage == 'customer'
            )
            if is_delivery:
                move_lines = picking.move_line_ids | picking.move_ids.move_line_ids
                for ml in move_lines:
                    if ml.lot_id and ml.product_id.is_textile_product:
                        roll = self.env['textile.roll'].search([('lot_id', '=', ml.lot_id.id)], limit=1)
                        if roll:
                            roll._compute_current_location_id()
        return res
