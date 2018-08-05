#!/usr/bin/env bash

METHOD=${1}
PARAMS=${2}
DOMAIN=${3}

curl -s \
    -o /dev/null \
    --write-out '@contrib/perf/curl_out_format.txt' \
    --header "Content-Type: application/json" \
    --request POST \
    --data "{\"id\":1,\"jsonrpc\":\"2.0\",\"method\":\"$1\",\"params\":$2}" \
    https://$3 | jq .
