set no-cd

# Show whether firewalld is running.
status:
    sudo firewall-cmd --state

# Show the default zone.
default-zone:
    sudo firewall-cmd --get-default-zone

# Show active zones and their bound interfaces or sources.
active-zones:
    sudo firewall-cmd --get-active-zones

# List ports currently open in the runtime configuration.
list zone='':
    #!/usr/bin/env bash
    set -euo pipefail
    zone={{ quote(zone) }}
    zone_args=()
    if [[ -n "$zone" ]]; then
        zone_args+=("--zone=$zone")
    fi
    sudo firewall-cmd "${zone_args[@]}" --list-ports

# List ports in the permanent configuration.
list-permanent zone='':
    #!/usr/bin/env bash
    set -euo pipefail
    zone={{ quote(zone) }}
    zone_args=()
    if [[ -n "$zone" ]]; then
        zone_args+=("--zone=$zone")
    fi
    sudo firewall-cmd "${zone_args[@]}" --permanent --list-ports

# Check whether a port is open in the runtime configuration.
check port protocol='tcp' zone='':
    #!/usr/bin/env bash
    set -euo pipefail
    port={{ quote(port) }}
    protocol={{ quote(protocol) }}
    zone={{ quote(zone) }}
    zone_args=()
    if [[ -n "$zone" ]]; then
        zone_args+=("--zone=$zone")
    fi
    sudo firewall-cmd "${zone_args[@]}" --query-port="$port/$protocol"

# Check whether a port is open in the permanent configuration.
check-permanent port protocol='tcp' zone='':
    #!/usr/bin/env bash
    set -euo pipefail
    port={{ quote(port) }}
    protocol={{ quote(protocol) }}
    zone={{ quote(zone) }}
    zone_args=()
    if [[ -n "$zone" ]]; then
        zone_args+=("--zone=$zone")
    fi
    sudo firewall-cmd "${zone_args[@]}" --permanent --query-port="$port/$protocol"

# Permanently open a port and reload firewalld.
add port protocol='tcp' zone='':
    #!/usr/bin/env bash
    set -euo pipefail
    port={{ quote(port) }}
    protocol={{ quote(protocol) }}
    zone={{ quote(zone) }}
    zone_args=()
    if [[ -n "$zone" ]]; then
        zone_args+=("--zone=$zone")
    fi
    sudo firewall-cmd "${zone_args[@]}" --permanent --add-port="$port/$protocol"
    sudo firewall-cmd --reload

# Permanently close a port and reload firewalld.
delete port protocol='tcp' zone='':
    #!/usr/bin/env bash
    set -euo pipefail
    port={{ quote(port) }}
    protocol={{ quote(protocol) }}
    zone={{ quote(zone) }}
    zone_args=()
    if [[ -n "$zone" ]]; then
        zone_args+=("--zone=$zone")
    fi
    sudo firewall-cmd "${zone_args[@]}" --permanent --remove-port="$port/$protocol"
    sudo firewall-cmd --reload

# Reload firewalld so permanent rules become active.
reload:
    sudo firewall-cmd --reload
