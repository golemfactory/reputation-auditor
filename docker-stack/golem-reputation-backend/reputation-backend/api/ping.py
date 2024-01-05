import asyncio
import json
import subprocess
from .models import NodeStatus, PingResult
from asgiref.sync import sync_to_async



async def async_fetch_node_ids():
    # Define the synchronous part as an inner function
    def get_node_ids():
        return [provider.provider.node_id for provider in NodeStatus.objects.filter(is_online=True).select_related('provider').only('provider__node_id')]

    # Use sync_to_async to convert it and immediately invoke
    node_ids = await sync_to_async(get_node_ids, thread_sensitive=True)()
    return node_ids


async def async_bulk_create_ping_results(all_data):
    # Define the synchronous part as an inner function
    def bulk_create():
        PingResult.objects.bulk_create(all_data)

    # Use sync_to_async to convert it and immediately invoke
    await sync_to_async(bulk_create, thread_sensitive=True)()


def parse_ping_time(ping_time_str):
    """Converts a ping time string into milliseconds."""
    total_ms = 0
    parts = ping_time_str.split(' ')
    for part in parts:
        if 'ms' in part:
            total_ms += int(part.replace('ms', ''))
        elif 's' in part:
            total_ms += int(part.replace('s', '')) * 1000
    return total_ms


# Function to execute command and process output
async def ping_provider(provider_id):
    try:
        # Use asyncio.create_subprocess_exec to run the command asynchronously
        process = await asyncio.create_subprocess_exec(
            "yagna", "net", "ping", provider_id, "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Wait for the command to complete and capture the output
        stdout, stderr = await process.communicate()
        
        if stdout:
            result = json.loads(stdout.decode())
            # Parse ping times into milliseconds
            for ping_data in result:
                ping_data['ping (tcp)'] = parse_ping_time(ping_data['ping (tcp)'])
                ping_data['ping (udp)'] = parse_ping_time(ping_data['ping (udp)'])
            return result
        else:
            print("ERROR pinging", stderr.decode())
            return False
        
    except asyncio.TimeoutError as e:
        print("Timeout reached while checking node status", e)
        return False



# Main logic to process each provider ID
async def ping_providers():
    node_ids = await async_fetch_node_ids()

    all_data = []  # This will be a list of PingResult instances
    chunk_size = 5
    for i in range(0, len(node_ids), chunk_size):
        print(f"Processing chunk {(i // chunk_size) + 1} of {len(node_ids) // chunk_size + 1}")

        chunk = node_ids[i:i+chunk_size]
        results = await asyncio.gather(*[ping_provider(id) for id in chunk], return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                continue
            for ping_data in result:
                all_data.append(PingResult(
                    provider_id=ping_data['nodeId'],
                    is_p2p=ping_data['p2p'],
                    ping_tcp=ping_data['ping (tcp)'],
                    ping_udp=ping_data['ping (udp)']
                ))

    # Use bulk_create to insert all the records into the database
    await async_bulk_create_ping_results(all_data)



