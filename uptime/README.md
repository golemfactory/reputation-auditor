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

# Looping the script

To ensure that a new instance of your script is only scheduled after the previous one has finished using systemd, you need to create a systemd service and a systemd timer. Here's how you can set it up:

1. Create a systemd Service
   A systemd service file will define how your script should be run. Create a new service file under /etc/systemd/system/ with a .service extension, for example, mynodescript.service.

Here's an example of what the file might look like:

```ini
[Unit]
Description=Node Monitoring Script

[Service]
Type=oneshot
User=ubuntu
ExecStart=/usr/bin/python3 /home/ubuntu/reputation-auditor/uptime/scanner.py
Environment=YAGNA_APPKEY=stats
WorkingDirectory=/home/ubuntu/reputation-auditor/uptime
```

Type=oneshot: This indicates that the service is a one-time task and will exit after running. Systemd will consider the service as 'finished' once the script exits.
ExecStart: The command to start your script. Change the paths according to your script's location and the Python interpreter. 2. Create a systemd Timer
A systemd timer will schedule when your service should be run. Create a new timer file under /etc/systemd/system/ with a .timer extension, for example, mynodescript.timer.

Here's an example of what the file might look like:

```ini
[Unit]
Description=Runs node script every 30 seconds

[Timer]
OnBootSec=10sec
OnUnitActiveSec=30sec
Unit=uptimescanner.service

[Install]
WantedBy=timers.target
```

OnBootSec: This sets a delay for the first time the timer is activated after boot. It's set to 10 seconds here but can be adjusted as needed.
OnUnitActiveSec: This sets the interval between job activations. Here, it's set to every 30 seconds.
Unit: The name of the service unit that this timer should activate. 3. Enable and Start the Timer
Once both the service and timer files are created, you need to enable and start them. First, reload the systemd manager configuration to read the newly created files:

```bash
sudo systemctl daemon-reload

```

Now, enable and start your timer:

```bash
sudo systemctl enable uptimescanner.timer  # Enables the timer to start on boot
sudo systemctl start uptimescanner.timer   # Starts the timer immediately
```

## Ensuring Non-Overlap

Systemd timers coupled with a Type=oneshot service inherently ensure that the script won't overlap with itself. The timer activates the service according to the schedule defined in OnUnitActiveSec, but if the service (your script) is still running from the last activation, systemd will wait for it to finish before starting it again.

This way, you can ensure that the script is only scheduled after the previous run has finished, preventing any overlaps that might occur with crontab.

## Viewing Logs and Status

To check the status of your timer and service, use:

systemctl status mynodescript.timer - for the timer
systemctl status mynodescript.service - for the service
And to view logs produced by your script:

journalctl -u mynodescript.service
This setup provides a robust and flexible way to schedule tasks like your script while ensuring they don't overlap, using the power and reliability of systemd.
