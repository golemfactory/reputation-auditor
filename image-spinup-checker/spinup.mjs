
// This script was the initial one that just runs a single task and then shuts down the node.

import { Events, BaseEvent, EventType, TaskExecutor, ProposalFilters } from "@golem-sdk/golem-js"
import minimist from "minimist"

// Parse command line arguments using minimist
const args = minimist(process.argv.slice(2))

// Retrieve arguments or use default values
const packageName = args.packageName || "golem/alpine:latest"
const nodeId = args.nodeId ? [args.nodeId] : null
const timeout = args.timeout || 1000 * 60 * 5 // 5 minutes
const eventTarget = new EventTarget()

let agreementConfirmedTime = 0
let activityReadyTime = 0
let providerId = ""
let taskSucceeded = false // Variable to track task success

eventTarget.addEventListener(EventType, (event) => handleEvents(event))

function handleEvents(event) {
    if (event instanceof Events.AgreementConfirmed) {
        agreementConfirmedTime = Date.now()
        providerId = event.detail.providerId
    } else if (event instanceof Events.ActivityStateChanged) {
        if (event.detail.state === "Ready") {
            activityReadyTime = Date.now()
        }
    }

    // Missing event for task timeout. Not implemented in the SDK so the workaround is just using the catch statement
}

const executorOptions = {
    package: packageName,
    eventTarget,
    yagnaOptions: { apiKey: "try_golem" },
    taskTimeout: timeout,
    payment: { network: "polygon" },
}

// Apply proposalFilter only if nodeId is not null
if (nodeId) {
    executorOptions.proposalFilter = ProposalFilters.whiteListProposalIdsFilter(nodeId)
}

const executor = await TaskExecutor.create(executorOptions)

try {
    await executor.run(async (ctx) => {
        const result = await ctx.run("ls -l")
        taskSucceeded = true // Mark the task as succeeded
    })
} catch (error) {
    console.log("Node failed to spin up in time")
    taskSucceeded = false // Mark the task as failed
} finally {
    await executor.shutdown()

    // Print providerId, image and task success
    console.log("Provider ID:", providerId)
    console.log("Image: ", packageName)
    console.log("Task Success:", taskSucceeded)

    // If task succeeded, print readiness duration
    if (taskSucceeded) {
        const readyDuration = activityReadyTime - agreementConfirmedTime
        console.log("Readiness Duration (ms):", readyDuration)
    }
}
