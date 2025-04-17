from http.client import responses

from ncclient import manager
from lxml import etree

import config

# host = "10.27.193.80"
port = 830
username = ""
password = ""

rpc_interface = """
  <get-interface-information xmlns="http://yang.juniper.net/junos/rpc/interfaces"/>
"""

rpc_mpls_0 = """
    <get-route-information xmlns="http://yang.juniper.net/junos/rpc/route">
        <table>mpls.0</table>
    </get-route-information>
"""

rpc_inet_3 = """
    <get-route-information xmlns="http://yang.juniper.net/junos/rpc/route">
        <table>inet.3</table>
    </get-route-information>
"""

responces = {}

def rpc_devices(ip_host):
    if ip_host == "10.27.193.80" or ip_host == "192.168.100.3":
        username = "lab"
        password = "lab123"
    else:
        username = config.username
        password = config.password
    try:
        with manager.connect(
            host=ip_host,
            port=port,
            username=username,
            password=password,
            hostkey_verify=False,
            device_params={"name": "junos"},
            allow_agent=False,
            look_for_keys=False,
            timeout=30
        ) as conn:

            if ip_host not in responces:
                responces[ip_host] = {}

            responces[ip_host]["interfaces"] = conn.rpc(rpc_interface).tostring
            responces[ip_host]["nhs"] = conn.rpc(rpc_inet_3).tostring
            responces[ip_host]["mpls_labels"] = conn.rpc(rpc_mpls_0).tostring

    except Exception as e:
        print(f"Ошибка при получении данных с устройства: {e}")
        if ip_host in responces:
            responces[ip_host] = {}



def get_interface_info(host):
    response = responces.get(host, {}).get("interfaces")
    lg_interfaces = parsing_interfaces(response)

    return lg_interfaces

def parsing_interfaces(xml_content):
    if xml_content is None:
        return {}
    tree = etree.fromstring(xml_content)

    # Список для хранения результатов
    logical_interfaces = dict()

    # Проход по всем physical-interface > logical-interface
    for physical in tree.findall(".//physical-interface"):
        speed_elem = physical.find("speed")
        if speed_elem is None:
            speed = ""
        else:
            speed = speed_elem.text.strip()
        for logical in physical.findall("logical-interface"):
            name_elem = logical.find("name")
            snmp_index_elem = logical.find("snmp-index")
            description_elem = logical.find("description")
            if description_elem is None:
                description = ""
            else:
                description = description_elem.text.strip()
            if name_elem is not None and snmp_index_elem is not None:
                name = name_elem.text.strip()
                snmp_index = snmp_index_elem.text.strip()
                logical_interfaces[snmp_index] = dict()
                logical_interfaces[snmp_index]["name"] = name
                logical_interfaces[snmp_index]["speed"] = speed
                logical_interfaces[snmp_index]["description"] = description


    return logical_interfaces

def get_nexthops(host):
    response = responces.get(host, {}).get("nhs")
    nhs = parsing_inet3(response)

    return nhs

def parsing_inet3(xml_content):
    if xml_content is None:
        return {}
    tree = etree.fromstring(xml_content)
    nexthops = {}
    for rt in tree.findall(".//rt"):
        destination = rt.findtext("rt-destination", default="").split("/")[0]
        if not destination:
            continue

        nexthops[destination] = {}

        for nh in rt.findall(".//nh"):
            via = nh.findtext("via", default="").strip()
            if not via:
                continue

            label = nh.findtext("mpls-label", default="").strip()
            if label.startswith("Push"):
                label = label.replace("Push", "").strip()
            nexthops[destination][via] = label

    return nexthops

def get_mpls_labels(host):
    response = responces.get(host, {}).get("mpls_labels")
    mpls_labels = parsing_mpls0(response)

    return mpls_labels

def parsing_mpls0(xml_content):
    if xml_content is None:
        return {}
    tree = etree.fromstring(xml_content)
    labels = {}
    for rt in tree.findall(".//rt"):
        destination = rt.findtext("rt-destination", default="")
        if not destination:
            continue

        labels[destination] = {}

        for nh in rt.findall(".//nh"):
            via = nh.findtext("via", default="").strip()
            if not via:
                continue

            label = nh.findtext("mpls-label", default="").strip()
            if not label:
                continue
            # if label.startswith("Push"):
            #     label = label.replace("Push", "").strip()
            parts = label.split()
            action = parts[0]
            value = parts[1] if len(parts) > 1 else ""
            labels[destination][via] = {
                "action": action,
                "label": value
            }

        if not labels[destination]:
            del labels[destination]

    return labels

# if __name__ == "__main__":
#     print(get_nexthops_info("10.27.193.80"))
