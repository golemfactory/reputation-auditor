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


class TaskCompletion(models.Model):
    provider = models.ForeignKey('Provider', on_delete=models.CASCADE)  # Link to a Node model
    task_name = models.CharField(max_length=255)  # A descriptive name or identifier for the task
    is_successful = models.BooleanField(default=False)  # Whether the task was completed successfully
    error_message = models.TextField(null=True)  # Error message if the task failed
    timestamp = models.DateTimeField(auto_now_add=True)  # When the record was created



class PingResult(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)  # Link to a Provider
    is_p2p = models.BooleanField(default=False)  # Whether it's peer-to-peer
    ping_tcp = models.IntegerField()  # Ping result for TCP, e.g., 96
    ping_udp = models.IntegerField()  # Ping result for UDP, e.g., 96



from django.utils import timezone
from django.db.models import F


from asgiref.sync import sync_to_async


# This decorator turns sync functions (like Django ORM calls) into async functions
async def async_get_or_create(model, defaults=None, **kwargs):
    return await sync_to_async(model.objects.get_or_create, thread_sensitive=True)(defaults=defaults, **kwargs)

async def async_save(obj):
    await sync_to_async(obj.save, thread_sensitive=True)()



class NodeStatus(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)  # Link to a Provider
    is_online = models.BooleanField(default=False)  # Whether the node is currently online
    last_seen = models.DateTimeField(default=timezone.now)
    total_online_scans = models.IntegerField(default=0) 
    uptime_percentage = models.FloatField(default=0.0)  # Default uptime percentage as 0%
    first_seen_scan_count = models.IntegerField(null=True)  # New field to track the scan count at first seen


    async def update_status(self, is_online_now, total_scanned_times_overall):
        if is_online_now:
            self.total_online_scans += 1

        self.is_online = is_online_now
        self.last_seen = timezone.now()

        # Set first_seen_scan_count on first successful scan update if it's None

        # Instead of min() use directly the first_seen_scan_count
        # since it should have been set correctly at the node's first appearance.
        self.first_seen_scan_count = self.first_seen_scan_count or total_scanned_times_overall

        # Ensure that the total scanned times is at least the same as the first time seen
        total_scanned_times_overall = max(self.first_seen_scan_count, total_scanned_times_overall)

        # Calculate effective scans
        effective_scans = total_scanned_times_overall - self.first_seen_scan_count + 1

        # Ensure effective_scans is never zero or negative
        effective_scans = max(effective_scans, 1)

        # Calculate the uptime percentage
        self.uptime_percentage = (self.total_online_scans / effective_scans) * 100

        # Ensure the uptime percentage never goes beyond 100%
        self.uptime_percentage = min(self.uptime_percentage, 100.0)

        await async_save(self)




    def __str__(self):
        status = "Online" if self.is_online else "Offline"
        return f"Node {self.provider.node_id} is {status} - Last seen: {self.last_seen}"


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