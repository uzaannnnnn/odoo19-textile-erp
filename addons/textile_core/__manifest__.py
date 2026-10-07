# -*- coding: utf-8 -*-
{
    'name': 'Textile Core',
    'version': '19.0.1.0.0',
    'category': 'Manufacturing/Textile',
    'summary': 'Textile Product Master Data and Shared Configuration',
    'description': """
Textile ERP Core Module
========================
- Textile attributes on Product Master (width, GSM, composition, material, fabric type, textile type).
- Shared Textile security groups and role hierarchy.
- Textile root menu and product catalog.
    """,
    'author': 'Antigravity / Textile ERP MVP Team',
    'depends': [
        'base',
        'product',
        'uom',
    ],
    'data': [
        'security/textile_security.xml',
        'views/product_template_views.xml',
        'views/textile_menus.xml',
        'data/textile_data.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
