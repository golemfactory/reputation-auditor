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

# Looping the script

To ensure that a new instance of your script is only scheduled after the previous one has finished using systemd, you need to create a systemd service and a systemd timer. Here's how you can set it up:

1. Create a systemd Service
   A systemd service file will define how your script should be run. Create a new service file under /etc/systemd/system/ with a .service extension, for example, pinger.service.

Here's an example of what the file might look like:

```ini
[Unit]
Description=Node Pinging Script

[Service]
Type=oneshot
User=ubuntu
ExecStart=/home/ubuntu/.nvm/versions/node/v21.4.0/bin/node /home/ubuntu/reputation-auditor/ping-checker/pingProviders.js
Environment=YAGNA_APPKEY=stats
WorkingDirectory=/home/ubuntu/reputation-auditor/ping-checker
Environment=PATH=/home/ubuntu/.local/bin:/home/ubuntu/.local/bin:/home/ubuntu/.nvm/versions/node/v21.4.0/bin:/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bins
```

Type=oneshot: This indicates that the service is a one-time task and will exit after running. Systemd will consider the service as 'finished' once the script exits.
ExecStart: The command to start your script. Change the paths according to your script's location and the Python interpreter. 2. Create a systemd Timer
A systemd timer will schedule when your service should be run. Create a new timer file under /etc/systemd/system/ with a .timer extension, for example, pinger.timer.

Here's an example of what the file might look like:

```ini
[Unit]
Description=Runs node script every 30 seconds

[Timer]
OnBootSec=10sec
OnUnitActiveSec=30sec
Unit=pinger.service

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
sudo systemctl enable pinger.timer  # Enables the timer to start on boot
sudo systemctl start pinger.timer   # Starts the timer immediately
```

## Ensuring Non-Overlap

Systemd timers coupled with a Type=oneshot service inherently ensure that the script won't overlap with itself. The timer activates the service according to the schedule defined in OnUnitActiveSec, but if the service (your script) is still running from the last activation, systemd will wait for it to finish before starting it again.

This way, you can ensure that the script is only scheduled after the previous run has finished, preventing any overlaps that might occur with crontab.

## Viewing Logs and Status

To check the status of your timer and service, use:

systemctl status pinger.timer - for the timer
systemctl status pinger.service - for the service
And to view logs produced by your script:

journalctl -u pinger.service
This setup provides a robust and flexible way to schedule tasks like your script while ensuring they don't overlap, using the power and reliability of systemd.
