#!/bin/bash

# Step 1: Perform updates and install necessary packages
sudo apt update && sudo apt upgrade -y
sudo apt install -y screen python3 python3-pip git

# Clone the repository and install dependencies
git clone https://github.com/golemfactory/reputation-auditor
pip3 install yapapi
cd reputation-auditor

# Install nvm and node
curl https://raw.githubusercontent.com/creationix/nvm/master/install.sh | bash
source ~/.bashrc
nvm install node
npm i

# Step 2: Create systemd service file
cat <<EOF | sudo tee /etc/systemd/system/yagna.service
[Unit]
Description=Yagna Service
After=network.target

[Service]
Environment="YAGNA_AUTOCONF_APPKEY=stats"
ExecStart=/home/ubuntu/.local/bin/yagna service run
User=ubuntu
Restart=on-failure
MemoryMax=2G
MemoryHigh=1.8G
Environment=PATH=/home/ubuntu/.local/bin:/home/ubuntu/.nvm/versions/node/v21.4.0/bin:/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin

[Install]
WantedBy=multi-user.target
EOF

# Step 3: Create pinger systemd service file
cat <<EOF | sudo tee /etc/systemd/system/pinger.service
[Unit]
Description=Node Pinging Script

[Service]
Type=oneshot
User=ubuntu
ExecStart=/home/ubuntu/.nvm/versions/node/v21.4.0/bin/node /home/ubuntu/reputation-auditor/ping-checker/pingProviders.js
Environment=YAGNA_APPKEY=stats
WorkingDirectory=/home/ubuntu/reputation-auditor/ping-checker
Environment=PATH=/home/ubuntu/.local/bin:/home/ubuntu/.local/bin:/home/ubuntu/.nvm/versions/node/v21.4.0/bin:/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bins
EOF

# Step 4: Create pinger timer file
cat <<EOF | sudo tee /etc/systemd/system/pinger.timer
[Unit]
Description=Runs node script every 30 seconds

[Timer]
OnBootSec=10sec
OnUnitActiveSec=30sec
Unit=pinger.service

[Install]
WantedBy=timers.target
EOF

# Step 6: Create uptimescanner systemd service file
cat <<EOF | sudo tee /etc/systemd/system/uptimescanner.service
[Unit]
Description=Node Monitoring Script

[Service]
Type=oneshot
User=ubuntu
ExecStart=/usr/bin/python3 /home/ubuntu/reputation-auditor/uptime/scanner.py
Environment=YAGNA_APPKEY=stats
WorkingDirectory=/home/ubuntu/reputation-auditor/uptime
Environment=PATH=/home/ubuntu/.local/bin:/home/ubuntu/.local/bin:/home/ubuntu/.nvm/versions/node/v21.4.0/bin:/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bins
EOF

# Step 7: Create uptimescanner timer file
cat <<EOF | sudo tee /etc/systemd/system/uptimescanner.timer
[Unit]
Description=Runs node script every 30 seconds

[Timer]
OnBootSec=10sec
OnUnitActiveSec=30sec
Unit=uptimescanner.service

[Install]
WantedBy=timers.target
EOF

# Step 8: Reload Systemd and Enable Service
sudo systemctl daemon-reload

sudo systemctl enable yagna.service

sudo systemctl start yagna.service

sudo systemctl enable pinger.timer
sudo systemctl enable uptimescanner.timer

# Optional: Start the service
sudo systemctl start pinger.timer
sudo systemctl start uptimescanner.timer
