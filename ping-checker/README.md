# Overview

The pingProviders.js script is a Node.js application designed to interact with the Golem Network. It fetches online node IDs from the Golem Network's statistics page, pings each provider, and generates a CSV file with the ping results. Additionally, it calculates and displays basic ping statistics.

## Requirements

-   Node.js environment.
-   yagna installed on your system for interacting with the Golem Network.

### Installation

1. Ensure Node.js is installed on your system.
2. Install Yagna
3. Clone this repository or download the pingProviders.js script to your local machine.
4. Navigate to the script's directory in your terminal.

#### Usage

To run the script, execute the following command in your terminal:

```bash
node pingProviders.js
```

### Functions

`fetchNodeIds()`: Fetches online node IDs from the Golem Network's statistics page.

`pingProvider(providerId)`: Pings a provider and returns the result.

`writeToCsv(data)`: Writes ping results to a CSV file.

`calculateStatistics(data)`: Calculates and logs minimum, maximum, and average ping times.

`processProviders()`: Orchestrates the entire process: fetching node IDs, pinging providers, writing to CSV, and calculating statistics.

### Output

-   A CSV file named `output.csv`, containing aliases, node IDs, and ping results.
-   Console log of minimum, maximum, and average ping times.

#### Customization

You can adjust the `chunkSize` variable in the `processProviders` function to change the number of concurrent ping requests.
