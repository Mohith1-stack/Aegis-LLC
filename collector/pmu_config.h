#ifndef PMU_CONFIG_H
#define PMU_CONFIG_H

/* Intel PMU Event Hex Codes (Example for Skylake/Ice Lake) */
#define PERF_EV_INST_RETIRED 0x00C0
#define PERF_EV_CPU_CYCLES   0x003C
#define PERF_EV_LLC_MISSES   0x412E
#define PERF_EV_BR_MISPRED   0x00C5
#define PERF_EV_L1D_MISS     0x0151

/* AMD PMU Event Hex Codes (Example for Zen 3) */
#define AMD_EV_INST_RETIRED  0x00C0
#define AMD_EV_CPU_CYCLES    0x0076
#define AMD_EV_LLC_MISSES    0x0343
#define AMD_EV_BR_MISPRED    0x00C3
#define AMD_EV_L1D_MISS      0x0041

#endif
