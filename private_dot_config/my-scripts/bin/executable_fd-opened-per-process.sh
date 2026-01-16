#!/bin/bash
for pid in /proc/[0-9]*; do
    fdcount=$(ls "$pid/fd" 2>/dev/null | wc -l)
    cmd=$(tr -d '\0' < "$pid/cmdline" 2>/dev/null | cut -c1-80)
    printf "%5d %-6s %s\n" "$fdcount" "$(basename "$pid")" "$cmd"
done | sort -nr | head

