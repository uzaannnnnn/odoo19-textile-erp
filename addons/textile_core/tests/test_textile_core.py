# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTextileCore(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.meter_uom = cls.env.ref('uom.product_uom_meter')
        cls.kg_uom = cls.env.ref('uom.product_uom_kgm')

    def test_product_textile_attributes(self):
        """Test product template creation and textile attributes."""
        fabric_tmpl = self.env['product.template'].create({
            'name': 'Test Cotton Poplin',
            'uom_id': self.meter_uom.id,
            'is_textile_product': True,
            'textile_type': 'fabric',
            'fabric_type': 'woven',
            'material': 'Cotton',
            'composition': '100% COT',
            'color': 'Navy Blue',
            'width_cm': 148.0,
            'gsm': 115.0,
        })
        self.assertTrue(fabric_tmpl.is_textile_product)
        self.assertEqual(fabric_tmpl.textile_type, 'fabric')
        self.assertEqual(fabric_tmpl.fabric_type, 'woven')
        self.assertEqual(fabric_tmpl.material, 'Cotton')
        self.assertEqual(fabric_tmpl.width_cm, 148.0)
        self.assertEqual(fabric_tmpl.gsm, 115.0)

    def test_product_search_filter(self):
        """Test domain searching on textile fields."""
        textile_products = self.env['product.template'].search([
            ('is_textile_product', '=', True),
            ('textile_type', '=', 'fabric')
        ])
        self.assertTrue(len(textile_products) >= 1)

    def test_product_negative_dimensions(self):
        """Test that negative width and GSM are blocked by validation constraints."""
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.env['product.template'].create({
                'name': 'Negative Width Fabric',
                'uom_id': self.meter_uom.id,
                'is_textile_product': True,
                'width_cm': -150.0,
            })

        with self.assertRaises(ValidationError):
            self.env['product.template'].create({
                'name': 'Negative GSM Fabric',
                'uom_id': self.meter_uom.id,
                'is_textile_product': True,
                'gsm': -120.0,
            })
