#!/bin/bash
echo "Starting continuous compilation workload..."
# In a real scenario, this would clone a large C project and run make -j$(nproc)
# For the prototype, we compile a dummy C file repeatedly

cat <<EOF > dummy.c
#include <stdio.h>
int main() {
    printf("Compilation noise\n");
    return 0;
}
EOF

while true; do
    gcc -O2 dummy.c -o dummy_bin
    rm dummy_bin
    sleep 0.1
done
