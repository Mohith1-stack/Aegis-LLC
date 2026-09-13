import time

def run_web_workload():
    print("Starting benign web parsing workload...")
    # Simulate headless browser layout rendering memory access patterns
    while True:
        # Create lots of small string objects and dicts to cause GC pressure
        dom_tree = [{"tag": f"div_{i}", "content": "hello world" * 10} for i in range(10000)]
        time.sleep(0.5)

if __name__ == "__main__":
    run_web_workload()
