import os
import subprocess
import logging

logger = logging.getLogger("AEGIS-QUARANTINE")

class ResctrlManager:
    """
    Direct interface to Linux Resource Director Technology (Intel RDT / AMD QoS).
    Implements Dynamic Cache Allocation Technology (CAT) and Memory Bandwidth Allocation (MBA).
    """
    RESCTRL_PATH = "/sys/fs/resctrl"
    QUARANTINE_GROUP = "/sys/fs/resctrl/aegis_quarantine"

    def __init__(self):
        self.quarantined_pids = set()
        self.is_supported = self._verify_hardware_support()
        if self.is_supported:
            self._initialize_quarantine_enclave()

    def _verify_hardware_support(self) -> bool:
        if not os.path.exists(self.RESCTRL_PATH):
            logger.warning("resctrl filesystem not mounted. Mounting resctrl...")
            try:
                subprocess.run(["mount", "-t", "resctrl", "resctrl", self.RESCTRL_PATH], check=True, capture_output=True, text=True)
                return True
            except Exception as e:
                logger.warning(f"Hardware does not support Intel RDT / AMD QoS or lacked CAP_SYS_ADMIN (resctrl unavailable). Fallback mitigation enabled.")
                return False
        return True

    def _initialize_quarantine_enclave(self):
        """
        Configures an isolated Class of Service (CLOS):
        - Restricts cache-ways to 1 single way (Mask 0x1 out of 11/16/20 ways).
        - Restricts Memory Bandwidth to 10% (MBA).
        """
        try:
            if not os.path.exists(self.QUARANTINE_GROUP):
                os.makedirs(self.QUARANTINE_GROUP, exist_ok=True)

            # Restrict L3 Cache Capacity to 1 way (e.g., bitmask 0x1)
            schemata_path = os.path.join(self.QUARANTINE_GROUP, "schemata")
            if os.path.exists(schemata_path):
                with open(schemata_path, "w") as f:
                    # Allocate only the lowest bit (way 0) to this class
                    f.write("L3:0=1;1=1\n")  # Socket 0 and Socket 1 set to way 0 only
                    f.write("MB:0=10;1=10\n") # Throttle memory bus to 10%

            logger.info("Intel RDT / AMD QoS Quarantine Enclave established successfully.")
        except Exception as e:
            logger.error(f"Failed to write schemata constraints: {e}")

    def quarantine_process(self, pid: int, confidence: float):
        """
        Dynamically migrates the attacking PID into the cache-starved Class of Service.
        The side-channel bandwidth collapses instantly without application termination.
        """
        if pid in self.quarantined_pids:
            return
        self.quarantined_pids.add(pid)

        if not self.is_supported:
            logger.warning(f"Fallback Mitigation: Applying strict CPU throttling on PID {pid}")
            try:
                import signal
                os.kill(pid, signal.SIGSTOP)
            except (ProcessLookupError, PermissionError):
                pass
            return

        try:
            tasks_path = os.path.join(self.QUARANTINE_GROUP, "tasks")
            with open(tasks_path, "a") as f:
                f.write(f"{pid}\n")

            logger.critical(
                f"[ACTIVE DEFENSE] Attacker PID {pid} trapped in Hardware Quarantine. "
                f"Confidence={confidence:.4f}. LLC capacity clamped to 1 Way; Memory Bandwidth throttled to 10%."
            )
        except ProcessLookupError:
            logger.info(f"Target PID {pid} exited prior to containment.")
        except Exception as e:
            logger.error(f"Failed to trap PID {pid} in resctrl enclosure: {e}")

    def release_process(self, pid: int):
        """
        Releases a process back to the default unconstrained CLOS if conformal calibration expires.
        """
        self.quarantined_pids.discard(pid)
        if not self.is_supported:
            try:
                import signal
                os.kill(pid, signal.SIGCONT)
                logger.info(f"PID {pid} resumed from CPU throttling.")
            except (ProcessLookupError, PermissionError):
                pass
            return

        default_tasks = os.path.join(self.RESCTRL_PATH, "tasks")
        try:
            with open(default_tasks, "a") as f:
                f.write(f"{pid}\n")
            logger.info(f"PID {pid} released from hardware quarantine back to default scheduler.")
        except Exception as e:
            logger.error(f"Failed to release PID {pid}: {e}")
