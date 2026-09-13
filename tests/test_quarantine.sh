#!/bin/bash

# Simple script to test resctrl setup
echo "Testing hardware quarantine module..."

if [ ! -d "/sys/fs/resctrl" ]; then
    echo "[!] /sys/fs/resctrl is not mounted. Are you on a compatible Linux system with RDT/QoS enabled?"
    exit 1
fi

echo "[*] resctrl is mounted."
if [ -d "/sys/fs/resctrl/aegis_quarantine" ]; then
    echo "[*] aegis_quarantine CLOS exists."
    cat /sys/fs/resctrl/aegis_quarantine/schemata
else
    echo "[!] aegis_quarantine CLOS does not exist. Run the daemon first to initialize it."
fi

echo "Test complete."
