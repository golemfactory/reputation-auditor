#! /bin/sh
_cputype="$(uname -m)"

case "$_cputype" in
x86_64 | x86-64 | x64 | amd64)
    _cputype=x86_64
    cp /yagna/amd64/yagna /root/.local/bin/yagna
    cp /yagna/amd64/gftp /root/.local/bin/gftp
    ;;
arm64 | aarch64)
    _cputype=aarch64
    cp /yagna/arm64/yagna /root/.local/bin/yagna
    cp /yagna/arm64/gftp /root/.local/bin/gftp
    ;;
*)
    err "invalid cputype: $_cputype"
    ;;
esac
# Start yagna service in the background and log it
mkdir -p /golem/work
touch /golem/work/yagna.log
echo "Starting Yagna"
export YA_NET_BIND_URL=udp://0.0.0.0:11500
YAGNA_AUTOCONF_APPKEY=reputation /root/.local/bin/yagna service run >/dev/null 2>&1 &
sleep 5
# Calculate a delay factor (e.g., 2 seconds between each replica)
DELAY_FACTOR=10

# Check if REPLICA_INDEX is set and is a number
if [ -n "$REPLICA_INDEX" ] && [ "$REPLICA_INDEX" -eq "$REPLICA_INDEX" ] 2>/dev/null; then
    # Calculate the delay for this specific replica
    DELAY=$((REPLICA_INDEX * DELAY_FACTOR))
else
    # Default to 0 if REPLICA_INDEX is not set or not a number
    DELAY=0
    REPLICA_INDEX=0
fi

# Debug output
echo "Replica Index: $REPLICA_INDEX"
echo "Calculated Delay: $DELAY seconds"

# Sleep for the calculated delay
echo "Sleeping for $DELAY seconds..."
sleep $DELAY
echo "Sleep completed."
yagna payment fund

yagna payment fund

# Check if "/key.json" exists
if [ -f "/key.json" ]; then
    echo "Checking wallet from /key.json"
    # Extract address from key.json
    json_address=$(jq -r '.address' /key.json)

    # Get the current yagna id address
    current_address=$(yagna id show --json | jq -r '.Ok.nodeId')

    # Compare the addresses
    if [ "0x$json_address" = "$current_address" ]; then
        echo "Wallet address matches the current yagna id. Skipping restoration."
    else
        echo "Restoring wallet from /key.json"
        echo "Found wallet with address: 0x${json_address}"

        # Proceed with wallet restoration
        yagna id create --from-keystore /key.json
        /root/.local/bin/yagna id update --set-default 0x${json_address}
        killall yagna
        sleep 5
        rm $HOME/.local/share/yagna/accounts.json

        YA_NET_BIND_URL=udp://0.0.0.0:11500 YAGNA_AUTOCONF_APPKEY=reputation /root/.local/bin/yagna service run >/dev/null 2>&1 &
        sleep 5
        echo "Wallet restored"
    fi
fi
