#!/bin/sh
set -eu

REGION="${AWS_DEFAULT_REGION:-ap-northeast-2}"
TRADING_QUEUE="${SQS_TRADING_COMMAND_QUEUE_NAME:-signaltrade-trading-commands}"
TRADING_DLQ="${SQS_TRADING_COMMAND_DLQ_NAME:-signaltrade-trading-commands-dlq}"

awslocal sqs create-queue \
  --region "$REGION" \
  --queue-name "$TRADING_DLQ" >/dev/null

DLQ_ARN="$(
  awslocal sqs get-queue-attributes \
    --region "$REGION" \
    --queue-url "$(awslocal sqs get-queue-url --region "$REGION" --queue-name "$TRADING_DLQ" --query QueueUrl --output text)" \
    --attribute-names QueueArn \
    --query 'Attributes.QueueArn' \
    --output text
)"

awslocal sqs create-queue \
  --region "$REGION" \
  --queue-name "$TRADING_QUEUE" \
  --attributes "{\"VisibilityTimeout\":\"30\",\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$DLQ_ARN\\\",\\\"maxReceiveCount\\\":\\\"5\\\"}\"}" >/dev/null
