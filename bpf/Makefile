CLANG ?= clang
LLC ?= llc
BPFTOOL ?= bpftool

ARCH := $(shell uname -m | sed 's/x86_64/x86/' | sed 's/aarch64/arm64/')

INCLUDES := -I. -I/usr/include/bpf

CFLAGS := -g -O2 -target bpf -D__TARGET_ARCH_$(ARCH) $(INCLUDES)

all: aegis_telemetry.bpf.o

aegis_telemetry.bpf.o: aegis_telemetry.bpf.c vmlinux.h
	$(CLANG) $(CFLAGS) -c $< -o $@

vmlinux.h:
	$(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > vmlinux.h

clean:
	rm -f *.o vmlinux.h
