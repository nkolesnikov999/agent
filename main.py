import http.server
import socketserver
import json
import parsing_netbox
import jun_collect

PORT = 8043
DIRECTORY = "result"
ADDRESS = "0.0.0.0"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

if __name__ == "__main__":

    data = dict()
    connections = parsing_netbox.get_netbox_cables()
    exporters = parsing_netbox.get_netbox_devices()
    data["exporters"] = exporters

    for exporter in exporters.keys():
        print(exporter)
        # host = "10.27.193.80" #TODO
        host = exporter
        if_data = jun_collect.get_interface_info(host) # set exporter/host
        device_name = exporters[exporter]["name"]
        for interface in if_data:
            if_name = if_data[interface]["name"]
            connection = connections.get(device_name, {}).get(if_name)
            if connection is not None:
                # print(device_name, if_name, connection)
                if_data[interface]["connection"] = connection
            else:
                if_data[interface]["connection"] = {
                    "device": "",
                    "interface": ""
                }
        exporters[exporter]["interfaces"] = if_data

        if_nhs = jun_collect.get_nexthops(host)
        nhs = {}
        for nh in if_nhs.keys():
            nhs[nh] = {}
            dev = exporters.get(nh, {})
            nhs[nh]["name"] = dev.get("name", "")
            nhs[nh]["site"] = dev.get("site", "")
            nhs[nh]["regions"] = dev.get("regions", [])
            nhs[nh]["labels"] = if_nhs[nh]

        exporters[exporter]["nexthops"] = nhs

        mpls_labels = jun_collect.get_mpls_labels(host)
        exporters[exporter]["mpls_labels"] = mpls_labels


    with open("result/tmp.json", "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

    with socketserver.TCPServer((ADDRESS, PORT), Handler) as httpd:
        print(f"Serving http://{ADDRESS}:{PORT}/tmp.json")
        httpd.serve_forever()
