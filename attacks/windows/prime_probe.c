#include <stdio.h>
#include <stdint.h>
#include <windows.h>
#include <intrin.h>

#define CACHE_SIZE (8 * 1024 * 1024)

int main() {
    char *eviction_set = (char*)VirtualAlloc(NULL, CACHE_SIZE, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!eviction_set) return 1;
    
    while (1) {
        // Prime
        for (int i = 0; i < CACHE_SIZE; i += 4096) {
            eviction_set[i] = 1;
        }
        
        // Wait
        Sleep(1);
        
        // Probe
        for (int i = 0; i < CACHE_SIZE; i += 4096) {
            unsigned int junk;
            uint64_t t1 = __rdtscp(&junk);
            volatile char x = eviction_set[i];
            uint64_t t2 = __rdtscp(&junk);
        }
    }
    VirtualFree(eviction_set, 0, MEM_RELEASE);
    return 0;
}
