import { TaskCompletion, ProviderData, Benchmark } from "./types"
const URL = process.env.API_HOST ?? process.env.DOCKER === "true" ? "django:8002" : "api.localhost"

export async function bulkSubmitTaskStatuses(taskStatuses: TaskCompletion[]) {
    if (!taskStatuses.length) return
    try {
        const endpoint = `http://${URL}/v1/submit/task/status/bulk`

        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${process.env.BACKEND_API_TOKEN}`,
            },
            body: JSON.stringify(taskStatuses), // Modified to send the array directly
        })

        // Handle response as needed
        if (!response.ok) {
            throw new Error("Failed to submit task statuses")
        }
        const responseBody = await response.json()
        console.log(responseBody) // Log success message or handle further as required
    } catch (error) {
        console.error("Error in bulkSubmitTaskStatuses:", error)
    }
}

export async function fetchProvidersData(): Promise<ProviderData[]> {
    try {
        const response = await fetch("https://api.stats.golem.network/v2/network/online")
        if (!response.ok) {
            throw new Error(`Error fetching providers data: ${response.statusText}`)
        }
        const data = await response.json()

        // Perform a basic type check, assuming the data should be an array
        // NOTE: This is a very simplistic type check. You might need a more detailed validation depending on your data structure.
        if (!Array.isArray(data) || !data.every((provider) => typeof provider === "object" && provider.node_id && provider.runtimes)) {
            throw new Error("Invalid data structure received from providers data")
        }

        // Cast the data to ProviderData[] now that we've performed a check
        return data as ProviderData[]
    } catch (error) {
        console.error(error)
        process.exit(1)
    }
}

export async function submitBulkBenchmark(benchmarks: Benchmark[]): Promise<string | undefined> {
    try {
        // Updated endpoint to handle bulk benchmark submissions
        const endpoint = `http://${URL}/v1/benchmark/bulk`
        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${process.env.BACKEND_API_TOKEN}`,
            },
            // The body now includes a 'benchmarks' field containing an array of benchmark entries
            body: JSON.stringify({ benchmarks }),
        })

        if (response.ok) {
            return "Bulk benchmark submission successful!"
        } else {
            console.log("Error in bulk benchmark submission", benchmarks)
            const errorResponse = await response.json()
            console.error("Response Error:", errorResponse)
            throw new Error("Bulk benchmark submission failed")
        }
    } catch (error) {
        console.error("Error:", error)
        throw error // Re-throw the error to handle it or log it in the calling function
    }
}

export async function getBlacklistedProviders(): Promise<string[]> {
    try {
        const endpoint = `http://${URL}/v1/blacklisted-providers`

        const response = await fetch(endpoint, {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
        })

        if (response.ok) {
            const data = (await response.json()) as string[]
            return data
        } else {
            process.exit(1)
        }
    } catch (error) {
        console.error("Error:", error)
        process.exit(1)
    }
}
export async function getBlacklistedOperators(): Promise<string[] | undefined> {
    try {
        const endpoint = `http://${URL}/v1/blacklisted-operators`

        const response = await fetch(endpoint, {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
        })

        if (response.ok) {
            const data = (await response.json()) as string[]
            return data
        } else {
            console.error(`Failed to initialize blacklisted providers, reponse not OK: ${response.status} ${response.statusText}`)
            console.error(await response.text())
            process.exit(1)
        }
    } catch (error) {
        console.error("Failed to initialize blacklisted providers:", error)
        process.exit(1)
    }
}

export async function sendStartTaskSignal(): Promise<string | undefined> {
    try {
        const endpoint = `http://${URL}/v1/task/start`
        const jsonData = JSON.stringify({
            name: "spinup suite",
        })

        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${process.env.BACKEND_API_TOKEN}`,
            },
            body: jsonData,
        })

        if (response.ok) {
            const data = (await response.json()) as { id: string }
            return data.id
        } else {
            console.log(`Error in task start: ${jsonData}`)
            const errorBody = await response.text()
            throw errorBody
        }
    } catch (error) {
        console.error("Error:", error)
    }
}

export async function sendStopTaskSignal(taskId: string, cost: number): Promise<string | undefined> {
    try {
        const endpoint = `http://${URL}/v1/task/end/${taskId}?cost=${cost}`
        console.log(`Sending stop signal to ${endpoint}`, cost, taskId)
        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${process.env.BACKEND_API_TOKEN}`,
            },
        })

        if (response.ok) {
            return "success"
        } else {
            const errorBody = (await response.json()) as { error: string }
            throw errorBody
        }
    } catch (error) {
        console.error("Error:", error)
    }
}

export async function sendOfferFromProvider(
    offer: {},
    nodeId: string,
    taskId: string,
    accepted: boolean,
    reason: string
): Promise<string | undefined> {
    try {
        const endpoint = `http://${URL}/v1/task/offer/${taskId}`
        const data = JSON.stringify({
            node_id: nodeId,
            offer,
            task_id: taskId,
            accepted: accepted,
            reason: reason,
        })
        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${process.env.BACKEND_API_TOKEN}`,
            },
            body: data,
        })

        if (response.ok) {
            return "success"
        } else {
            console.log(`Error in offer submission: ${data}`)
            const errorBody = (await response.json()) as { error: string }
            throw errorBody
        }
    } catch (error) {
        console.error("Error:", error)
    }
}

export async function sendBulkTaskCostUpdates(
    updates: Array<{ taskId: string; providerId: string; cost: number }>
): Promise<string | undefined> {
    try {
        const endpoint = `http://${URL}/v1/tasks/update-costs`
        const data = JSON.stringify({
            updates: updates.map((update) => ({
                task_id: Number(update.taskId),
                provider_id: update.providerId,
                cost: Number(update.cost),
            })),
        })

        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${process.env.BACKEND_API_TOKEN}`,
            },
            body: data,
        })

        if (response.ok) {
            return "success"
        } else {
            console.error(`Error in sending bulk task cost updates: ${data}`)
            const errorBody = (await response.json()) as { error: string }
            console.error(errorBody)
        }
    } catch (error) {
        console.error("Error:", error)
        return undefined
    }
}
