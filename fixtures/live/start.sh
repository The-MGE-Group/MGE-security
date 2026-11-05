#!/usr/bin/env bash
# Starts the fake app for the self-test. Usage: bash fixtures/live/start.sh [--leaky]
set -euo pipefail
cd "$(dirname "$0")"
openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 1 -subj /CN=localhost 2>/dev/null
# Fake test logins (not real anywhere), handed to the access test like repository secrets would be.
{
  echo "FIXTURE_ANON_KEY=fixture-anon-key"
  echo "FIXTURE_PASSWORD=fixture-password-not-real"
  echo "FIXTURE_A_ADMIN_EMAIL=a-admin@fixture.test"
  echo "FIXTURE_A_MEMBER_EMAIL=a-member@fixture.test"
  echo "FIXTURE_B_ADMIN_EMAIL=b-admin@fixture.test"
} >> "$GITHUB_ENV"
nohup python3 server.py "$@" > /tmp/fixture-server.log 2>&1 &
