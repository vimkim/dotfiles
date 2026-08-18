set no-cd

# Install or update PM2 for the active Node.js installation.
package-install:
    npm install --global pm2@latest

# Start an executable under PM2 from the current directory.
process-start name executable *args:
    pm2 start "{{ executable }}" --name "{{ name }}" --cwd "{{ invocation_directory() }}" --interpreter none -- {{ args }}

# List all PM2-managed processes.
process-status:
    pm2 status

# Show details for one PM2-managed process.
process-describe name:
    pm2 describe "{{ name }}"

# Follow logs for a process, or all processes by default.
process-logs name='all':
    pm2 logs "{{ name }}"

# Restart one PM2-managed process.
process-restart name:
    pm2 restart "{{ name }}"

# Stop one PM2-managed process without removing it.
process-stop name:
    pm2 stop "{{ name }}"

# Remove one process from PM2's managed process list.
process-delete name:
    pm2 delete "{{ name }}"

# Save the current process list for boot-time restoration.
process-list-save:
    pm2 save

# Generate the OS-specific boot startup installation command.
startup-install:
    pm2 startup

# Restore the last process list saved by `pm2 save`.
process-list-restore:
    pm2 resurrect

# Install the self-hosted Markdown renderers and replace the copyparty PM2 definitions.
copyparty-renderers:
    ~/.config/my-scripts/bin/copyparty-render-install.sh
    -pm2 delete copyparty copyparty-index copyparty-docs copyparty-develop copyparty-learnings
    pm2 start ~/.config/copyparty/ecosystem.config.cjs
    pm2 save
