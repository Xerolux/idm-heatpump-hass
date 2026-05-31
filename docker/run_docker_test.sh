#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Docker Test Script for IDM Heatpump HA Integration
# ============================================================================
# Tests the integration against a real IDM heat pump via Home Assistant
# running in Docker. READ-ONLY - no writes to the heat pump.
#
# Usage:
#   ./run_docker_test.sh              # Full test: start HA, install, verify
#   ./run_docker_test.sh smoke        # Quick smoke test only
#   ./run_docker_test.sh logs         # Show HA logs
#   ./run_docker_test.sh status       # Show container + entity status
#   ./run_docker_test.sh clean        # Remove container + volume
#   ./run_docker_test.sh restart      # Restart container
# ============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IDM_IP="${IDM_IP:-192.168.178.103}"
IDM_PORT="${IDM_PORT:-502}"
IDM_SLAVE_ID="${IDM_SLAVE_ID:-1}"
HA_PORT="${HA_PORT:-8123}"
CONTAINER_NAME="homeassistant-idm-test"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
HA_URL="http://localhost:${HA_PORT}"
MAX_WAIT_SECONDS=180

# Logging
log_info()    { echo -e "${BLUE}[INFO]${NC}    $1"; }
log_success() { echo -e "${GREEN}[OK]${NC}      $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}    $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC}    $1"; }
log_step()    { echo -e "\n${CYAN}>>> $1${NC}"; }

header() {
    echo ""
    echo -e "${CYAN}============================================================${NC}"
    echo -e "${CYAN} $1${NC}"
    echo -e "${CYAN}============================================================${NC}"
}

# ============================================================================
# Prerequisites
# ============================================================================

check_prerequisites() {
    header "CHECKING PREREQUISITES"

    if ! command -v docker &>/dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    log_success "Docker found: $(docker --version)"

    if ! docker info &>/dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    log_success "Docker daemon is running"

    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "docker-compose.yml not found at $COMPOSE_FILE"
        exit 1
    fi

    if [ ! -d "$PROJECT_ROOT/custom_components/heatpump_idm" ]; then
        log_error "Integration source not found at $PROJECT_ROOT/custom_components/heatpump_idm"
        exit 1
    fi
    log_success "Integration source found"

    log_info "IDM Heat Pump: ${IDM_IP}:${IDM_PORT} (slave_id=${IDM_SLAVE_ID})"
}

# ============================================================================
# Container Lifecycle
# ============================================================================

container_exists() {
    docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"
}

container_running() {
    docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"
}

start_container() {
    header "STARTING HOME ASSISTANT CONTAINER"

    if container_running; then
        log_info "Container is already running"
        return 0
    fi

    if container_exists; then
        log_info "Starting existing container..."
        docker compose -f "$COMPOSE_FILE" start
    else
        log_info "Pulling latest Home Assistant image..."
        docker compose -f "$COMPOSE_FILE" pull 2>/dev/null || true

        log_info "Creating and starting container..."
        docker compose -f "$COMPOSE_FILE" up -d
    fi

    log_success "Container started"
}

wait_for_ha() {
    header "WAITING FOR HOME ASSISTANT TO BOOT"

    local elapsed=0
    local interval=5

    while [ $elapsed -lt $MAX_WAIT_SECONDS ]; do
        if curl -sf "${HA_URL}/api/" -o /dev/null 2>/dev/null; then
            log_success "Home Assistant is responding after ${elapsed}s"
            return 0
        fi

        printf "\r${BLUE}[INFO]${NC}    Waiting... %ds / %ds" "$elapsed" "$MAX_WAIT_SECONDS"
        sleep $interval
        elapsed=$((elapsed + interval))
    done

    echo ""
    log_error "Home Assistant did not respond within ${MAX_WAIT_SECONDS}s"
    log_info "Showing last 30 lines of logs:"
    docker logs --tail 30 "$CONTAINER_NAME" 2>&1
    return 1
}

stop_container() {
    header "STOPPING CONTAINER"
    docker compose -f "$COMPOSE_FILE" down 2>/dev/null || true
    log_success "Container stopped"
}

clean_all() {
    header "CLEANING UP"
    docker compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true
    log_success "Container and volume removed"
}

# ============================================================================
# Integration Setup via HA API
# ============================================================================

get_ha_token() {
    # Try to get a long-lived access token from the container
    # HA creates one on first start via onboarding
    HA_TOKEN="${HA_TOKEN:-}"

    if [ -n "$HA_TOKEN" ]; then
        log_info "Using provided HA_TOKEN"
        return 0
    fi

    # Check if onboarding is needed
    local onboard_status
    onboard_status=$(curl -sf -o /dev/null -w "%{http_code}" "${HA_URL}/api/onboarding" 2>/dev/null || echo "000")

    if [ "$onboard_status" = "200" ]; then
        log_info "Running onboarding..."

        # Complete onboarding via API
        local response
        response=$(curl -sf -X POST "${HA_URL}/api/onboarding/users" \
            -H "Content-Type: application/json" \
            -d '{
                "client_id": "idm_test_script",
                "name": "Test User",
                "username": "admin",
                "password": "admin123!",
                "language": "de"
            }' 2>/dev/null || echo "")

        if [ -z "$response" ]; then
            log_warn "Onboarding may have already been completed"
        else
            HA_TOKEN=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('auth_code',''))" 2>/dev/null || echo "")
        fi
    fi

    # If still no token, try to get via websocket or auth flow
    if [ -z "$HA_TOKEN" ]; then
        log_warn "Could not auto-obtain HA token"
        log_info "You may need to create a long-lived access token manually:"
        log_info "  1. Open ${HA_URL} in a browser"
        log_info "  2. Go to Profile > Security > Long-Lived Access Tokens"
        log_info "  3. Create a token and set: export HA_TOKEN=<your_token>"
        log_info ""
        log_info "Continuing with log-based verification only..."
        return 1
    fi

    log_success "HA token obtained"
    return 0
}

install_integration() {
    header "INSTALLING IDM HEATPUMP INTEGRATION"

    if [ -z "${HA_TOKEN:-}" ]; then
        log_warn "No HA token available, skipping API-based setup"
        log_info "The integration files are already mounted into the container"
        log_info "You can add the integration manually via:"
        log_info "  ${HA_URL}/config/integrations/dashboard"
        log_info "  -> Add Integration -> Search 'IDM Heatpump'"
        log_info "  -> Host: ${IDM_IP}, Port: ${IDM_PORT}, Slave ID: ${IDM_SLAVE_ID}"
        return 0
    fi

    local headers=(-H "Authorization: Bearer ${HA_TOKEN}" -H "Content-Type: application/json")

    # Initiate config flow
    log_info "Starting config flow..."
    local flow_id
    flow_id=$(curl -sf -X POST "${HA_URL}/api/config/config_entries/flow" \
        "${headers[@]}" \
        -d "{
            \"handler\": \"heatpump_idm\",
            \"show_advanced_options\": false
        }" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('flow_id',''))" 2>/dev/null || echo "")

    if [ -z "$flow_id" ]; then
        log_warn "Could not initiate config flow (integration may need to be loaded first)"
        log_info "Trying to reload integration..."
        curl -sf -X POST "${HA_URL}/api/services/homeassistant/reload_config_entry" \
            "${headers[@]}" -d '{}' 2>/dev/null || true
        sleep 5

        flow_id=$(curl -sf -X POST "${HA_URL}/api/config/config_entries/flow" \
            "${headers[@]}" \
            -d "{
                \"handler\": \"heatpump_idm\",
                \"show_advanced_options\": false
            }" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('flow_id',''))" 2>/dev/null || echo "")
    fi

    if [ -z "$flow_id" ]; then
        log_error "Config flow failed. Install manually via HA UI."
        return 1
    fi
    log_info "Flow ID: ${flow_id}"

    # Step 1: Provide connection details
    log_info "Submitting connection details..."
    curl -sf -X POST "${HA_URL}/api/config/config_entries/flow/${flow_id}" \
        "${headers[@]}" \
        -d "{
            \"name\": \"IDM Waermepumpe\",
            \"host\": \"${IDM_IP}\",
            \"port\": ${IDM_PORT},
            \"slave_id\": ${IDM_SLAVE_ID}
        }" 2>/dev/null > /dev/null || true

    sleep 2

    # Step 2: Options (use defaults)
    log_info "Submitting options..."
    curl -sf -X POST "${HA_URL}/api/config/config_entries/flow/${flow_id}" \
        "${headers[@]}" \
        -d "{
            \"scan_interval\": 10,
            \"heating_circuits\": [\"a\"],
            \"zone_count\": 0,
            \"hide_unused_registers\": true,
            \"enable_cascade\": false,
            \"technician_codes\": false
        }" 2>/dev/null > /dev/null || true

    sleep 3
    log_success "Config flow submitted"
}

# ============================================================================
# Verification Tests
# ============================================================================

test_integration_in_logs() {
    header "TEST 1: Integration Loaded in HA"

    local logs
    logs=$(docker logs "$CONTAINER_NAME" 2>&1)

    if echo "$logs" | grep -q "Setting up IDM Heatpump"; then
        log_success "Integration setup initiated"
    elif echo "$logs" | grep -q "heatpump_idm"; then
        log_success "Integration referenced in logs"
    else
        log_warn "Integration not found in logs yet"
        log_info "This is normal on first start if HA hasn't loaded custom_components yet"
        return 1
    fi

    if echo "$logs" | grep -q "heatpump_idm.*Connected"; then
        log_success "Modbus connection established"
    fi

    return 0
}

test_no_critical_errors() {
    header "TEST 2: No Critical Errors in Logs"

    local logs
    logs=$(docker logs "$CONTAINER_NAME" 2>&1)

    local idm_errors
    idm_errors=$(echo "$logs" | grep -i "heatpump_idm" | grep -iE "error|exception|traceback" | grep -v "ConfigEntryNotReady" | tail -20)

    if [ -z "$idm_errors" ]; then
        log_success "No IDM-related errors found"
        return 0
    else
        log_warn "Found IDM-related errors:"
        echo "$idm_errors"
        return 1
    fi
}

test_entities_via_api() {
    header "TEST 3: Entities Registered"

    if [ -z "${HA_TOKEN:-}" ]; then
        log_warn "No HA token, skipping API-based entity check"
        log_info "Check manually at: ${HA_URL}/config/integrations/integration/heatpump_idm"
        return 0
    fi

    local headers=(-H "Authorization: Bearer ${HA_TOKEN}")

    # Check states for heatpump_idm entities
    local entity_count
    entity_count=$(curl -sf "${HA_URL}/api/states" \
        "${headers[@]}" 2>/dev/null | \
        python3 -c "
import sys, json
states = json.load(sys.stdin)
idm = [s for s in states if s['entity_id'].startswith('sensor.idm') or s['entity_id'].startswith('binary_sensor.idm') or s['entity_id'].startswith('number.idm') or s['entity_id'].startswith('select.idm') or s['entity_id'].startswith('switch.idm')]
print(len(idm))
" 2>/dev/null || echo "0")

    if [ "$entity_count" -gt 0 ]; then
        log_success "Found ${entity_count} IDM entities registered"

        # Show some key entity values
        log_info "Key sensor values:"
        curl -sf "${HA_URL}/api/states" \
            "${headers[@]}" 2>/dev/null | \
            python3 -c "
import sys, json
states = json.load(sys.stdin)
idm = [s for s in states if s['entity_id'].startswith('sensor.idm') and s.get('state', 'unavailable') not in ('unavailable', 'unknown')]
for s in sorted(idm, key=lambda x: x['entity_id'])[:15]:
    print(f\"  {s['entity_id']}: {s['state']} {s.get('attributes', {}).get('unit_of_measurement', '')}\")
if len(idm) > 15:
    print(f'  ... and {len(idm)-15} more')
" 2>/dev/null || log_warn "Could not parse entity states"

        return 0
    else
        log_warn "No IDM entities found yet (integration may still be loading)"
        return 1
    fi
}

test_modbus_readings() {
    header "TEST 4: Modbus Data Readings"

    if [ -z "${HA_TOKEN:-}" ]; then
        log_warn "No HA token, skipping"
        return 0
    fi

    local headers=(-H "Authorization: Bearer ${HA_TOKEN}")

    # Check for specific key sensors
    local key_sensors=(
        "sensor.idm_waermepumpe_aussentemperatur"
        "sensor.idm_waermepumpe_waermespeichertemperatur"
        "sensor.idm_waermepumpe_betriebsart_waermepumpe"
    )

    local found=0
    local total=${#key_sensors[@]}

    for sensor in "${key_sensors[@]}"; do
        local state
        state=$(curl -sf "${HA_URL}/api/states/${sensor}" \
            "${headers[@]}" 2>/dev/null | \
            python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('state','unavailable'))" 2>/dev/null || echo "not_found")

        if [ "$state" != "not_found" ] && [ "$state" != "unavailable" ] && [ "$state" != "unknown" ]; then
            log_success "  ${sensor}: ${state}"
            found=$((found + 1))
        else
            log_warn "  ${sensor}: ${state}"
        fi
    done

    if [ $found -gt 0 ]; then
        log_success "${found}/${total} key sensors have data"
        return 0
    else
        log_warn "No key sensors have data yet"
        return 1
    fi
}

test_direct_modbus() {
    header "TEST 5: Direct Modbus TCP Connection Test"

    # Test raw TCP connection to IDM heat pump
    if command -v python3 &>/dev/null; then
        python3 -c "
import socket, struct, sys

host = '${IDM_IP}'
port = ${IDM_PORT}

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect((host, port))

    # Modbus TCP: Read 2 registers (outdoor temp) at address 1000
    # Transaction ID: 0x0001, Protocol: 0x0000, Length: 6, Unit: 1
    # Function: 0x04 (read input registers), Start: 1000, Count: 2
    req = struct.pack('>HHHBBHH', 1, 0, 6, 1, 4, 1000, 2)
    s.send(req)
    resp = s.recv(256)
    s.close()

    if len(resp) >= 9:
        byte_count = resp[8]
        if byte_count >= 4:
            raw = resp[9:13]
            val = struct.unpack('<f', struct.pack('<HH', struct.unpack('>H', raw[0:2])[0], struct.unpack('>H', raw[2:4])[0]))[0]
            print(f'  Connected to {host}:{port}')
            print(f'  Outdoor temperature: {val:.1f} C')
            sys.exit(0)
    print(f'  Connected but unexpected response')
    sys.exit(1)
except socket.timeout:
    print(f'  Connection timed out to {host}:{port}')
    sys.exit(1)
except Exception as e:
    print(f'  Connection failed: {e}')
    sys.exit(1)
" 2>/dev/null
        local rc=$?
        if [ $rc -eq 0 ]; then
            log_success "Direct Modbus TCP connection successful"
            return 0
        else
            log_warn "Direct Modbus TCP connection failed (heat pump may be unreachable from Docker host)"
            return 1
        fi
    else
        log_warn "python3 not available for direct test"
        return 0
    fi
}

test_error_handling() {
    header "TEST 6: Error Handling"

    local logs
    logs=$(docker logs "$CONTAINER_NAME" 2>&1)

    # Check for known bad patterns
    local bad_patterns=(
        "ImportError.*heatpump_idm"
        "ModuleNotFoundError.*heatpump_idm"
        "TypeError.*entity_category"
        "TypeError.*_number"
    )

    local found_errors=0
    for pattern in "${bad_patterns[@]}"; do
        if echo "$logs" | grep -qE "$pattern"; then
            log_error "Found matching error: $pattern"
            found_errors=$((found_errors + 1))
        fi
    done

    if [ $found_errors -eq 0 ]; then
        log_success "No critical code errors detected"
        return 0
    else
        log_error "Found ${found_errors} critical errors"
        return 1
    fi
}

# ============================================================================
# Test Suites
# ============================================================================

run_smoke_tests() {
    header "SMOKE TESTS (READ-ONLY)"
    local failures=0

    check_prerequisites || return 1
    start_container || return 1
    wait_for_ha || return 1

    # Wait a bit more for custom components to load
    log_info "Waiting 30s for custom components to load..."
    sleep 30

    test_integration_in_logs || failures=$((failures + 1))
    test_no_critical_errors || failures=$((failures + 1))
    test_error_handling || failures=$((failures + 1))

    if [ $failures -eq 0 ]; then
        log_success "All smoke tests passed!"
    else
        log_warn "${failures} smoke test(s) failed"
    fi

    return $failures
}

run_full_tests() {
    header "FULL TEST SUITE (READ-ONLY)"
    local failures=0

    run_smoke_tests || failures=$?

    test_direct_modbus || failures=$((failures + 1))

    # API tests (require token)
    get_ha_token || true
    test_entities_via_api || failures=$((failures + 1))
    test_modbus_readings || failures=$((failures + 1))

    echo ""
    header "TEST RESULTS"

    if [ $failures -eq 0 ]; then
        log_success "ALL TESTS PASSED!"
        echo ""
        log_info "Home Assistant: ${HA_URL}"
        log_info "Integration:    ${HA_URL}/config/integrations/integration/heatpump_idm"
        log_info "IDM Heat Pump:  ${IDM_IP}:${IDM_PORT}"
    else
        log_warn "${failures} test(s) failed - check logs above"
        log_info "Show full logs: $0 logs"
    fi

    return $failures
}

show_logs() {
    header "HOME ASSISTANT LOGS (IDM-related, last 100 lines)"
    docker logs --tail 500 "$CONTAINER_NAME" 2>&1 | grep -i "idm" | tail -100
    echo ""
    log_info "Full logs: docker logs ${CONTAINER_NAME}"
}

show_status() {
    header "CONTAINER STATUS"
    docker ps -a --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"

    echo ""
    header "HA HEALTH"
    if curl -sf "${HA_URL}/api/" -o /dev/null 2>/dev/null; then
        log_success "HA is responding"
    else
        log_error "HA is not responding"
    fi

    echo ""
    if [ -n "${HA_TOKEN:-}" ]; then
        header "IDM ENTITIES"
        curl -sf "${HA_URL}/api/states" \
            -H "Authorization: Bearer ${HA_TOKEN}" 2>/dev/null | \
            python3 -c "
import sys, json
try:
    states = json.load(sys.stdin)
    idm = [s for s in states if 'idm' in s['entity_id']]
    available = [s for s in idm if s.get('state', 'unknown') not in ('unavailable', 'unknown')]
    print(f'  Total IDM entities: {len(idm)}')
    print(f'  Available: {len(available)}')
    print(f'  Unavailable: {len(idm) - len(available)}')
except:
    print('  Could not retrieve entity data')
" 2>/dev/null || log_info "  No HA token set"
    fi
}

# ============================================================================
# Main
# ============================================================================

usage() {
    echo "IDM Heatpump Docker Test Script"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  all       Run full test suite (default)"
    echo "  smoke     Run smoke tests only"
    echo "  start     Start HA container"
    echo "  stop      Stop HA container"
    echo "  restart   Restart HA container"
    echo "  logs      Show IDM-related logs"
    echo "  status    Show container and entity status"
    echo "  clean     Remove container and volume"
    echo "  install   Install integration via API"
    echo "  test      Run direct Modbus connection test"
    echo ""
    echo "Environment variables:"
    echo "  IDM_IP       Heat pump IP (default: 192.168.178.103)"
    echo "  IDM_PORT     Modbus port (default: 502)"
    echo "  IDM_SLAVE_ID Slave ID (default: 1)"
    echo "  HA_PORT      HA web port (default: 8123)"
    echo "  HA_TOKEN     Long-lived HA access token"
}

main() {
    local cmd="${1:-all}"

    case "$cmd" in
        all|"")
            run_full_tests
            ;;
        smoke)
            run_smoke_tests
            ;;
        start)
            check_prerequisites
            start_container
            wait_for_ha
            log_success "HA is ready at ${HA_URL}"
            ;;
        stop)
            stop_container
            ;;
        restart)
            stop_container
            start_container
            wait_for_ha
            ;;
        logs)
            show_logs
            ;;
        status)
            show_status
            ;;
        clean)
            clean_all
            ;;
        install)
            get_ha_token
            install_integration
            ;;
        test)
            test_direct_modbus
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            log_error "Unknown command: $cmd"
            usage
            exit 1
            ;;
    esac
}

main "$@"
