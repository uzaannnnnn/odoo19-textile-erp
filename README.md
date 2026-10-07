# Textile Manufacturing ERP

A comprehensive Textile Manufacturing ERP MVP built on **Odoo 19 Community**, containerized with **Docker** and **Docker Compose**, and powered by **PostgreSQL 16**.

---

## Overview

This project is an academic ERP project implemented as a practical **Textile Manufacturing ERP MVP** using Odoo 19 Community. The system extends standard Odoo ERP functionality with custom textile-specific workflows for fabric roll management, production tracking, quality control, inventory traceability, and delivery validation.

Standard ERP systems treat fabrics as standard bulk commodities tracked purely by aggregate meters or kilograms. In real-world textile mills and finishing plants, fabric is produced, inspected, warehoused, and shipped as **discrete physical rolls**. This system bridges the gap between bulk accounting and physical roll-level operational reality.

---

## Business Problem

Textile manufacturing and finishing operations face distinct operational challenges that generic ERP configurations fail to address cleanly:

1. **Discrete Roll vs. Bulk Inventory Disconnect**: While sales and general accounting operate in continuous linear meters, physical inventory sits on warehouse racks as discrete rolls with varying individual lengths and weights.
2. **Quality Isolation**: Defective or off-spec fabric rolls must be immediately quarantined upon production completion. Shipping an uninspected or rejected roll to a garment manufacturer results in catastrophic downstream fabric wastage and chargebacks.
3. **Traceability Gaps**: When a garment factory discovers yarn or weaving defects, the textile mill must rapidly trace the defect back to the exact manufacturing order, production shift, operator, and raw yarn lot.
4. **Partial Delivery Hazards**: Standard inventory pickings allow arbitrary partial quantities. In textile dispatch, shipping a partial fraction of a physical roll without physically cutting and re-registering it causes severe stock phantom discrepancies.

---

## Features

- **Textile Product Master**: Extended product specifications including fabric width (cm), surface density (GSM), yarn composition, material classification, and fabric type.
- **Physical Fabric Roll Tracking (`textile.roll`)**: Each produced roll receives an immutable identifier with recorded length (meters), gross/tare/net weight (kg), production timestamp, shift, and assigned operator.
- **1 Roll = 1 Unique Stock Lot**: Every physical roll is linked 1:1 to an Odoo `stock.lot` with strict uniqueness validation.
- **Manufacturing Roll Registration**: Dedicated wizard within Manufacturing Orders to register multiple output rolls and automatically validate mass/length balance invariants (`Actual Good Output + Production Scrap = Planned Quantity`).
- **Four-Location Quality Workflow**: Automatic routing to dedicated internal locations:
  - `WH/QC-Hold` (Immediate post-production quarantine)
  - `WH/Stock` (QC PASS — available for customer reservation and delivery)
  - `WH/Rework` (QC REWORK — quarantined for reprocessing/scouring)
  - `WH/Scrap` (QC REJECT — isolated from inventory)
- **Strict Delivery Quality Gate**: Automated server-side validation on outgoing delivery orders (`stock.picking`) preventing any roll from being validated unless its QC status is verified as `PASS`.
- **Whole-Roll Delivery Enforcement**: Strict delivery line validation blocking partial roll quantities without explicit physical splitting.
- **Bi-directional Traceability**: Instant end-to-end audit trail linking Customer Deliveries $\leftrightarrow$ Finished Fabric Rolls $\leftrightarrow$ Quality Inspection History $\leftrightarrow$ Manufacturing Orders $\leftrightarrow$ Production Shifts $\leftrightarrow$ Consumed Raw Yarn Lots.

---

## ERP Workflow

The core operational lifecycle follows a linear, quality-gated progression:

```text
Sales Order
    ↓
Manufacturing Order (MRP)
    ↓
Fabric Roll Registration (Wizard)
    ↓
Quality Inspection (WH/QC-Hold)
    ↓
    ├── [PASS]   ──> Relocated to WH/Stock    ──> Reserved for Delivery Order
    ├── [REWORK] ──> Relocated to WH/Rework   ──> Quarantined from Delivery
    └── [REJECT] ──> Relocated to WH/Scrap    ──> Quarantined from Delivery
    ↓
Delivery Validation (Server-side Quality & Whole-Roll Gates)
    ↓
Customer Shipment & Invoice
```

### Core Invariants:
- **1 physical roll = 1 unique stock lot**.
- **Finished fabric inventory is tracked in meters** (primary UoM), while roll weight (kg) serves as supplementary operational data.
- **No delivery without passing QC**: Transfers containing rolls in `pending`, `rework`, or `rejected` states are aborted with descriptive error dialogs.

---

## Architecture

The system extends Odoo 19 Community Edition through a modular four-tier addon architecture mounted into the standard container runtime:

```text
                           ODOO 19 COMMUNITY
                                   │
       ┌───────────────────────────┼───────────────────────────┐
       │                           │                           │
     SALES                      PURCHASE                   INVENTORY
  (sale_management)             (purchase)                  (stock)
       │                           │                           │
       └───────────────────────────┼───────────────────────────┘
                                   │
                                  MRP
                            (mrp production)
                                   │
                    ┌──────────────┴──────────────┐
                    │     TEXTILE ERP ADDONS      │
                    └──────────────┬──────────────┘
                                   │
         ┌──────────────────┬──────┴───────────┬──────────────────┐
         │                  │                  │                  │
    textile_core    textile_inventory     textile_mrp      textile_quality
  (Product Master)    (Roll Tracking)     (Roll Wizard)     (QC Gate & Insp)
         │                  │                  │                  │
         └──────────────────┼──────────────────┴──────────────────┘
                            │
                     TEXTILE WORKFLOW
                 ┌──────────┼──────────┐
                 │          │          │
             ROLL MGMT   QC GATES   TRACEABILITY
                 │          │          │
                 └──────────┼──────────┘
                            ▼
                    DELIVERY VALIDATION
```

---

## Custom Odoo Modules

The project consists of 4 focused, decoupled custom addons located in [`addons/`](file:///Users/zannho/odoo19/addons):

### 1. `textile_core`
- **Purpose**: Defines textile product master data and shared configuration.
- **Main Models**:
  - `product.template`: Extended with technical attributes: `width_cm`, `gsm`, `composition`, `textile_type` (Raw / Greige / Finished), `fabric_type` (Woven / Knit / Non-woven), `raw_material_type`.
- **Main Functionality**: Shared Textile security groups (`group_textile_user`, `group_textile_manager`), root navigation menus, and foundational UoM categories.
- **Dependencies**: `base`, `product`, `uom`.

### 2. `textile_inventory`
- **Purpose**: Physical fabric roll management, unique lot mapping, and warehouse location management.
- **Main Models**:
  - `textile.roll`: Master entity for discrete fabric rolls tracking length, gross/tare/net weight, operational status, and automated sequence `ROLL-YYYY-XXXXX`.
  - `stock.lot`: Extended with bi-directional `roll_id` relation enforcing 1 roll = 1 lot.
- **Main Functionality**: Dedicated warehouse stock locations (`WH/QC-Hold`, `WH/Rework`, `WH/Scrap`), roll deletion guards, identity immutability constraints.
- **Dependencies**: `textile_core`, `stock`, `mrp`.

### 3. `textile_mrp`
- **Purpose**: Textile manufacturing extensions, shift management, and roll registration during production.
- **Main Models**:
  - `mrp.production`: Extended with `shift_id`, `operator_name`, roll output lines, roll metrics, and completion guards.
  - `textile.shift`: Production shifts (Shift A, Shift B, Night Shift) with active schedules.
  - `register.rolls.wizard`: Interactive wizard allowing operators to log produced rolls with individual lengths and weights upon MO completion.
- **Main Functionality**: Balance invariant enforcement (`actual_output_m + production_loss_m == product_qty`), automatic roll and `stock.lot` creation.
- **Dependencies**: `textile_core`, `textile_inventory`, `mrp`.

### 4. `textile_quality`
- **Purpose**: Quality control inspections, defect logging, and automated delivery quality gates.
- **Main Models**:
  - `textile.inspection`: Inspection records with result grading (`passed`, `rework`, `rejected`, `pending`), grade assignment (`A`, `B`, `C`), and inspector metadata.
  - `textile.defect.type`: Configurable textile defect library (e.g., Oil Stains, Broken Ends, Weft Slub, Selvedge Flaw, Uneven Dyeing).
  - `textile.defect.line`: Specific defect observations per inspection with meter point markers and severity levels.
  - `stock.picking`: Overridden `button_validate()` enforcing the strict Delivery Quality Gate and whole-roll integrity.
- **Main Functionality**: Automatic stock relocation on inspection completion (moves roll lot from `WH/QC-Hold` to `WH/Stock`, `WH/Rework`, or `WH/Scrap`); blocks validation of deliveries containing unpassed or partially consumed rolls.
- **Dependencies**: `textile_core`, `textile_inventory`, `stock`.

---

## Technology Stack

- **ERP Core**: [Odoo 19 Community Edition](https://www.odoo.com)
- **Runtime Language**: Python 3.12
- **Database Engine**: PostgreSQL 16
- **Containerization**: Docker & Docker Compose
- **ORM & Framework**: Odoo ORM (Models, Fields, API decorators)
- **View Architecture**: Odoo Python / XML Views (Form, List, Search, Kanban)
- **Reporting Engine**: QWeb / Wkhtmltopdf
- **Security**: Odoo Record Rules & Access Control Lists (`ir.model.access.csv`)
- **Version Control**: Git

---

## Docker Environment

The project runs using standard Docker Compose orchestration:

```yaml
services:
  db:
    image: postgres:16
    container_name: odoo19-db
    environment:
      POSTGRES_DB: postgres
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - odoo-db-data:/var/lib/postgresql/data/pgdata
    restart: unless-stopped

  web:
    image: odoo:19.0
    container_name: odoo19-web
    depends_on:
      - db
    ports:
      - "8069:8069"
    environment:
      HOST: db
      USER: odoo
      PASSWORD: odoo
    volumes:
      - odoo-web-data:/var/lib/odoo
      - ./addons:/mnt/extra-addons
      - ./config:/etc/odoo
    restart: unless-stopped

volumes:
  odoo-db-data:
  odoo-web-data:
```

- Custom addons in [`./addons`](file:///Users/zannho/odoo19/addons) are mounted to `/mnt/extra-addons` inside the container.
- Configuration in [`./config`](file:///Users/zannho/odoo19/config) is mounted to `/etc/odoo` inside the container.

---

## Installation

### Prerequisites
- Docker Engine $\ge$ 24.0
- Docker Compose $\ge$ 2.20
- Git

### 1. Clone the Repository
```bash
git clone <repository-url>
cd odoo19-textile-erp
```

### 2. Configure Environment
Copy the example configuration file:
```bash
cp config/odoo.conf.example config/odoo.conf
```
*(Adjust database credentials or admin master password if running in non-default environments).*

### 3. Launch Docker Services
```bash
docker compose up -d
```

### 4. Verify Container Status
```bash
docker compose ps
```
Both `odoo19-web` and `odoo19-db` should report state `Up` (healthy).

### 5. Access Odoo
Open your browser and navigate to:
```text
http://localhost:8069
```
Create a new database (e.g. `erp_textile`) or log in with your configured administrator credentials.

### 6. Install Modules
In the Odoo Web UI:
1. Activate **Developer Mode** (Settings $\rightarrow$ Activate Developer Mode).
2. Go to **Apps** $\rightarrow$ **Update Apps List**.
3. Search for `textile_core` and click **Activate**.
4. The dependent modules (`textile_inventory`, `textile_mrp`, `textile_quality`) can be installed individually or together.

---

## Configuration

Standard configuration file located at [`config/odoo.conf`](file:///Users/zannho/odoo19/config/odoo.conf):

```ini
[options]
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons
data_dir = /var/lib/odoo
admin_passwd = CHANGE_ME
list_db = True
proxy_mode = True
db_host = db
db_port = 5432
db_user = odoo
db_password = CHANGE_ME
http_interface = 0.0.0.0
```

### Safe Development Commands
```bash
# Start background services
docker compose up -d

# Stop services safely
docker compose down

# Restart application
docker compose restart

# View web container logs
docker compose logs -f odoo19-web

# View database logs
docker compose logs -f odoo19-db

# Check running services
docker compose ps
```

---

## Demo Workflow

The standard operational demonstration covers the entire manufacturing lifecycle:

### Step 1: Master Data Setup
- Create raw yarn product: *Yarn Polyester 150D* (UoM: kg, Tracking: By Lots).
- Create finished fabric product: *Polyester Grey Fabric* (UoM: m, Tracking: By Unique Lots, Width: 150 cm, GSM: 180).

### Step 2: Inbound Raw Material
- Receive yarn into `WH/Stock` with vendor lot `YARN-LOT-001`.

### Step 3: Manufacturing & Roll Output
- Create Manufacturing Order for 1,000 m of finished fabric consuming 200 kg of yarn lot.
- Launch the **Register Rolls Wizard**:
  - Register 8 discrete rolls (e.g., 6 rolls $\times$ 125 m, 2 rolls $\times$ 50 m) = 850 m good output.
  - Record 150 m scrap/loss (Balance check: $850\text{ m} + 150\text{ m} = 1,000\text{ m}$).
- Mark MO as Done. All 8 rolls are automatically assigned lots and moved into `WH/QC-Hold` in `pending` quality state.

### Step 4: Quality Inspection
- Open Quality Inspections for the produced rolls:
  - Rolls 1 to 6: **PASS** $\rightarrow$ Automatically relocated to `WH/Stock`.
  - Roll 7: **REWORK** (e.g. slight oil stain) $\rightarrow$ Relocated to `WH/Rework`.
  - Roll 8: **REJECT** (e.g. major tear) $\rightarrow$ Relocated to `WH/Scrap`.

### Step 5: Delivery & Gate Enforcement
- Create Delivery Order for a customer:
  - Attempting to pick Roll 7 (REWORK) $\rightarrow$ **Validation BLOCKED** by quality gate.
  - Attempting to pick Roll 8 (REJECT) $\rightarrow$ **Validation BLOCKED** by quality gate.
  - Attempting to pick 50 m from a 100 m roll $\rightarrow$ **Validation BLOCKED** by whole-roll gate.
  - Picking Roll 1 (PASS, 100 m) $\rightarrow$ **Validation SUCCEEDS** and inventory moves to `Partner Locations/Customers`.

---

## Traceability

The system provides instant bi-directional traceability at the physical roll level:

```text
[Customer Delivery WH/OUT/00103]
               ▲
               │ (Lot ROLL-2026-00432)
       [Fabric Roll Record]
       ├── Length: 100.0 m | Weight: 25.4 kg
       ├── QC Inspection: QC-2026-00205 (Result: PASS, Grade: A)
       │         ▲
       │         │
       └── [Manufacturing Order WH/MO/00213]
                 ├── Shift: Shift A | Operator: Budi
                 └── Raw Consumed Lot: YARN-LOT-E2E-1791377207
                           ▲
                           │
                 [Purchase Receipt WH/IN/00015]
```

Every stock movement for the lot is permanently recorded in Odoo stock ledger (`WH/QC-Hold` $\rightarrow$ `WH/Stock` $\rightarrow$ `Customers`).

---

## Testing

The project includes both native Odoo unit test suites and a full 32-step end-to-end integration test runner:

### 1. Odoo Unit Tests (41 Tests)
All 41 native test cases pass across the four custom modules:
- `textile_core` (5 tests): Master data validations, UoM conversions, security access rules.
- `textile_inventory` (23 tests): Roll sequence generation, unique lot constraints, immutability guards, unlink protection, single and batch report rendering.
- `textile_mrp` (8 tests): Wizard inputs, production balance invariants, scrap constraints, shift tracking.
- `textile_quality` (13 tests): QC state transitions, defect line tracking, delivery quality gate validations, whole-roll integrity, reinspection history.

Run unit tests inside the container:
```bash
docker exec odoo19-web odoo --test-enable --test-tags=textile_core,textile_inventory,textile_mrp,textile_quality --stop-after-init -d erp_textile -u textile_core,textile_inventory,textile_mrp,textile_quality --log-level=test --http-port=8070
```

### 2. End-to-End Test Suite (32 Steps)
An automated Python integration suite tests the complete operational lifecycle inside the running container:
```bash
bash scripts/run_e2e_test.sh
```
```text
==================================================
STARTING TEXTILE ERP MVP END-TO-END TEST (32 STEPS)
==================================================
[Step 1/32] Creating Customer...                     PASS
[Step 2/32] Creating Supplier...                     PASS
[Step 3/32] Creating Yarn Product...                 PASS
[Step 4/32] Creating Fabric Product...               PASS
[Step 5/32] Receiving Yarn Lot...                    PASS
[Step 6/32] Creating Sales Order for 1,000 m...      PASS
[Step 7/32] Creating Manufacturing Order...          PASS
[Step 8/32] Consuming yarn lot...                    PASS
[Step 9/32] Registering multiple rolls (850 m)...    PASS
[Step 10/32] Verifying production balance...         PASS
[Step 11/32] Completing production...                PASS
[Step 12/32] Verifying rolls in QC-Hold...           PASS
[Step 13/32] Creating inspections for rolls...       PASS
[Step 14/32] Executing QC PASS for rolls 1-6...      PASS
[Step 15/32] Executing QC REWORK for roll 7...       PASS
[Step 16/32] Executing QC REJECT for roll 8...       PASS
[Step 17/32] Verifying PASS rolls in Stock...        PASS
[Step 18/32] Verifying REWORK roll in Rework...      PASS
[Step 19/32] Verifying REJECT roll in Scrap...       PASS
[Step 20-21] Verifying REWORK delivery BLOCKED...    PASS
[Step 22-23] Verifying REJECT delivery BLOCKED...    PASS
[Step 24-25] Verifying Partial delivery BLOCKED...   PASS
[Step 26-27] Delivering full PASS roll...            PASS
[Step 28/32] Inspecting delivered roll record...     PASS
[Step 29/32] Verifying MO backward traceability...   PASS
[Step 30/32] Verifying raw yarn lot traceability...  PASS
[Step 31/32] Verifying QC inspection history...      PASS
[Step 32/32] Verifying complete stock moves...       PASS
==================================================
ALL 32 END-TO-END STEPS PASSED SUCCESSFULLY!
==================================================
```

---

## Project Scope

### Implemented in MVP:
- [x] Sales Order integration with standard delivery generation.
- [x] Purchase and Goods Receipt for raw yarn with lot tracking.
- [x] Multi-location inventory management (`WH/Stock`, `WH/QC-Hold`, `WH/Rework`, `WH/Scrap`).
- [x] Manufacturing Orders with custom shift and operator tracking.
- [x] Fabric Roll registration wizard generating discrete rolls and 1:1 lots.
- [x] Full production balance invariant validation.
- [x] Quality Control inspection workflows (PASS, REWORK, REJECT).
- [x] Defect classification library and defect observation lines.
- [x] Server-side Delivery Quality Gate blocking non-passed rolls.
- [x] Whole-roll delivery gate preventing partial roll cuts.
- [x] Bi-directional backward and forward traceability.
- [x] Role-based access control (User vs. Manager).
- [x] Docker & Docker Compose development deployment.

---

## Roadmap

The following enterprise textile capabilities are deliberately **out of scope** for this MVP:
- [ ] Dyeing recipe management and color matching lab dip approvals.
- [ ] Textile printing and finishing chemical batch processing.
- [ ] Advanced Finite Capacity Planning (APS) / Gantt scheduling.
- [ ] Overall Equipment Effectiveness (OEE) and loom telemetry.
- [ ] IoT loom sensor integrations and automated cut counters.
- [ ] Native mobile barcode scanning app (WMS).
- [ ] Partial roll cut / split wizard on picking.
- [ ] Advanced multi-currency textile costing and cost accounting absorption.
- [ ] Machine learning defect vision inspection and automated grading.

---

## Project Context

- **Author**: Antigravity / Textile ERP MVP Team
- **Intended Audience**: Open-source Odoo developers, ERP evaluators, and textile manufacturing IT professionals.
- **Academic Disclaimer**: This project is developed as an educational and technical portfolio demonstration of domain-driven ERP architecture on Odoo 19 Community. It is not an official Odoo S.A. product nor a commercial deployment.

---

## Screenshots

<!-- TODO: Add application screenshots showcasing:
1. Textile Product Master Data (product.template)
2. Manufacturing Order with Roll Output (mrp.production)
3. Fabric Roll Master Record (textile.roll)
4. Quality Inspection with Defect Lines (textile.inspection)
5. Delivery Quality Gate Error Dialog (stock.picking)
6. Bi-directional Traceability Graph / Stock Move History
-->
*Screenshots will be uploaded upon live deployment.*

---

## License

This project is licensed under the **GNU Lesser General Public License v3.0 (LGPL-3)** — see the [LICENSE](file:///Users/zannho/odoo19/LICENSE) file for details.
