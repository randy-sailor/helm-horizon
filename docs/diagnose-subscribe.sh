#!/usr/bin/env bash
# Isolates why POST /contacts is failing, by talking to Resend directly.
#
#   RESEND_API_KEY=re_xxx bash docs/diagnose-subscribe.sh
#
# Nothing here touches the site. Test 1 uses a @example.com address, which is
# reserved and undeliverable, so it will not mail a real person. Delete the
# contact from the Resend dashboard afterwards if you like.

set -u

if [ -z "${RESEND_API_KEY:-}" ]; then
  echo "Set RESEND_API_KEY first:  RESEND_API_KEY=re_xxx bash $0"
  exit 1
fi

API="https://api.resend.com"
AUTH="Authorization: Bearer $RESEND_API_KEY"
JSON="Content-Type: application/json"

hr() { printf '%s\n' "----------------------------------------------------------------"; }

hr
echo "1. Minimal contact — the payload the form falls back to"
curl -sS -o /tmp/hh1.json -w "   HTTP %{http_code}\n" \
  -X POST "$API/contacts" -H "$AUTH" -H "$JSON" \
  -d '{"email":"diagnostic@example.com","first_name":"Diag","last_name":"Nostic","unsubscribed":false}'
sed 's/^/   /' /tmp/hh1.json; echo

hr
echo "2. Same contact WITH custom properties — what the form actually sends"
curl -sS -o /tmp/hh2.json -w "   HTTP %{http_code}\n" \
  -X POST "$API/contacts" -H "$AUTH" -H "$JSON" \
  -d '{"email":"diagnostic2@example.com","first_name":"Diag","last_name":"Nostic","unsubscribed":false,"properties":{"role":"Broker","company":"Test"}}'
sed 's/^/   /' /tmp/hh2.json; echo

hr
echo "3. Key permission check — listing domains needs full_access"
curl -sS -o /tmp/hh3.json -w "   HTTP %{http_code}\n" \
  -X GET "$API/domains" -H "$AUTH"
sed 's/^/   /' /tmp/hh3.json | cut -c1-300; echo

hr
cat <<'EOF'
How to read this:

  1 fails 401/403, 3 fails too   -> the key is sending_access. Regenerate it
                                    with Full access. This is the common case.
  1 fails 401/403, 3 succeeds    -> key is fine but lacks contact scope;
                                    check the key's settings in Resend.
  1 succeeds, 2 fails            -> the custom properties are the problem.
                                    api/subscribe.js now falls back
                                    automatically, so signups survive it, but
                                    role/company will not be recorded until
                                    the properties exist on the account.
  1 and 2 both succeed           -> Resend is fine and the fault is on the
                                    Vercel side. Almost always the env var
                                    not reaching a build: confirm
                                    RESEND_API_KEY is set for Production and
                                    redeploy, then check the function logs.
  everything 429                 -> rate limited, just retry.
EOF
hr
