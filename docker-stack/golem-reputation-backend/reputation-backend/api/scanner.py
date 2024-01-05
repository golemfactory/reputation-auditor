#!/usr/bin/env python3
import asyncio
import csv
import json
import pathlib
import sys
import subprocess
from datetime import datetime, timedelta
from django.utils import timezone
from .models import Provider, NodeStatus, ScanCount, async_get_or_create, async_save
from asgiref.sync import sync_to_async
from yapapi import props as yp
from yapapi.config import ApiConfig
from yapapi.log import enable_default_logger
from yapapi.props.builder import DemandBuilder
from yapapi.rest import Configuration, Market

from django.db.models import Q


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

async def update_db(issuer_id, is_online, scanned_times, props=None):
    if props is not None and props.get("golem.runtime.name") == "vm":
        # Extracting information from props
        payment_addresses = {
        key: value for key, value in props.items()
        if key.startswith("golem.com.payment.platform.") and key.endswith(".address")
        }
        network = 'testnet' if any(key in TESTNET_KEYS for key in payment_addresses.keys()) else 'mainnet'
        cores = props.get("golem.inf.cpu.cores")
        memory = props.get("golem.inf.mem.gib")
        cpu = props.get("golem.inf.cpu.brand")
        runtime = props.get("golem.runtime.name")
        runtime_version = props.get("golem.runtime.version")
        threads = props.get("golem.inf.cpu.threads")
        storage = props.get("golem.inf.storage.gib")
        name = props.get("golem.node.id.name")
        # Database operations
        provider, created = await async_get_or_create(Provider, node_id=issuer_id)


        # Update provider properties if it already exists and has changes
        updated = False
        if not created or provider.payment_addresses != payment_addresses:  # If new or there are changes
            provider.payment_addresses = payment_addresses
            provider.network = network
            updated = True
            
            # Check each field for changes and update if necessary
            
            if provider.cores != cores:
                provider.cores = cores
                updated = True
            if provider.memory != memory:
                provider.memory = memory
                updated = True
            if provider.cpu != cpu:
                provider.cpu = cpu
                updated = True
            if provider.runtime != runtime:
                provider.runtime = runtime
                updated = True
            if provider.runtime_version != runtime_version:
                provider.runtime_version = runtime_version
                updated = True
            if provider.threads != threads:
                provider.threads = threads
                updated = True
            if provider.storage != storage:
                provider.storage = storage
                updated = True
            if provider.name != name:
                provider.name = name
                updated = True
            
            if updated:  # If any field was updated, save the changes
                await async_save(provider)

        # Now handle the NodeStatus
        node_status, _ = await async_get_or_create(NodeStatus, provider=provider, defaults={'first_seen_scan_count': scanned_times})
        await node_status.update_status(is_online_now=is_online, total_scanned_times_overall=scanned_times)
        await async_save(node_status)
    else:
        # When props are not available, only update the online status
        provider, _ = await async_get_or_create(Provider, node_id=issuer_id)
        node_status, _ = await async_get_or_create(NodeStatus, provider=provider)
        
        await node_status.update_status(is_online_now=is_online, total_scanned_times_overall=scanned_times)
        await async_save(node_status)




async def check_node_status(issuer_id):
    try:
        # Use asyncio.create_subprocess_exec to run the command asynchronously
        process = await asyncio.create_subprocess_exec(
            "yagna", "net", "find", issuer_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Wait for the command to complete and capture the output
        stdout, stderr = await process.communicate()
        
        # Process finished, return True if it was successful and "seen:" is in the output
        return process.returncode == 0 and "seen:" in stdout.decode()
    except asyncio.TimeoutError as e:
        print("Timeout reached while checking node status", e)
        return False

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
                            "is_online": False
                        }
                        await update_db(event.issuer, True, scanned_times, event.props)
                    else:
                        continue

                    
                    

async def monitor_nodes_status(subnet_tag: str = "public"):
    nodes_data = {}
    ScanCount.increment()  # Increment the scan count
    scanned_times = ScanCount.get_current_count()  # Load the current scan count
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

    RECENT_TIMEFRAME = timedelta(seconds=30)

    # Get the current time
    current_time = timezone.now()

    # Query NodeStatus objects that were last seen within the RECENT_TIMEFRAME and are marked as online
    recent_nodes = await sync_to_async(NodeStatus.objects.filter)(
        last_seen__lt=current_time - RECENT_TIMEFRAME, 
        is_online=True
    )

    # Iterate over these nodes and check their current status
    for node_status in recent_nodes:
        # Ensure the node is not in the current scan data
        if node_status.provider.node_id not in nodes_data:
            # Perform the online check
            is_online = await check_node_status(node_status.provider.node_id)

            if not is_online:
                # If the node is not online, update the database
                await update_db(node_status.provider.node_id, False, scanned_times)



