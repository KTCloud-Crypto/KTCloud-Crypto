#!/bin/sh
set -eu

REGION="${AWS_DEFAULT_REGION:-ap-northeast-2}"
TRADING_QUEUE="${SQS_TRADING_COMMAND_QUEUE_NAME:-signaltrade-trading-commands}"
TRADING_DLQ="${SQS_TRADING_COMMAND_DLQ_NAME:-signaltrade-trading-commands-dlq}"
STRATEGY_QUEUE="${SQS_STRATEGY_COMMAND_QUEUE_NAME:-signaltrade-strategy-commands}"
NOTIFICATION_QUEUE="${SQS_NOTIFICATION_QUEUE_NAME:-signaltrade-notifications}"
NOTIFICATION_DLQ="${SQS_NOTIFICATION_DLQ_NAME:-signaltrade-notifications-dlq}"
TRADING_VISIBILITY="${SQS_TRADING_VISIBILITY_TIMEOUT_SECONDS:-300}"
STRATEGY_VISIBILITY="${SQS_STRATEGY_VISIBILITY_TIMEOUT_SECONDS:-60}"
NOTIFICATION_VISIBILITY="${SQS_NOTIFICATION_VISIBILITY_TIMEOUT_SECONDS:-120}"

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

TRADING_QUEUE_URL="$(
  awslocal sqs get-queue-url --region "$REGION" --queue-name "$TRADING_QUEUE" --query QueueUrl --output text 2>/dev/null ||
    awslocal sqs create-queue --region "$REGION" --queue-name "$TRADING_QUEUE" --query QueueUrl --output text
)"
awslocal sqs set-queue-attributes \
  --region "$REGION" \
  --queue-url "$TRADING_QUEUE_URL" \
  --attributes "{\"VisibilityTimeout\":\"$TRADING_VISIBILITY\",\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$DLQ_ARN\\\",\\\"maxReceiveCount\\\":\\\"5\\\"}\"}" >/dev/null

STRATEGY_QUEUE_URL="$(
  awslocal sqs get-queue-url --region "$REGION" --queue-name "$STRATEGY_QUEUE" --query QueueUrl --output text 2>/dev/null ||
    awslocal sqs create-queue --region "$REGION" --queue-name "$STRATEGY_QUEUE" --query QueueUrl --output text
)"
awslocal sqs set-queue-attributes \
  --region "$REGION" \
  --queue-url "$STRATEGY_QUEUE_URL" \
  --attributes "{\"VisibilityTimeout\":\"$STRATEGY_VISIBILITY\"}" >/dev/null

awslocal sqs create-queue --region "$REGION" --queue-name "$NOTIFICATION_DLQ" >/dev/null
NOTIFICATION_DLQ_ARN="$(
  awslocal sqs get-queue-attributes \
    --region "$REGION" \
    --queue-url "$(awslocal sqs get-queue-url --region "$REGION" --queue-name "$NOTIFICATION_DLQ" --query QueueUrl --output text)" \
    --attribute-names QueueArn \
    --query 'Attributes.QueueArn' \
    --output text
)"
NOTIFICATION_QUEUE_URL="$(
  awslocal sqs get-queue-url --region "$REGION" --queue-name "$NOTIFICATION_QUEUE" --query QueueUrl --output text 2>/dev/null ||
    awslocal sqs create-queue --region "$REGION" --queue-name "$NOTIFICATION_QUEUE" --query QueueUrl --output text
)"
awslocal sqs set-queue-attributes \
  --region "$REGION" \
  --queue-url "$NOTIFICATION_QUEUE_URL" \
  --attributes "{\"VisibilityTimeout\":\"$NOTIFICATION_VISIBILITY\",\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$NOTIFICATION_DLQ_ARN\\\",\\\"maxReceiveCount\\\":\\\"5\\\"}\"}" >/dev/null
