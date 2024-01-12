import { TaskExecutor } from "@golem-sdk/golem-js"
import pkg from "./utils.js"
const { submitBenchmark, submitTaskStatus } = pkg

const successfulRunproviders = []
const failedProvidersIds = []
const agreementCreated = []
const currentlyRunningProviders = []


let lastNotEmpty = Date.now(); // Track when the array was last not empty

const checkEmpty = async () => {
    if (currentlyRunningProviders.length === 0) {
        if (Date.now() - lastNotEmpty >= 120000) { // 120000 ms = 120 seconds
            console.log("No providers running for 120 seconds, initiating shutdown.");
            await executor.shutdown();
            process.exit(0); // Exit the script
        }
    } else {
        lastNotEmpty = Date.now(); // Reset the timer whenever the array is not empty
    }
};

const watchDog = () => {
    setInterval(checkEmpty, 10000); // Check every 10 seconds
};

async function logAndSubmitFailure(node_id, task_name, error_message) {
    console.log(`Benchmarking ${task_name} failed on node:`, node_id)
    failedProvidersIds.push(node_id)
    await submitTaskStatus({
        node_id: node_id,
        task_name,
        is_successful: false,
        error_message,
    })
}

const myFilter = async (proposal) => {
    let decision = false
    if (successfulRunproviders.includes(proposal.provider.id) || failedProvidersIds.includes(proposal.provider.id)) {
        console.log("Skipping provider:", proposal.provider.id)
        return false
    }

    let usageVector = proposal.properties["golem.com.usage.vector"]
    let pricingCoeffs = proposal.properties["golem.com.pricing.model.linear.coeffs"]

    for (let i = 0; i < usageVector.length; i++) {
        if (pricingCoeffs[i] * 3600 > 0.7 || usageVector[i] > 0.7) {
            // Too expensive
            return false
        } else {
            return true
        }
    }
    return decision
}

const checkIfArrayContainsId = (ids, id) => ids.includes(id)

export const checkIfIssuerIdExists = (candidates) => {
    for (const candidate of candidates) {
        if (checkIfArrayContainsId(agreementCreated, candidate.proposal.issuerId)) {
            console.log(`IssuerId ${candidate.proposal.issuerId} is already present.`)
        } else {
            return candidate
        }
    }
    return null
}

const benchmarkTest = async (ctx, node_id, testName, scriptName, filePaths) => {
    console.log(`BENCHMARKING ${testName.toUpperCase()} on node:`, node_id, ctx.provider.name)
    const benchmarkResult = await ctx.run(`${scriptName} ${node_id}`)
    if (benchmarkResult.result === "Error") {
        await logAndSubmitFailure(node_id, `Benchmark ${testName}`, benchmarkResult.stdout)
        currentlyRunningProviders.splice(currentlyRunningProviders.indexOf(node_id), 1)
        return
    }

    for (const filePath of filePaths) {
        const performanceData = await ctx.run(`cat /golem/work/${filePath}.json`)
        await submitBenchmark(performanceData.stdout, testName.toLowerCase())
    }
}

;(async () => {
    const executor = await TaskExecutor.create({
        package: "33a9f08e1cc3c6b44f4174fc750d1053eb401d4b9b9532af87c882d4",
        yagnaOptions: { apiKey: "try_golem" },
        taskTimeout: 60 * 60 * 1000,
        minStorageGib: 12,
        maxParallelTasks: 10,
        budget: 1,
        // payment: { network: "polygon" },
        proposalFilter: myFilter,
        agreementSelector: checkIfIssuerIdExists,
        activityExeBatchResultPollIntervalSeconds: 20,
    })

    watchDog();

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

    try {
        const promises = Array.from({ length: 10 }, () =>
            executor.run(async (ctx) => {
                const node_id = ctx.provider.id
                currentlyRunningProviders.push(node_id)
                if (!checkIfArrayContainsId(agreementCreated, node_id)) {
                    await benchmarkTest(ctx, node_id, "memory", `/benchmark-memory.sh`, benchmarkMemoryFiles)
                    await benchmarkTest(ctx, node_id, "cpu", `/benchmark-cpu.sh`, benchmarkCpuFiles)
                    await benchmarkTest(ctx, node_id, "disk", `/benchmark-disk.sh`, benchmarkDiskFiles)
                    successfulRunproviders.push(node_id)
                    await submitTaskStatus({
                        node_id,
                        task_name: "Full benchmark suite",
                        is_successful: true,
                        error_message: "",
                    })
                    currentlyRunningProviders.splice(currentlyRunningProviders.indexOf(node_id), 1)
                }
            })
        )

        await Promise.all(promises)
        console.log("Benchmarking complete!")
    } catch (err) {
        console.error("An error occurred:", err)
    } finally {
        await executor.shutdown()
        console.log("Nodes that computed the task:", successfulRunproviders)
        console.log("Nodes that failed to compute the task:", failedProvidersIds)
    }
})()
