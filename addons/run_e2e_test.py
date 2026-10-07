# -*- coding: utf-8 -*-
import os
import sys

# Auto-delegate to Docker container if executed directly on host machine
if not os.path.exists('/.dockerenv') and 'env' not in globals():
    import subprocess
    cmd = [
        "docker", "exec", "-i", "odoo19-web",
        "odoo", "shell", "-d", "erp_textile", "--stop-after-init"
    ]
    with open(__file__, 'r') as f:
        res = subprocess.run(cmd, stdin=f)
    sys.exit(res.returncode)

import time
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare

if 'env' not in globals():
    import odoo
    from odoo.modules.registry import Registry
    from odoo import api, SUPERUSER_ID
    odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'erp_textile'])
    registry = Registry('erp_textile')
    _cr = registry.cursor()
    env = api.Environment(_cr, SUPERUSER_ID, {})
    is_standalone = True
else:
    is_standalone = False

print("==================================================")
print("STARTING TEXTILE ERP MVP END-TO-END TEST (32 STEPS)")
print("==================================================")

# Step 1: Create Customer
print("\n[Step 1/32] Creating Customer...")
customer = env['res.partner'].create({
    'name': 'PT ABC Garment E2E',
    'is_company': True,
})
assert customer.id, "Customer creation failed"
print(f"PASS: Customer created: {customer.name} (ID: {customer.id})")

# Step 2: Create Supplier
print("\n[Step 2/32] Creating Supplier...")
supplier = env['res.partner'].create({
    'name': 'PT Supplier Yarn E2E',
    'is_company': True,
})
assert supplier.id, "Supplier creation failed"
print(f"PASS: Supplier created: {supplier.name} (ID: {supplier.id})")

# Step 3: Create Yarn Product
print("\n[Step 3/32] Creating Yarn Product...")
uom_kg = env.ref('uom.product_uom_kgm')
yarn = env['product.product'].create({
    'name': 'Yarn Polyester 150D E2E',
    'is_storable': True,
    'is_textile_product': True,
    'textile_type': 'raw_material',
    'material': 'Polyester',
    'uom_id': uom_kg.id,
    'tracking': 'lot',
})
assert yarn.id and yarn.is_textile_product and yarn.tracking == 'lot', "Yarn product creation failed"
print(f"PASS: Yarn product created: {yarn.name} (UoM: {yarn.uom_id.name}, Tracking: {yarn.tracking})")

# Step 4: Create Fabric Product
print("\n[Step 4/32] Creating Fabric Product...")
uom_meter = env.ref('uom.product_uom_meter')
fabric = env['product.product'].create({
    'name': 'Polyester Grey Fabric E2E',
    'is_storable': True,
    'is_textile_product': True,
    'textile_type': 'fabric',
    'fabric_type': 'woven',
    'material': 'Polyester',
    'composition': '100% PES',
    'color': 'Grey',
    'width_cm': 150.0,
    'gsm': 120.0,
    'uom_id': uom_meter.id,
    'tracking': 'lot',
})
assert fabric.id and fabric.is_textile_product and fabric.tracking == 'lot', "Fabric product creation failed"
print(f"PASS: Fabric product created: {fabric.name} (UoM: {fabric.uom_id.name}, Tracking: {fabric.tracking})")

# Step 5: Receive Yarn Lot
print("\n[Step 5/32] Receiving Yarn Lot...")
wh_stock_loc = env.ref('stock.stock_location_stock')
supplier_loc = env.ref('stock.stock_location_suppliers')
picking_type_in = env['stock.picking.type'].search([('code', '=', 'incoming')], limit=1)

yarn_lot = env['stock.lot'].create({
    'name': f"YARN-LOT-E2E-{int(time.time())}",
    'product_id': yarn.id,
})

receipt = env['stock.picking'].create({
    'partner_id': supplier.id,
    'picking_type_id': picking_type_in.id,
    'location_id': supplier_loc.id,
    'location_dest_id': wh_stock_loc.id,
    'move_ids': [(0, 0, {
        'description_picking': f"Receive {yarn.name}",
        'product_id': yarn.id,
        'product_uom': uom_kg.id,
        'product_uom_qty': 300.0,
        'location_id': supplier_loc.id,
        'location_dest_id': wh_stock_loc.id,
        'picked': True,
        'move_line_ids': [(0, 0, {
            'product_id': yarn.id,
            'product_uom_id': uom_kg.id,
            'location_id': supplier_loc.id,
            'location_dest_id': wh_stock_loc.id,
            'lot_id': yarn_lot.id,
            'quantity': 300.0,
            'picked': True,
        })],
    })],
})
receipt.action_confirm()
for move in receipt.move_ids:
    move.move_line_ids.picking_id = receipt.id
receipt.button_validate()
assert receipt.state == 'done', "Receipt validation failed"
print(f"PASS: Received 300 kg of {yarn.name} with Lot {yarn_lot.name} into {wh_stock_loc.name} (Receipt: {receipt.name})")

# Step 6: Create Sales Order for 1,000 m
print("\n[Step 6/32] Creating Sales Order for 1,000 m...")
so = env['sale.order'].create({
    'partner_id': customer.id,
    'order_line': [(0, 0, {
        'product_id': fabric.id,
        'product_uom_qty': 1000.0,
        'product_uom_id': uom_meter.id,
        'price_unit': 25000.0,
    })],
})
so.action_confirm()
assert so.state == 'sale', "Sales Order confirmation failed"
assert so.picking_ids, "Delivery order was not created from SO"
delivery_picking = so.picking_ids[0]
print(f"PASS: Sales Order {so.name} confirmed for 1,000 m. Delivery order created: {delivery_picking.name}")

# Step 7: Create Manufacturing Order
print("\n[Step 7/32] Creating Manufacturing Order for 1,000 m...")
shift_a = env['textile.shift'].search([('code', '=', 'SHIFT-A')], limit=1)
bom = env['mrp.bom'].create({
    'product_tmpl_id': fabric.product_tmpl_id.id,
    'product_qty': 1.0,
    'product_uom_id': uom_meter.id,
    'bom_line_ids': [(0, 0, {
        'product_id': yarn.id,
        'product_qty': 0.20,
        'product_uom_id': uom_kg.id,
    })],
})
mo = env['mrp.production'].create({
    'product_id': fabric.id,
    'product_qty': 1000.0,
    'product_uom_id': uom_meter.id,
    'bom_id': bom.id,
    'textile_shift_id': shift_a.id if shift_a else False,
})
mo.action_confirm()
assert mo.state == 'confirmed', "MO confirmation failed"
assert mo.location_dest_id.name == 'QC-Hold', f"MO destination location should be QC-Hold, got {mo.location_dest_id.name}"
print(f"PASS: Manufacturing Order {mo.name} created and confirmed. Dest location: {mo.location_dest_id.name}")

# Step 8: Consume yarn
print("\n[Step 8/32] Consuming yarn lot...")
raw_move = mo.move_raw_ids.filtered(lambda m: m.product_id == yarn)
assert raw_move, "Raw yarn move not found on MO"
raw_move.move_line_ids.unlink()
env['stock.move.line'].create({
    'move_id': raw_move.id,
    'production_id': mo.id,
    'product_id': yarn.id,
    'product_uom_id': uom_kg.id,
    'location_id': wh_stock_loc.id,
    'location_dest_id': mo.production_location_id.id,
    'lot_id': yarn_lot.id,
    'quantity': 200.0,
    'picked': True,
})
raw_move.picked = True
print(f"PASS: Consumed 200.0 kg of {yarn.name} (Lot: {yarn_lot.name})")

# Step 9: Register multiple rolls totaling 850 m
print("\n[Step 9/32] Registering multiple rolls totaling 850 m...")
roll_specs = [
    (100.0, 15.0),
    (120.0, 18.0),
    (110.0, 16.5),
    (100.0, 15.0),
    (105.0, 15.75),
    (95.0, 14.25),
    (110.0, 16.5),
    (110.0, 16.5),
]
wizard = env['textile.register.rolls.wizard'].create({
    'production_id': mo.id,
    'production_loss_m': 150.0,
    'line_ids': [(0, 0, {'length_m': l, 'weight_kg': w}) for l, w in roll_specs],
})
wizard.action_register_rolls()
assert len(mo.roll_ids) == 8, f"Expected 8 rolls, got {len(mo.roll_ids)}"
assert float_compare(mo.good_output_m, 850.0, precision_rounding=0.01) == 0, f"Expected 850m, got {mo.good_output_m}"
print(f"PASS: Registered 8 rolls totaling {mo.good_output_m} m: {[r.name for r in mo.roll_ids]}")

# Step 10: Record production loss = 150 m
print("\n[Step 10/32] Verifying production loss = 150 m and balance invariant...")
assert float_compare(mo.production_loss_m, 150.0, precision_rounding=0.01) == 0, "Production loss should be 150.0 m"
total_accounted = mo.good_output_m + mo.production_loss_m
assert float_compare(total_accounted, mo.product_qty, precision_rounding=0.01) == 0, "Balance invariant failed"
print(f"PASS: Good ({mo.good_output_m}m) + Loss ({mo.production_loss_m}m) = Planned ({mo.product_qty}m)")

# Step 11: Complete production
print("\n[Step 11/32] Completing production...")
mo.button_mark_done()
assert mo.state == 'done', f"Expected MO state 'done', got {mo.state}"
print(f"PASS: MO {mo.name} completed successfully (state: {mo.state})")

# Step 12: Verify rolls are in QC-Hold
print("\n[Step 12/32] Verifying all 8 rolls are in QC-Hold with 'pending' status...")
env.invalidate_all()
qc_hold_loc = env['stock.location'].search([('name', '=', 'QC-Hold'), ('usage', '=', 'internal')], limit=1)
for roll in mo.roll_ids:
    assert roll.qc_state == 'pending', f"Roll {roll.name} qc_state is {roll.qc_state}, expected pending"
    assert roll.current_location_id.id == qc_hold_loc.id, f"Roll {roll.name} in {roll.current_location_id.name}, expected QC-Hold"
print(f"PASS: All {len(mo.roll_ids)} rolls are in QC-Hold with qc_state = pending")

# Step 13: Inspect rolls
print("\n[Step 13/32] Creating inspections for rolls...")
rolls = mo.roll_ids.sorted('id')
inspections = []
for i, roll in enumerate(rolls):
    insp = env['textile.inspection'].create({
        'roll_id': roll.id,
        'grade': 'A' if i < 4 else ('B' if i < 6 else 'C'),
        'actual_width_cm': 150.0,
        'actual_gsm': 120.0,
        'notes': f"E2E inspection for roll {roll.name}",
    })
    inspections.append(insp)
print(f"PASS: Created {len(inspections)} inspection records")

# Step 14: PASS selected rolls
print("\n[Step 14/32] Executing QC PASS for rolls 1 to 6...")
pass_rolls = rolls[:6]
for i in range(6):
    inspections[i].action_pass()
    assert pass_rolls[i].qc_state == 'passed', f"Roll {pass_rolls[i].name} should be passed"
print(f"PASS: Rolls 1 to 6 successfully passed QC: {[r.name for r in pass_rolls]}")

# Step 15: REWORK one roll
print("\n[Step 15/32] Executing QC REWORK for roll 7...")
rework_roll = rolls[6]
crease_defect = env['textile.defect.type'].search([('code', '=', 'CREASE')], limit=1)
env['textile.defect.line'].create({
    'inspection_id': inspections[6].id,
    'defect_type_id': crease_defect.id if crease_defect else False,
    'defect_count': 2,
    'note': 'Crease marks found along edges',
})
inspections[6].action_rework()
assert rework_roll.qc_state == 'rework', f"Expected rework, got {rework_roll.qc_state}"
print(f"PASS: Roll 7 ({rework_roll.name}) marked as REWORK")

# Step 16: REJECT one roll
print("\n[Step 16/32] Executing QC REJECT for roll 8...")
reject_roll = rolls[7]
hole_defect = env['textile.defect.type'].search([('code', '=', 'HOLE')], limit=1)
env['textile.defect.line'].create({
    'inspection_id': inspections[7].id,
    'defect_type_id': hole_defect.id if hole_defect else False,
    'defect_count': 3,
    'note': 'Holes detected in fabric body',
})
inspections[7].action_reject()
assert reject_roll.qc_state == 'rejected', f"Expected rejected, got {reject_roll.qc_state}"
print(f"PASS: Roll 8 ({reject_roll.name}) marked as REJECTED")

# Step 17: Verify PASS rolls in Stock
print("\n[Step 17/32] Verifying PASS rolls in WH/Stock...")
env.invalidate_all()
stock_loc = env.ref('stock.stock_location_stock')
for roll in pass_rolls:
    assert roll.current_location_id.id == stock_loc.id, f"Roll {roll.name} in {roll.current_location_id.name}, expected Stock"
print(f"PASS: All 6 PASS rolls are physically in {stock_loc.name}")

# Step 18: Verify REWORK roll in Rework
print("\n[Step 18/32] Verifying REWORK roll in WH/Rework...")
rework_loc = env['stock.location'].search([('name', '=', 'Rework'), ('usage', '=', 'internal')], limit=1)
assert rework_roll.current_location_id.id == rework_loc.id, f"Roll {rework_roll.name} in {rework_roll.current_location_id.name}, expected Rework"
print(f"PASS: Roll {rework_roll.name} is physically in {rework_loc.name}")

# Step 19: Verify REJECT roll in Scrap
print("\n[Step 19/32] Verifying REJECT roll in WH/Scrap...")
scrap_loc = env['stock.location'].search([('name', '=', 'Scrap'), ('usage', '=', 'inventory')], limit=1)
assert reject_roll.current_location_id.id == scrap_loc.id, f"Roll {reject_roll.name} in {reject_roll.current_location_id.name}, expected Scrap"
print(f"PASS: Roll {reject_roll.name} is physically in {scrap_loc.name}")

# Step 20: Attempt delivery of REWORK roll
print("\n[Step 20/32] Testing Delivery Quality Gate: Attempting delivery of REWORK roll...")
customer_loc = env.ref('stock.stock_location_customers')
picking_type_out = env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)

rework_delivery = env['stock.picking'].create({
    'partner_id': customer.id,
    'picking_type_id': picking_type_out.id,
    'location_id': stock_loc.id,
    'location_dest_id': customer_loc.id,
    'move_ids': [(0, 0, {
        'description_picking': f"Attempt delivery {rework_roll.name}",
        'product_id': fabric.id,
        'product_uom': uom_meter.id,
        'product_uom_qty': rework_roll.length_m,
        'location_id': stock_loc.id,
        'location_dest_id': customer_loc.id,
        'picked': True,
        'move_line_ids': [(0, 0, {
            'product_id': fabric.id,
            'product_uom_id': uom_meter.id,
            'location_id': stock_loc.id,
            'location_dest_id': customer_loc.id,
            'lot_id': rework_roll.lot_id.id,
            'quantity': rework_roll.length_m,
            'picked': True,
        })],
    })],
})
rework_delivery.action_confirm()
for move in rework_delivery.move_ids:
    move.move_line_ids.picking_id = rework_delivery.id

# Step 21: Expected: BLOCK
print("\n[Step 21/32] Verifying delivery of REWORK roll is BLOCKED...")
failed_as_expected = False
try:
    rework_delivery.button_validate()
except UserError as e:
    failed_as_expected = True
    assert "has not passed quality inspection" in str(e) and "REWORK" in str(e), f"Unexpected error message: {e}"
    print(f"PASS: REWORK delivery blocked as expected with message:\n{e}")
assert failed_as_expected, "CRITICAL ERROR: Delivering REWORK roll did not fail!"

# Step 22: Attempt delivery of REJECT roll
print("\n[Step 22/32] Testing Delivery Quality Gate: Attempting delivery of REJECT roll...")
reject_delivery = env['stock.picking'].create({
    'partner_id': customer.id,
    'picking_type_id': picking_type_out.id,
    'location_id': stock_loc.id,
    'location_dest_id': customer_loc.id,
    'move_ids': [(0, 0, {
        'description_picking': f"Attempt delivery {reject_roll.name}",
        'product_id': fabric.id,
        'product_uom': uom_meter.id,
        'product_uom_qty': reject_roll.length_m,
        'location_id': stock_loc.id,
        'location_dest_id': customer_loc.id,
        'picked': True,
        'move_line_ids': [(0, 0, {
            'product_id': fabric.id,
            'product_uom_id': uom_meter.id,
            'location_id': stock_loc.id,
            'location_dest_id': customer_loc.id,
            'lot_id': reject_roll.lot_id.id,
            'quantity': reject_roll.length_m,
            'picked': True,
        })],
    })],
})
reject_delivery.action_confirm()
for move in reject_delivery.move_ids:
    move.move_line_ids.picking_id = reject_delivery.id

# Step 23: Expected: BLOCK
print("\n[Step 23/32] Verifying delivery of REJECT roll is BLOCKED...")
failed_as_expected = False
try:
    reject_delivery.button_validate()
except UserError as e:
    failed_as_expected = True
    assert "has not passed quality inspection" in str(e) and "REJECTED" in str(e), f"Unexpected error message: {e}"
    print(f"PASS: REJECT delivery blocked as expected with message:\n{e}")
assert failed_as_expected, "CRITICAL ERROR: Delivering REJECTED roll did not fail!"

# Step 24: Attempt partial delivery of PASS roll
print("\n[Step 24/32] Testing Whole-Roll Delivery Gate: Attempting partial delivery (50 m of 100 m roll)...")
pass_roll_1 = pass_rolls[0]
partial_delivery = env['stock.picking'].create({
    'partner_id': customer.id,
    'picking_type_id': picking_type_out.id,
    'location_id': stock_loc.id,
    'location_dest_id': customer_loc.id,
    'move_ids': [(0, 0, {
        'description_picking': f"Partial delivery {pass_roll_1.name}",
        'product_id': fabric.id,
        'product_uom': uom_meter.id,
        'product_uom_qty': 50.0,
        'location_id': stock_loc.id,
        'location_dest_id': customer_loc.id,
        'picked': True,
        'move_line_ids': [(0, 0, {
            'product_id': fabric.id,
            'product_uom_id': uom_meter.id,
            'location_id': stock_loc.id,
            'location_dest_id': customer_loc.id,
            'lot_id': pass_roll_1.lot_id.id,
            'quantity': 50.0,
            'picked': True,
        })],
    })],
})
partial_delivery.action_confirm()
for move in partial_delivery.move_ids:
    move.move_line_ids.picking_id = partial_delivery.id

# Step 25: Expected: BLOCK
print("\n[Step 25/32] Verifying partial roll delivery is BLOCKED...")
failed_as_expected = False
try:
    partial_delivery.button_validate()
except UserError as e:
    failed_as_expected = True
    assert "Partial roll delivery is not supported" in str(e), f"Unexpected error message: {e}"
    print(f"PASS: Partial delivery blocked as expected with message:\n{e}")
assert failed_as_expected, "CRITICAL ERROR: Partial roll delivery did not fail!"

# Step 26: Deliver full PASS roll
print("\n[Step 26/32] Delivering full PASS roll (Roll 1, 100.0 m)...")
valid_delivery = env['stock.picking'].create({
    'partner_id': customer.id,
    'picking_type_id': picking_type_out.id,
    'location_id': stock_loc.id,
    'location_dest_id': customer_loc.id,
    'move_ids': [(0, 0, {
        'description_picking': f"Deliver full {pass_roll_1.name}",
        'product_id': fabric.id,
        'product_uom': uom_meter.id,
        'product_uom_qty': pass_roll_1.length_m,
        'location_id': stock_loc.id,
        'location_dest_id': customer_loc.id,
        'picked': True,
        'move_line_ids': [(0, 0, {
            'product_id': fabric.id,
            'product_uom_id': uom_meter.id,
            'location_id': stock_loc.id,
            'location_dest_id': customer_loc.id,
            'lot_id': pass_roll_1.lot_id.id,
            'quantity': pass_roll_1.length_m,
            'picked': True,
        })],
    })],
})
valid_delivery.action_confirm()
for move in valid_delivery.move_ids:
    move.move_line_ids.picking_id = valid_delivery.id
valid_delivery.button_validate()

# Step 27: Expected: SUCCESS
print("\n[Step 27/32] Verifying valid delivery status is 'done'...")
assert valid_delivery.state == 'done', f"Delivery failed, state is {valid_delivery.state}"
print(f"PASS: Valid delivery of PASS roll {pass_roll_1.name} succeeded! Picking state: {valid_delivery.state}")

# Step 28: Open delivered roll
print("\n[Step 28/32] Inspecting/opening delivered roll record...")
roll_to_check = env['textile.roll'].browse(pass_roll_1.id)
assert roll_to_check.exists(), "Roll record does not exist"
print(f"PASS: Opened Roll {roll_to_check.name} (Lot: {roll_to_check.lot_id.name}, Length: {roll_to_check.length_m} m)")

# Step 29: Trace to MO
print("\n[Step 29/32] Verifying Manufacturing Order backward traceability...")
assert roll_to_check.production_id.id == mo.id, f"Expected MO {mo.name}, got {roll_to_check.production_id.name}"
assert roll_to_check.production_id.state == 'done', "MO is not in done state"
print(f"PASS: Roll traced backward to MO {roll_to_check.production_id.name} (Shift: {roll_to_check.production_id.textile_shift_id.name})")

# Step 30: Trace to input lot
print("\n[Step 30/32] Verifying raw input lot traceability...")
consumed_move_lines = roll_to_check.production_id.move_raw_ids.move_line_ids
consumed_lots = consumed_move_lines.mapped('lot_id')
assert yarn_lot in consumed_lots, f"Expected input yarn lot {yarn_lot.name} in consumed lots: {consumed_lots.mapped('name')}"
print(f"PASS: Traced to consumed raw yarn lot: {consumed_lots.mapped('name')}")

# Step 31: Trace to QC history
print("\n[Step 31/32] Verifying QC inspection history...")
inspections_for_roll = roll_to_check.inspection_ids
assert len(inspections_for_roll) >= 1, "No inspection records found for roll"
assert inspections_for_roll[0].result == 'passed', f"Expected passed result, got {inspections_for_roll[0].result}"
print(f"PASS: QC Inspection history verified: Ref={inspections_for_roll[0].name}, Result={inspections_for_roll[0].result}, Grade={inspections_for_roll[0].grade}")

# Step 32: Trace to stock moves
print("\n[Step 32/32] Verifying complete stock moves traceability for roll lot...")
stock_move_lines = env['stock.move.line'].search([
    ('lot_id', '=', roll_to_check.lot_id.id),
    ('state', '=', 'done')
], order='id asc')
print("Stock Movement History for Lot " + roll_to_check.lot_id.name + ":")
for ml in stock_move_lines:
    print(f"  - Move {ml.move_id.id}: {ml.location_id.complete_name} -> {ml.location_dest_id.complete_name} ({ml.quantity} {ml.product_uom_id.name})")

locations_dest = [ml.location_dest_id.name for ml in stock_move_lines]
assert 'QC-Hold' in locations_dest, "Missing Production -> QC-Hold move"
assert 'Stock' in locations_dest, "Missing QC-Hold -> Stock move"
assert 'Customers' in locations_dest, "Missing Stock -> Customers move"
print("PASS: Verified complete movement lifecycle: Production -> QC-Hold -> Stock -> Customers")

print("\n==================================================")
print("ALL 32 END-TO-END STEPS PASSED SUCCESSFULLY!")
print("==================================================")

if is_standalone:
    env.cr.commit()
    env.cr.close()


