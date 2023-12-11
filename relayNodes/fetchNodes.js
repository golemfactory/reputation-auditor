const fs = require("fs")
const Papa = require("papaparse") // CSV parser

async function queryApiForAllPrefixes() {
    let allData = {}
    const characters = "0123456789abcdef" // Valid first characters for an Ethereum address

    for (let char of characters) {
        try {
            let response = await fetch(`http://yacn2.dev.golem.network:9000/nodes/${char}`)
            let data = await response.json()

            for (let [id, nodes] of Object.entries(data)) {
                nodes.forEach((node) => {
                    allData[id] = {
                        ip: node.peer.split(":")[0],
                        port: node.peer.split(":")[1],
                        seen: node.seen,
                    }
                })
            }
        } catch (error) {
            console.error("Error fetching data for prefix", char, ":", error)
        }
    }

    // Convert object to array for CSV
    let csvData = Object.entries(allData).map(([id, node]) => ({ id, ...node }))

    // Convert to CSV
    let csv = Papa.unparse(csvData)

    // Write to a CSV file
    fs.writeFileSync("nodes.csv", csv)
    console.log("Data written to nodes.csv")
}

queryApiForAllPrefixes()
