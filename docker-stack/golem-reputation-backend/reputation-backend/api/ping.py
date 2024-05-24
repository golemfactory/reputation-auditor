import asyncio
import json
import subprocess
from .models import NodeStatusHistory, PingResult
from asgiref.sync import sync_to_async



async def async_fetch_node_ids():
    # Define the synchronous part as an inner function
    def get_node_ids():
        # Fetch the latest status for each provider and filter those that are online
        latest_statuses = NodeStatusHistory.objects.filter(
            provider_id__in=NodeStatusHistory.objects.order_by('provider', '-timestamp').distinct('provider').values_list('provider_id', flat=True)
        ).order_by('provider', '-timestamp').distinct('provider')

        # Return provider IDs where the latest status is online
        return [status.provider.node_id for status in latest_statuses if status.is_online]

    # Use sync_to_async to convert it and immediately invoke
    node_ids = await sync_to_async(get_node_ids, thread_sensitive=True)()
    return node_ids



import aiohttp  # For asynchronous HTTP requests
import os  # To access environment variables

async def async_bulk_create_ping_results(chunk_data, p2p):
    endpoint = os.getenv('REPUTATION_PING_ENDPOINT')
    region = os.getenv('REGION')  # Ensure this is appropriately set
    ping_secret = os.getenv('PING_SECRET')  # Fetching the ping secret from environment variables

    if not endpoint or not region or not ping_secret:
        print("Endpoint, region, or ping secret is not configured.")
        return

    async with aiohttp.ClientSession() as session:
        # Prepare the JSON payload as a list of dictionaries
        json_payload = [
            {
                'provider_id': data.provider_id,
                'ping_udp': data.ping_udp,
                'ping_tcp': data.ping_tcp,
                'is_p2p': data.is_p2p,
                'from_non_p2p_pinger': True
            } for data in chunk_data
        ]
        print("Sending data:", json_payload)

        # Construct the URL with the region query parameter
        request_url = f"{endpoint}?region={region}"

        # Define headers with the ping secret
        headers = {'Authorization': f'Bearer {ping_secret}'}

        # POST the data with headers including the ping secret
        try:
            async with session.post(request_url, json=json_payload, headers=headers) as response:
                if response.status == 200:
                    # Assuming response is JSON and you want to log or handle it
                    response_data = await response.json()
                    print("Data sent successfully:", response_data)
                else:
                    response_text = await response.text()
                    print(f"Failed to send data: {response_text}")
        except Exception as e:
            print(f"An error occurred during POST request: {str(e)}")






def parse_ping_time(ping_time_str):
    
    """Converts a ping time string into milliseconds."""
    total_ms = ping_time_str
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
        results = []

        for _ in range(2):
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
                results.append(result)
            else:
                print("ERROR pinging", stderr.decode())
                return False

        # Compare the two results and return the one with the lowest ping times
        if len(results) == 2:
            final_result = []
            for ping_data_1, ping_data_2 in zip(results[0], results[1]):
                print(ping_data_1['p2p'])
                final_result.append({
                    'nodeId': ping_data_1['nodeId'],
                    'p2p': ping_data_1['p2p'],
                    'ping (tcp)': min(ping_data_1['ping (tcp)'], ping_data_2['ping (tcp)']),
                    'ping (udp)': min(ping_data_1['ping (udp)'], ping_data_2['ping (udp)'])
                })
            return final_result
        else:
            return results[0] if results else False
        
    except asyncio.TimeoutError as e:
        print("Timeout reached while checking node status", e)
        return False



# Main logic to process each provider ID
async def ping_providers(p2p):
    node_ids = await async_fetch_node_ids()
    chunk_size = 5
    all_chunk_data = []  # This will hold all accumulated PingResult instances

    for i in range(0, len(node_ids), chunk_size):
        print(f"Processing chunk {(i // chunk_size) + 1} of {len(node_ids) // chunk_size + 1}")

        chunk = node_ids[i:i+chunk_size]
        results = await asyncio.gather(*[ping_provider(id) for id in chunk], return_exceptions=True)

        chunk_data = []  # This will hold the PingResult instances for the current chunk
        for result in results:
            if isinstance(result, Exception):
                print(f"An error occurred: {result}")  # Optionally log the exception
                continue
            for ping_data in result:
                chunk_data.append(PingResult(
                    provider_id=ping_data['nodeId'],
                    is_p2p=ping_data['p2p'],
                    ping_tcp=ping_data['ping (tcp)'],
                    ping_udp=ping_data['ping (udp)']
                ))

        all_chunk_data.extend(chunk_data)  # Accumulate results from each chunk

        # Bulk create results after every 10 chunks
        if (i // chunk_size + 1) % 10 == 0:
            if all_chunk_data:
                await async_bulk_create_ping_results(all_chunk_data, p2p)
                all_chunk_data = []  # Reset for next batch

    # Handle any remaining data that wasn't sent because it didn't complete a full set of 10 chunks
    if all_chunk_data:
        await async_bulk_create_ping_results(all_chunk_data, p2p)
