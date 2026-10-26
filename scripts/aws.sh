#!/bin/sh
# Runs the AWS CLI (pinned container) as CloudPilot's own AWS identity from .env
# (CLOUDPILOT_AWS_*), never the LocalStack test values. Values are passed by name only.
#   scripts/aws.sh sts get-caller-identity
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
set -a
# shellcheck disable=SC1091
. "$ROOT/.env"
set +a
export AWS_ACCESS_KEY_ID="$CLOUDPILOT_AWS_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$CLOUDPILOT_AWS_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="${CLOUDPILOT_AWS_REGION:-us-east-1}"
unset AWS_ENDPOINT_URL AWS_SESSION_TOKEN
MSYS_NO_PATHCONV=1 exec docker run --rm -i \
    -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION \
    -v "$ROOT:/work" -w /work \
    amazon/aws-cli:2.27.50 "$@"
