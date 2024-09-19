#!/usr/bin/env python3
import redis
import requests
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
r = redis.Redis(host='redis', port=6379, db=0)


@app.task(queue='default', options={'queue': 'default', 'routing_key': 'default'})
def update_providers_info(node_props):
    provider_data = []
    for props in node_props:
        prop_data = {key: value for key, value in props.items() if key.startswith(
            "golem.com.payment.platform.") and key.endswith(".address")}
        provider_data.append({
            "node_id": props['node_id'],
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
        })

    node_ids = [data['node_id'] for data in provider_data]
    existing_providers = {
        provider.node_id: provider
        for provider in Provider.objects.filter(node_id__in=node_ids)
    }

    providers_to_create = []
    providers_to_update = []

    for data in provider_data:
        if data['node_id'] in existing_providers:
            provider = existing_providers[data['node_id']]
            for key, value in data.items():
                setattr(provider, key, value)
            providers_to_update.append(provider)
        else:
            providers_to_create.append(Provider(**data))

    Provider.objects.bulk_create(providers_to_create, ignore_conflicts=True)
    Provider.objects.bulk_update(
        providers_to_update,
        fields=[field for field in provider_data[0].keys() if field !=
                'node_id']
    )


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


def check_node_status(issuer_id):
    node_id_no_prefix = issuer_id[2:] if issuer_id.startswith(
        '0x') else issuer_id
    url = f"http://yacn2.dev.golem.network:9000/nodes/{node_id_no_prefix}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        node_key = issuer_id.lower()
        node_info = data.get(node_key)

        if node_info:
            if isinstance(node_info, list):
                if node_info == [] or node_info == [None]:
                    return False
                else:
                    return any('seen' in item for item in node_info if item)
            else:
                return False
        else:
            return False
    except requests.exceptions.RequestException as e:
        print(
            f"HTTP request exception when checking node status for {issuer_id}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error checking node status for {issuer_id}: {e}")
        return False


async def list_offers(conf: Configuration, subnet_tag: str, current_scan_providers, node_props):
    nodes_data = {}
    async with conf.market() as client:
        market_api = Market(client)
        dbuild = DemandBuilder()
        dbuild.add(yp.NodeInfo(
            name="some scanning node", subnet_tag=subnet_tag))
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
                        existing_entry = next((item for item in node_props if item['node_id'] == event.issuer and item.get(
                            "golem.runtime.name") == "wasmtime"), None)
                        if existing_entry and event.props.get("golem.runtime.name") == "vm":
                            # Replace the existing 'wasmtime' entry with the 'vm' entry
                            node_props[node_props.index(
                                existing_entry)] = event.props


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
    update_providers_info.delay(node_props)
