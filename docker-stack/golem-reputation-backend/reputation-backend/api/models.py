from django.db import models
from django.db.models.fields import BigIntegerField, CharField
from django.utils import timezone




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

class Offer(models.Model):
    provider = models.ForeignKey('Provider', on_delete=models.CASCADE)  # Link to a Provider
    task = models.ForeignKey('Task', on_delete=models.CASCADE)  # Link to a Task
    offer = models.JSONField(default=dict)  # JSON object with offer data
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    accepted = models.BooleanField(default=False)
    reason = models.CharField(max_length=255, blank=True, null=True)  # Reason for rejection


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
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    

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
    created_at = models.DateTimeField(auto_now_add=True, null=True)



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

class NetworkBenchmark(models.Model):
    provider = models.ForeignKey('Provider', on_delete=models.CASCADE)  
    mbit_per_second = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True, null=True)

class Task(models.Model):
    name= models.CharField(max_length=255)  # Name of the task
    started_at = models.DateTimeField(default=timezone.now)  # When the task was started
    finished_at = models.DateTimeField(null=True)  # When the task was finished
    cost = models.FloatField(null=True)  # Cost of the task in GLM


class TaskCompletion(models.Model):
    provider = models.ForeignKey('Provider', on_delete=models.CASCADE)  # Link to a Node model
    task_name = models.CharField(max_length=255)  # A descriptive name or identifier for the task
    is_successful = models.BooleanField(default=False)  # Whether the task was completed successfully
    error_message = models.TextField(null=True)  # Error message if the task failed
    timestamp = models.DateTimeField(auto_now_add=True)  # When the record was created
    task= models.ForeignKey('Task', on_delete=models.CASCADE, null=True)  # Link to a Task model
    cost = models.FloatField(null=True)  # Cost of the task in GLM



class PingResult(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)  # Link to a Provider
    is_p2p = models.BooleanField(default=False)  # Whether it's peer-to-peer
    ping_tcp = models.IntegerField()  # Ping result for TCP, e.g., 96
    ping_udp = models.IntegerField()  # Ping result for UDP, e.g., 96
    created_at = models.DateTimeField(auto_now_add=True, null=True)


class PingResultP2P(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)  # Link to a Provider
    is_p2p = models.BooleanField(default=False)  # Whether it's peer-to-peer
    ping_tcp = models.IntegerField()  # Ping result for TCP, e.g., 96
    ping_udp = models.IntegerField()  # Ping result for UDP, e.g., 96
    created_at = models.DateTimeField(auto_now_add=True, null=True)




from django.utils import timezone
from django.db.models import F


from asgiref.sync import sync_to_async


# This decorator turns sync functions (like Django ORM calls) into async functions
async def async_get_or_create(model, defaults=None, **kwargs):
    return await sync_to_async(model.objects.get_or_create, thread_sensitive=True)(defaults=defaults, **kwargs)

async def async_save(obj):
    await sync_to_async(obj.save, thread_sensitive=True)()




class NodeStatusHistory(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    is_online = models.BooleanField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.provider.node_id} - {'Online' if self.is_online else 'Offline'} at {self.timestamp}"

class ScanCount(models.Model):
    scan_count = models.IntegerField(default=0)

    @classmethod
    def increment(cls):
        obj, created = cls.objects.get_or_create(id=1)
        obj.scan_count = F('scan_count') + 1
        obj.save()

    @classmethod
    def get_current_count(cls):
        obj, created = cls.objects.get_or_create(id=1)
        return obj.scan_count