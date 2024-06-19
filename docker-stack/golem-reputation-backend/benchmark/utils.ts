import { TaskCompletion, ProviderData, Benchmark } from "./types"
import { Logger } from "pino";
const HOST = process.env.API_HOST ?? (process.env.DOCKER === "true" ? "django:8002" : "api.localhost")
const HTTP = process.env.HTTP ?? "http";
const URL=`${HTTP}://${HOST}`

export async function delay(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function bulkSubmitTaskStatuses(taskStatuses: TaskCompletion[], logger: Logger) {
    if (!taskStatuses.length) return
    try {
        const endpoint = `${URL}/v1/submit/task/status/bulk`

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
        logger.info(responseBody) // Log success message or handle further as required
    } catch (error) {
        logger.error(error, "Error in bulkSubmitTaskStatuses:")
    }
}

export async function fetchProvidersData(logger: Logger): Promise<ProviderData[]> {
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
        logger.error(error, 'Failed to fetch providers data');
        process.exit(1)
    }
}

export async function submitBulkBenchmark(benchmarks: Benchmark[], logger: Logger): Promise<string | undefined> {
    try {
        // Updated endpoint to handle bulk benchmark submissions
        const endpoint = `${URL}/v1/benchmark/bulk`
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
            logger.error({
                error: await response.json().catch((e) => response.statusText),
                data: benchmarks,
            }, "Error in bulk benchmark submission", )
            throw new Error("Bulk benchmark submission failed")
        }
    } catch (error) {
        logger.error(error, "Error:")
        throw error // Re-throw the error to handle it or log it in the calling function
    }
}

export async function getBlacklistedProviders(logger: Logger): Promise<string[]> {
    try {
        const endpoint = `${URL}/v1/blacklisted-providers`

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
            throw new Error(`Failed to get blacklisted providers: ${response.status} ${response.statusText}`)
        }
    } catch (error) {
        logger.error(error, "Failed to get blacklisted providers")
        process.exit(1)
    }
}
export async function getBlacklistedOperators(logger: Logger): Promise<string[] | undefined> {
    try {
        const endpoint = `${URL}/v1/blacklisted-operators`

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
            logger.error(`Failed to initialize blacklisted providers, reponse not OK: ${response.status} ${response.statusText}`)
            logger.error(await response.text())
            process.exit(1)
        }
    } catch (error) {
        logger.error(error, "Failed to initialize blacklisted providers:")
        process.exit(1);
    }
}

export async function sendStartTaskSignal(logger: Logger): Promise<string> {
    try {
        const endpoint = `${URL}/v1/task/start`
        const jsonData = JSON.stringify({
            name: "spinup suite",
        });

        const response = await fetch(endpoint, {
            method: "POST",
            credentials: "include",
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
            const errorBody = await response.text()
            throw errorBody
        }
    } catch (error) {
        logger.error(error, `Error in task start`)
        throw error;
    }
}

export async function sendStopTaskSignal(taskId: string, cost: number, logger: Logger): Promise<string | undefined> {
    try {
        const endpoint = `${URL}/v1/task/end/${taskId}?cost=${cost}`
        logger.info(`Sending stop signal task ${taskId}, cost ${cost}`);
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
        logger.error(error, "Failed to send stop signal");
    }
}

export async function sendOfferFromProvider(
    offer: {},
    nodeId: string,
    taskId: string,
    accepted: boolean,
    reason: string,
    logger: Logger,
): Promise<string | undefined> {
    const data = {
        node_id: nodeId,
        offer,
        task_id: taskId,
        accepted: accepted,
        reason: reason,
    };

    try {
        const endpoint = `${URL}/v1/task/offer/${taskId}`
        const json = JSON.stringify(data);
        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${process.env.BACKEND_API_TOKEN}`,
            },
            body: json,
        })

        if (response.ok) {
            return "success"
        } else {
            const errorBody = (await response.json()) as { error: string }
            throw errorBody
        }
    } catch (error) {
        logger.error({error, data}, "Failed log offer")
    }
}

export async function sendBulkTaskCostUpdates(
    updates: Array<{ taskId: string; providerId: string; cost: number }>,
    logger: Logger,
): Promise<string | undefined> {
    try {
        const endpoint = `${URL}/v1/tasks/update-costs`
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
            const errorBody = (await response.json()) as { error: string }
            throw errorBody;
        }
    } catch (error) {
        logger.error({
            error,
            data: updates,
          }, "Error in sending bulk task cost updates:"
        )
        return undefined
    }
}
