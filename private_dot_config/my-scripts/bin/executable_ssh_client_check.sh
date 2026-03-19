#!/usr/bin/env bash
# =============================================================================
# ssh_client_check.sh
# Run this on the SSH client (Linux) to audit local SSH settings for
# reliable reconnection to remote servers.
#
# Checks performed (PASS/WARN/FAIL):
#   1. SSH client binary — is ssh installed and what version?
#   2. Keepalive — ServerAliveInterval, ServerAliveCountMax, TCPKeepAlive
#   3. Connection multiplexing — ControlMaster, ControlPath, ControlPersist
#   4. Authentication — key files, ssh-agent, IdentityFile
#   5. Reconnection tools — autossh, mosh, tmux/screen availability
#   6. OS TCP keepalive — kernel sysctl params (informational)
#   7. Network — DNS resolution, default route, firewall hints
#   8. Config sanity — ssh_config syntax, Include directives
#
# Prints a summary with PASS/WARN/FAIL counts and suggested config fixes.
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

# Read effective value from ssh_config for a given host
# Searches: ~/.ssh/config, /etc/ssh/ssh_config
ssh_config_val() {
    local key="$1"
    local host="${2:-*}"
    # ssh -G gives the fully resolved config for a given host
    if command -v ssh &>/dev/null; then
        ssh -G "$host" 2>/dev/null | grep -i "^${key} " | awk '{print $2}' | head -1
    fi
}

# Read a raw value from ~/.ssh/config (Host * block or global)
ssh_config_raw() {
    local key="$1"
    local conf="$HOME/.ssh/config"
    [[ -f "$conf" ]] || return
    grep -i "^[[:space:]]*${key}[[:space:]]" "$conf" | head -1 | awk '{print $2}'
}

# ─────────────────────────────────────────────
# Preflight
# ─────────────────────────────────────────────

echo ""
echo -e "${BOLD}SSH Client Reconnection Readiness Check${NC}"
echo -e "${DIM}Hostname: $(hostname)   User: $(whoami)   Date: $(date)${NC}"

# ─────────────────────────────────────────────
# 1. SSH client binary
# ─────────────────────────────────────────────

header "SSH CLIENT"

if command -v ssh &>/dev/null; then
    SSH_VER=$(ssh -V 2>&1 | head -1)
    check PASS "ssh installed" "$SSH_VER"
else
    check FAIL "ssh not found" "OpenSSH client is not installed"
    echo -e "\n${RED}Cannot continue without ssh. Install with: sudo apt install openssh-client${NC}"
    exit 1
fi

# Check ssh_config exists
USER_CONF="$HOME/.ssh/config"
if [[ -f "$USER_CONF" ]]; then
    check PASS "~/.ssh/config" "exists"
else
    check WARN "~/.ssh/config" "not found — using system defaults only"
fi

SYS_CONF=""
for f in /etc/ssh/ssh_config /usr/local/etc/ssh_config; do
    [[ -f "$f" ]] && SYS_CONF="$f" && break
done
if [[ -n "$SYS_CONF" ]]; then
    note "System config: $SYS_CONF"
fi

# ─────────────────────────────────────────────
# 2. Keepalive settings
# ─────────────────────────────────────────────

header "KEEPALIVE  —  Dead connection detection"

# ServerAliveInterval
SAI=$(ssh_config_val serveraliveinterval)
SAI="${SAI:-0}"
if [[ "$SAI" == "0" ]]; then
    check FAIL "ServerAliveInterval" "= 0 (disabled) — client will NOT detect a dead server/broken connection"
elif (( SAI <= 30 )); then
    check PASS "ServerAliveInterval" "= ${SAI}s  (fast detection)"
elif (( SAI <= 60 )); then
    check PASS "ServerAliveInterval" "= ${SAI}s  (reasonable)"
else
    check WARN "ServerAliveInterval" "= ${SAI}s  — slow; consider ≤ 60"
fi

# ServerAliveCountMax
SACM=$(ssh_config_val serveralivecountmax)
SACM="${SACM:-3}"
if (( SACM == 0 )); then
    check FAIL "ServerAliveCountMax" "= 0 — connection will drop on the very first missed probe"
elif (( SACM >= 1 && SACM <= 5 )); then
    TIMEOUT=$(( SAI * SACM ))
    check PASS "ServerAliveCountMax" "= ${SACM}  (dead connection detected after ~${TIMEOUT}s)"
elif (( SACM > 10 )); then
    check WARN "ServerAliveCountMax" "= ${SACM}  — very high; dead connections linger a long time"
else
    check PASS "ServerAliveCountMax" "= ${SACM}"
fi

# TCPKeepAlive
TCPKA=$(ssh_config_val tcpkeepalive)
TCPKA="${TCPKA:-yes}"
if [[ "${TCPKA,,}" == "yes" ]]; then
    check PASS "TCPKeepAlive" "= yes  (OS-level TCP probes enabled)"
else
    check WARN "TCPKeepAlive" "= no  — some NAT/firewall drops may go undetected"
fi

# ─────────────────────────────────────────────
# 3. Connection multiplexing
# ─────────────────────────────────────────────

header "CONNECTION MULTIPLEXING  —  Reuse & persistence"

# ControlMaster
CM=$(ssh_config_val controlmaster)
CM="${CM:-no}"
if [[ "${CM,,}" == "auto" || "${CM,,}" == "autoask" ]]; then
    check PASS "ControlMaster" "= ${CM}  (connection sharing enabled — faster reconnects)"
elif [[ "${CM,,}" == "yes" ]]; then
    check PASS "ControlMaster" "= yes  (explicit multiplexing)"
else
    check WARN "ControlMaster" "= ${CM}  — consider 'auto' to share connections and speed up reconnects"
fi

# ControlPath
CP=$(ssh_config_val controlpath)
if [[ -n "$CP" && "$CP" != "none" ]]; then
    check PASS "ControlPath" "= ${CP}"
else
    if [[ "${CM,,}" == "auto" || "${CM,,}" == "yes" ]]; then
        check WARN "ControlPath" "not set — ControlMaster is enabled but has no socket path"
    else
        note "ControlPath = ${CP:-none}  (not needed when ControlMaster is off)"
    fi
fi

# ControlPersist
CPER=$(ssh_config_val controlpersist)
if [[ -n "$CPER" && "$CPER" != "no" && "$CPER" != "0" ]]; then
    check PASS "ControlPersist" "= ${CPER}  (master connection stays alive in background)"
else
    if [[ "${CM,,}" == "auto" || "${CM,,}" == "yes" ]]; then
        check WARN "ControlPersist" "= ${CPER:-no}  — master closes when last session exits; set to '10m' or 'yes'"
    else
        note "ControlPersist = ${CPER:-no}"
    fi
fi

# ─────────────────────────────────────────────
# 4. Authentication — key setup
# ─────────────────────────────────────────────

header "AUTHENTICATION  —  Non-interactive reconnects"

# Check for SSH keys
SSH_DIR="$HOME/.ssh"
KEY_COUNT=0
if [[ -d "$SSH_DIR" ]]; then
    for ktype in id_rsa id_ed25519 id_ecdsa id_dsa; do
        if [[ -f "$SSH_DIR/$ktype" ]]; then
            ((KEY_COUNT++))
        fi
    done
    # Also count any other private key files (no .pub extension, not config/known_hosts)
    while IFS= read -r -d '' kf; do
        base=$(basename "$kf")
        case "$base" in
            id_rsa|id_ed25519|id_ecdsa|id_dsa|config|known_hosts|known_hosts.old|authorized_keys|*.pub) continue ;;
            *) ((KEY_COUNT++)) ;;
        esac
    done < <(find "$SSH_DIR" -maxdepth 1 -type f -print0 2>/dev/null)
fi

if (( KEY_COUNT > 0 )); then
    check PASS "SSH private keys" "found ${KEY_COUNT} key(s) in ~/.ssh/"
else
    check FAIL "SSH private keys" "no keys found in ~/.ssh/ — generate with: ssh-keygen -t ed25519"
fi

# Check for ed25519 specifically (preferred)
if [[ -f "$SSH_DIR/id_ed25519" ]]; then
    check PASS "Ed25519 key" "present (recommended key type)"
elif (( KEY_COUNT > 0 )); then
    note "Consider generating an Ed25519 key: ssh-keygen -t ed25519"
fi

# SSH agent
if [[ -n "$SSH_AUTH_SOCK" ]]; then
    AGENT_KEYS=$(ssh-add -l 2>/dev/null | grep -c -v "no identities")
    if (( AGENT_KEYS > 0 )); then
        check PASS "ssh-agent" "running with ${AGENT_KEYS} key(s) loaded"
    else
        check WARN "ssh-agent" "running but no keys loaded — run: ssh-add"
    fi
else
    check WARN "ssh-agent" "not running or SSH_AUTH_SOCK not set — passphrase-protected keys will prompt on reconnect"
fi

# AddKeysToAgent
AKTA=$(ssh_config_val addkeystoagent)
AKTA="${AKTA:-no}"
if [[ "${AKTA,,}" == "yes" || "${AKTA,,}" == "confirm" || "${AKTA,,}" == "ask" ]]; then
    check PASS "AddKeysToAgent" "= ${AKTA}  (keys auto-added to agent on first use)"
else
    note "AddKeysToAgent = ${AKTA}  (set to 'yes' to auto-load keys into agent)"
fi

# ─────────────────────────────────────────────
# 5. Reconnection tools
# ─────────────────────────────────────────────

header "RECONNECTION TOOLS"

# autossh
if command -v autossh &>/dev/null; then
    AUTOSSH_VER=$(autossh -V 2>&1 | head -1)
    check PASS "autossh" "installed  (${AUTOSSH_VER})"
else
    check WARN "autossh" "not installed — auto-reconnecting tunnels not available"
    note "Install with: sudo apt install autossh"
fi

# mosh
if command -v mosh &>/dev/null; then
    check PASS "mosh" "installed  (UDP-based, survives roaming/sleep)"
else
    note "mosh not installed — optional UDP-based alternative (sudo apt install mosh)"
fi

# tmux
if command -v tmux &>/dev/null; then
    check PASS "tmux" "installed  (session persistence across disconnects)"
else
    note "tmux not installed — consider installing for session persistence"
fi

# screen
if command -v screen &>/dev/null; then
    note "screen installed  (alternative to tmux for session persistence)"
fi

# systemd user service for autossh
if [[ -d "$HOME/.config/systemd/user" ]]; then
    AUTOSSH_UNITS=$(find "$HOME/.config/systemd/user" -name '*autossh*' -o -name '*ssh-tunnel*' 2>/dev/null | head -5)
    if [[ -n "$AUTOSSH_UNITS" ]]; then
        note "Found systemd user unit(s) for SSH tunnels:"
        while IFS= read -r u; do
            note "  $(basename "$u")"
        done <<< "$AUTOSSH_UNITS"
    fi
fi

# ─────────────────────────────────────────────
# 6. OS-level TCP keepalive parameters
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

note "OS TCP keepalive defaults are conservative (2hr). SSH-level ServerAliveInterval is more important."

# ─────────────────────────────────────────────
# 7. Network basics
# ─────────────────────────────────────────────

header "NETWORK  —  Connectivity basics"

# Default route
if ip route show default &>/dev/null 2>&1; then
    DEF_GW=$(ip route show default 2>/dev/null | head -1)
    if [[ -n "$DEF_GW" ]]; then
        check PASS "Default route" "$DEF_GW"
    else
        check FAIL "Default route" "no default route — SSH connections will fail"
    fi
elif command -v route &>/dev/null; then
    DEF_GW=$(route -n 2>/dev/null | grep '^0\.0\.0\.0' | head -1)
    if [[ -n "$DEF_GW" ]]; then
        check PASS "Default route" "present"
    else
        check FAIL "Default route" "no default route"
    fi
else
    note "Cannot check default route (no ip or route command)"
fi

# DNS resolution
if command -v host &>/dev/null; then
    if host -W 3 google.com &>/dev/null 2>&1; then
        check PASS "DNS resolution" "working"
    else
        check WARN "DNS resolution" "failed to resolve google.com — DNS may be down"
    fi
elif command -v dig &>/dev/null; then
    if dig +time=3 +tries=1 google.com &>/dev/null 2>&1; then
        check PASS "DNS resolution" "working"
    else
        check WARN "DNS resolution" "failed — DNS may be down"
    fi
elif command -v nslookup &>/dev/null; then
    if nslookup google.com &>/dev/null 2>&1; then
        check PASS "DNS resolution" "working"
    else
        check WARN "DNS resolution" "failed — DNS may be down"
    fi
else
    note "No DNS lookup tool available (host/dig/nslookup)"
fi

# Firewall — check if outbound port 22 might be filtered
if command -v iptables &>/dev/null && iptables -L OUTPUT -n 2>/dev/null | grep -q "DROP\|REJECT"; then
    check WARN "Firewall (iptables)" "OUTPUT chain has DROP/REJECT rules — verify port 22 is allowed"
else
    note "No obvious outbound firewall blocks detected (iptables)"
fi

if command -v nft &>/dev/null && nft list ruleset 2>/dev/null | grep -q "drop\|reject"; then
    note "nftables rules detected — verify outbound SSH (port 22) is allowed"
fi

# ─────────────────────────────────────────────
# 8. Config sanity
# ─────────────────────────────────────────────

header "CONFIG SANITY"

# Permissions on ~/.ssh
if [[ -d "$SSH_DIR" ]]; then
    SSH_DIR_PERMS=$(stat -c '%a' "$SSH_DIR" 2>/dev/null || stat -f '%Lp' "$SSH_DIR" 2>/dev/null)
    if [[ "$SSH_DIR_PERMS" == "700" ]]; then
        check PASS "~/.ssh permissions" "= 700  (correct)"
    else
        check WARN "~/.ssh permissions" "= ${SSH_DIR_PERMS}  — should be 700 (chmod 700 ~/.ssh)"
    fi
else
    check WARN "~/.ssh directory" "does not exist — create with: mkdir -p ~/.ssh && chmod 700 ~/.ssh"
fi

# Permissions on ~/.ssh/config
if [[ -f "$USER_CONF" ]]; then
    CONF_PERMS=$(stat -c '%a' "$USER_CONF" 2>/dev/null || stat -f '%Lp' "$USER_CONF" 2>/dev/null)
    if [[ "$CONF_PERMS" == "600" || "$CONF_PERMS" == "644" ]]; then
        check PASS "~/.ssh/config permissions" "= ${CONF_PERMS}  (ok)"
    else
        check WARN "~/.ssh/config permissions" "= ${CONF_PERMS}  — should be 600 (chmod 600 ~/.ssh/config)"
    fi
fi

# Check for Include directives
if [[ -f "$USER_CONF" ]] && grep -qi "^[[:space:]]*Include" "$USER_CONF" 2>/dev/null; then
    INCLUDES=$(grep -i "^[[:space:]]*Include" "$USER_CONF" | awk '{print $2}')
    note "Include directives found: $INCLUDES"
    note "Use 'ssh -G <host>' to see the fully resolved config for a given host"
fi

# known_hosts hashing
HKH=$(ssh_config_val hashknownhosts)
if [[ "${HKH,,}" == "yes" ]]; then
    note "HashKnownHosts = yes  (hostnames in known_hosts are hashed — more private)"
else
    note "HashKnownHosts = ${HKH:-no}  (hostnames stored in plaintext in known_hosts)"
fi

# ─────────────────────────────────────────────
# 9. Summary
# ─────────────────────────────────────────────

header "SUMMARY"

TOTAL=$((PASS + WARN + FAIL))
echo -e "  ${GRN}✔ PASS${NC}  $PASS / $TOTAL"
echo -e "  ${YEL}⚠ WARN${NC}  $WARN / $TOTAL"
echo -e "  ${RED}✘ FAIL${NC}  $FAIL / $TOTAL"
echo ""

if (( FAIL == 0 && WARN == 0 )); then
    echo -e "  ${GRN}${BOLD}All checks passed. Client is well-configured for reliable SSH reconnection.${NC}"
elif (( FAIL == 0 )); then
    echo -e "  ${YEL}${BOLD}No hard failures — but review warnings above.${NC}"
else
    echo -e "  ${RED}${BOLD}Fix the failing checks above for reliable reconnection.${NC}"
fi

# ─────────────────────────────────────────────
# 10. Suggested config
# ─────────────────────────────────────────────

if (( FAIL > 0 || WARN > 0 )); then
    header "SUGGESTED ~/.ssh/config SETTINGS"
    cat <<'EOF'

  Host *
      # Detect dead server / broken connection within ~90s
      ServerAliveInterval 30
      ServerAliveCountMax 3

      # OS-level TCP probes (catches NAT table expiry)
      TCPKeepAlive yes

      # Connection multiplexing — faster reconnects, shared sessions
      ControlMaster auto
      ControlPath ~/.ssh/sockets/%r@%h-%p
      ControlPersist 10m

      # Auto-add keys to agent on first use
      AddKeysToAgent yes

  # NOTE: Create the socket directory:
  #   mkdir -p ~/.ssh/sockets && chmod 700 ~/.ssh/sockets

EOF
fi

echo ""
