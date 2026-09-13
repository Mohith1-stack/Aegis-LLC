#include <stdio.h>
#include <stdint.h>
#include <x86intrin.h>

#define SECRET_ADDR (char *)0x12345678 // Dummy address

static inline void maccess(void *p) {
    asm volatile("movq (%0), %%rax\n" : : "c"(p) : "rax");
}

static inline void flush(void *p) {
    asm volatile("clflush 0(%0)\n" : : "c"(p) : "rax");
}

int main() {
    char target_array[256 * 4096];
    
    while (1) {
        // Flush
        for (int i = 0; i < 256; i++) {
            flush(&target_array[i * 4096]);
        }
        
        // Wait
        for (volatile int z = 0; z < 1000; z++) {}
        
        // Reload & Measure
        for (int i = 0; i < 256; i++) {
            unsigned int junk;
            uint64_t t1 = __rdtscp(&junk);
            maccess(&target_array[i * 4096]);
            uint64_t t2 = __rdtscp(&junk);
            if (t2 - t1 < 100) { // cache hit threshold
                // Address accessed by victim
            }
        }
    }
    return 0;
}
