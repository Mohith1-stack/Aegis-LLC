#include <stdio.h>
#include <stdint.h>
#include <windows.h>
#include <intrin.h>

#define SECRET_ADDR (char *)0x12345678

static inline void maccess(void *p) {
    volatile char dummy = *(char*)p;
}

static inline void flush(void *p) {
    _mm_clflush(p);
}

int main() {
    char *target_array = (char*)VirtualAlloc(NULL, 256 * 4096, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!target_array) return 1;
    
    while (1) {
        // Flush
        for (int i = 0; i < 256; i++) {
            flush(&target_array[i * 4096]);
        }
        
        // Wait
        Sleep(1);
        
        // Reload & Measure
        for (int i = 0; i < 256; i++) {
            unsigned int junk;
            uint64_t t1 = __rdtscp(&junk);
            maccess(&target_array[i * 4096]);
            uint64_t t2 = __rdtscp(&junk);
            if (t2 - t1 < 100) { 
                // Cache hit
            }
        }
    }
    VirtualFree(target_array, 0, MEM_RELEASE);
    return 0;
}
