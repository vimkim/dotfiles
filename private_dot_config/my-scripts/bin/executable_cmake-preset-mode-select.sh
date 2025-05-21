#!/bin/bash
cmake --list-presets=configure |
    awk '/Available configure presets:/,0' |
    tail -n +2 |
    sed 's/"//g' |
    awk 'NF' | # removes empty lines
    fzf --prompt="Choose preset:" |
    xargs -I {} echo "PRESET_MODE={}" >.env
