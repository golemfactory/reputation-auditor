const URL = process.env.DOCKER === "true" ? "django:8002" : "api.localhost"

export async function submitTaskStatus(data: any): Promise<string | undefined> {
    try {
        const endpoint = `http://${URL}/v1/submit/task/status`

        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                // Include other headers as required, like authentication tokens
            },
            body: JSON.stringify(data),
        })

        if (response.ok) {
            return "Task failure submitted successfully!"
        } else {
            const errorBody = await response.json()
            throw errorBody
        }
    } catch (error) {
        console.error("Error:", error)
    }
}

export async function submitBenchmark(benchmarkData: string, type: string): Promise<string | undefined> {
    try {
        const endpoint = `http://${URL}/v1/benchmark/${type}`

        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                // Include other headers as required, like authentication tokens
            },
            body: benchmarkData,
        })

        if (response.ok) {
            return "Benchmark submitted successfully!"
        } else {
            console.log(`Error in benchmark submission: ${benchmarkData}`)
            const errorBody = await response.json()
            throw errorBody
        }
    } catch (error) {
        console.error("Error:", error)
    }
}

export async function getBlacklistedProviders(): Promise<string[] | undefined> {
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

export async function sendStartTaskSignal(): Promise<string | undefined> {
    try {
        const endpoint = `http://${URL}/v1/task/start`
        const jsonData = JSON.stringify({
            name: "benchmark suite",
        })

        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                // Include other headers as required, like authentication tokens
            },
            body: jsonData,
        })

        if (response.ok) {
            const data = (await response.json()) as { id: string }
            return data.id
        } else {
            console.log(`Error in task start: ${jsonData}`)
            const errorBody = await response.json()
            throw errorBody
        }
    } catch (error) {
        console.error("Error:", error)
    }
}

export async function sendStopTaskSignal(taskId: string): Promise<string | undefined> {
    try {
        const endpoint = `http://${URL}/v1/task/end/${taskId}`

        const response = await fetch(endpoint, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                // Include other headers as required, like authentication tokens
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

export async function sendOfferFromProvider(offer: {}, nodeId: string, taskId: string): Promise<string | undefined> {
    try {
        const endpoint = `http://${URL}/v1/task/offer/${taskId}`
        const data = JSON.stringify({
            node_id: nodeId,
            offer,
            task_id: taskId,
        })
        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                // Include other headers as required, like authentication tokens
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
