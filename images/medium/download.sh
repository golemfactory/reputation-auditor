#!/bin/sh

URL="https://registry.golem.network/v1/image/download?tag=scalepointai/automatic1111:2&https=true"
TIME=$1        # time in seconds taken from the first script argument
PROVIDER_ID=$2 # provider_id taken from the second script argument
OUTPUT_FILE="/golem/work/downloaded_file"
OUTPUT_JSON="/golem/work/networkspeedresult.json"
ERROR_MSG=""

# Function to calculate download speed
calculate_speed() {
    if [ -f "$OUTPUT_FILE" ]; then
        SIZE_KB=$(du -k "$OUTPUT_FILE" | cut -f1)      # File size in KB
        SPEED=$(echo "scale=2; $SIZE_KB / $TIME" | bc) # Calculate speed in KB/s
        echo "scale=2; ($SPEED * 8 / 1000)" | bc       # Convert speed to Mbit/s
    else
        echo "Error: Downloaded file not found."
        return 1
    fi
}

# Check if time and provider_id were provided
if [ -z "$TIME" ] || [ -z "$PROVIDER_ID" ]; then
    ERROR_MSG="Error: Required parameters (download timeout and provider_id) not provided."
    echo '{"speed": null, "error": "'$ERROR_MSG'", "node_id": "'$PROVIDER_ID'"}' >$OUTPUT_JSON
    echo $ERROR_MSG
    exit 1
fi

# Start the download in the background
curl -L $URL --output $OUTPUT_FILE &

# Capture the PID of the download process
DOWNLOAD_PID=$!

# Wait for the specified time
sleep $TIME

# Kill the download process
kill $DOWNLOAD_PID

# Calculate the speed
SPEED=$(calculate_speed)
if [ $? -ne 0 ]; then
    ERROR_MSG=$SPEED
    echo '{"speed": null, "error": "'$ERROR_MSG'", "node_id": "'$PROVIDER_ID'"}' >$OUTPUT_JSON
    echo $ERROR_MSG
    exit 1
fi

# Create a JSON string
JSON_STRING=$(printf '{"speed": %s, "error": "%s", "node_id": "%s"}' "$SPEED" "$ERROR_MSG" "$PROVIDER_ID")

# Write the JSON string to a file
echo $JSON_STRING >$OUTPUT_JSON

rm $OUTPUT_FILE
