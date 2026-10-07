# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTextileMrp(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.meter_uom = cls.env.ref('uom.product_uom_meter')
        cls.kg_uom = cls.env.ref('uom.product_uom_kgm')

        cls.fabric_product = cls.env['product.product'].search([
            ('is_textile_product', '=', True),
            ('textile_type', '=', 'fabric')
        ], limit=1)
        cls.yarn_product = cls.env['product.product'].search([
            ('is_textile_product', '=', True),
            ('textile_type', '=', 'raw_material')
        ], limit=1)

        # Workcenter and shift
        cls.workcenter = cls.env.ref('textile_mrp.workcenter_weav_01')
        cls.shift = cls.env.ref('textile_mrp.shift_a')

    def test_roll_registration_wizard(self):
        """Test wizard roll registration and MO statistics computation."""
        mo = self.env['mrp.production'].create({
            'product_id': self.fabric_product.id,
            'product_qty': 100.0,
            'product_uom_id': self.meter_uom.id,
            'textile_shift_id': self.shift.id,
        })
        mo.action_confirm()

        wiz = self.env['textile.register.rolls.wizard'].create({
            'production_id': mo.id,
            'production_loss_m': 10.0,
            'line_ids': [
                (0, 0, {'length_m': 50.0, 'weight_kg': 10.0}),
                (0, 0, {'length_m': 40.0, 'weight_kg': 8.0}),
            ]
        })
        wiz.action_register_rolls()

        self.assertEqual(mo.roll_count, 2)
        self.assertEqual(mo.good_output_m, 90.0)
        self.assertEqual(mo.production_loss_m, 10.0)
        for roll in mo.roll_ids:
            self.assertEqual(roll.qc_state, 'pending')
            self.assertTrue(roll.lot_id)

    def test_production_completion_without_rolls_fails(self):
        """Textile MO cannot be completed without registered rolls."""
        mo = self.env['mrp.production'].create({
            'product_id': self.fabric_product.id,
            'product_qty': 100.0,
            'product_uom_id': self.meter_uom.id,
        })
        mo.action_confirm()
        with self.assertRaises(UserError):
            mo.button_mark_done()

    def test_production_balance_validation_failure(self):
        """Production completion fails when Good Output + Loss != Planned Qty."""
        mo = self.env['mrp.production'].create({
            'product_id': self.fabric_product.id,
            'product_qty': 100.0,
            'product_uom_id': self.meter_uom.id,
        })
        mo.action_confirm()

        wiz = self.env['textile.register.rolls.wizard'].create({
            'production_id': mo.id,
            'production_loss_m': 10.0,
            'line_ids': [
                (0, 0, {'length_m': 50.0, 'weight_kg': 10.0}),
                # Total good = 50, loss = 10 -> total accounted = 60 != 100
            ]
        })
        wiz.action_register_rolls()

        with self.assertRaises(UserError):
            mo.button_mark_done()

    def test_negative_production_loss_fails(self):
        """Negative production loss is blocked by validation constraints."""
        mo = self.env['mrp.production'].create({
            'product_id': self.fabric_product.id,
            'product_qty': 100.0,
            'product_uom_id': self.meter_uom.id,
        })
        with self.assertRaises(ValidationError):
            mo.write({'production_loss_m': -20.0})

    def test_wizard_negative_dimensions_fails(self):
        """Wizard rejects negative and zero roll lengths."""
        mo = self.env['mrp.production'].create({
            'product_id': self.fabric_product.id,
            'product_qty': 100.0,
            'product_uom_id': self.meter_uom.id,
        })
        with self.assertRaises(ValidationError):
            self.env['textile.register.rolls.wizard'].create({
                'production_id': mo.id,
                'production_loss_m': 10.0,
                'line_ids': [
                    (0, 0, {'length_m': -50.0, 'weight_kg': 10.0}),
                ]
            })

    def test_production_completion_success(self):
        """Production succeeds when Good Output + Loss == Planned Qty."""
        mo = self.env['mrp.production'].create({
            'product_id': self.fabric_product.id,
            'product_qty': 100.0,
            'product_uom_id': self.meter_uom.id,
        })
        mo.action_confirm()

        wiz = self.env['textile.register.rolls.wizard'].create({
            'production_id': mo.id,
            'production_loss_m': 15.0,
            'line_ids': [
                (0, 0, {'length_m': 50.0, 'weight_kg': 10.0}),
                (0, 0, {'length_m': 35.0, 'weight_kg': 7.0}),
            ]
        })
        wiz.action_register_rolls()

        mo.button_mark_done()
        self.assertEqual(mo.state, 'done')
        for roll in mo.roll_ids:
            self.assertEqual(roll.qc_state, 'pending')
            self.assertEqual(roll.current_location_id.name, 'QC-Hold')

