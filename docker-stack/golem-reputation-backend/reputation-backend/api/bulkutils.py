from .models import Provider, DiskBenchmark, CpuBenchmark, MemoryBenchmark, NetworkBenchmark

def process_disk_benchmark(data_list):
    """
    Processes a list of disk benchmark data in bulk.

    :param data_list: A list of dictionaries, each containing disk benchmark data.
    :return: Dictionary with operation results.
    """
    disk_benchmark_objects = []
    provider_node_ids = {data['node_id'] for data in data_list}

    # Bulk get or create Providers
    existing_providers = {provider.node_id: provider for provider in Provider.objects.filter(node_id__in=provider_node_ids)}

    # Handling providers not already in the database
    new_providers = [Provider(node_id=node_id) for node_id in provider_node_ids if node_id not in existing_providers]
    if new_providers:
        Provider.objects.bulk_create(new_providers)
        # Update cache of existing providers
        existing_providers.update({provider.node_id: provider for provider in new_providers})

    for data in data_list:
        provider = existing_providers[data['node_id']]

        disk_benchmark_objects.append(DiskBenchmark(
            provider=provider,
            benchmark_name=data['benchmark_name'],
            reads_per_second=float(data['reads_per_second']),
            writes_per_second=float(data['writes_per_second']),
            fsyncs_per_second=float(data['fsyncs_per_second']),
            read_throughput_mb_ps=float(data['read_throughput_mb_ps']),
            write_throughput_mb_ps=float(data['write_throughput_mb_ps']),
            total_time_sec=float(data['total_time_sec']),
            total_io_events=int(data['total_io_events']),
            min_latency_ms=float(data['min_latency_ms']),
            avg_latency_ms=float(data['avg_latency_ms']),
            max_latency_ms=float(data['max_latency_ms']),
            latency_95th_percentile_ms=float(data['latency_95th_percentile_ms']),
            disk_size_gb=float(data['disk_size_gb'])
        ))

    # Now, bulk create all DiskBenchmark objects
    DiskBenchmark.objects.bulk_create(disk_benchmark_objects)

    return {"status": "success", "created_count": len(disk_benchmark_objects)}

def process_cpu_benchmark(data_list):
    """
    Processes a list of CPU benchmark data in bulk.

    :param data_list: A list of dictionaries, each containing CPU benchmark data.
    :return: Dictionary with operation results.
    """
    cpu_benchmark_objects = []
    provider_node_ids = {data['node_id'] for data in data_list}

    # Bulk get or create Providers
    existing_providers = {provider.node_id: provider for provider in Provider.objects.filter(node_id__in=provider_node_ids)}

    # Handling providers not already in the database
    new_providers = [Provider(node_id=node_id) for node_id in provider_node_ids if node_id not in existing_providers]
    if new_providers:
        Provider.objects.bulk_create(new_providers)
        # Update the cache of existing providers
        existing_providers.update({provider.node_id: provider for provider in new_providers})

    for data in data_list:
        provider = existing_providers[data['node_id']]

        cpu_benchmark_objects.append(CpuBenchmark(
            provider=provider,
            benchmark_name=data['benchmark_name'],
            threads=int(data['threads']),
            total_time_sec=data['total_time_sec'].replace("s", ""),  # Remove 's' if present
            total_events=int(data['total_events']),
            events_per_second=float(data['events_per_second']),
            min_latency_ms=float(data['min_latency_ms']),
            avg_latency_ms=float(data['avg_latency_ms']),
            max_latency_ms=float(data['max_latency_ms']),
            latency_95th_percentile_ms=float(data['latency_95th_percentile_ms']),
            sum_latency_ms=float(data['sum_latency_ms'])
        ))

    # Now, bulk create all CpuBenchmark objects
    CpuBenchmark.objects.bulk_create(cpu_benchmark_objects)

    return {"status": "success", "created_count": len(cpu_benchmark_objects)}


def process_memory_benchmark(data_list):
    """
    Processes a list of memory benchmark data in bulk.

    :param data_list: A list of dictionaries, each containing memory benchmark data.
    :return: Dictionary with operation results.
    """
    memory_benchmark_objects = []
    provider_node_ids = {data['node_id'] for data in data_list}

    # Bulk get or create Providers
    existing_providers = {provider.node_id: provider for provider in Provider.objects.filter(node_id__in=provider_node_ids)}

    # Handling providers not already in the database
    new_providers = [Provider(node_id=node_id) for node_id in provider_node_ids if node_id not in existing_providers]
    if new_providers:
        Provider.objects.bulk_create(new_providers)
        # Update the cache of existing providers
        existing_providers.update({provider.node_id: provider for provider in new_providers})

    for data in data_list:
        provider = existing_providers[data['node_id']]

        memory_benchmark_objects.append(MemoryBenchmark(
            provider=provider,
            benchmark_name=data['benchmark_name'],
            total_operations=int(data['total_operations']),
            operations_per_second=float(data['operations_per_second']),
            total_data_transferred_mi_b=float(data['total_data_transferred_mi_b']),
            throughput_mi_b_sec=float(data['throughput_mi_b_sec']),
            total_time_sec=float(data['total_time_sec']),
            total_events=int(data['total_events']),
            min_latency_ms=float(data['min_latency_ms']),
            avg_latency_ms=float(data['avg_latency_ms']),
            max_latency_ms=float(data['max_latency_ms']),
            latency_95th_percentile_ms=float(data['latency_95th_percentile_ms']),
            sum_latency_ms=float(data['sum_latency_ms']),
            events=float(data['events']),
            execution_time_sec=float(data['execution_time_sec']),
            memory_size_gb=float(data['memory_size_gb'])
        ))

    # Now, bulk create all MemoryBenchmark objects
    MemoryBenchmark.objects.bulk_create(memory_benchmark_objects)

    return {"status": "success", "created_count": len(memory_benchmark_objects)}


def process_network_benchmark(network_data):
    network_benchmarks = []
    provider_ids = set(data['node_id'] for data in network_data)
    providers = {provider.node_id: provider for provider in Provider.objects.filter(node_id__in=provider_ids)}

    for data in network_data:
        provider = providers.get(data['node_id'])
        if provider:
            network_benchmarks.append(NetworkBenchmark(
                provider=provider,
                mbit_per_second=float(data['speed'])
            ))

    NetworkBenchmark.objects.bulk_create(network_benchmarks)
    return len(network_benchmarks)


from .models import Provider, DiskBenchmark, CpuBenchmark, MemoryBenchmark, NetworkBenchmark, GPUTask

from decimal import Decimal

# ...

def process_gpu_task(data_list):
    """
    Processes a list of GPU task data in bulk.

    :param data_list: A list of dictionaries, each containing GPU task data.
    :return: Dictionary with operation results.
    """
    gpu_task_objects = []
    provider_node_ids = {data['node_id'] for data in data_list}

    # Bulk get or create Providers
    existing_providers = {provider.node_id: provider for provider in Provider.objects.filter(node_id__in=provider_node_ids)}

    # Handling providers not already in the database
    new_providers = [Provider(node_id=node_id) for node_id in provider_node_ids if node_id not in existing_providers]
    if new_providers:
        Provider.objects.bulk_create(new_providers)
        # Update cache of existing providers
        existing_providers.update({provider.node_id: provider for provider in new_providers})

    for data in data_list:
        provider = existing_providers[data['node_id']]

        gpu_task_objects.append(GPUTask(
            provider=provider,
            name=data['name'],
            pcie=int(data['pcie']),
            memory_total=int(data['memory_total']),
            memory_free=int(data['memory_free']),
            cuda_cap=Decimal(data['cuda_cap'])  # Use Decimal here
        ))

    # Now, bulk create all GPUTask objects
    GPUTask.objects.bulk_create(gpu_task_objects)

    return {"status": "success", "created_count": len(gpu_task_objects)}