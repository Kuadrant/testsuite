#!/usr/bin/env bash

# Elasticsearch parameters
ES_INDEX="kube-burner"
ES_URL="$ES_SERVER/$ES_INDEX/_search"

# If UUID1 and UUID2 are not set, get the most recent two jobSummary entries
if [ -z "$UUID1" ] || [ -z "$UUID2" ]; then
  # Get the most recent two jobSummary entries
  curl -k -s -X GET "$ES_URL" \
    -H 'Content-Type: application/json' \
    -d '{
      "size": 2,
      "query": {
        "bool": {
          "must": [
            { "term": { "metricName.keyword": "jobSummary" } },
            { "term": { "jobConfig.name.keyword": "scale-test-main" } }
          ]
        }
      },
      "sort": [
        { "timestamp": { "order": "desc" } }
      ],
      "_source": ["uuid", "elapsedTime", "timestamp"]
    }' > jobSummary.json

  # Extract the uuids, elapsedTime values, and timestamps
  UUID1=$(jq -r '.hits.hits[1]._source.uuid' jobSummary.json)
  UUID2=$(jq -r '.hits.hits[0]._source.uuid' jobSummary.json)

  ELAPSED1=$(jq -r '.hits.hits[1]._source.elapsedTime' jobSummary.json)
  ELAPSED2=$(jq -r '.hits.hits[0]._source.elapsedTime' jobSummary.json)

  TIMESTAMP1=$(jq -r '.hits.hits[1]._source.timestamp' jobSummary.json)
  TIMESTAMP2=$(jq -r '.hits.hits[0]._source.timestamp' jobSummary.json)
else
  # Use the provided UUID1 and UUID2 to get elapsedTime and timestamp
  # Fetch ELAPSED1 and TIMESTAMP1 for UUID1
  response1=$(curl -k -s -X GET "$ES_URL" \
    -H 'Content-Type: application/json' \
    -d "{
      \"size\": 1,
      \"query\": {
        \"bool\": {
          \"must\": [
            { \"term\": { \"metricName.keyword\": \"jobSummary\" } },
            { \"term\": { \"uuid.keyword\": \"$UUID1\" } },
            { \"term\": { \"jobConfig.name.keyword\": \"scale-test-main\" } }
          ]
        }
      },
      \"_source\": [\"elapsedTime\", \"timestamp\"]
    }")
  ELAPSED1=$(echo "$response1" | jq -r '.hits.hits[0]._source.elapsedTime')
  TIMESTAMP1=$(echo "$response1" | jq -r '.hits.hits[0]._source.timestamp')

  # Fetch ELAPSED2 and TIMESTAMP2 for UUID2
  response2=$(curl -k -s -X GET "$ES_URL" \
    -H 'Content-Type: application/json' \
    -d "{
      \"size\": 1,
      \"query\": {
        \"bool\": {
          \"must\": [
            { \"term\": { \"metricName.keyword\": \"jobSummary\" } },
            { \"term\": { \"uuid.keyword\": \"$UUID2\" } },
            { \"term\": { \"jobConfig.name.keyword\": \"scale-test-main\" } }
          ]
        }
      },
      \"_source\": [\"elapsedTime\", \"timestamp\"]
    }")
  ELAPSED2=$(echo "$response2" | jq -r '.hits.hits[0]._source.elapsedTime')
  TIMESTAMP2=$(echo "$response2" | jq -r '.hits.hits[0]._source.timestamp')
fi

# Shorten UUIDs for column headers
UUID_SHORT1="${UUID1:0:8}"
UUID_SHORT2="${UUID2:0:8}"

# Function to get per-namespace CPU values for a given uuid
get_namespace_metric_values() {
  local uuid="$1"
  local metricName="$2"

  curl -k -s -X GET "$ES_URL" \
    -H 'Content-Type: application/json' \
    -d "{
      \"size\": 0,
      \"query\": {
        \"bool\": {
          \"must\": [
            { \"term\": { \"metricName.keyword\": \"$metricName\" } },
            { \"term\": { \"uuid.keyword\": \"$uuid\" } },
            { \"term\": { \"jobName.keyword\": \"scale-test-main\" } }
          ]
        }
      },
      \"aggs\": {
        \"namespaces\": {
          \"terms\": {
            \"field\": \"labels.namespace.keyword\",
            \"size\": 1000
          },
          \"aggs\": {
            \"avg_value\": {
              \"avg\": {
                \"field\": \"value\"
              }
            }
          }
        }
      }
    }" | jq -r '.aggregations.namespaces.buckets[] | [ .key, (.avg_value.value | tostring) ] | @tsv'
}

# Function to get per-controller reconcile time values for a given uuid
get_controller_reconcile() {
  local uuid="$1"

  curl -k -s -X GET "$ES_URL" \
    -H 'Content-Type: application/json' \
    -d "{
      \"size\": 50,
      \"query\": {
        \"bool\": {
          \"must\": [
            { \"term\": { \"metricName.keyword\": \"Controller99thReconcile\" } },
            { \"term\": { \"uuid.keyword\": \"$uuid\" } },
            { \"term\": { \"jobName.keyword\": \"scale-test-main\" } }
          ]
        }
      },
      \"_source\": [\"value\", \"labels.controller\"],
      \"sort\": [
        { \"timestamp\": { \"order\": \"desc\" } }
      ]
    }" | jq -r '.hits.hits[] | [ .["_source"]["labels"]["controller"], .["_source"]["value"] ] | @tsv'
}

# Get per-namespace CPU values
declare -A CPU1_VALUES
declare -A CPU2_VALUES
while IFS=$'\t' read -r namespace value; do
  if [ -z "${CPU1_VALUES["$namespace"]}" ]; then
    CPU1_VALUES["$namespace"]=$value
  fi
done < <(get_namespace_metric_values "$UUID1" "namespaceCPU")

while IFS=$'\t' read -r namespace value; do
  if [ -z "${CPU2_VALUES["$namespace"]}" ]; then
    CPU2_VALUES["$namespace"]=$value
  fi
done < <(get_namespace_metric_values "$UUID2" "namespaceCPU")

ALL_CPU_NAMESPACES=()
for namespace in "${!CPU1_VALUES[@]}"; do
  ALL_CPU_NAMESPACES+=("$namespace")
done
for namespace in "${!CPU2_VALUES[@]}"; do
  if [[ ! " ${ALL_CPU_NAMESPACES[@]} " =~ " ${namespace} " ]]; then
    ALL_CPU_NAMESPACES+=("$namespace")
  fi
done

# Get per-namespace Memory values
declare -A MEM1_VALUES
declare -A MEM2_VALUES
while IFS=$'\t' read -r namespace value; do
  if [ -z "${MEM1_VALUES["$namespace"]}" ]; then
    MEM1_VALUES["$namespace"]=$value
  fi
done < <(get_namespace_metric_values "$UUID1" "namespaceMemory")

while IFS=$'\t' read -r namespace value; do
  if [ -z "${MEM2_VALUES["$namespace"]}" ]; then
    MEM2_VALUES["$namespace"]=$value
  fi
done < <(get_namespace_metric_values "$UUID2" "namespaceMemory")

ALL_MEM_NAMESPACES=()
for namespace in "${!MEM1_VALUES[@]}"; do
  ALL_MEM_NAMESPACES+=("$namespace")
done
for namespace in "${!MEM2_VALUES[@]}"; do
  if [[ ! " ${ALL_MEM_NAMESPACES[@]} " =~ " ${namespace} " ]]; then
    ALL_MEM_NAMESPACES+=("$namespace")
  fi
done

# Get per-controller reconcile time values
declare -A RECONCILE1_VALUES
declare -A RECONCILE2_VALUES
while IFS=$'\t' read -r namespace value; do
  if [ -z "${RECONCILE1_VALUES["$namespace"]}" ]; then
    RECONCILE1_VALUES["$namespace"]=$value
  fi
done < <(get_controller_reconcile "$UUID1")

while IFS=$'\t' read -r namespace value; do
  if [ -z "${RECONCILE2_VALUES["$namespace"]}" ]; then
    RECONCILE2_VALUES["$namespace"]=$value
  fi
done < <(get_controller_reconcile "$UUID2")

ALL_RECONCILE_CONTROLLERS=()
for namespace in "${!RECONCILE1_VALUES[@]}"; do
  ALL_RECONCILE_CONTROLLERS+=("$namespace")
done
for namespace in "${!RECONCILE2_VALUES[@]}"; do
  if [[ ! " ${ALL_RECONCILE_CONTROLLERS[@]} " =~ " ${namespace} " ]]; then
    ALL_RECONCILE_CONTROLLERS+=("$namespace")
  fi
done

# Compare the values and compute differences
compare_values() {
  local val1="$1"
  local val2="$2"
  local format="$3"
  local diff
  local sign

  diff=$(echo "$val2 - $val1" | bc -l)
  if (( $(echo "$diff < 0" | bc -l) )); then
    sign="-"
    diff=$(echo "$val1 - $val2" | bc -l)
  else
    sign="+"
  fi

  printf "%s${format}" "$sign" "$diff"
}

ELAPSED_DIFF=$(compare_values "$ELAPSED1" "$ELAPSED2" "%.0f")

# Output the report
printf "%-25s %-27s %-27s %-20s\n" "Metric" "UUID 1 ($UUID_SHORT1)" "UUID 2 ($UUID_SHORT2)" "Diff"
printf "%-25s %-27s %-27s %-20s\n" "Timestamp" "$TIMESTAMP1" "$TIMESTAMP2" ""
printf "%-25s %-27s %-27s %-20s\n" "Elapsed Time" "$ELAPSED1" "$ELAPSED2" "$ELAPSED_DIFF"
printf "Namespace CPU\n"
for namespace in "${ALL_CPU_NAMESPACES[@]}"; do
  value1="${CPU1_VALUES[$namespace]}"
  value2="${CPU2_VALUES[$namespace]}"

  if [ -z "$value1" ]; then value1=0; fi
  if [ -z "$value2" ]; then value2=0; fi
  diff=$(compare_values "$value1" "$value2" "%.4f")

  value1_formatted=$(printf "%.4f" "$value1")
  value2_formatted=$(printf "%.4f" "$value2")

  printf "%-25s %-27s %-27s %-20s\n" "$namespace" "$value1_formatted" "$value2_formatted" "$diff"
done
printf "Namespace Memory (MB)\n"
for namespace in "${ALL_MEM_NAMESPACES[@]}"; do
  value1="${MEM1_VALUES[$namespace]}"
  value2="${MEM2_VALUES[$namespace]}"

  if [ -z "$value1" ]; then value1=0; fi
  if [ -z "$value2" ]; then value2=0; fi
  diff=$(echo "$value2 - $value1" | bc -l)
  sign=""
  if (( $(echo "$diff < 0" | bc -l) )); then
    sign="-"
    diff=$(echo "$value1 - $value2" | bc -l)
  else
    sign="+"
  fi
  diff=$(echo "scale=2; $diff / 1048576" | bc)

  value1_formatted=$(echo "scale=2; $value1 / 1048576" | bc)
  value2_formatted=$(echo "scale=2; $value2 / 1048576" | bc)

  printf "%-25s %-27s %-27s %s%-20s\n" "$namespace" "$value1_formatted" "$value2_formatted" "$sign" "$diff"
done
printf "Controller 99th Reconcile (s)\n"
for namespace in "${ALL_RECONCILE_CONTROLLERS[@]}"; do
  value1="${RECONCILE1_VALUES[$namespace]}"
  value2="${RECONCILE2_VALUES[$namespace]}"

  if [ -z "$value1" ]; then value1=0; fi
  if [ -z "$value2" ]; then value2=0; fi
  diff=$(compare_values "$value1" "$value2" "%.4f")

  value1_formatted=$(printf "%.4f" "$value1")
  value2_formatted=$(printf "%.4f" "$value2")

  printf "%-25s %-27s %-27s %-20s\n" "$namespace" "$value1_formatted" "$value2_formatted" "$diff"
done
