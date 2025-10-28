#!/bin/bash

# Load test script for producer service
# Usage: ./load-test.sh [number_of_requests]

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default to 10 requests if no argument provided
NUM_REQUESTS=${1:-10}

# Validate input is a number
if ! [[ "$NUM_REQUESTS" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}Error: Argument must be a positive integer${NC}"
    echo "Usage: $0 [number_of_requests]"
    exit 1
fi

# Producer endpoint
ENDPOINT="http://localhost:8000/jobs"

echo -e "${YELLOW}=== Load Test Starting ===${NC}"
echo "Endpoint: $ENDPOINT"
echo "Number of requests: $NUM_REQUESTS"
echo ""

# Job types to vary the payload
JOB_TYPES=("email" "resize" "transcode" "notification" "backup")
SUCCESS_COUNT=0
FAILURE_COUNT=0

START_TIME=$(date +%s)

for i in $(seq 1 $NUM_REQUESTS); do
    # Randomly select a job type
    JOB_TYPE=${JOB_TYPES[$((RANDOM % ${#JOB_TYPES[@]}))]}
    
    # Generate varied payload based on job type
    case $JOB_TYPE in
        "email")
            PAYLOAD="{\"type\":\"email\",\"recipient\":\"user${i}@example.com\",\"subject\":\"Test ${i}\"}"
            ;;
        "resize")
            PAYLOAD="{\"type\":\"resize\",\"image_id\":\"img_${i}\",\"size\":\"1024x768\"}"
            ;;
        "transcode")
            PAYLOAD="{\"type\":\"transcode\",\"video_id\":\"vid_${i}\",\"format\":\"mp4\"}"
            ;;
        "notification")
            PAYLOAD="{\"type\":\"notification\",\"user_id\":\"user_${i}\",\"message\":\"Update ${i}\"}"
            ;;
        "backup")
            PAYLOAD="{\"type\":\"backup\",\"file_id\":\"file_${i}\",\"destination\":\"s3\"}"
            ;;
    esac
    
    # Send the request
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" 2>&1)
    
    # Extract HTTP status code (last line) and response body (everything else)
    HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    
    if [ "$HTTP_CODE" = "200" ]; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        MESSAGE_ID=$(echo "$BODY" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
        echo -e "${GREEN}✓${NC} Request $i/$NUM_REQUESTS - Type: $JOB_TYPE - Message ID: $MESSAGE_ID"
    else
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        echo -e "${RED}✗${NC} Request $i/$NUM_REQUESTS - Type: $JOB_TYPE - HTTP $HTTP_CODE - $BODY"
    fi
    
    # Optional: Add a small delay to avoid overwhelming the service
    # Uncomment the line below to add a 10ms delay between requests
    # sleep 0.01
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo -e "${YELLOW}=== Load Test Complete ===${NC}"
echo "Total requests: $NUM_REQUESTS"
echo -e "${GREEN}Successful: $SUCCESS_COUNT${NC}"
echo -e "${RED}Failed: $FAILURE_COUNT${NC}"
echo "Duration: ${DURATION}s"

# Calculate requests per second (handle division by zero)
if [ "$DURATION" -gt 0 ]; then
    RPS=$(echo "scale=2; $NUM_REQUESTS / $DURATION" | bc)
    echo "Requests per second: $RPS"
else
    echo "Requests per second: N/A (completed too quickly)"
fi

