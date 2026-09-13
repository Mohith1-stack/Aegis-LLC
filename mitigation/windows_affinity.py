import ctypes
import logging

logger = logging.getLogger("AEGIS-WIN-AFFINITY")

class WindowsAffinityManager:
    """
    Windows-specific mitigation engine.
    Lacking Intel RDT resctrl on Windows user-space, this isolates an attacker
    by pinning it to a single CPU core and dropping its scheduling priority.
    """
    def __init__(self):
        self.kernel32 = ctypes.windll.kernel32
        
        # Windows Constants
        self.PROCESS_ALL_ACCESS = 0x1F0FFF
        self.IDLE_PRIORITY_CLASS = 0x00000040
        
        logger.info("Windows Process Affinity Mitigation Engine Initialized.")

    def quarantine_process(self, pid: int, confidence: float):
        try:
            # 1. Open Process
            hProcess = self.kernel32.OpenProcess(self.PROCESS_ALL_ACCESS, False, pid)
            if not hProcess:
                logger.error(f"Failed to open process {pid} for quarantine.")
                return

            # 2. Set CPU Affinity to core 0 (bitmask 0x1)
            # This traps the process on a single logical core, minimizing shared cache access
            success = self.kernel32.SetProcessAffinityMask(hProcess, 1)
            if not success:
                logger.warning(f"Failed to set affinity for PID {pid}.")

            # 3. Drop Priority to IDLE
            success = self.kernel32.SetPriorityClass(hProcess, self.IDLE_PRIORITY_CLASS)
            if not success:
                logger.warning(f"Failed to set IDLE priority for PID {pid}.")

            logger.critical(
                f"[ACTIVE DEFENSE WINDOWS] Attacker PID {pid} trapped. "
                f"Confidence={confidence:.4f}. Pinned to Core 0 with IDLE priority."
            )
            
            self.kernel32.CloseHandle(hProcess)
            
        except Exception as e:
            logger.error(f"Failed to quarantine PID {pid} on Windows: {e}")

    def release_process(self, pid: int):
        # In a full implementation, this would restore the original affinity mask
        logger.info(f"PID {pid} released logic triggered (not fully implemented for Windows).")
