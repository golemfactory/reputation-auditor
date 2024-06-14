from django.db import models
from django.db.models.fields import BigIntegerField, CharField
from django.utils import timezone
import os



class Provider(models.Model):
    node_id = models.CharField(max_length=255, unique=True, primary_key=True)  # Node ID
    name = models.CharField(max_length=255, blank=True, null=True)  # Name of the provider
    cores = models.FloatField(blank=True, null=True)
    memory = models.FloatField(blank=True, null=True)
    cpu = models.CharField(max_length=255, blank=True, null=True)
    runtime = models.CharField(max_length=255, blank=True, null=True)
    runtime_version = models.CharField(max_length=50, blank=True, null=True)
    threads = models.IntegerField(blank=True, null=True)
    storage = models.FloatField(blank=True, null=True)
    payment_addresses = models.JSONField(default=dict, blank=True, null=True)  # JSON object with payment addresses
    network = models.CharField(max_length=50, default='mainnet')  # 'mainnet' or 'testnet'
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    class Meta:
        indexes = [
            models.Index(fields=['network']),
            models.Index(fields=['created_at']),
        ]

class Offer(models.Model):
    provider = models.ForeignKey('Provider', on_delete=models.CASCADE)  # Link to a Provider
    task = models.ForeignKey('Task', on_delete=models.CASCADE)  # Link to a Task
    offer = models.JSONField(default=dict)  # JSON object with offer data
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    accepted = models.BooleanField(default=False)
    reason = models.CharField(max_length=255, blank=True, null=True)  # Reason for rejection
    class Meta:
        indexes = [
            models.Index(fields=['provider']),
            models.Index(fields=['task']),
            models.Index(fields=['created_at']),
        ]

class BlacklistedOperator(models.Model):
    wallet = models.CharField(max_length=255, unique=True)  # Payment address
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    reason = models.CharField(max_length=255, blank=True, null=True)  # Reason for blacklisting
    class Meta:
        indexes = [
            models.Index(fields=['wallet']),
            models.Index(fields=['created_at']),
        ]

class BlacklistedProvider(models.Model):
    provider = models.ForeignKey('Provider', on_delete=models.CASCADE)  # Link to a Provider
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    reason = models.CharField(max_length=255, blank=True, null=True)  # Reason for blacklisting
    class Meta:
        indexes = [
            models.Index(fields=['provider']),
            models.Index(fields=['created_at']),
        ]

class DiskBenchmark(models.Model):
    provider = models.ForeignKey('Provider', on_delete=models.CASCADE)  
    benchmark_name = models.CharField(max_length=255)  # Name of the benchmark

    reads_per_second = models.FloatField()
    writes_per_second = models.FloatField()
    fsyncs_per_second = models.FloatField()
    read_throughput_mb_ps = models.FloatField()
    write_throughput_mb_ps = models.FloatField()

    total_time_sec = models.FloatField()
    total_io_events = models.IntegerField()

    min_latency_ms = models.FloatField()
    avg_latency_ms = models.FloatField()
    max_latency_ms = models.FloatField()
    latency_95th_percentile_ms = models.FloatField()
    disk_size_gb = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    class Meta:
        indexes = [
            models.Index(fields=['provider']),
            models.Index(fields=['benchmark_name']),
            models.Index(fields=['created_at']),
            models.Index(fields=['reads_per_second']),
            models.Index(fields=['writes_per_second']),
            models.Index(fields=['read_throughput_mb_ps']),
            models.Index(fields=['write_throughput_mb_ps']),
            models.Index(fields=['provider', 'created_at']),
            models.Index(fields=['benchmark_name', 'created_at']),
            models.Index(fields=['provider', 'benchmark_name', 'created_at']),
        ]

class MemoryBenchmark(models.Model):
    provider = models.ForeignKey('Provider', on_delete=models.CASCADE)  
    benchmark_name = models.CharField(max_length=255)  # Name of the benchmark

    total_operations = models.IntegerField()
    operations_per_second = models.FloatField()
    total_data_transferred_mi_b = models.FloatField()
    throughput_mi_b_sec = models.FloatField()

    total_time_sec = models.FloatField()
    total_events = models.IntegerField()

    min_latency_ms = models.FloatField()
    avg_latency_ms = models.FloatField()
    max_latency_ms = models.FloatField()
    latency_95th_percentile_ms = models.FloatField()
    sum_latency_ms = models.FloatField()

    events = models.FloatField()
    execution_time_sec = models.FloatField()
    memory_size_gb = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    class Meta:
        indexes = [
            models.Index(fields=['provider']),
            models.Index(fields=['benchmark_name']),
            models.Index(fields=['created_at']),
            models.Index(fields=['throughput_mi_b_sec']),
            models.Index(fields=['provider', 'created_at']),
            models.Index(fields=['benchmark_name', 'created_at']),
            models.Index(fields=['provider', 'benchmark_name', 'created_at']),
        ]


class CpuBenchmark(models.Model):
    provider = models.ForeignKey('Provider', on_delete=models.CASCADE)  
    benchmark_name = models.CharField(max_length=255)  # Name of the benchmark

    threads = models.IntegerField()
    total_time_sec = models.FloatField()
    total_events = models.IntegerField()
    events_per_second = models.FloatField()

    min_latency_ms = models.FloatField()
    avg_latency_ms = models.FloatField()
    max_latency_ms = models.FloatField()
    latency_95th_percentile_ms = models.FloatField()
    sum_latency_ms = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    class Meta:
        indexes = [
            models.Index(fields=['provider']),
            models.Index(fields=['benchmark_name']),
            models.Index(fields=['created_at']),
            models.Index(fields=['events_per_second']),
            models.Index(fields=['provider', 'created_at']),
            models.Index(fields=['benchmark_name', 'created_at']),
        ]

class GPUTask(models.Model):
    provider = models.ForeignKey('Provider', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)  # Name of the GPU task
    pcie = models.IntegerField()  # PCIe slot number
    memory_total = models.IntegerField()  # Total memory in MB
    memory_free = models.IntegerField()  # Free memory in MB
    cuda_cap = models.DecimalField(max_digits=4, decimal_places=2)  # CUDA capability version
    gpu_burn_gflops = models.IntegerField(null=True, blank=True)  # GFLOPS for GPU burn
    created_at = models.DateTimeField(auto_now_add=True, null=True)

class NetworkBenchmark(models.Model):
    provider = models.ForeignKey('Provider', on_delete=models.CASCADE)  
    mbit_per_second = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True, null=True)

class Task(models.Model):
    name= models.CharField(max_length=255)  # Name of the task
    started_at = models.DateTimeField(default=timezone.now)  # When the task was started
    finished_at = models.DateTimeField(null=True)  # When the task was finished
    cost = models.FloatField(null=True)  # Cost of the task in GLM
    class Meta:
        indexes = [
            models.Index(fields=['started_at']),
            models.Index(fields=['finished_at']),
        ]

class TaskCompletion(models.Model):
    provider = models.ForeignKey('Provider', on_delete=models.CASCADE)  # Link to a Node model
    task_name = models.CharField(max_length=255)  # A descriptive name or identifier for the task
    is_successful = models.BooleanField(default=False)  # Whether the task was completed successfully
    error_message = models.TextField(null=True)  # Error message if the task failed
    timestamp = models.DateTimeField(auto_now_add=True)  # When the record was created
    task= models.ForeignKey('Task', on_delete=models.CASCADE, null=True)  # Link to a Task model
    cost = models.FloatField(null=True)  # Cost of the task in GLM
    # type , default CPU but GPU also possible
    type = models.CharField(max_length=255, default='CPU')  # Type of the task, e.g., 'CPU' or 'GPU'
    class Meta:
        indexes = [
            models.Index(fields=['provider', 'timestamp']),
            models.Index(fields=['task']),
            models.Index(fields=['provider', 'is_successful'], name='idx_provider_success', condition=models.Q(is_successful=True)),
            models.Index(fields=['type']),
        ]

class PingResult(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)  # Link to a Provider
    is_p2p = models.BooleanField(default=False)  # Whether it's peer-to-peer
    ping_tcp = models.IntegerField()  # Ping result for TCP, e.g., 96
    ping_udp = models.IntegerField()  # Ping result for UDP, e.g., 96
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    region = models.CharField(max_length=255, default='local')
    from_non_p2p_pinger = models.BooleanField(default=False)  # Whether the ping was from a non-P2P node. If it was and is_p2p is True, it's a P2P ping and we can assume the provider has opened the port.
    class Meta:
        indexes = [
            models.Index(fields=['provider']),
            models.Index(fields=['created_at']),
            models.Index(fields=['is_p2p']),
            models.Index(fields=['from_non_p2p_pinger']),
            models.Index(fields=['region']),
            models.Index(fields=['provider', 'is_p2p', 'region']),  # Composite index
            models.Index(fields=['provider', 'from_non_p2p_pinger']),  # New composite index
        ]




class NodeStatusHistory(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    is_online = models.BooleanField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.provider.node_id} - {'Online' if self.is_online else 'Offline'} at {self.timestamp}"

    class Meta:
        indexes = [
            models.Index(fields=["provider", "timestamp"]),
        ]