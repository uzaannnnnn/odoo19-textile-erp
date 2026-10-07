# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTextileQuality(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.meter_uom = cls.env.ref('uom.product_uom_meter')
        cls.stock_location = cls.env.ref('stock.stock_location_stock')
        cls.customer_location = cls.env.ref('stock.stock_location_customers')
        cls.customer = cls.env.ref('textile_core.partner_customer_abc')

        cls.fabric_product = cls.env['product.product'].search([
            ('is_textile_product', '=', True),
            ('textile_type', '=', 'fabric')
        ], limit=1)

        # Create MO and produce 1 roll into QC-Hold
        cls.mo = cls.env['mrp.production'].create({
            'product_id': cls.fabric_product.id,
            'product_qty': 100.0,
            'product_uom_id': cls.meter_uom.id,
        })
        cls.mo.action_confirm()

        wiz = cls.env['textile.register.rolls.wizard'].create({
            'production_id': cls.mo.id,
            'production_loss_m': 0.0,
            'line_ids': [
                (0, 0, {'length_m': 100.0, 'weight_kg': 20.0}),
            ]
        })
        wiz.action_register_rolls()
        cls.mo.button_mark_done()
        cls.roll = cls.mo.roll_ids[0]

    def _create_delivery(self, roll, qty):
        """Helper to create an outgoing delivery picking with this roll's lot."""
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing')
        ], limit=1)

        picking = self.env['stock.picking'].create({
            'partner_id': self.customer.id,
            'picking_type_id': picking_type.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
            'move_ids': [(0, 0, {
                'description_picking': f"Deliver {roll.name}",
                'product_id': roll.product_id.id,
                'product_uom': roll.product_id.uom_id.id,
                'product_uom_qty': qty,
                'location_id': self.stock_location.id,
                'location_dest_id': self.customer_location.id,
                'picked': True,
                'move_line_ids': [(0, 0, {
                    'product_id': roll.product_id.id,
                    'product_uom_id': roll.product_id.uom_id.id,
                    'location_id': self.stock_location.id,
                    'location_dest_id': self.customer_location.id,
                    'lot_id': roll.lot_id.id,
                    'quantity': qty,
                    'picked': True,
                })],
            })],
        })
        picking.action_confirm()
        for move in picking.move_ids:
            move.move_line_ids.picking_id = picking.id
        return picking

    def test_qc_pass_workflow(self):
        """Test QC PASS transitions roll to 'passed' and moves stock to WH/Stock."""
        inspection = self.env['textile.inspection'].create({
            'roll_id': self.roll.id,
            'grade': 'A',
            'actual_width_cm': 150.0,
            'actual_gsm': 120.0,
        })
        inspection.action_pass()

        self.assertEqual(inspection.state, 'done')
        self.assertEqual(inspection.result, 'passed')
        self.assertEqual(self.roll.qc_state, 'passed')
        self.assertEqual(self.roll.current_location_id.id, self.stock_location.id)

    def test_qc_rework_workflow(self):
        """Test QC REWORK transitions roll to 'rework' and moves stock to WH/Rework."""
        # Create a new roll for rework test
        mo2 = self.env['mrp.production'].create({
            'product_id': self.fabric_product.id,
            'product_qty': 50.0,
            'product_uom_id': self.meter_uom.id,
        })
        mo2.action_confirm()
        wiz = self.env['textile.register.rolls.wizard'].create({
            'production_id': mo2.id,
            'production_loss_m': 0.0,
            'line_ids': [(0, 0, {'length_m': 50.0, 'weight_kg': 10.0})]
        })
        wiz.action_register_rolls()
        mo2.button_mark_done()
        rework_roll = mo2.roll_ids[0]

        inspection = self.env['textile.inspection'].create({
            'roll_id': rework_roll.id,
            'grade': 'B',
        })
        inspection.action_rework()

        self.assertEqual(inspection.state, 'done')
        self.assertEqual(inspection.result, 'rework')
        self.assertEqual(rework_roll.qc_state, 'rework')
        self.assertEqual(rework_roll.current_location_id.name, 'Rework')

    def test_qc_reject_workflow(self):
        """Test QC REJECT transitions roll to 'rejected' and moves stock to WH/Scrap."""
        mo3 = self.env['mrp.production'].create({
            'product_id': self.fabric_product.id,
            'product_qty': 40.0,
            'product_uom_id': self.meter_uom.id,
        })
        mo3.action_confirm()
        wiz = self.env['textile.register.rolls.wizard'].create({
            'production_id': mo3.id,
            'production_loss_m': 0.0,
            'line_ids': [(0, 0, {'length_m': 40.0, 'weight_kg': 8.0})]
        })
        wiz.action_register_rolls()
        mo3.button_mark_done()
        reject_roll = mo3.roll_ids[0]

        inspection = self.env['textile.inspection'].create({
            'roll_id': reject_roll.id,
            'grade': 'C',
        })
        inspection.action_reject()

        self.assertEqual(inspection.state, 'done')
        self.assertEqual(inspection.result, 'rejected')
        self.assertEqual(reject_roll.qc_state, 'rejected')
        self.assertEqual(reject_roll.current_location_id.name, 'Scrap')

    def test_delivery_gate_blocks_pending_roll(self):
        """Test that pending rolls are blocked from delivery."""
        mo_pend = self.env['mrp.production'].create({
            'product_id': self.fabric_product.id,
            'product_qty': 60.0,
            'product_uom_id': self.meter_uom.id,
        })
        mo_pend.action_confirm()
        wiz = self.env['textile.register.rolls.wizard'].create({
            'production_id': mo_pend.id,
            'production_loss_m': 0.0,
            'line_ids': [(0, 0, {'length_m': 60.0, 'weight_kg': 12.0})]
        })
        wiz.action_register_rolls()
        mo_pend.button_mark_done()
        pending_roll = mo_pend.roll_ids[0]

        delivery = self._create_delivery(pending_roll, 60.0)
        with self.assertRaises(UserError) as cm:
            delivery.button_validate()
        self.assertIn("has not passed quality inspection", str(cm.exception))

    def test_delivery_gate_blocks_rework_roll(self):
        """Test that rework rolls are blocked from delivery."""
        mo_rew = self.env['mrp.production'].create({
            'product_id': self.fabric_product.id,
            'product_qty': 70.0,
            'product_uom_id': self.meter_uom.id,
        })
        mo_rew.action_confirm()
        wiz = self.env['textile.register.rolls.wizard'].create({
            'production_id': mo_rew.id,
            'production_loss_m': 0.0,
            'line_ids': [(0, 0, {'length_m': 70.0, 'weight_kg': 14.0})]
        })
        wiz.action_register_rolls()
        mo_rew.button_mark_done()
        rework_roll = mo_rew.roll_ids[0]

        insp = self.env['textile.inspection'].create({
            'roll_id': rework_roll.id,
            'grade': 'B',
        })
        insp.action_rework()

        delivery = self._create_delivery(rework_roll, 70.0)
        with self.assertRaises(UserError) as cm:
            delivery.button_validate()
        self.assertIn("REWORK", str(cm.exception))

    def test_delivery_gate_blocks_partial_roll(self):
        """Test whole-roll delivery restriction (partial quantities blocked)."""
        mo_part = self.env['mrp.production'].create({
            'product_id': self.fabric_product.id,
            'product_qty': 80.0,
            'product_uom_id': self.meter_uom.id,
        })
        mo_part.action_confirm()
        wiz = self.env['textile.register.rolls.wizard'].create({
            'production_id': mo_part.id,
            'production_loss_m': 0.0,
            'line_ids': [(0, 0, {'length_m': 80.0, 'weight_kg': 16.0})]
        })
        wiz.action_register_rolls()
        mo_part.button_mark_done()
        passed_roll = mo_part.roll_ids[0]

        insp = self.env['textile.inspection'].create({
            'roll_id': passed_roll.id,
            'grade': 'A',
        })
        insp.action_pass()

        # Attempt delivering partial 50m of 80m roll
        delivery = self._create_delivery(passed_roll, 50.0)
        with self.assertRaises(UserError) as cm:
            delivery.button_validate()
        self.assertIn("Partial roll delivery is not supported", str(cm.exception))

    def test_reinspection_preserves_history(self):
        """Test multiple inspections on the same roll preserve full history."""
        mo_hist = self.env['mrp.production'].create({
            'product_id': self.fabric_product.id,
            'product_qty': 90.0,
            'product_uom_id': self.meter_uom.id,
        })
        mo_hist.action_confirm()
        wiz = self.env['textile.register.rolls.wizard'].create({
            'production_id': mo_hist.id,
            'production_loss_m': 0.0,
            'line_ids': [(0, 0, {'length_m': 90.0, 'weight_kg': 18.0})]
        })
        wiz.action_register_rolls()
        mo_hist.button_mark_done()
        roll = mo_hist.roll_ids[0]

        # 1st inspection: REWORK
        insp1 = self.env['textile.inspection'].create({
            'roll_id': roll.id,
            'grade': 'B',
        })
        insp1.action_rework()
        self.assertEqual(roll.qc_state, 'rework')

        # 2nd inspection: PASS
        insp2 = self.env['textile.inspection'].create({
            'roll_id': roll.id,
            'grade': 'A',
        })
        insp2.action_pass()
        self.assertEqual(roll.qc_state, 'passed')

        # Both inspections must remain in roll history
        self.assertEqual(len(roll.inspection_ids), 2)
        self.assertEqual(roll.inspection_ids[0].result, 'passed')
        self.assertEqual(roll.inspection_ids[1].result, 'rework')

    def test_completed_inspection_immutability(self):
        """Test that completed inspections cannot be deleted or modified."""
        insp = self.env['textile.inspection'].create({
            'roll_id': self.roll.id,
            'grade': 'A',
        })
        insp.action_pass()
        self.assertEqual(insp.state, 'done')

        # Deletion must be blocked
        with self.assertRaises(UserError):
            insp.unlink()

        # Modification by non-manager must be blocked
        sales_user = self.env['res.users'].create({
            'name': 'Test Sales Person',
            'login': 'test_sales_user',
            'email': 'sales@test.com',
            'group_ids': [(6, 0, [self.env.ref('textile_core.group_textile_sales').id])],
        })
        with self.assertRaises(UserError):
            insp.with_user(sales_user).write({'grade': 'C'})

    def test_cannot_pass_or_rework_rejected_roll(self):
        """Test that rejected rolls cannot transition to pass or rework."""
        mo_rej = self.env['mrp.production'].create({
            'product_id': self.fabric_product.id,
            'product_qty': 30.0,
            'product_uom_id': self.meter_uom.id,
        })
        mo_rej.action_confirm()
        wiz = self.env['textile.register.rolls.wizard'].create({
            'production_id': mo_rej.id,
            'production_loss_m': 0.0,
            'line_ids': [(0, 0, {'length_m': 30.0, 'weight_kg': 6.0})]
        })
        wiz.action_register_rolls()
        mo_rej.button_mark_done()
        roll = mo_rej.roll_ids[0]

        insp1 = self.env['textile.inspection'].create({
            'roll_id': roll.id,
            'grade': 'C',
        })
        insp1.action_reject()
        self.assertEqual(roll.qc_state, 'rejected')

        insp2 = self.env['textile.inspection'].create({
            'roll_id': roll.id,
            'grade': 'A',
        })
        with self.assertRaises(UserError):
            insp2.action_pass()
        with self.assertRaises(UserError):
            insp2.action_rework()
        with self.assertRaises(UserError):
            insp2.action_reject()

    def test_delivery_gate_blocks_rejected_roll(self):
        """Test that rejected rolls are strictly blocked from delivery."""
        mo_rej = self.env['mrp.production'].create({
            'product_id': self.fabric_product.id,
            'product_qty': 25.0,
            'product_uom_id': self.meter_uom.id,
        })
        mo_rej.action_confirm()
        wiz = self.env['textile.register.rolls.wizard'].create({
            'production_id': mo_rej.id,
            'production_loss_m': 0.0,
            'line_ids': [(0, 0, {'length_m': 25.0, 'weight_kg': 5.0})]
        })
        wiz.action_register_rolls()
        mo_rej.button_mark_done()
        roll = mo_rej.roll_ids[0]

        insp = self.env['textile.inspection'].create({
            'roll_id': roll.id,
            'grade': 'C',
        })
        insp.action_reject()

        delivery = self._create_delivery(roll, 25.0)
        with self.assertRaises(UserError) as cm:
            delivery.button_validate()
        self.assertIn("REJECTED", str(cm.exception))

    def test_traceability_backward_and_forward(self):
        """Test complete backward and forward traceability navigation."""
        # 1. Yarn Lot
        yarn_product = self.env['product.product'].search([
            ('is_textile_product', '=', True),
            ('textile_type', '=', 'raw_material')
        ], limit=1)
        yarn_lot = self.env['stock.lot'].create({
            'name': 'TEST-TRACE-YARN-01',
            'product_id': yarn_product.id,
            'company_id': self.env.company.id,
        })

        # 2. MO consuming Yarn Lot
        mo = self.env['mrp.production'].create({
            'product_id': self.fabric_product.id,
            'product_qty': 100.0,
            'product_uom_id': self.meter_uom.id,
        })
        mo.action_confirm()
        # Add consumed raw move line
        raw_move = mo.move_raw_ids.filtered(lambda m: m.product_id == yarn_product)
        if raw_move:
            self.env['stock.move.line'].create({
                'move_id': raw_move.id,
                'product_id': yarn_product.id,
                'product_uom_id': yarn_product.uom_id.id,
                'location_id': raw_move.location_id.id,
                'location_dest_id': raw_move.location_dest_id.id,
                'lot_id': yarn_lot.id,
                'quantity': 20.0,
                'picked': True,
            })

        wiz = self.env['textile.register.rolls.wizard'].create({
            'production_id': mo.id,
            'production_loss_m': 0.0,
            'line_ids': [(0, 0, {'length_m': 100.0, 'weight_kg': 20.0})]
        })
        wiz.action_register_rolls()
        mo.button_mark_done()
        roll = mo.roll_ids[0]

        # 3. QC Pass
        insp = self.env['textile.inspection'].create({
            'roll_id': roll.id,
            'grade': 'A',
        })
        insp.action_pass()

        # 4. Delivery
        delivery = self._create_delivery(roll, 100.0)
        delivery.button_validate()
        self.assertEqual(delivery.state, 'done')

        # Backward Traceability:
        # Delivered roll -> Lot -> MO -> Input Lot -> QC
        self.assertEqual(roll.lot_id.name, roll.name)
        self.assertEqual(roll.production_id.id, mo.id)
        consumed_lots = mo.move_raw_ids.move_line_ids.lot_id
        if raw_move:
            self.assertIn(yarn_lot, consumed_lots)
        self.assertEqual(len(roll.inspection_ids), 1)
        self.assertEqual(roll.inspection_ids.result, 'passed')

        # Forward Traceability:
        # Yarn Lot -> MOs -> Rolls -> Deliveries
        if raw_move:
            produced_mos = self.env['stock.move.line'].search([
                ('lot_id', '=', yarn_lot.id)
            ]).move_id.raw_material_production_id
            self.assertIn(mo, produced_mos)
            self.assertIn(roll, produced_mos.roll_ids)
            del_pickings = self.env['stock.move.line'].search([
                ('lot_id', '=', roll.lot_id.id),
                ('location_dest_id.usage', '=', 'customer'),
                ('state', '=', 'done')
            ]).picking_id
            self.assertIn(delivery, del_pickings)
