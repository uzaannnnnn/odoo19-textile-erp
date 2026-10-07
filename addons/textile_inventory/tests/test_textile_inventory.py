# -*- coding: utf-8 -*-
import base64
import io
from psycopg2.errors import UniqueViolation

from odoo import fields
from odoo.exceptions import ValidationError, AccessError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger
from odoo.tools.pdf import PdfFileReader


@tagged('post_install', '-at_install')
class TestTextileInventory(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env['product.product'].search([
            ('is_textile_product', '=', True),
            ('textile_type', '=', 'fabric')
        ], limit=1)
        if not cls.product:
            cls.product = cls.env['product.product'].create({
                'name': 'Test Fabric',
                'uom_id': cls.env.ref('uom.product_uom_meter').id,
                'is_textile_product': True,
                'is_storable': True,
                'tracking': 'lot',
            })
        cls.mo = cls.env['mrp.production'].create({
            'product_id': cls.product.id,
            'product_qty': 100.0,
            'product_uom_id': cls.product.uom_id.id,
        })

    def _create_test_roll(self, prefix='TEST', length=100.0, weight=20.0, grade='A', qc_state='pending'):
        lot = self.env['stock.lot'].create({
            'name': f'{prefix}-LOT-{fields.Datetime.now().strftime("%Y%m%d%H%M%S%f")}',
            'product_id': self.product.id,
            'company_id': self.env.company.id,
        })
        roll = self.env['textile.roll'].create({
            'product_id': self.product.id,
            'production_id': self.mo.id,
            'lot_id': lot.id,
            'length_m': length,
            'weight_kg': weight,
            'grade': grade,
            'qc_state': qc_state,
        })
        return roll

    def test_roll_creation_and_sequence(self):
        """Test roll creation with valid lot and sequence."""
        roll = self._create_test_roll(prefix='SEQ', length=120.5, weight=24.1)
        self.assertTrue(roll.name.startswith('ROLL-'))
        self.assertEqual(roll.qc_state, 'pending')
        self.assertEqual(roll.length_m, 120.5)
        self.assertTrue(roll.lot_id)

    def test_roll_validation_positive_length(self):
        """Test that length must be strictly greater than 0."""
        lot = self.env['stock.lot'].create({
            'name': 'TEST-LOT-ZERO-LEN',
            'product_id': self.product.id,
            'company_id': self.env.company.id,
        })
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception):
            self.env['textile.roll'].create({
                'product_id': self.product.id,
                'production_id': self.mo.id,
                'lot_id': lot.id,
                'length_m': 0.0,
            })

    def test_roll_validation_negative_weight(self):
        """Test that weight cannot be negative."""
        lot = self.env['stock.lot'].create({
            'name': 'TEST-LOT-NEG-WT',
            'product_id': self.product.id,
            'company_id': self.env.company.id,
        })
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception):
            self.env['textile.roll'].create({
                'product_id': self.product.id,
                'production_id': self.mo.id,
                'lot_id': lot.id,
                'length_m': 50.0,
                'weight_kg': -5.0,
            })

    def test_locations_exist(self):
        """Test that all required textile warehouse locations exist."""
        qc_hold = self.env['stock.location'].search([('name', '=', 'QC-Hold')], limit=1)
        rework = self.env['stock.location'].search([('name', '=', 'Rework')], limit=1)
        scrap = self.env['stock.location'].search([('name', '=', 'Scrap')], limit=1)

        self.assertTrue(qc_hold, "WH/QC-Hold location must exist")
        self.assertTrue(rework, "WH/Rework location must exist")
        self.assertTrue(scrap, "WH/Scrap location must exist")

    def test_roll_unique_lot_constraint(self):
        """Test that 1 physical roll = 1 unique lot invariant is enforced."""
        lot = self.env['stock.lot'].create({
            'name': 'TEST-LOT-UNIQ-01',
            'product_id': self.product.id,
            'company_id': self.env.company.id,
        })
        self.env['textile.roll'].create({
            'product_id': self.product.id,
            'production_id': self.mo.id,
            'lot_id': lot.id,
            'length_m': 100.0,
        })
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception):
            self.env['textile.roll'].create({
                'product_id': self.product.id,
                'production_id': self.mo.id,
                'lot_id': lot.id,
                'length_m': 80.0,
            })

    def test_roll_unique_name_constraint(self):
        """Test that roll numbers must be unique across all records."""
        roll1 = self._create_test_roll(prefix='UNIQNAME1')
        lot2 = self.env['stock.lot'].create({
            'name': 'TEST-LOT-UNIQNAME2',
            'product_id': self.product.id,
            'company_id': self.env.company.id,
        })
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception):
            self.env['textile.roll'].create({
                'name': roll1.name,
                'product_id': self.product.id,
                'production_id': self.mo.id,
                'lot_id': lot2.id,
                'length_m': 60.0,
            })

    def test_roll_unlink_protection(self):
        """Test that non-pending rolls cannot be deleted."""
        roll = self._create_test_roll(prefix='UNLINK')
        roll.write({'qc_state': 'passed'})
        with self.assertRaises(ValidationError):
            roll.unlink()

    def test_stock_lot_roll_relation(self):
        """Test the bidirectional relation between stock.lot and textile.roll."""
        roll = self._create_test_roll(prefix='REL')
        self.assertEqual(roll.lot_id.roll_id.id, roll.id)
        self.assertTrue(roll.lot_id.is_textile_roll)

    # =========================================================================
    # V1.1 QR ROLL IDENTITY & PAYLOAD TESTS
    # =========================================================================

    def test_qr_payload_deterministic_and_environment_aware(self):
        """Test QR payload is deterministic, environment-aware, and safe."""
        roll = self._create_test_roll(prefix='QRPAYLOAD')
        base_url = roll.get_base_url().rstrip('/')
        expected_url = f"{base_url}/textile/roll/{roll.id}"

        # Deterministic and environment-aware
        self.assertEqual(roll.qr_payload, expected_url)
        self.assertTrue(roll.qr_payload.startswith(base_url))
        self.assertIn(f"/textile/roll/{roll.id}", roll.qr_payload)

        # Security check: payload must not contain sensitive info
        for forbidden in ['password', 'secret', 'token', 'admin', 'db=']:
            self.assertNotIn(forbidden, roll.qr_payload.lower())

    def test_qr_code_image_preview_dynamic(self):
        """Test dynamic QR preview generation and verify it does not pollute DB storage."""
        roll = self._create_test_roll(prefix='QRIMG')
        self.assertTrue(roll.qr_code_image, "QR preview image must be generated dynamically.")
        
        # Verify valid PNG header
        raw_bytes = base64.b64decode(roll.qr_code_image)
        self.assertTrue(raw_bytes.startswith(b'\x89PNG\r\n\x1a\n'), "Generated QR must be a valid PNG.")
        
        # Verify store=False: field is not a database column
        self.assertFalse(self.env['textile.roll']._fields['qr_code_image'].store, "QR image must be store=False.")

    # =========================================================================
    # V1.1 PRINTABLE LABEL & REPORT RENDERING TESTS
    # =========================================================================

    def test_single_roll_report_rendering(self):
        """Test single roll PDF report rendering with 100x150mm custom paperformat."""
        roll = self._create_test_roll(prefix='LABEL1', length=52.4, weight=11.8, grade='A', qc_state='passed')
        report = self.env.ref('textile_inventory.action_report_textile_roll')
        self.assertTrue(report, "action_report_textile_roll must exist.")

        pdf_bytes, report_type = report.with_context(force_report_rendering=True)._render_qweb_pdf(report.report_name, res_ids=[roll.id])
        self.assertEqual(report_type, 'pdf')
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "Report output must be valid PDF format.")

        reader = PdfFileReader(io.BytesIO(pdf_bytes))
        self.assertEqual(reader.numPages, 1, "Single roll print must generate exactly 1 label page.")

        # Check paper dimensions (100mm x 150mm -> ~283x425 points)
        page = reader.getPage(0)
        width_pt = float(page.mediaBox.width)
        height_pt = float(page.mediaBox.height)
        self.assertAlmostEqual(width_pt, 283.46, delta=5.0, msg="Width should be ~100mm (283 pt)")
        self.assertAlmostEqual(height_pt, 425.20, delta=5.0, msg="Height should be ~150mm (425 pt)")

    def test_multi_roll_report_rendering(self):
        """Test batch roll PDF printing: N selected rolls produce exactly N label pages."""
        roll1 = self._create_test_roll(prefix='BATCH1', length=50.0, weight=10.0)
        roll2 = self._create_test_roll(prefix='BATCH2', length=75.0, weight=15.0)
        roll3 = self._create_test_roll(prefix='BATCH3', length=120.0, weight=24.0)
        rolls = roll1 | roll2 | roll3

        report = self.env.ref('textile_inventory.action_report_textile_roll')
        pdf_bytes, report_type = report.with_context(force_report_rendering=True)._render_qweb_pdf(report.report_name, res_ids=rolls.ids)
        self.assertEqual(report_type, 'pdf')
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "Report output must be valid PDF format.")

        reader = PdfFileReader(io.BytesIO(pdf_bytes))
        self.assertEqual(reader.numPages, 3, "Multi-roll printing must generate exactly 1 label per roll.")

    def test_report_filename_formatting(self):
        """Test report base filename generation."""
        roll = self._create_test_roll(prefix='FNAME')
        filename = roll._get_report_base_filename()
        self.assertEqual(filename, f"Roll_Label_{roll.name}")

    def test_action_print_label_button(self):
        """Test form view Print Label button returns action."""
        roll = self._create_test_roll(prefix='BTN')
        action = roll.action_print_label()
        action_type = action.get('type')
        if action_type == 'ir.actions.act_window' and 'report_action' in action.get('context', {}):
            report_act = action['context']['report_action']
            self.assertEqual(report_act.get('type'), 'ir.actions.report')
            self.assertEqual(report_act.get('report_name'), 'textile_inventory.report_roll_label_template')
        else:
            self.assertEqual(action.get('type'), 'ir.actions.report')
            self.assertEqual(action.get('report_name'), 'textile_inventory.report_roll_label_template')

    # =========================================================================
    # V1.1 INVARIANTS: REPRINT IDEMPOTENCY & NON-MUTATION
    # =========================================================================

    def test_label_reprint_idempotency_and_no_stock_change(self):
        """Reprinting labels must NEVER create rolls, lots, stock quants, or stock moves."""
        roll = self._create_test_roll(prefix='REPRINT', length=85.0, weight=17.0, qc_state='passed')
        report = self.env.ref('textile_inventory.action_report_textile_roll')

        # Snapshot baseline state
        roll_count_before = self.env['textile.roll'].search_count([])
        lot_count_before = self.env['stock.lot'].search_count([])
        move_count_before = self.env['stock.move'].search_count([])
        quant_count_before = self.env['stock.quant'].search_count([])
        qc_state_before = roll.qc_state

        # Reprint 5 times
        for _ in range(5):
            pdf_bytes, _ = report.with_context(force_report_rendering=True)._render_qweb_pdf(report.report_name, res_ids=[roll.id])
            self.assertTrue(pdf_bytes)

        # Verify absolute zero state changes
        self.assertEqual(self.env['textile.roll'].search_count([]), roll_count_before)
        self.assertEqual(self.env['stock.lot'].search_count([]), lot_count_before)
        self.assertEqual(self.env['stock.move'].search_count([]), move_count_before)
        self.assertEqual(self.env['stock.quant'].search_count([]), quant_count_before)
        self.assertEqual(roll.qc_state, qc_state_before)

    def test_roll_identity_immutability(self):
        """Roll Number and Lot identity cannot be modified after creation."""
        roll = self._create_test_roll(prefix='IMMUTABLE')
        other_lot = self.env['stock.lot'].create({
            'name': 'OTHER-LOT-IMMUTABLE',
            'product_id': self.product.id,
            'company_id': self.env.company.id,
        })

        with self.assertRaises(ValidationError):
            roll.write({'name': 'ROLL-MODIFIED-9999'})

        with self.assertRaises(ValidationError):
            roll.write({'lot_id': other_lot.id})

    def test_roll_copy_forbidden(self):
        """Roll duplication is strictly disallowed."""
        roll = self._create_test_roll(prefix='NOCOPY')
        with self.assertRaises(ValidationError):
            roll.copy()

    # =========================================================================
    # V1.1 FAST SEARCH TESTS
    # =========================================================================

    def test_fast_search_domains(self):
        """Test search view filter capabilities for fast roll lookup."""
        roll = self._create_test_roll(prefix='SEARCH', grade='B', qc_state='rework')

        # Search by roll number
        found_by_name = self.env['textile.roll'].search([('name', '=', roll.name)])
        self.assertIn(roll, found_by_name)

        # Search by lot name
        found_by_lot = self.env['textile.roll'].search([('lot_id.name', '=', roll.lot_id.name)])
        self.assertIn(roll, found_by_lot)

        # Search by MO
        found_by_mo = self.env['textile.roll'].search([('production_id.name', '=', roll.production_id.name)])
        self.assertIn(roll, found_by_mo)

        # Search by QC state
        found_by_qc = self.env['textile.roll'].search([('qc_state', '=', 'rework')])
        self.assertIn(roll, found_by_qc)

        # Search by Grade
        found_by_grade = self.env['textile.roll'].search([('grade', '=', 'B')])
        self.assertIn(roll, found_by_grade)

    # =========================================================================
    # V1.1 MOBILE SCAN TEMPLATE TESTS
    # =========================================================================

    def test_mobile_roll_page_template_rendering(self):
        """Test that the mobile roll page template renders cleanly with all details."""
        roll = self._create_test_roll(prefix='MOBILE', length=62.3, weight=12.5, grade='A', qc_state='passed')
        html = self.env['ir.qweb']._render('textile_inventory.textile_roll_mobile_page', {'roll': roll})
        self.assertIn(roll.name, html)
        self.assertIn(self.product.display_name, html)
        self.assertIn('62.30 m', html)
        self.assertIn('12.50 kg', html)
        self.assertIn('Grade A', html)
        self.assertIn('QC: PASSED', html)
        self.assertIn('Open in Odoo ERP', html)

    def test_mobile_roll_error_template_rendering(self):
        """Test that the mobile error page template renders cleanly without tracebacks."""
        html = self.env['ir.qweb']._render('textile_inventory.textile_roll_mobile_error', {
            'title': 'Roll Not Found',
            'message': 'The scanned roll identifier is invalid or no longer available.',
        })
        self.assertIn('Roll Not Found', html)
        self.assertIn('The scanned roll identifier is invalid', html)

    def test_mobile_controller_workflow(self):
        """Test mobile controller endpoints for valid roll, scan by name, not found, and unauthorized."""
        from odoo.addons.textile_inventory.controllers.roll import TextileRollController
        import odoo.addons.textile_inventory.controllers.roll as roll_ctrl_module
        from unittest.mock import MagicMock

        roll = self._create_test_roll(prefix='CTRL', length=55.0, weight=11.0, grade='A', qc_state='passed')
        ctrl = TextileRollController()

        from odoo.http import Response
        mock_req = MagicMock()
        mock_req.env = self.env
        def fake_render(template, qcontext=None, status=200):
            html = self.env['ir.qweb']._render(template, qcontext)
            return Response(html, status=status)
        mock_req.render = fake_render

        orig_req = getattr(roll_ctrl_module, 'request', None)
        try:
            roll_ctrl_module.request = mock_req

            # 1. Access by roll_id
            resp_id = ctrl.textile_roll_mobile_view(roll_id=roll.id)
            self.assertEqual(resp_id.status_code, 200)
            self.assertIn(roll.name, resp_id.get_data(as_text=True))

            # 2. Access by roll_name
            resp_name = ctrl.textile_roll_mobile_view(roll_name=roll.name)
            self.assertEqual(resp_name.status_code, 200)
            self.assertIn(roll.name, resp_name.get_data(as_text=True))

            # 3. Non-existent roll
            resp_404 = ctrl.textile_roll_mobile_view(roll_id=9999999)
            self.assertEqual(resp_404.status_code, 404)
            self.assertIn('Roll Not Found', resp_404.get_data(as_text=True))

            # 4. Unauthorized user (without textile group)
            unauth_user = self.env['res.users'].create({
                'name': 'Test Unauth User',
                'login': 'test_unauth_user_ctrl',
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
            })
            mock_req.env = self.env(user=unauth_user)
            resp_403 = ctrl.textile_roll_mobile_view(roll_id=roll.id)
            self.assertEqual(resp_403.status_code, 403)
            self.assertIn('Access Denied', resp_403.get_data(as_text=True))
        finally:
            roll_ctrl_module.request = orig_req

