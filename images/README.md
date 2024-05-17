# Spin up P2P pinger

docker run -d --net host -p 11500:11500/udp --env-file docker-stack/.envs/.p2p --name ping_worker_p2p --restart unless-stopped ghcr.io/golemfactory/reputation-p2p-ping:latest /bin/sh -c "/start.sh && sleep 5 && python /p2p-ping.py"
