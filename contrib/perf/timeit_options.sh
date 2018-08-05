#!/usr/bin/env bash

METHOD=${1}
PARAMS=${2}
DOMAIN=${3}

curl -s \
    -o /dev/null \
    --write-out '@contrib/perf/curl_out_format.txt' \
    --header "Content-Type: application/json" \
    --request OPTIONS \
    https://$3 | jq .
