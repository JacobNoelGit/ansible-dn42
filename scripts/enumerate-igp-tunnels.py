#!/usr/bin/env python3
"""
Enumerate intra-AS tunnel settings for AS4242421080. This script generates a list of intra-AS neighbours for each node (mesh and non-mesh), as well as which Wireguard ports to connect to.
This was split from the Ansible playbook to allow for more flexibility.
"""
import itertools
import os
import pprint

from _common import *

OUTFILE = "global-config/igp-tunnels.yml"
START_PORT = 55000  # Port to start building tunnels from

def _read_previous_settings():
    if os.path.exists(OUTFILE):
        with open(OUTFILE) as f:
            data = yaml.safe_load(f.read())
            return data
    else:  # Default template
        return {
            'next_port': START_PORT,
            'igp_neighbours': {},
            'igp_wg_ports': {},
        }

def main():
    data = _read_previous_settings()
    hosts = yaml_load('hosts.yml')

    dn42routers = get_hosts(hosts)
    meshrouters = hosts['meshrouters']['hosts']
    data['igp_neighbours'].clear()  # clear igp_neighbours, we will be rewriting it
    seen_shortnames = {}

    # For each router, populate a list of neighbours
    for server, serverdata in dn42routers.items():
        neighbours = data['igp_neighbours'].setdefault(server, set())

        # Sanity check: make sure there are no duplicate shortnames
        shortname = serverdata['shortname']
        if shortname in seen_shortnames:
            raise ValueError(f"Duplicate shortname {shortname}: {seen_shortnames[shortname]}, {server}")
        seen_shortnames[shortname] = server

        if server in meshrouters:
            # For servers in meshrouters group, add all other nodes in the mesh
            neighbours |= set(meshrouters)
            neighbours.remove(server)

        # For leaf servers, add all nodes specified in igp_upstreams
        igp_upstreams = set(serverdata.get('igp_upstreams', []))

        # ^ in this case is logical xor
        if not ((server in meshrouters) ^ bool(igp_upstreams)):
            raise ValueError(f'{server} must either define igp_upstreams or be part of meshrouters group (and not both)')

        neighbours |= igp_upstreams
        for neighbour in igp_upstreams:
            # Add ourselves as neighbour to all of our upstreams
            data['igp_neighbours'].setdefault(neighbour, set()).add(server)

    # Now populate ports for each combination of routers. This simplfies by including all routers, even those that aren't directly connected
    ports = data['igp_wg_ports']
    for cmb in itertools.combinations(dn42routers, 2):
        # Join tuples together as they are not a native YAML type
        cmb_reverse = ','.join((cmb[1], cmb[0]))
        cmb = ','.join(cmb)
        if cmb not in ports or cmb_reverse not in ports:
            # Only add combinations we haven't seen before
            print(f"Adding port {data['next_port']} for IGP link {cmb}")
            ports[cmb] = ports[cmb_reverse] = data['next_port']
            data['next_port'] += 1
        else:
            print(f"Using existing port {ports[cmb]} for IGP link {cmb}")

    pprint.pprint(data)
    with open(OUTFILE, 'w') as f:
        f.write(f'# Generated by {os.path.basename(__file__)}, do not edit!\n')
        f.write(yaml.safe_dump(data))

if __name__ == '__main__':
    main()
