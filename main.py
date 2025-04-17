import http.server
import socketserver
import json

import config
import parsing_netbox
import jun_collect
import threading
import schedule
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

PORT = 8043
DIRECTORY = "result"
ADDRESS = "0.0.0.0"
EXPORT_FILE = "result/tmp.json"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)


def process_exporter(exporter, connections, exporters):
    try:
        print(f"[DEBUG] Processing exporter: {exporter}")
        jun_collect.rpc_devices(exporter)

        if_data = jun_collect.get_interface_info(exporter)
        device_name = exporters[exporter]["name"]

        for interface in if_data:
            if_name = if_data[interface]["name"]
            connection = connections.get(device_name, {}).get(if_name)
            if connection is not None:
                if_data[interface]["connection"] = connection
            else:
                if_data[interface]["connection"] = {
                    "device": "",
                    "interface": ""
                }

        if_nhs = jun_collect.get_nexthops(exporter)
        nhs = {}
        for nh in if_nhs.keys():
            nhs[nh] = {}
            dev = exporters.get(nh, {})
            nhs[nh]["name"] = dev.get("name", "")
            nhs[nh]["site"] = dev.get("site", "")
            nhs[nh]["regions"] = dev.get("regions", [])
            nhs[nh]["labels"] = if_nhs[nh]

        mpls_labels = jun_collect.get_mpls_labels(exporter)

        return exporter, {
            "interfaces": if_data,
            "nexthops": nhs,
            "mpls_labels": mpls_labels
        }

    except Exception as e:
        print(f"[ERROR] Failed to process exporter {exporter}: {e}")
        raise

def collect_and_write_data():
    print("[INFO] Starting data collection...")
    data = dict()
    connections = parsing_netbox.get_netbox_cables()
    exporters = parsing_netbox.get_netbox_devices()
    data["exporters"] = exporters

    futures = {}
    with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
        for exporter in exporters.keys():
            future = executor.submit(process_exporter, exporter, connections, exporters)
            futures[future] = exporter

        for future in as_completed(futures):
            exporter_key, result = future.result()
            exporters[exporter_key]["interfaces"] = result["interfaces"]
            exporters[exporter_key]["nexthops"] = result["nexthops"]
            exporters[exporter_key]["mpls_labels"] = result["mpls_labels"]

    with open(EXPORT_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
    print("[INFO] Data collection complete.")

def run_scheduler():
    schedule.every(config.update_time).minutes.do(collect_and_write_data)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    # Запускаем планировщик в отдельном потоке
    threading.Thread(target=run_scheduler, daemon=True).start()

    # Создаём стартовый tmp.json (на случай если его нет)
    try:
        collect_and_write_data()
    except Exception as e:
        print(f"[ERROR] Initial data collection failed: {e}")

    # Запускаем HTTP сервер
    with socketserver.TCPServer((ADDRESS, PORT), Handler) as httpd:
        print(f"Serving http://{ADDRESS}:{PORT}/tmp.json")
        httpd.serve_forever()