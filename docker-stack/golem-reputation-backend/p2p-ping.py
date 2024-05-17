import asyncio
import json
import aiohttp  # For asynchronous HTTP requests
import os  # To access environment variables

# Fetch node IDs from the API
async def async_fetch_node_ids():
    url = 'https://api.stats.golem.network/v2/network/online'

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                node_ids = [item['node_id'] for item in data]
                return node_ids
            else:
                print(f"Failed to fetch data from API. Status code: {response.status}")
                return []

# Send ping results to the endpoint
async def async_bulk_create_ping_results(chunk_data, p2p):

    endpoint = os.getenv('REPUTATION_PING_ENDPOINT')
    region = os.getenv('REGION')
    ping_secret = os.getenv('PING_SECRET')

    if not endpoint or not region or not ping_secret:
        print("Endpoint, region, or ping secret is not configured.")
        return

    async with aiohttp.ClientSession() as session:
        json_payload = [
            {
                'provider_id': data['provider_id'],
                'ping_udp': data['ping_udp'],
                'ping_tcp': data['ping_tcp'],
                'is_p2p': data['is_p2p']
            } for data in chunk_data
        ]

        print("Sending data:", json_payload)

        request_url = f"{endpoint}?region={region}"
        headers = {'Authorization': f'Bearer {ping_secret}'}

        try:
            async with session.post(request_url, json=json_payload, headers=headers) as response:
                if response.status == 200:
                    response_data = await response.json()
                    print("Data sent successfully:", response_data)
                else:
                    response_text = await response.text()
                    print(f"Failed to send data: {response_text}")
        except Exception as e:
            print(f"An error occurred during POST request: {str(e)}")

# Convert ping time strings into milliseconds
def parse_ping_time(ping_time_str):
    """Converts a ping time string into milliseconds."""
    if ping_time_str is None:
        return None

    try:
        # Check if the input string is a valid float
        return int(float(ping_time_str))
    except ValueError:
        total_ms = 0
        parts = ping_time_str.split(' ')
        for part in parts:
            if 'ms' in part:
                total_ms += int(part.replace('ms', ''))
            elif 's' in part:
                total_ms += int(part.replace('s', '')) * 1000
        return total_ms

# Ping a provider and process the result
async def ping_provider(provider_id):
    try:
        results = []

        for _ in range(2):
            process = await asyncio.create_subprocess_exec(
                "yagna", "net", "ping", provider_id, "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if stdout:
                result = json.loads(stdout.decode())
                for ping_data in result:
                    ping_data['ping (tcp)'] = parse_ping_time(ping_data['ping (tcp)'])
                    ping_data['ping (udp)'] = parse_ping_time(ping_data['ping (udp)'])
                results.append(result)
            else:
                print("ERROR pinging", stderr.decode())
                return False

        if len(results) == 2:
            final_result = []
            for ping_data_1, ping_data_2 in zip(results[0], results[1]):
                if ping_data_1['ping (tcp)'] is not None and ping_data_1['ping (tcp)'] > 0 and \
                   ping_data_1['ping (udp)'] is not None and ping_data_1['ping (udp)'] > 0 and \
                   ping_data_2['ping (tcp)'] is not None and ping_data_2['ping (tcp)'] > 0 and \
                   ping_data_2['ping (udp)'] is not None and ping_data_2['ping (udp)'] > 0:
                    final_result.append({
                        'nodeId': ping_data_1['nodeId'],
                        'p2p': ping_data_1['p2p'],
                        'ping (tcp)': min(ping_data_1['ping (tcp)'], ping_data_2['ping (tcp)']),
                        'ping (udp)': min(ping_data_1['ping (udp)'], ping_data_2['ping (udp)'])
                    })
            return final_result if final_result else False
        else:
            return [ping_data for ping_data in results[0] if ping_data['ping (tcp)'] is not None and ping_data['ping (tcp)'] > 0 and ping_data['ping (udp)'] is not None and ping_data['ping (udp)'] > 0] if results else False

    except asyncio.TimeoutError as e:
        print("Timeout reached while checking node status", e)
        return False

# Process each provider ID and send ping results in chunks
async def ping_providers(p2p):
    node_ids = await async_fetch_node_ids()
    chunk_size = 5
    all_chunk_data = []

    for i in range(0, len(node_ids), chunk_size):
        print(f"Processing chunk {(i // chunk_size) + 1} of {len(node_ids) // chunk_size + 1}")

        chunk = node_ids[i:i+chunk_size]
        results = await asyncio.gather(*[ping_provider(id) for id in chunk], return_exceptions=True)

        chunk_data = []
        for result in results:
            if isinstance(result, Exception):
                print(f"An error occurred: {result}")
                continue
            if result:
                for ping_data in result:
                    chunk_data.append({
                        'provider_id': ping_data['nodeId'],
                        'is_p2p': ping_data['p2p'],
                        'ping_tcp': ping_data['ping (tcp)'],
                        'ping_udp': ping_data['ping (udp)'],
                    })

        all_chunk_data.extend(chunk_data)

        if (i // chunk_size + 1) % 10 == 0:
            if all_chunk_data:
                await async_bulk_create_ping_results(all_chunk_data, p2p)
                all_chunk_data = []

    if all_chunk_data:
        await async_bulk_create_ping_results(all_chunk_data, p2p)

# Run the script continuously
async def main():
    p2p = True  # Adjust this as needed
    while True:
        await ping_providers(p2p)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Script interrupted and stopped.")