# Introduction

This script is designed to monitor and measure the uptime of nodes within the Golem network. It uses Python and the Golem API (`yapapi`) to periodically check the status of various nodes and updates a CSV file with the latest status information.

## Features

-   **Node Status Tracking:** Tracks whether nodes are online or offline at each scan.
-   **Uptime Calculation:** Calculates the uptime percentage for each node based on the number of scans.
-   **CSV Logging:** Records node status in a CSV file for historical analysis.
-   **Configurable Scan Frequency:** Allows setting the time interval for node status scans.

## Requirements

-   Python 3.7 or higher.
-   `yapapi` package: Golem API for Python.
-   `asyncio` for asynchronous programming.
-   Other dependencies: `csv`, `json`, `pathlib`, `subprocess`, `datetime`.

## Installation

1. Ensure Python 3.7 or higher is installed on your system.
2. Install `yapapi` and other required packages using pip:

## Usage

1. Run the script using Python:
2. Optionally, specify a subnet tag to monitor nodes in a specific subnet `python scanner.py --subnet-tag someSubnet`:

## Key Functions

-   `update_csv()`: Writes node status data to a CSV file.
-   `calculate_uptime()`: Calculates the uptime percentage of a node.
-   `check_node_status()`: Checks if a node is currently online.
-   `load_scan_count()`: Loads the number of scans conducted so far.
-   `save_scan_count()`: Saves the current scan count to a file.
-   `list_offers()`: Lists offers in the Golem market and updates node status.
-   `monitor_nodes_status()`: Main function to monitor nodes and update their status.
-   `main()`: Entry point of the script, handling command-line arguments.

## CSV File Format

The CSV file `nodes_status.csv` contains the following columns:

-   `issuer_id`: Unique identifier of the node.
-   `is_online`: Indicates if the node is online (`True` or `False`).
-   `last_seen`: Timestamp of the last time the node was seen online.
-   `total_online_scans`: Total number of times the node was found online.
-   `uptime`: Calculated uptime percentage of the node.

## Notes

-   The script uses `asyncio` for asynchronous operations and `subprocess` for executing shell commands.
-   Make sure `yagna` service is running and configured on the system where the script is executed.
-   The script can be modified for more detailed logging or different interval settings as needed.

## License

This script is provided "as is", without warranty of any kind. Feel free to use, modify, and distribute as per your requirements.
