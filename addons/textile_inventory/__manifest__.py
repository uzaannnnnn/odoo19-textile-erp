# -*- coding: utf-8 -*-
{
    'name': 'Textile Inventory',
    'version': '19.0.1.1.0',
    'category': 'Manufacturing/Textile',
    'summary': 'Physical Fabric Roll Management, QR Identity, Label Printing, and Fast Traceability',
    'description': """
Textile Inventory Management V1.1
=================================
- Physical fabric roll tracking (textile.roll)
- 1 physical roll = 1 unique stock lot mapping
- Warehousing locations: WH/Stock, WH/QC-Hold, WH/Rework, WH/Scrap
- QR Roll Identity and deterministic environment-aware URL payload
- Dedicated 100x150mm industrial roll label PDF printing (single & batch)
- Real-time QR preview on roll form view
- Read-only mobile scan and traceability interface
- Roll sequence, validations, and immutability guards
    """,
    'author': 'Antigravity / Textile ERP Team',
    'depends': [
        'textile_core',
        'stock',
        'mrp',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/textile_inventory_security.xml',
        'data/sequence_data.xml',
        'data/location_data.xml',
        'data/product_stock_data.xml',
        'data/paperformat_data.xml',
        'report/roll_label_report.xml',
        'views/textile_roll_views.xml',
        'views/mobile_roll_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
