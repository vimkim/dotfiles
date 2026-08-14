set no-cd

# Install or update PM2 for the active Node.js installation.
install:
    npm install --global pm2@latest

# Start an executable under PM2 from the current directory.
start name executable *args:
    pm2 start "{{ executable }}" --name "{{ name }}" --cwd "{{ invocation_directory() }}" --interpreter none -- {{ args }}

# List all PM2-managed processes.
status:
    pm2 status

# Show details for one PM2-managed process.
describe name:
    pm2 describe "{{ name }}"

# Follow logs for a process, or all processes by default.
logs name='all':
    pm2 logs "{{ name }}"

# Restart one PM2-managed process.
restart name:
    pm2 restart "{{ name }}"

# Stop one PM2-managed process without removing it.
stop name:
    pm2 stop "{{ name }}"

# Remove one process from PM2's managed process list.
delete name:
    pm2 delete "{{ name }}"

# Save the current process list for boot-time restoration.
save:
    pm2 save

# Generate the OS-specific boot startup command.
startup:
    pm2 startup

# Restore the last process list saved by `pm2 save`.
resurrect:
    pm2 resurrect

# Install the self-hosted Markdown renderers and replace the copyparty PM2 definitions.
copyparty-renderers:
    ~/.config/my-scripts/bin/copyparty-render-install.sh
    -pm2 delete copyparty copyparty-docs copyparty-develop copyparty-learnings
    pm2 start ~/.config/copyparty/ecosystem.config.cjs
    pm2 save
