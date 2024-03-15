import { Golem, GolemError } from "./golem"
import {
    bulkSubmitTaskStatuses,
    getBlacklistedProviders,
    getBlacklistedOperators,
    sendStartTaskSignal,
    sendStopTaskSignal,
    sendBulkTaskCostUpdates,
    fetchProvidersData,
    submitBulkBenchmark,
} from "./utils"
import { TaskCompletion, Benchmark } from "./types"
import { readFile } from "node:fs/promises"
let blacklistedProviders: string[] = []
let blacklistedOperators: string[] = []
let failedProvidersIds: string[] = []
let accumulatedBenchmarkData: Benchmark[] = []

const taskStatuses = <TaskCompletion[]>[]
async function logAndSubmitFailure(node_id: string, task_name: string, error_message: string, taskId: string): Promise<void> {
    console.log(`Benchmarking ${task_name} failed on node:`, node_id)
    if (!failedProvidersIds.includes(node_id)) {
        taskStatuses.push({
            node_id: node_id,
            task_name,
            is_successful: false,
            error_message,
            task_id: Number(taskId),
        })
        failedProvidersIds.push(node_id)
    }
}

async function initializeBlacklists() {
    try {
        let providerBlacklist = await getBlacklistedProviders()
        if (providerBlacklist) {
            blacklistedProviders = providerBlacklist
        }
        let operatorBlacklist = await getBlacklistedOperators()
        if (operatorBlacklist) {
            blacklistedOperators = operatorBlacklist
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

const networkSpeedFiles = ["networkspeedresult"]

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
        if (!performanceData.stdout) {
            await logAndSubmitFailure(node_id, `Benchmark ${testName}`, `No performance data for ${filePath}`, taskId)
            return false
        } else {
            try {
                // The data is already JSON formatted from the provider, so we want to parse it and then submit the final array JSON formatted
                const benchmarkDataObject = JSON.parse(performanceData.stdout)
                accumulatedBenchmarkData.push({ type: testName.toLowerCase(), data: benchmarkDataObject })
            } catch (error) {
                console.error(`Error parsing JSON for ${testName} on node ${node_id}:`, performanceData.stdout)
            }
            // await submitBenchmark(performanceData.stdout, testName.toLowerCase())
        }
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

export async function runProofOfWork(numOfChecks: number, pricePerHour: null | number) {
    const events = new EventTarget()
    let totalRunCost = 0
    const providerRunCost = new Map<string, number>()

    events.addEventListener("GolemEvent", (event: any) => {
        if (event.name === "PaymentAccepted") {
            // console.log(event.detail)
            const cost = Number(event.detail.amount)
            totalRunCost += cost
            // providerRunCost.set(event.detail.provider.id, cost)
            providerRunCost.set(event.detail.providerId, cost)
        }
    })

    const taskId = await sendStartTaskSignal()
    if (!taskId) {
        throw new Error("Failed to send start task signal")
    }
    await initializeBlacklists()
    const STATS_PAGE_PROVIDER_OFFERS = await fetchProvidersData()
    if (!STATS_PAGE_PROVIDER_OFFERS) {
        throw new Error("Failed to fetch providers data")
    }

    const EXPECTED_EXECUTION_TIME_SECONDS = 60 * 20
    const EXPECTED_DEPLOYMENT_TIME_SECONDS = 60
    const EXPECTED_TOTAL_DURATION_SECONDS = EXPECTED_EXECUTION_TIME_SECONDS + EXPECTED_DEPLOYMENT_TIME_SECONDS

    const PRICE_GLM_HOUR = parseFloat(process.env["PRICE_GLM_HOUR"] ?? "3")
    const DURATION_HOURS = EXPECTED_TOTAL_DURATION_SECONDS / 3600

    const REQUEST_START_TIMEOUT_SEC = 90

    const manifest = await readFile("manifest.json")

    const golem = new Golem({
        initTimeoutSec: 90,
        requestStartTimeoutSec: REQUEST_START_TIMEOUT_SEC,
        requestTimeoutSec: EXPECTED_EXECUTION_TIME_SECONDS,
        deploy: {
            // imageHash: "c317251c8e48a74e73f2bf0b74937a2d7e33e0a06ed04e043ab9e2ab",
            manifest: manifest.toString("base64"),
            maxReplicas: numOfChecks,
            resources: { minCpu: 1, minMemGib: 0.5, minStorageGib: 12 },
            downscaleIntervalSec: 90,
            readyTimeoutSec: EXPECTED_DEPLOYMENT_TIME_SECONDS,
        },
        market: {
            // budget: pricePerHour,
            priceGlmPerHour: PRICE_GLM_HOUR,
            rentHours: DURATION_HOURS,
            withoutProviders: blacklistedProviders,
            withoutOperators: blacklistedOperators,
            statsData: STATS_PAGE_PROVIDER_OFFERS,
        },
        taskId: taskId,
        computedAlready: blacklistedProviders,
        eventTarget: events,
    })

    console.log("Preparing activities to run the suite")
    await golem.start()
    console.log("Activities ready, going to start the test")

    try {
        const tasks = []

        // FIXME #sdk This code suffers from the same illness - some of the providers fail to init the activity, and I don't have a easy way to access this info ('Preparing activity timeout' example)
        for (let i = 0; i < numOfChecks; i++) {
            console.log(`Scheduling task #${i}`)
            tasks.push(
                golem.sendTask<GolemTaskResult | undefined>(async (ctx: any) => {
                    const providerId = ctx.provider!.id
                    console.log(`Task #${i} started on provider `, providerId)
                    try {
                        const memory = await benchmarkTest(ctx, providerId, "memory", `/benchmark-memory.sh`, benchmarkMemoryFiles, taskId)
                        if (!memory) {
                            throw new Error("Benchmark failed")
                        }
                        const cpu = await benchmarkTest(ctx, providerId, "cpu", `/benchmark-cpu.sh`, benchmarkCpuFiles, taskId)
                        if (!cpu) {
                            throw new Error("Benchmark failed on CPU speed test")
                        }

                        const disk = await benchmarkTest(ctx, providerId, "disk", `/benchmark-disk.sh`, benchmarkDiskFiles, taskId)

                        if (!disk) {
                            throw new Error("Benchmark failed on disk speed test")
                        }
                        const networkSpeed = await benchmarkTest(ctx, providerId, "network", `/download.sh 10`, networkSpeedFiles, taskId)
                        if (!networkSpeed) {
                            throw new Error("Benchmark failed on network speed test")
                        }

                        if (!failedProvidersIds.includes(providerId)) {
                            taskStatuses.push({
                                node_id: providerId,
                                task_name: "Full benchmark suite",
                                is_successful: true,
                                error_message: "",
                                task_id: Number(taskId),
                            })
                        }

                        return {
                            result: "success",
                            context: {
                                providerId: ctx.activity.agreement.provider.id,
                                activityId: ctx.activity.id,
                                agreementId: ctx.activity.agreement.id,
                            },
                        }
                    } catch (err) {
                        interface ErrorObject {
                            [key: string]: any // This allows indexing with a string to get any value
                        }
                        const errorMessage = err && typeof err === "object" && "message" in err ? err.message : err
                        console.log(`Task #${i} failed on provider ${providerId}:`, errorMessage, "ERROR OBJECT", err)

                        if (!failedProvidersIds.includes(providerId)) {
                            failedProvidersIds.push(providerId)
                            // Submit task status only if the provider is not already blacklisted
                            taskStatuses.push({
                                node_id: providerId,
                                task_name: "Full benchmark suite",
                                is_successful: false,
                                error_message: "Provider hit the timeout limit",
                                task_id: Number(taskId),
                            })
                        } else {
                            console.log(`Provider ${providerId} is already blacklisted, not submitting failed task status`)
                        }
                    } finally {
                        console.log(`Finished benchmarking on provider: ${providerId}`)
                    }
                })
            )
        }

        const results = await Promise.allSettled(tasks)

        const rejected = results.filter((r) => r.status === "rejected") as PromiseRejectedResult[]

        for (const failed of rejected) {
            try {
                if (failed.reason instanceof GolemError) {
                    if (failed.reason.activity?.agreement.provider) {
                        console.log(`Provider failed: ${failed.reason.activity?.agreement.provider.id}`, failed.reason.message)
                        taskStatuses.push({
                            node_id: failed.reason.activity?.agreement.provider.id,
                            task_name: "Full benchmark suite",
                            is_successful: false,
                            error_message: "Provider failed to deploy the activity",
                            task_id: Number(taskId),
                        })
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
        await submitBulkBenchmark(accumulatedBenchmarkData)
        await bulkSubmitTaskStatuses(taskStatuses)

        console.log("Costs:")
        let bulkUpdates = []

        for (const key of providerRunCost.keys()) {
            const cost = providerRunCost.get(key)

            if (typeof cost === "number") {
                console.log(`> ${key}: ${cost}`)
                bulkUpdates.push({ taskId, providerId: key, cost })
            } else {
                console.error(`Cost for provider ${key} is undefined`)
            }
        }

        if (bulkUpdates.length > 0) {
            await sendBulkTaskCostUpdates(bulkUpdates).then((result) => {
                if (result === "success") {
                    console.log("Bulk task cost updates sent successfully.")
                } else {
                    console.error("Error in sending bulk task cost updates.")
                }
            })
        } else {
            console.log("No updates to send.")
        }

        console.log(`Total running cost: ${totalRunCost}`)

        if (taskId) {
            // WE NEED TO ATTACH TOTAL SUM OF EVERYTHING TO THE TASK
            await sendStopTaskSignal(taskId, totalRunCost)
        } else {
            throw new Error("Failed to send stop task signal")
        }
    }
}

// // This function triggers runProofOfWork with the provided number of runs
function triggerRunProofOfWork(num: number, pricePerHour: null | number): void {
    runProofOfWork(num, pricePerHour).catch((err) => {
        console.log(err)
    })
}

// Get the number of runs from the command line arguments
const numRuns = parseInt(process.argv[2])
const pricePerHour = process.argv[3] ? parseInt(process.argv[3]) : null
// Check if the number of runs is a valid number
if (!isNaN(numRuns)) {
    triggerRunProofOfWork(numRuns, pricePerHour)
} else {
    console.log("Please provide a valid number of runs.")
}
