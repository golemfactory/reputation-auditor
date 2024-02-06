import { Golem, GolemError } from "./golem"
import { submitTaskStatus, submitBenchmark, getBlacklistedProviders, sendStartTaskSignal, sendStopTaskSignal } from "./utils"

let blacklistedProviders: string[] = []

async function logAndSubmitFailure(node_id: string, task_name: string, error_message: string, taskId: string): Promise<void> {
    console.log(`Benchmarking ${task_name} failed on node:`, node_id)
    // failedProvidersIds.push(node_id)
    if (!blacklistedProviders.includes(node_id)) {
        await submitTaskStatus({
            node_id: node_id,
            task_name,
            is_successful: false,
            error_message,
            task_id: taskId,
        })
    }
}

async function initializeBlacklistedProviders() {
    try {
        let blacklist = await getBlacklistedProviders()
        if (blacklist) {
            blacklistedProviders = blacklist
        }
    } catch (error) {
        console.error("Failed to initialize blacklisted providers:", error)
    }
}

const benchmarkMemoryFiles = [
    "sequential_write_single_thread",
    "sequential_read_single_thread",
    "random_write_multi_threaded",
    "random_read_multi_threaded",
    "latency_test_single_thread",
]
const benchmarkCpuFiles = ["cpu/cpu_single_thread", "cpu/cpu_multi_thread"]
const benchmarkDiskFiles = [
    "sysbench/random_read",
    "sysbench/random_write",
    "sysbench/sequential_read",
    "sysbench/sequential_write",
    "sysbench/random_read_write",
]

const benchmarkTest = async (ctx: any, node_id: string, testName: string, scriptName: string, filePaths: string[], taskId: string) => {
    console.log(`BENCHMARKING ${testName.toUpperCase()} on node:`, node_id, ctx.provider.name)
    const benchmarkResult = await ctx.run(`${scriptName} ${node_id}`)
    if (benchmarkResult.result === "Error") {
        await logAndSubmitFailure(node_id, `Benchmark ${testName}`, benchmarkResult.stdout ?? benchmarkResult.stderr ?? testName, taskId)
        return false
    }

    for (const filePath of filePaths) {
        const performanceData = await ctx.run(`cat /golem/work/${filePath}.json`)
        await submitBenchmark(performanceData.stdout, testName.toLowerCase())
    }
    return true
}

interface GolemTaskResult {
    // result: IValidationTaskResult
    context: {
        providerId: string
        activityId: string
        agreementId: string
    }
}

export async function runProofOfWork(numOfChecks: number, budget: null | number) {
    const taskId = await sendStartTaskSignal()
    if (!taskId) {
        throw new Error("Failed to send start task signal")
    }
    initializeBlacklistedProviders()

    const EXPECTED_EXECUTION_TIME_SECONDS = 60 * 20
    const EXPECTED_DEPLOYMENT_TIME_SECONDS = 60
    const EXPECTED_TOTAL_DURATION_SECONDS = EXPECTED_EXECUTION_TIME_SECONDS + EXPECTED_DEPLOYMENT_TIME_SECONDS

    const PRICE_GLM_HOUR = parseFloat(process.env["PRICE_GLM_HOUR"] ?? "3")
    const DURATION_HOURS = EXPECTED_TOTAL_DURATION_SECONDS / 3600

    const bannedAddresses = <string[]>[]

    const REQUEST_START_TIMEOUT_SEC = 90

    const golem = new Golem({
        initTimeoutSec: 90,
        requestStartTimeoutSec: REQUEST_START_TIMEOUT_SEC,
        requestTimeoutSec: EXPECTED_EXECUTION_TIME_SECONDS,
        deploy: {
            maxReplicas: numOfChecks,
            resources: { minCpu: 1, minMemGib: 0.5, minStorageGib: 12 },
            downscaleIntervalSec: 90,
            readyTimeoutSec: EXPECTED_DEPLOYMENT_TIME_SECONDS,
        },
        market: {
            budget: budget,
            priceGlmPerHour: PRICE_GLM_HOUR,
            rentHours: DURATION_HOURS,
            withoutProviders: blacklistedProviders,
            withoutOperators: bannedAddresses,
        },
        taskId: taskId,
        computedAlready: blacklistedProviders,
    })

    console.log("Preparing activities to run the suite")
    await golem.start()
    console.log("Activities ready, going to start the test")

    try {
        const tasks = []

        // FIXME #sdk This code suffers from the same illness - some of the providers fail to init the activity, and I don't have a easy way to access this info ('Preparing activity timeout' example)
        for (let i = 0; i < numOfChecks; i++) {
            tasks.push(
                golem.sendTask<GolemTaskResult | undefined>(async (ctx: any) => {
                    const providerId = ctx.provider!.id

                    try {
                        const memory = await benchmarkTest(ctx, providerId, "memory", `/benchmark-memory.sh`, benchmarkMemoryFiles, taskId)
                        if (!memory) {
                            throw new Error("Benchmark failed")
                        }
                        const cpu = await benchmarkTest(ctx, providerId, "cpu", `/benchmark-cpu.sh`, benchmarkCpuFiles, taskId)
                        if (!cpu) {
                            throw new Error("Benchmark failed")
                        }

                        const disk = await benchmarkTest(ctx, providerId, "disk", `/benchmark-disk.sh`, benchmarkDiskFiles, taskId)

                        if (!disk) {
                            throw new Error("Benchmark failed")
                        }

                        await submitTaskStatus({
                            node_id: providerId,
                            task_name: "Full benchmark suite",
                            is_successful: true,
                            error_message: "",
                            task_id: taskId,
                        })

                        return {
                            result: "success",
                            context: {
                                providerId: ctx.activity.agreement.provider.id,
                                activityId: ctx.activity.id,
                                agreementId: ctx.activity.agreement.id,
                            },
                        }
                    } catch (err) {
                        const errorMessage = typeof err === "string" ? err : "unknown error"
                        console.log("Activity failed!", errorMessage)

                        if (!blacklistedProviders.includes(providerId)) {
                            blacklistedProviders.push(providerId)

                            // Submit task status only if the provider is not already blacklisted
                            await submitTaskStatus({
                                node_id: providerId,
                                task_name: "Full benchmark suite",
                                is_successful: false,
                                error_message: errorMessage,
                                task_id: taskId,
                            })
                        }
                    } finally {
                        console.log(`Finished benchmarking on provider: ${providerId}`)
                    }
                })
            )
        }

        const results = await Promise.allSettled(tasks)

        const rejected = results.filter((r) => r.status === "rejected") as PromiseRejectedResult[]

        const fulfilled = results.filter((r) => r.status === "fulfilled") as PromiseFulfilledResult<GolemTaskResult>[]

        for (const failed of rejected) {
            try {
                if (failed.reason instanceof GolemError) {
                    if (failed.reason.activity?.agreement.provider) {
                        console.log(`Provider failed: ${failed.reason.activity?.agreement.provider.id}`, failed.reason.message)
                    }
                } else if (failed.reason instanceof Error && failed.reason.name === "TimeoutError") {
                    console.warn(
                        `One of the tasks didn't start in the expected ${REQUEST_START_TIMEOUT_SEC}s. Could not find enough providers?`
                    )
                } else {
                    console.error(
                        { error: failed.reason },
                        "Didn't deal with this error while processing failed computation tasks. Investigate and address."
                    )
                }
            } catch (err) {
                console.error(
                    err,
                    "Issue when processing failed computation tasks, continuing to the next one, but you should investigate this"
                )
            }
        }
    } catch (err) {
        // We consider this as a warning - most of the time we run into Task 1 timeout here, because of the provider failing
        // to deploy and run the computations within expected time.
        // Task 1 timeout also means that we could not even get an agreement, effectively no valid proposal for our demand
        // This might be either due to wrongly set demands, but also due to issues on the network, which make it impossible
        // to reach any provider even when having a lot of offers available
        console.warn(err, "Failed to run the tests due to an error")
    } finally {
        await golem.stop()
        if (taskId) {
            await sendStopTaskSignal(taskId)
        } else {
            throw new Error("Failed to send stop task signal")
        }
    }
}
import process from "process"

// // This function triggers runProofOfWork with the provided number of runs
function triggerRunProofOfWork(num: number, budget: null | number): void {
    runProofOfWork(num, budget).catch((err) => {
        console.log(err)
    })
}

// Get the number of runs from the command line arguments
const numRuns = parseInt(process.argv[2])
const budget = process.argv[3] ? parseInt(process.argv[3]) : null
// Check if the number of runs is a valid number
if (!isNaN(numRuns)) {
    triggerRunProofOfWork(numRuns, budget)
} else {
    console.log("Please provide a valid number of runs.")
}
