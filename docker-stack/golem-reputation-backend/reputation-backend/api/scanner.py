#!/usr/bin/env python3
import asyncio
import csv
import json
import pathlib
import sys
import subprocess
from datetime import datetime, timedelta
from django.utils import timezone
from .models import Provider, NodeStatusHistory
from asgiref.sync import sync_to_async
from yapapi import props as yp
from yapapi.config import ApiConfig
from yapapi.log import enable_default_logger
from yapapi.props.builder import DemandBuilder
from yapapi.rest import Configuration, Market
from core.celery import app
from django.db.models import Q
from django.db.models import Case, When, Value, F
from django.db import transaction

@app.task()
def update_providers_info(node_props):
    node_ids = [prop['node_id'] for prop in node_props]
    existing_providers = Provider.objects.filter(node_id__in=node_ids)
    existing_providers_dict = {provider.node_id: provider for provider in existing_providers}

    create_batch = []

    for props in node_props:
        prop_data = {key: value for key, value in props.items() if key.startswith("golem.com.payment.platform.") and key.endswith(".address")}
        provider_data = {
            "payment_addresses": prop_data,
            "network": 'testnet' if any(key in TESTNET_KEYS for key in props.keys()) else 'mainnet',
            "cores": props.get("golem.inf.cpu.cores"),
            "memory": props.get("golem.inf.mem.gib"),
            "cpu": props.get("golem.inf.cpu.brand"),
            "runtime": props.get("golem.runtime.name"),
            "runtime_version": props.get("golem.runtime.version"),
            "threads": props.get("golem.inf.cpu.threads"),
            "storage": props.get("golem.inf.storage.gib"),
            "name": props.get("golem.node.id.name"),
        }

        issuer_id = props['node_id']
        if issuer_id in existing_providers_dict:
            provider_instance = existing_providers_dict[issuer_id]
            for key, value in provider_data.items():
                setattr(provider_instance, key, value)
            update_fields_list = [field for field in provider_data.keys() if field != 'node_id']
            provider_instance.save(update_fields=update_fields_list)
        else:
            create_batch.append(Provider(node_id=issuer_id, **provider_data))

    Provider.objects.bulk_create(create_batch)


TESTNET_KEYS = [
                "golem.com.payment.platform.erc20-goerli-tglm.address",
                "golem.com.payment.platform.erc20-mumbai-tglm.address",
                "golem.com.payment.platform.erc20-holesky-tglm.address",
                "golem.com.payment.platform.erc20next-goerli-tglm.address",
                "golem.com.payment.platform.erc20next-mumbai-tglm.address",
                "golem.com.payment.platform.erc20next-holesky-tglm.address"
            ]

examples_dir = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(examples_dir))
from .utils import build_parser, print_env_info, format_usage  # noqa: E402

import redis

def update_nodes_status(provider_id, is_online_now):
    provider, created = Provider.objects.get_or_create(node_id=provider_id)

    # Check the last status in the NodeStatusHistory
    last_status = NodeStatusHistory.objects.filter(provider=provider).last()
    
    if not last_status or last_status.is_online != is_online_now:
        # Create a new status entry if there's a change in status
        NodeStatusHistory.objects.create(provider=provider, is_online=is_online_now)



@app.task(queue='uptime', options={'queue': 'uptime', 'routing_key': 'uptime'})
def update_nodes_data(node_props):
    r = redis.Redis(host='redis', port=6379, db=0)

    for props in node_props:
        issuer_id = props['node_id']
        is_online_now = check_node_status(issuer_id)
        print(f"Updating NodeStatus for {issuer_id} with is_online_now={is_online_now}")
        try:
            update_nodes_status(issuer_id, is_online_now)
            r.set(f"provider:{issuer_id}:status", str(is_online_now))
        except Exception as e:
            print(f"Error updating NodeStatus for {issuer_id}: {e}")

    provider_ids_in_props = {props['node_id'] for props in node_props}
    previously_online_providers_ids = Provider.objects.filter(
        nodestatushistory__is_online=True
    ).distinct().values_list('node_id', flat=True)
    
    provider_ids_not_in_scan = set(previously_online_providers_ids) - provider_ids_in_props

    for issuer_id in provider_ids_not_in_scan:
        is_online_now = check_node_status(issuer_id)
        print(f"Verifying NodeStatus for {issuer_id} with is_online_now={is_online_now}")
        try:
            update_nodes_status(issuer_id, is_online_now)
            r.set(f"provider:{issuer_id}:status", str(is_online_now))
        except Exception as e:
            print(f"Error verifying/updating NodeStatus for {issuer_id}: {e}")



def check_node_status(issuer_id):
    try:
        process = subprocess.run(
            ["yagna", "net", "find", issuer_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5  # 5-second timeout for the subprocess
        )

        # Process finished, return True if it was successful and "seen:" is in the output
        return process.returncode == 0 and "seen:" in process.stdout.decode()
    except subprocess.TimeoutExpired as e:
        print("Timeout reached while checking node status", e)
        return False
    except Exception as e:
        print(f"Unexpected error checking node status: {e}")
        return False

async def list_offers(conf: Configuration, subnet_tag: str, current_scan_providers, node_props):
    nodes_data = {}
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
                        event.props['node_id'] = event.issuer
                        node_props.append(event.props)
                    else:
                        # Check if there is an existing 'wasmtime' entry for the same issuer
                        existing_entry = next((item for item in node_props if item['node_id'] == event.issuer and item.get("golem.runtime.name") == "wasmtime"), None)
                        if existing_entry and event.props.get("golem.runtime.name") == "vm":
                            # Replace the existing 'wasmtime' entry with the 'vm' entry
                            node_props[node_props.index(existing_entry)] = event.props


                    
                    

async def monitor_nodes_status(subnet_tag: str = "public"):
    node_props = []
    current_scan_providers = set()

    # Call list_offers with a timeout
    try:
        await asyncio.wait_for(
            list_offers(
                Configuration(api_config=ApiConfig()),
                subnet_tag=subnet_tag,
                node_props=node_props,
                current_scan_providers=current_scan_providers
            ),
            timeout=30  # 30-second timeout for each scan
        )
    except asyncio.TimeoutError:
        print("Scan timeout reached")

    # Delay update_nodes_data call using Celery
    update_nodes_data.delay(node_props)
    update_providers_info.delay(node_props)

    