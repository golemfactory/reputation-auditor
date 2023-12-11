const { exec } = require("child_process")
const fs = require("fs")

// Function to fetch node IDs from the API
async function fetchNodeIds() {
    const url = "https://api.stats.golem.network/v1/network/online"
    const response = await fetch(url)
    const data = await response.json()
    return data.map((item) => item.node_id)
}

// Function to execute command and process output
function pingProvider(providerId) {
    return new Promise((resolve, reject) => {
        exec(`yagna net ping ${providerId} --json`, (error, stdout, stderr) => {
            if (error) {
                reject(`error: ${error.message}`)
                return
            }
            if (stderr) {
                reject(`stderr: ${stderr}`)
                return
            }
            resolve(JSON.parse(stdout))
        })
    })
}

// Function to write to CSV
function writeToCsv(data) {
    let csvContent = "alias,nodeId,p2p,ping (tcp),ping (udp)\n" // Add header line

    data.forEach((item) => {
        csvContent += `${item.alias},${item.nodeId},${item.p2p},${item["ping (tcp)"]},${item["ping (udp)"]}\n`
    })

    fs.writeFile("output.csv", csvContent, (err) => {
        if (err) throw err
        console.log("CSV file saved!")
    })
}

// Function to calculate statistics
function calculateStatistics(data) {
    let minPing = Number.MAX_VALUE
    let maxPing = 0
    let sumPing = 0

    data.forEach((item) => {
        const tcpPing = parseFloat(item["ping (tcp)"])
        const udpPing = parseFloat(item["ping (udp)"])

        minPing = Math.min(minPing, tcpPing, udpPing)
        maxPing = Math.max(maxPing, tcpPing, udpPing)
        sumPing += (tcpPing + udpPing) / 2 // Average of TCP and UDP pings
    })

    const avgPing = sumPing / data.length
    console.log(`Ping Statistics: \n- Minimum Ping: ${minPing} ms\n- Maximum Ping: ${maxPing} ms\n- Average Ping: ${avgPing.toFixed(2)} ms`)
}

// Main logic to process each provider ID
async function processProviders() {
    try {
        const nodeIds = await fetchNodeIds()

        // Splitting nodeIds into smaller chunks for concurrent processing
        const chunkSize = 100 // adjust this number based on your concurrency needs
        let allData = []

        for (let i = 0; i < nodeIds.length; i += chunkSize) {
            const chunk = nodeIds.slice(i, i + chunkSize)

            const results = await Promise.allSettled(chunk.map((id) => pingProvider(id)))

            for (const result of results) {
                if (result.status === "fulfilled") {
                    allData = allData.concat(result.value)
                } else {
                    console.error("Ping failed:", result.reason)
                }
            }
        }

        writeToCsv(allData)
        calculateStatistics(allData)
    } catch (error) {
        console.error("Error fetching node IDs:", error)
    }
}

processProviders()
