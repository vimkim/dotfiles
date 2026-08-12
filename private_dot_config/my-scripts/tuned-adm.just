set no-cd

# Show the active TuneD profile.
active:
    tuned-adm active

# Show the profile TuneD recommends for this system.
recommend:
    tuned-adm recommend

# List available TuneD profiles.
list:
    tuned-adm list

# Change the active TuneD profile.
profile name:
    sudo tuned-adm profile "{{ name }}"
