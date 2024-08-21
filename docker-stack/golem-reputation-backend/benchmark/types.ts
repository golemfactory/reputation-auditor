export interface ProviderData {
    node_id: string
    runtimes: {
        vm: {
            is_overpriced: boolean
            times_more_expensive: number | null // Can be null
            times_cheaper: number | null // Can be null
        }
    }
}

export interface TaskCompletion {
    node_id: string
    task_name: string
    is_successful: boolean
    error_message?: string // assuming error_message is optional
    task_id: number
    type?: 'CPU' | 'GPU';
}

export interface Benchmark {
    type: string // 'disk', 'cpu', 'memory', 'network', 'gpu'
    data: any // This should ideally be replaced with a more specific interface based on the structure of your benchmark data
}


export interface GPUInfo {
    name: string;
    pcie: number;
    memory_total: number;
    memory_free: number;
    cuda_cap: number;
    // Remove gpu_burn_gflops from here
}

export interface GPUBenchmarkData {
    node_id: string;
    gpus: (GPUInfo & { quantity: number })[];
    gpu_burn_gflops: number;
}
  
  export interface Benchmark {
    type: string; // 'disk', 'cpu', 'memory', 'network', 'gpu'
    data: DiskBenchmarkData | CPUBenchmarkData | MemoryBenchmarkData | NetworkBenchmarkData | GPUBenchmarkData;
  }