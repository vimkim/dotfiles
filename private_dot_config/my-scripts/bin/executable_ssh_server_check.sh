#!/usr/bin/env bash
# =============================================================================
# ssh_server_check.sh
# Run this directly on the SSH server (requires sudo for accurate results).
#
# Audits sshd_config for settings that affect client reconnection reliability.
# Checks performed (PASS/WARN/FAIL):
#   1. sshd process — is sshd running?
#   2. Keepalive — ClientAliveInterval, ClientAliveCountMax, TCPKeepAlive
#   3. Session/tunnel — MaxSessions, MaxStartups, AllowTcpForwarding, GatewayPorts
#   4. Authentication — PubkeyAuthentication, PasswordAuthentication
#   5. OS TCP keepalive — kernel sysctl params (informational)
#   6. Config sanity — sshd -t syntax check, Include directives
#
# Prints a summary with PASS/WARN/FAIL counts and suggested config fixes.
# Uses `sshd -T` for effective config when available, falls back to file parsing.
# =============================================================================

RED='\033[0;31m'
YEL='\033[1;33m'
GRN='\033[0;32m'
BLU='\033[0;34m'
CYN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

PASS=0
WARN=0
FAIL=0

header() {
    echo ""
    echo -e "${BOLD}${BLU}══════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${BLU}  $1${NC}"
    echo -e "${BOLD}${BLU}══════════════════════════════════════════════${NC}"
}

check() {
    local status="$1" label="$2" detail="$3"
    case "$status" in
        PASS) echo -e "  ${GRN}✔${NC}  ${BOLD}${label}${NC}  ${DIM}${detail}${NC}"; ((PASS++)) ;;
        WARN) echo -e "  ${YEL}⚠${NC}  ${BOLD}${label}${NC}  ${DIM}${detail}${NC}"; ((WARN++)) ;;
        FAIL) echo -e "  ${RED}✘${NC}  ${BOLD}${label}${NC}  ${DIM}${detail}${NC}"; ((FAIL++)) ;;
    esac
}

note() { echo -e "  ${CYN}ℹ${NC}  ${DIM}$1${NC}"; }

# Read effective value from sshd_config (skips commented lines)
# Uses `sshd -T` (full config dump) when available — handles Include directives correctly
sshd_effective() {
    local key="$1"
    # sshd -T dumps the fully-parsed, merged config — most reliable
    if sshd -T 2>/dev/null | grep -qi "^${key} "; then
        sshd -T 2>/dev/null | grep -i "^${key} " | awk '{print $2}' | head -1
        return
    fi
    # Fallback: parse sshd_config directly
    local conf
    for f in /etc/ssh/sshd_config /usr/local/etc/sshd_config; do
        [[ -f "$f" ]] && conf="$f" && break
    done
    [[ -z "$conf" ]] && return
    grep -i "^[[:space:]]*${key}[[:space:]]" "$conf" | tail -1 | awk '{print $2}'
}

# ─────────────────────────────────────────────
# Preflight
# ─────────────────────────────────────────────

echo ""
echo -e "${BOLD}SSH Server Reconnection Readiness Check${NC}"
echo -e "${DIM}Hostname: $(hostname)   Date: $(date)${NC}"

# Locate sshd_config
SSHD_CONF=""
for f in /etc/ssh/sshd_config /usr/local/etc/sshd_config; do
    [[ -f "$f" ]] && SSHD_CONF="$f" && break
done

if [[ -z "$SSHD_CONF" ]]; then
    echo -e "\n${RED}✘ Cannot find sshd_config. Is sshd installed?${NC}"
    exit 1
fi

note "Reading config from: $SSHD_CONF"

if ! command -v sshd &>/dev/null; then
    note "sshd binary not in PATH — falling back to direct file parsing (Include directives won't be followed)"
fi

# ─────────────────────────────────────────────
# 1. sshd process
# ─────────────────────────────────────────────

header "SSHD PROCESS"

if pgrep -x sshd &>/dev/null; then
    SSHD_PID=$(pgrep -x sshd | head -1)
    check PASS "sshd running" "PID $SSHD_PID"
else
    check FAIL "sshd not running" "No sshd process found"
fi

SSHD_VER=$(sshd -V 2>&1 | head -1)
note "Version: ${SSHD_VER:-unknown}"

# ─────────────────────────────────────────────
# 2. Keepalive settings
# ─────────────────────────────────────────────

header "KEEPALIVE  —  Dead client detection"

# ClientAliveInterval
CAI=$(sshd_effective ClientAliveInterval)
CAI="${CAI:-0}"
if [[ "$CAI" == "0" ]]; then
    check FAIL "ClientAliveInterval" "= 0 (disabled) — server will NEVER detect a dead/disconnected client"
elif (( CAI <= 30 )); then
    check PASS "ClientAliveInterval" "= ${CAI}s  (fast detection)"
elif (( CAI <= 60 )); then
    check PASS "ClientAliveInterval" "= ${CAI}s  (reasonable)"
else
    check WARN "ClientAliveInterval" "= ${CAI}s  — slow; consider ≤ 60"
fi

# ClientAliveCountMax
CACM=$(sshd_effective ClientAliveCountMax)
CACM="${CACM:-3}"   # OpenSSH default is 3
if (( CACM == 0 )); then
    check FAIL "ClientAliveCountMax" "= 0 — sshd will disconnect client after the very first missed probe"
elif (( CACM >= 1 && CACM <= 5 )); then
    TIMEOUT=$(( CAI * CACM ))
    check PASS "ClientAliveCountMax" "= ${CACM}  (dead client detected after ~${TIMEOUT}s)"
elif (( CACM > 10 )); then
    check WARN "ClientAliveCountMax" "= ${CACM}  — very high; dead sessions may persist a long time"
else
    check PASS "ClientAliveCountMax" "= ${CACM}"
fi

# TCPKeepAlive
TCPKA=$(sshd_effective TCPKeepAlive)
TCPKA="${TCPKA:-yes}"
if [[ "${TCPKA,,}" == "yes" ]]; then
    check PASS "TCPKeepAlive" "= yes  (OS-level TCP probes; catches NAT table expiry)"
else
    check WARN "TCPKeepAlive" "= no  — only SSH-level probes active; some NAT drops may go undetected"
fi

# ─────────────────────────────────────────────
# 3. Session / tunnel settings
# ─────────────────────────────────────────────

header "SESSION & TUNNEL SETTINGS"

# MaxSessions
MS=$(sshd_effective MaxSessions)
MS="${MS:-10}"
if (( MS >= 10 )); then
    check PASS "MaxSessions" "= ${MS}  (enough headroom for reconnects)"
elif (( MS >= 3 )); then
    check WARN "MaxSessions" "= ${MS}  — low; stale sessions from dropped reconnects may block new ones"
else
    check FAIL "MaxSessions" "= ${MS}  — dangerously low for reliable reconnection"
fi

# MaxStartups  (unauthenticated connection throttle)
MSU=$(sshd_effective MaxStartups)
MSU="${MSU:-10:30:100}"
note "MaxStartups = ${MSU}  (throttles unauthenticated handshakes; default 10:30:100 is fine)"

# LoginGraceTime
LGT=$(sshd_effective LoginGraceTime)
if [[ -z "$LGT" || "$LGT" == "120" || "$LGT" == "2m" ]]; then
    note "LoginGraceTime = ${LGT:-120s (default)}  (time to authenticate after connect)"
elif [[ "$LGT" == "0" ]]; then
    check WARN "LoginGraceTime" "= 0  — no timeout on unauthenticated connections (security risk)"
else
    note "LoginGraceTime = ${LGT}"
fi

# GatewayPorts
GP=$(sshd_effective GatewayPorts)
GP="${GP:-no}"
note "GatewayPorts = ${GP}  (set to 'yes' only if remote-forwards must be reachable externally)"

# AllowTcpForwarding
ATF=$(sshd_effective AllowTcpForwarding)
ATF="${ATF:-yes}"
if [[ "${ATF,,}" == "yes" || "${ATF,,}" == "all" || "${ATF,,}" == "local" || "${ATF,,}" == "remote" ]]; then
    check PASS "AllowTcpForwarding" "= ${ATF}  (port forwarding / tunnels allowed)"
else
    check FAIL "AllowTcpForwarding" "= ${ATF}  — tunnels are BLOCKED; autossh -L/-R/-D will fail"
fi

# ─────────────────────────────────────────────
# 4. Authentication (reconnect speed)
# ─────────────────────────────────────────────

header "AUTHENTICATION  —  Reconnect speed"

# PubkeyAuthentication
PKA=$(sshd_effective PubkeyAuthentication)
PKA="${PKA:-yes}"
if [[ "${PKA,,}" == "yes" ]]; then
    check PASS "PubkeyAuthentication" "= yes  (key auth enabled — fast, non-interactive reconnects)"
else
    check FAIL "PubkeyAuthentication" "= no  — autossh cannot reconnect non-interactively without key auth"
fi

# PasswordAuthentication (informational)
PWA=$(sshd_effective PasswordAuthentication)
PWA="${PWA:-yes}"
if [[ "${PWA,,}" == "yes" ]]; then
    note "PasswordAuthentication = yes  (consider disabling if using key auth only)"
else
    note "PasswordAuthentication = no  (good — key-only)"
fi

# AuthorizedKeysFile
AKF=$(sshd_effective AuthorizedKeysFile)
note "AuthorizedKeysFile = ${AKF:-.ssh/authorized_keys (default)}"

# ─────────────────────────────────────────────
# 5. OS-level TCP keepalive parameters
# ─────────────────────────────────────────────

header "OS TCP KEEPALIVE  (kernel settings)"

check_sysctl() {
    local key="$1" label="$2" good_desc="$3"
    if command -v sysctl &>/dev/null; then
        val=$(sysctl -n "$key" 2>/dev/null)
        if [[ -n "$val" ]]; then
            echo -e "  ${CYN}ℹ${NC}  ${BOLD}${label}${NC}  ${DIM}= ${val}   ${good_desc}${NC}"
        fi
    fi
}

check_sysctl net.ipv4.tcp_keepalive_time     "tcp_keepalive_time"     "(seconds before first probe; default 7200)"
check_sysctl net.ipv4.tcp_keepalive_intvl    "tcp_keepalive_intvl"    "(seconds between probes; default 75)"
check_sysctl net.ipv4.tcp_keepalive_probes   "tcp_keepalive_probes"   "(probe count before drop; default 9)"

if ! command -v sysctl &>/dev/null; then
    note "sysctl not available — cannot read kernel TCP settings"
fi

note "OS TCP keepalive defaults are very conservative (2hr). SSH-level ClientAliveInterval is more important."

# ─────────────────────────────────────────────
# 6. Config file sanity
# ─────────────────────────────────────────────

header "CONFIG FILE SANITY"

# Test sshd config syntax
if command -v sshd &>/dev/null; then
    SYNTAX=$(sshd -t 2>&1)
    if [[ $? -eq 0 ]]; then
        check PASS "sshd config syntax" "No errors"
    else
        check FAIL "sshd config syntax" "$SYNTAX"
    fi
else
    note "Cannot run 'sshd -t' — skipping syntax check"
fi

# Check for Include directives
if grep -qi "^Include" "$SSHD_CONF" 2>/dev/null; then
    INCLUDES=$(grep -i "^Include" "$SSHD_CONF" | awk '{print $2}')
    note "Include directives found: $INCLUDES"
    note "Use 'sshd -T' to see the fully merged effective config"
fi

# ─────────────────────────────────────────────
# 7. Summary
# ─────────────────────────────────────────────

header "SUMMARY"

TOTAL=$((PASS + WARN + FAIL))
echo -e "  ${GRN}✔ PASS${NC}  $PASS / $TOTAL"
echo -e "  ${YEL}⚠ WARN${NC}  $WARN / $TOTAL"
echo -e "  ${RED}✘ FAIL${NC}  $FAIL / $TOTAL"
echo ""

if (( FAIL == 0 && WARN == 0 )); then
    echo -e "  ${GRN}${BOLD}All checks passed. Server is well-configured for reliable SSH reconnection.${NC}"
elif (( FAIL == 0 )); then
    echo -e "  ${YEL}${BOLD}No hard failures — but review warnings above.${NC}"
else
    echo -e "  ${RED}${BOLD}Fix the failing checks above for reliable reconnection.${NC}"
fi

# ─────────────────────────────────────────────
# 8. Suggested config
# ─────────────────────────────────────────────

if (( FAIL > 0 || WARN > 0 )); then
    header "SUGGESTED /etc/ssh/sshd_config SETTINGS"
    cat <<'EOF'

  # Dead client detection — drop ghost sessions within ~90s
  ClientAliveInterval 30
  ClientAliveCountMax 3

  # OS-level TCP probes (catches NAT table expiry)
  TCPKeepAlive yes

  # Allow tunnels/port-forwarding (needed for autossh -L/-R/-D)
  AllowTcpForwarding yes

  # Key-based auth for non-interactive reconnects
  PubkeyAuthentication yes

  # After editing, reload with:
  #   sudo systemctl reload sshd     (systemd)
  #   sudo service ssh reload         (sysvinit/upstart)
  #   sudo kill -HUP $(cat /var/run/sshd.pid)

EOF
fi

echo ""
