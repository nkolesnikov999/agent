import xml.etree.ElementTree as ET

def parse_inet3_to_dict(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    nexthops = {}

    for rt in root.findall(".//rt"):
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

    return {"nexthops": nexthops}

def parse_mpls_to_dict(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    labels = {}
    for rt in root.findall(".//rt"):
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

    return {"labels": labels}

# Пример использования
# result = parse_inet3_to_dict("inet.3.xml")
result = parse_mpls_to_dict("mpls.0.xml")
print(result)