#!/bin/bash
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-eu-west-2}"
ENV_ID="${ENV_ID:-de1}"
ENV_INSTANCE_ID="${ENV_INSTANCE_ID:-001}"

QUEUE_NAMES=(
  "cbif-${ENV_ID}-euw2-sqs-dss-orchestrator-${ENV_INSTANCE_ID}"
  "cbif-${ENV_ID}-euw2-sqs-dss-requests-${ENV_INSTANCE_ID}"
  "cbif-${ENV_ID}-euw2-sqs-dss-statements-${ENV_INSTANCE_ID}"
  "cbif-${ENV_ID}-euw2-sqs-dss-assignment-orchestrator-${ENV_INSTANCE_ID}"
  "cbif-${ENV_ID}-euw2-sqs-dss-assignment-requests-${ENV_INSTANCE_ID}"
)

echo "Creating LocalStack queues in region ${REGION}..."
for q in "${QUEUE_NAMES[@]}"; do
  awslocal sqs create-queue --region "${REGION}" --queue-name "${q}" >/dev/null
  echo "  - created: ${q}"
done

echo "LocalStack queue bootstrap complete."
