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
}

export interface Benchmark {
    type: string // 'disk', 'cpu', 'memory'
    data: any // This should ideally be replaced with a more specific interface based on the structure of your benchmark data
}
