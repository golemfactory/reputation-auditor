#!/usr/bin/env python3
import asyncio
import csv
import json
import pathlib
import sys
import subprocess
from datetime import datetime, timezone, timedelta

from yapapi import props as yp
from yapapi.config import ApiConfig
from yapapi.log import enable_default_logger
from yapapi.props.builder import DemandBuilder
from yapapi.rest import Configuration, Market

examples_dir = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(examples_dir))
import utils

CSV_FILE = "nodes_status.csv"
SCAN_COUNT_FILE = "scan_count.txt"

def update_csv(issuer_id, is_online, nodes_data, scanned_times):
    with open(CSV_FILE, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["issuer_id", "is_online", "last_seen", "total_online_scans", "uptime"])
        for node_id, data in nodes_data.items():
            uptime = calculate_uptime(data["total_online_scans"], scanned_times)
            writer.writerow([node_id, data["is_online"], data["last_seen"], data["total_online_scans"], uptime])

def calculate_uptime(total_online_scans, scanned_times):
    return (total_online_scans / scanned_times) * 100 if scanned_times > 0 else 0

def check_node_status(issuer_id):
    try:
        result = subprocess.run(
            ["yagna", "net", "find", issuer_id],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0 and "seen:" in result.stdout
    except subprocess.TimeoutExpired:
        return False

def load_scan_count():
    if pathlib.Path(SCAN_COUNT_FILE).exists():
        with open(SCAN_COUNT_FILE, 'r') as file:
            return int(file.read().strip())
    return 0

def save_scan_count(scanned_times):
    with open(SCAN_COUNT_FILE, 'w') as file:
        file.write(str(scanned_times))

async def list_offers(conf: Configuration, subnet_tag: str, nodes_data, scanned_times, current_scan_providers):
    async with conf.market() as client:
        market_api = Market(client)
        dbuild = DemandBuilder()
        dbuild.add(yp.NodeInfo(name="some scanning node", subnet_tag=subnet_tag))
        dbuild.add(yp.Activity(expiration=datetime.now(timezone.utc)))

        async with market_api.subscribe(dbuild.properties, dbuild.constraints) as subscription:
            async for event in subscription.events():
                if event.issuer not in current_scan_providers:
                    current_scan_providers.add(event.issuer)

                    if event.issuer not in nodes_data:
                        nodes_data[event.issuer] = {
                            "last_seen": datetime.now(),
                            "is_online": True,
                            "total_online_scans": 1
                        }
                    else:
                        nodes_data[event.issuer]["is_online"] = True
                        nodes_data[event.issuer]["last_seen"] = datetime.now()
                        nodes_data[event.issuer]["total_online_scans"] += 1

                    update_csv(event.issuer, True, nodes_data, scanned_times)

async def monitor_nodes_status(subnet_tag: str = "public"):
    nodes_data = {}
    scanned_times = load_scan_count()

    if pathlib.Path(CSV_FILE).exists():
        with open(CSV_FILE, mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                nodes_data[row["issuer_id"]] = {
                    "last_seen": datetime.fromisoformat(row["last_seen"]),
                    "is_online": row["is_online"] == "True",
                    "total_online_scans": int(row["total_online_scans"])
                }

    scanned_times += 1
    save_scan_count(scanned_times)
    current_scan_providers = set()  # Initialize an empty set for the current scan

    try:
        await asyncio.wait_for(
            list_offers(
                Configuration(api_config=ApiConfig()),
                subnet_tag=subnet_tag,
                nodes_data=nodes_data,
                scanned_times=scanned_times,
                current_scan_providers=current_scan_providers
            ),
            timeout=30  # 30-second timeout for each scan
        )
    except asyncio.TimeoutError:
        print("Scan timeout reached")

    for node_id, data in nodes_data.items():
        
        if datetime.now() - data["last_seen"] > timedelta(seconds=30):
            print(f"We haven't seen node {node_id} for more than 30 seconds, checking its status...")
            is_online = check_node_status(node_id)
            

            data["is_online"] = is_online
            if not is_online:
                print(f"Node {node_id} is offline")
                data["total_online_scans"] -= 1  # Subtract one scan if the node is found offline
            else:
                print(f"Node {node_id} is online")
            update_csv(node_id, is_online, nodes_data, scanned_times)


def main():
    parser = utils.build_parser("List offers")
    args = parser.parse_args()

    subnet = args.subnet_tag or "public"
    sys.stderr.write(f"Using subnet: {utils.TEXT_COLOR_YELLOW}{subnet}{utils.TEXT_COLOR_DEFAULT}\n")

    enable_default_logger()
    asyncio.run(monitor_nodes_status(subnet))

if __name__ == "__main__":
    main()
