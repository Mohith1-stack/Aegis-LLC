#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>

struct record_t {
    __u64 timestamp;
    __u32 pid;
    __u32 cpu;
    __u64 instructions;
    __u64 cycles;
    __u64 llc_misses;
    __u64 branch_misses;
    __u64 l1d_misses;
    char comm[16];
};

struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 512 * 1024);
} ringbuf SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_PERF_EVENT_ARRAY);
    __uint(key_size, sizeof(__u32));
    __uint(value_size, sizeof(__u32));
} pmu_instructions SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_PERF_EVENT_ARRAY);
    __uint(key_size, sizeof(__u32));
    __uint(value_size, sizeof(__u32));
} pmu_llc_miss SEC(".maps");

SEC("perf_event")
int on_pmu_sample(struct bpf_perf_event_data *ctx) {
    struct record_t *rec = bpf_ringbuf_reserve(&ringbuf, sizeof(*rec), 0);
    if (!rec) return 0;

    __u64 pid_tgid = bpf_get_current_pid_tgid();
    rec->timestamp = bpf_ktime_get_ns();
    rec->pid = (__u32)pid_tgid;
    rec->cpu = bpf_get_smp_processor_id();
    bpf_get_current_comm(&rec->comm, sizeof(rec->comm));

    rec->instructions = bpf_perf_event_read(&pmu_instructions, rec->cpu);
    rec->llc_misses = bpf_perf_event_read(&pmu_llc_miss, rec->cpu);

    bpf_ringbuf_submit(rec, 0);
    return 0;
}

char LICENSE[] SEC("license") = "GPL";
