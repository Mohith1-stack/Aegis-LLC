from flask import Flask, jsonify
from flask_cors import CORS
import psutil
import platform
import os

app = Flask(__name__)
CORS(app)

@app.route('/api/specs', methods=['GET'])
def get_specs():
    try:
        mem = psutil.virtual_memory()
        cpu_freq = psutil.cpu_freq()
        disk = psutil.disk_usage(os.path.abspath(os.sep))
        
        specs = {
            "os": f"{platform.system()} {platform.release()}",
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "ram_gb": f"{round(mem.total / (1024**3), 2)} GB",
            "physical_cores": psutil.cpu_count(logical=False) or 0,
            "logical_cores": psutil.cpu_count(logical=True) or 0,
            "cpu_freq": f"{round(cpu_freq.current / 1000, 2)} GHz" if cpu_freq else "Unknown",
            "l3_cache": "12 MB (Simulated)", # OS-agnostic L3 cache fetching is complex
            "disk_total": f"{round(disk.total / (1024**3), 2)} GB",
            "vulnerable": True
        }
        return jsonify(specs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    try:
        status = {
            "active_processes": len(psutil.pids()),
            "cpu_loads": psutil.cpu_percent(interval=None, percpu=True)
        }
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Initialize CPU percent
    psutil.cpu_percent(interval=0.1, percpu=True)
    app.run(host='0.0.0.0', port=5000)
