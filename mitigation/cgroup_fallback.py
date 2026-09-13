import os
import logging

logger = logging.getLogger("AEGIS-CGROUP-FALLBACK")

class CgroupFallbackManager:
    """
    Fallback mitigation mechanism when Intel RDT is unavailable.
    Freezes or strictly throttles CPU shares for the attacking PID using cgroups v2.
    """
    CGROUP_PATH = "/sys/fs/cgroup/aegis_fallback"

    def __init__(self):
        self._initialize_cgroup()

    def _initialize_cgroup(self):
        try:
            if not os.path.exists(self.CGROUP_PATH):
                os.makedirs(self.CGROUP_PATH, exist_ok=True)
            
            # Restrict CPU usage severely
            with open(os.path.join(self.CGROUP_PATH, "cpu.max"), "w") as f:
                f.write("1000 100000\n") # 1% CPU allowance
            
            logger.info("Cgroup v2 fallback mitigation initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize cgroups fallback: {e}")

    def throttle_process(self, pid: int):
        try:
            with open(os.path.join(self.CGROUP_PATH, "cgroup.procs"), "a") as f:
                f.write(f"{pid}\n")
            logger.critical(f"PID {pid} throttled via cgroups v2 fallback.")
        except Exception as e:
            logger.error(f"Failed to throttle PID {pid}: {e}")
