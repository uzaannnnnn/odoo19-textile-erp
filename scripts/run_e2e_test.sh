#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Running Textile ERP E2E tests inside odoo19-web container..."
docker exec -i odoo19-web odoo shell -d erp_textile --stop-after-init < "${DIR}/addons/run_e2e_test.py"
