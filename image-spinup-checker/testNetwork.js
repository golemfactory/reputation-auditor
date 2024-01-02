// This script tries to fetch all nodes from the stats page and then run a single task on each node.

const { createObjectCsvWriter } = require("csv-writer")
const { exec } = require("child_process")
const { Events, BaseEvent, EventType, TaskExecutor, ProposalFilters } = require("@golem-sdk/golem-js")
const minimist = require("minimist")
function chunkArray(array, size) {
    const chunks = []
    for (let i = 0; i < array.length; i += size) {
        chunks.push(array.slice(i, i + size))
    }
    return chunks
}

const apiUrl = "https://api.stats.golem.network/v2/network/online"
const csvWriter = createObjectCsvWriter({
    path: "test-results.csv",
    header: [
        { id: "date", title: "DATE" },
        { id: "nodeId", title: "NODE_ID" },
        { id: "status", title: "STATUS" },
        { id: "providerId", title: "PROVIDER_ID" },
        { id: "readinessDuration", title: "READINESS_DURATION" },
        { id: "packageName", title: "PACKAGE_NAME" },
        { id: "timeout", title: "TIMEOUT" },
    ],
})

async function fetchProviders() {
    try {
        const response = await fetch(apiUrl)
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
        }
        const data = await response.json()
        return data.map((provider) => provider.node_id)
    } catch (error) {
        console.error("Error fetching providers:", error)
        return []
    }
}

async function runSpinupScript(nodeId) {
    return new Promise(async (resolve, reject) => {
        console.log("Running spinup script for node:", nodeId)
        const simulatedArgs = [`--nodeId=${nodeId}`]
        const args = minimist(simulatedArgs, {
            default: { packageName: "golem/alpine:latest", timeout: 1000 * 60 * 1 }, // 1 minute
        })
        console.log(args)
        const eventTarget = new EventTarget()
        let agreementConfirmedTime = 0
        let activityReadyTime = 0
        let providerId = ""
        let taskSucceeded = false

        eventTarget.addEventListener(EventType, (event) => {
            if (event instanceof Events.AgreementConfirmed) {
                agreementConfirmedTime = Date.now()
                providerId = event.detail.providerId
            } else if (event instanceof Events.ActivityStateChanged && event.detail.state === "Ready") {
                activityReadyTime = Date.now()
            }
        })

        const executorOptions = {
            package: args.packageName,
            eventTarget,
            yagnaOptions: { apiKey: "try_golem" },
            taskTimeout: args.timeout,
            payment: { network: "polygon" },
            budget: 0.05,
        }
        console.log(executorOptions)

        if (nodeId) {
            executorOptions.proposalFilter = ProposalFilters.whiteListProposalIdsFilter([nodeId])
        }

        const executor = await TaskExecutor.create(executorOptions)

        try {
            await executor.run(async (ctx) => {
                await ctx.run("ls -l")
                taskSucceeded = true
            })
        } catch (error) {
            taskSucceeded = false
        } finally {
            await executor.shutdown()
            const readyDuration = taskSucceeded ? activityReadyTime - agreementConfirmedTime : null
            resolve({ providerId, taskSucceeded, readyDuration, packageName: args.packageName, timeout: args.timeout })
        }
    })
}

async function testProviders() {
    const nodeIds = await fetchProviders()
    const chunkedNodeIds = chunkArray(nodeIds.slice(0, 10) , 3) // chunking into groups of 30

    for (const chunk of chunkedNodeIds) {
        const providerTests = chunk.map((nodeId) => runSpinupScript(nodeId))

        const results = await Promise.allSettled(providerTests)

        const csvData = results.map((result, index) => {
            if (result.status === "fulfilled") {
                const { providerId, taskSucceeded, readyDuration, packageName, timeout } = result.value
                const status = taskSucceeded ? "Success" : "Failed"
                return {
                    date: new Date().toISOString(),
                    nodeId: chunk[index],
                    status,
                    providerId,
                    readinessDuration: readyDuration,
                    packageName,
                    timeout,
                }
            } else {
                return { date: new Date().toISOString(), nodeId: chunk[index], status: "Failed", packageName: null, timeout: null }
            }
        })

        await csvWriter.writeRecords(csvData)
    }
}

testProviders()
