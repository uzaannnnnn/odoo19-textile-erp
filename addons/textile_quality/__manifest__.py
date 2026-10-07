# -*- coding: utf-8 -*-
{
    'name': 'Textile Quality',
    'version': '19.0.1.0.0',
    'category': 'Manufacturing/Textile',
    'summary': 'Textile QC Inspections, Defect Tracking, and Delivery Quality Gate',
    'description': """
Textile Quality Control Management
==================================
- Fabric roll quality inspections (PASS, REWORK, REJECT)
- Stock relocation to WH/Stock, WH/Rework, or WH/Scrap
- Defect types and defect lines tracking
- Strict server-side delivery quality gate (blocks unpassed rolls)
- Whole roll delivery enforcement (no partial roll delivery)
    """,
    'author': 'Antigravity / Textile ERP MVP Team',
    'depends': [
        'textile_core',
        'textile_inventory',
        'stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/defect_type_data.xml',
        'views/textile_defect_type_views.xml',
        'views/textile_inspection_views.xml',
        'views/textile_roll_views.xml',
        'views/textile_quality_menus.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
