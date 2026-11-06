#!/bin/bash

INSTANCE_ID="${1:?Missing instance ID}"
EXECUTION_TIMEOUT="${2:-3600}"

# Build the remote shell script as a JSON array for AWS-RunShellScript.
commands=$(jq -Rs -c 'split("\n") | if .[-1] == "" then .[:-1] else . end')

# Run the script on the EC2 instance through SSM.
command_id=$(aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --parameters "commands=$commands,executionTimeout=$EXECUTION_TIMEOUT" \
  --query 'Command.CommandId' \
  --output text)

# Poll SSM until the remote command finishes, then print its output.
while true; do
  status=$(aws ssm get-command-invocation \
    --command-id "$command_id" \
    --instance-id "$INSTANCE_ID" \
    --query 'Status' \
    --output text)

  case "$status" in
    Success)
      break
      ;;
    Failed|Cancelled|TimedOut|Cancelling)
      aws ssm get-command-invocation --command-id "$command_id" --instance-id "$INSTANCE_ID" --query 'StandardOutputContent' --output text
      aws ssm get-command-invocation --command-id "$command_id" --instance-id "$INSTANCE_ID" --query 'StandardErrorContent' --output text
      exit 1
      ;;
    Pending|InProgress|Delayed)
      sleep 10
      ;;
  esac
done

aws ssm get-command-invocation \
  --command-id "$command_id" \
  --instance-id "$INSTANCE_ID" \
  --query 'StandardOutputContent' \
  --output text
