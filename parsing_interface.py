from lxml import etree

# Загрузка XML из файла
with open("interfaces.xml", "rb") as f:
    xml_content = f.read()

# Парсинг XML
tree = etree.fromstring(xml_content)

# Используем namespace, если потребуется
namespaces = {
    "junos": "http://yang.juniper.net/junos/rpc/interfaces"
}

# Список для хранения результатов
logical_interfaces = []

# Проход по всем physical-interface > logical-interface
for physical in tree.findall(".//physical-interface"):
    speed = physical.find("speed")
    for logical in physical.findall("logical-interface"):
        name_elem = logical.find("name")
        snmp_index_elem = logical.find("snmp-index")

        if name_elem is not None and snmp_index_elem is not None:
            name = name_elem.text.strip()
            snmp_index = snmp_index_elem.text.strip()
            logical_interfaces.append((name, snmp_index))

# Выводим пары name, snmp-index
for name, snmp_index in logical_interfaces:
    print(f"{name}: {snmp_index}")
