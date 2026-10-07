# -*- coding: utf-8 -*-
{
    'name': 'Textile MRP',
    'version': '19.0.1.0.0',
    'category': 'Manufacturing/Textile',
    'summary': 'Textile Manufacturing Extensions, Shifts, and Roll Registration',
    'description': """
Textile Manufacturing Management
=================================
- Integration of physical fabric rolls with Manufacturing Orders.
- Register Rolls Wizard with automatic stock.lot and roll generation.
- Production balance invariants (Good Output + Scrap = Planned Qty).
- Production shifts and operators metadata.
    """,
    'author': 'Antigravity / Textile ERP MVP Team',
    'depends': [
        'textile_core',
        'textile_inventory',
        'mrp',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/textile_mrp_security.xml',
        'data/textile_shift_data.xml',
        'data/workcenter_data.xml',
        'wizard/register_rolls_wizard_views.xml',
        'views/textile_shift_views.xml',
        'views/mrp_production_views.xml',
        'views/textile_mrp_menus.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
