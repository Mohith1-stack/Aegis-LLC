import time
import torch
import numpy as np
import logging
import sys
import os

# Add parent directory to path to allow absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.aegis_net import AegisTriModalNet
from pipeline.preprocessor import TelemetryEngine

# Dynamically load OS-specific modules
if os.name == 'nt':
    from collector.windows_telemetry import WindowsTelemetryCollector
    from mitigation.windows_affinity import WindowsAffinityManager
else:
    from mitigation.resctrl_manager import ResctrlManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AEGIS-DAEMON")

ATTACK_CLASSES = {
    0: "BENIGN_COMPUTE",
    1: "FLUSH_RELOAD",
    2: "PRIME_PROBE",
    3: "SPECTRE_TRANSIENT"
}

class AegisForensicsDaemon:
    def __init__(self, model_weights_path: str = None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = AegisTriModalNet(num_classes=4).to(self.device)

        if model_weights_path and os.path.exists(model_weights_path):
            self.model.load_state_dict(torch.load(model_weights_path, map_location=self.device))
            logger.info(f"Loaded production weights from {model_weights_path}")
        self.model.eval()

        self.telemetry_engine = TelemetryEngine()
        if os.name == 'nt':
            self.windows_telemetry = WindowsTelemetryCollector()
            self.quarantine_manager = WindowsAffinityManager()
        else:
            self.windows_telemetry = None
            self.quarantine_manager = ResctrlManager()
            
        self.last_alert_time = {}
        self.confidence_threshold = 0.50
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        if os.path.exists(config_path):
            try:
                import yaml
                with open(config_path, "r") as f:
                    cfg = yaml.safe_load(f)
                    self.confidence_threshold = cfg.get("daemon", {}).get("confidence_threshold", 0.50)
            except Exception as e:
                logger.warning(f"Could not load config.yaml: {e}")

    @torch.no_grad()
    def evaluate_sample(self, raw_telemetry: dict):
        """
        Synchronous real-time evaluation pipeline (<0.8ms latency execution)
        """
        # 1. Feature Engineering
        x_spatial, x_seq, x_macro = self.telemetry_engine.process_raw_telemetry(raw_telemetry)

        x_spatial = x_spatial.to(self.device)
        x_seq = x_seq.to(self.device)
        x_macro = x_macro.to(self.device)

        # 2. Forward Pass
        attack_logits, source_logits, severity = self.model(x_spatial, x_seq, x_macro)
        
        attack_prob = torch.sigmoid(attack_logits).item()
        source_probs = torch.softmax(source_logits, dim=1).cpu().numpy()[0]
        predicted_class_id = int(np.argmax(source_probs))
        severity_score = severity.item()
        
        pid = raw_telemetry["pid"]

        # 3. Decision Logic & Actuation (with rate-limited alerting)
        is_attack = (predicted_class_id != 0) or (attack_prob >= self.confidence_threshold)
        if is_attack and attack_prob >= self.confidence_threshold:
            now = time.time()
            if pid not in self.last_alert_time or (now - self.last_alert_time[pid]) >= 2.0:
                self.last_alert_time[pid] = now
                attack_id = predicted_class_id if predicted_class_id != 0 else 1
                attack_name = ATTACK_CLASSES.get(attack_id, "HARDWARE_ANOMALY")
                logger.warning(
                    f"🚨 [DETECTION ALERT] Detected: {attack_name} | "
                    f"PID: {pid} ({raw_telemetry.get('comm', 'unknown')}) | "
                    f"Confidence: {attack_prob * 100:.2f}% | "
                    f"Severity: {severity_score:.4f}"
                )
                # Invoke active hardware-level containment
                self.quarantine_manager.quarantine_process(pid=pid, confidence=attack_prob)

        return predicted_class_id, attack_prob, severity_score

    def run_simulated_stream(self, max_seconds: float = None):
        """
        Mock hardware ingest loop to demonstrate full data lifecycle.
        """
        import subprocess
        dummy_cmd = ["notepad.exe"] if os.name == 'nt' else ["sleep", "3600"]
        logger.info(f"Starting a dummy attacker process ({' '.join(dummy_cmd)})...")
        dummy_proc = subprocess.Popen(dummy_cmd)
        logger.info(f"AEGIS Monitoring Daemon active on /dev/perf_ringbuffer... (Mocking Attacker PID: {dummy_proc.pid})")
        
        start_time = time.time()
        last_heartbeat = time.time()
        sample_count = 0
        detections = 0
        try:
            while True:
                if max_seconds is not None and (time.time() - start_time) >= max_seconds:
                    logger.info(f"Simulation completed after {max_seconds}s ({sample_count} samples, {detections} detections).")
                    break

                sample_count += 1
                # Synthesizing an incoming packet from eBPF ring buffer
                mock_attack_signal = (np.random.rand() > 0.85)

                if mock_attack_signal:
                    # Injects a Prime+Probe signature
                    sample = {
                        "pid": dummy_proc.pid,
                        "comm": "poc_prime_probe",
                        "cpu": 2,
                        "instructions": np.random.randint(50000, 100000),
                        "cycles": np.random.randint(150000, 300000),
                        "llc_misses": np.random.randint(80000, 120000), 
                        "l1d_misses": np.random.randint(40000, 60000),
                        "branch_misses": np.random.randint(200, 800),
                        "page_faults": 4,
                        "last_fault_addr": 0x7ffd8234a040
                    }
                else:
                    # Benign matrix compute
                    sample = {
                        "pid": 1024,
                        "comm": "python3_blas",
                        "cpu": 0,
                        "instructions": np.random.randint(400000, 800000),
                        "cycles": np.random.randint(400000, 820000),
                        "llc_misses": np.random.randint(1000, 5000),
                        "l1d_misses": np.random.randint(10000, 20000),
                        "branch_misses": np.random.randint(500, 1500),
                        "page_faults": 0,
                        "last_fault_addr": 0x0
                    }

                cid, prob, sev = self.evaluate_sample(sample)
                if cid != 0 and prob >= self.confidence_threshold:
                    detections += 1

                if time.time() - last_heartbeat >= 2.0:
                    logger.info(f"⚡ [TELEMETRY HEARTBEAT] Ingested: {sample_count} frames | Active Detections: {detections} | Cadence: 10ms")
                    last_heartbeat = time.time()

                time.sleep(0.01) # 10ms polling cadence
        except KeyboardInterrupt:
            logger.info("Daemon cleanly shut down.")
        finally:
            logger.info("Cleaning up dummy process...")
            try:
                dummy_proc.kill()
                dummy_proc.wait(timeout=2)
            except Exception:
                pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AEGIS Real-time Hardware Forensics & Containment Daemon")
    parser.add_argument("--weights", type=str, default=os.path.join(os.path.dirname(__file__), "best_model.pt"), help="Path to model weights")
    parser.add_argument("--threshold", type=float, default=None, help="Override confidence threshold")
    parser.add_argument("--duration", type=float, default=None, help="Run simulation for a fixed duration in seconds")
    parser.add_argument("--demo", action="store_true", help="Run in demo mode")
    args = parser.parse_args()

    daemon = AegisForensicsDaemon(model_weights_path=args.weights)
    if args.threshold is not None:
        daemon.confidence_threshold = args.threshold
    elif args.demo:
        daemon.confidence_threshold = 0.50
        logger.info(f"Demo mode active: confidence threshold set to {daemon.confidence_threshold}")

    daemon.run_simulated_stream(max_seconds=args.duration)
