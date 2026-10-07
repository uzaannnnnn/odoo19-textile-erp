# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, MissingError


class TextileRollController(http.Controller):

    @http.route([
        '/textile/roll/<int:roll_id>',
        '/textile/roll/scan/<string:roll_name>',
        '/textile/roll/lookup',
    ], type='http', auth='user', website=False)
    def textile_roll_mobile_view(self, roll_id=None, roll_name=None, **kwargs):
        """Authenticated read-only mobile view for fabric rolls."""
        Roll = request.env['textile.roll']
        
        # 1. Enforce read access permissions without bypassing via sudo()
        try:
            Roll.check_access('read')
        except AccessError:
            return request.render('textile_inventory.textile_roll_mobile_error', {
                'title': 'Access Denied',
                'message': 'You do not have permission to view fabric roll records.',
            }, status=403)

        # 2. Locate the requested roll
        roll = None
        target_name = roll_name or kwargs.get('name') or kwargs.get('q')
        
        if roll_id:
            roll = Roll.browse(roll_id)
        elif target_name:
            roll = Roll.search([('name', '=', target_name.strip())], limit=1)

        # 3. Verify record existence and record-level access rules
        try:
            if not roll or not roll.exists():
                return request.render('textile_inventory.textile_roll_mobile_error', {
                    'title': 'Roll Not Found',
                    'message': 'The scanned roll identifier is invalid or no longer available.',
                }, status=404)
            # Evaluate access rules
            roll.check_access('read')
            _ = roll.name
        except (AccessError, MissingError):
            return request.render('textile_inventory.textile_roll_mobile_error', {
                'title': 'Access Denied',
                'message': 'You do not have permission to view this roll.',
            }, status=403)

        # 4. Render read-only mobile view
        return request.render('textile_inventory.textile_roll_mobile_page', {
            'roll': roll,
        })
