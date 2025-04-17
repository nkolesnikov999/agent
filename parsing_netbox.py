import config
import requests

debug = False

netbox_address = config.netbox_address
payload = {}
nb_token = 'Token ' + config.netbox_token
headers = {
    'Accept': 'application/json',
    'Authorization': nb_token,
}

def get_netbox_devices():
    url = f'http://{netbox_address}/api/dcim/devices/'

    ips = dict()
    while url is not None:
        response = requests.request("GET", url, headers=headers, data=payload)
        next_url = response.json()['next']
        results = response.json()['results']
        for device in results:
            ip4 = name = 'None'
            if device['name']:
                name = device['name']
            if device['primary_ip4'] and device['primary_ip4']['address']:
                ip4 = device['primary_ip4']['address']
            if ip4 != 'None':
                site, regions = get_site_regions(name)
                ips[ip4.split('/')[0]] = {
                    "name": name,
                    "site": site,
                    "regions": regions
                }
            #print(name, ip4)
        url = next_url

    return ips

def get_site_regions(d_name: str):
    url = f'http://{netbox_address}/api/dcim/devices/?name={d_name}'

    response = requests.request("GET", url, headers=headers, data=payload)
    results = response.json()['results']
    if len(results) != 1:
        print('NOT FOUND in NETBOX, results: ', results)
        return
    site_url = results[0]['site']['url']
    if debug:
        print('Request to Site_URL:', site_url)
    site_response = requests.request("GET", site_url, headers=headers, data=payload)
    site_results = site_response.json()
    site_name = site_results['name']

    region_url = site_results['region']['url']
    regions = []

    while region_url:
        if debug:
            print('region_url:', region_url)
        region_responce = requests.request("GET", region_url, headers=headers, data=payload)
        region_results = region_responce.json()
        # print('Region name:', region_results['name'])
        regions.append(region_results['name'])
        if region_results['parent']:
            region_url = region_results['parent']['url']
        else:
            break
    if debug:
        print(site_name, regions)

    return (
        site_name, regions
    )

"""
curl -X 'GET' \
  'http://10.27.200.47:8000/api/dcim/cables/' \
  -H 'accept: application/json'
"""

def get_netbox_cables():
    url = f'http://{netbox_address}/api/dcim/cables/'

    connections = dict()
    while url is not None:
        response = requests.request("GET", url, headers=headers, data=payload)
        next_url = response.json()['next']
        results = response.json()['results']
        for cable in results:
            a_term = cable.get("a_terminations")
            b_term = cable.get("b_terminations")
            if a_term is not None and b_term is not None:
                if len(a_term) == 1 and len(b_term) == 1:
                    a_cable = a_term[0]
                    b_cable = b_term[0]
                    a_device = a_cable.get("object", {}).get("device", {}).get("name", "")
                    a_interface = a_cable.get("object", {}).get("name", "")
                    b_device = b_cable.get("object", {}).get("device", {}).get("name", "")
                    b_interface = b_cable.get("object", {}).get("name", "")
                    if a_device not in connections:
                        connections[a_device] = {}
                    connections[a_device][a_interface] = {
                        "device": b_device,
                        "interface": b_interface
                    }
                    if b_device not in connections:
                        connections[b_device] = {}
                    connections[b_device][b_interface] = {
                        "device": a_device,
                        "interface": a_interface
                    }

            #print(name, ip4)
        url = next_url

    return connections


# if __name__ == '__main__':
#     print(get_netbox_devices())
#     get_site_regions("dc2-cr12.sma")
#     print(get_netbox_cables())