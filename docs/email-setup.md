# Email setup — Resend + ImprovMX

> **Before merging:** the site now publishes `editor@thehelmandhorizon.com` in
> every footer, the About masthead, and the corrections and error messages. That
> alias does not exist until you create it in ImprovMX and the MX records
> resolve. Merging this branch before then means the site advertises an address
> that bounces. Create the alias first, confirm with
> `dig MX thehelmandhorizon.com +short`, then merge.

Two services, two jobs.

| Service | Job | Owns |
| --- | --- | --- |
| **Resend** | Sends the monthly edition and the site's transactional mail | `send.thehelmandhorizon.com` (return path only) |
| **ImprovMX** | Receives mail at `@thehelmandhorizon.com` and forwards it to you | `thehelmandhorizon.com` MX |

## Add the root domain to Resend, not a subdomain

This is the part that is easy to get backwards.

Resend needs an MX record to collect bounce and complaint reports. It does
**not** put that record on your root domain. When you add
`thehelmandhorizon.com` to Resend, it generates a return-path MX on
`send.thehelmandhorizon.com` for you. Your root MX is never touched, so
ImprovMX keeps receiving mail.

That means you should add **`thehelmandhorizon.com`** — the root — as the
sending domain. Doing so is what lets you send *from*
`newsletter@thehelmandhorizon.com` and `editor@thehelmandhorizon.com`.

If you instead add `send.thehelmandhorizon.com` as the domain, you can only
send from `@send.thehelmandhorizon.com`, which is not an address you want on a
masthead.

## Do not turn on Resend receiving

Resend also offers inbound email, but it is webhook-based, not forwarding-based:
it accepts the mail, stores it, and POSTs metadata to an endpoint you have to
build and host. Nothing reaches your inbox without code.

Worse, enabling it on the root domain means
[all mail routes to Resend and none to any other mailbox](https://resend.com/docs/dashboard/receiving/introduction)
— which would silently replace ImprovMX. If you have already enabled receiving,
remove that MX record from the root before the change propagates.

ImprovMX handles this with per-alias rules and no code. Resend inbound is a
catch-all that needs an application behind it.

## DNS records

Add these wherever `thehelmandhorizon.com`'s DNS lives (Vercel, or your
registrar if the nameservers point elsewhere).

### ImprovMX — receiving, on the root

| Type | Name / Host | Value | Priority |
| --- | --- | --- | --- |
| MX | `@` | `mx1.improvmx.com` | 10 |
| MX | `@` | `mx2.improvmx.com` | 20 |
| TXT | `@` | `v=spf1 include:spf.improvmx.com ~all` | — |

### Resend — sending

Resend generates these when you add the domain. Copy the values from its
dashboard rather than from here — **the DKIM key is unique to your domain and
cannot be guessed**, and the MX hostname is region-specific.

| Type | Name / Host | Value | Priority |
| --- | --- | --- | --- |
| MX | `send` | `feedback-smtp.<region>.amazonses.com` (from Resend) | 10 |
| TXT | `send` | `v=spf1 include:amazonses.com ~all` (from Resend) | — |
| TXT | `resend._domainkey` | the long DKIM value from Resend | — |

Note that the MX and SPF land on `send`, while DKIM sits on the root. That
split is deliberate and is why the two services coexist.

Pick the region deliberately — it is **immutable after creation**. `us-east-1`
is the default and is right unless you have an EU data-residency reason.

### DMARC — recommended, once both are live

| Type | Name / Host | Value |
| --- | --- | --- |
| TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:dmarc@thehelmandhorizon.com` |

Start at `p=none` (monitor only). Move to `quarantine` and then `reject` after
a few weeks of clean reports — going straight to `reject` on a new setup is how
you silently lose real mail.

### Two SPF traps

1. **One SPF record per hostname.** Root and `send.` are different hostnames,
   so the two SPF records above do not conflict. But if the root already has an
   SPF record from anything else, do not add a second — merge the includes into
   one: `v=spf1 include:spf.improvmx.com include:otherservice.com ~all`.
2. **If your DNS provider auto-appends the domain,** entering
   `feedback-smtp.us-east-1.amazonses.com` can become
   `feedback-smtp.us-east-1.amazonses.com.thehelmandhorizon.com`. Add a trailing
   dot to the value, or enter just the subdomain portion for the host.

On Cloudflare, set all of these to **DNS only** (grey cloud). Proxying breaks
DKIM verification.

## Sending as editor@ from your own inbox

ImprovMX forwarding is one-directional: mail arrives and is forwarded, but
replying from your normal inbox still sends from that inbox's address.

**Resend's SMTP interface solves this at no extra cost**, so ImprovMX's paid
SMTP add-on is not needed. In Gmail, go to *Settings → Accounts and Import →
Send mail as → Add another email address* and use:

| Setting | Value |
| --- | --- |
| Email address | `editor@thehelmandhorizon.com` |
| SMTP server | `smtp.resend.com` |
| Port | `587` (STARTTLS) or `465` (SSL/TLS) |
| Username | `resend` |
| Password | your `sending_access` Resend API key |

This works only because the **root** domain is verified for sending in Resend.
It is also why the API key needs treating as a real credential — it is now
sitting in Gmail's settings as an SMTP password. Consider a separate key for
this, so you can rotate it without breaking the site's forms.

One tradeoff: your personal replies then share sending reputation with the
newsletter. For a low-volume editorial address that is fine.

## Suggested aliases

Set these up in ImprovMX, all forwarding to `randy@waltongroup.net`:

| Alias | Used for |
| --- | --- |
| `editor@` | **Required** — the site publishes this in 25 places |
| `hello@` | General |
| `tips@` | The "Tips" route on the contribute page |
| `dmarc@` | DMARC aggregate reports (they are noisy — worth its own alias) |

A catch-all (`*@`) is convenient but attracts spam. Named aliases are safer.

## Vercel environment variables

Set these in the Vercel project (Settings → Environment Variables), for
Production and Preview:

| Variable | Required | Value |
| --- | --- | --- |
| `RESEND_API_KEY` | yes | Resend API key with **Full access** — see below |
| `SUBMIT_FROM` | yes | `Helm & Horizon <newsletter@thehelmandhorizon.com>` |
| `EDITOR_EMAIL` | yes | `editor@thehelmandhorizon.com` |
| `RESEND_SEGMENT_ID` | no | A segment ID, if you want new readers filed into one |
| `MAIL_FROM` | no | Overrides `SUBMIT_FROM` as the sending identity |
| `CONFIRM_SECRET` | no | Signing key for confirmation links — see below |

There is deliberately **no** `RESEND_AUDIENCE_ID`. Resend has moved to a global
Contacts model: Audiences were renamed Segments, contacts are no longer scoped
to one, and `POST /contacts` takes no audience. If you set that variable
earlier, delete it — nothing reads it.

The subscribe form writes `role` and `company` as custom contact properties, so
they are available for segmenting and for personalising a Broadcast.

### The key needs Full access, not Sending access

Resend offers two permissions, and the distinction matters here:

- `full_access` — create, delete, get, and update any resource
- `sending_access` — **can only send emails**

`/api/submit` sends an email, so a sending key would do. But `/api/subscribe`
creates a *contact*, which is not a send. A `sending_access` key is rejected,
and the reader sees "We could not add you just now."

So `RESEND_API_KEY` must be **Full access**. If the subscribe form fails while
the contribute form works, this is almost certainly why — and the function logs
will say so explicitly.

Use a **second, `sending_access` key** for Gmail send-as. That key lives in
Gmail's settings rather than in your own infrastructure, so it is the one worth
restricting, and sending is all it needs to do.

The API key is a secret: it belongs only in Vercel's environment variables,
never in this repository. `.env` is already gitignored.

## Order of operations

1. In Resend, add the domain as **`thehelmandhorizon.com`**, pick the region.
2. If Resend receiving is enabled, disable it and remove its root MX record.
3. Add the ImprovMX records **and** the Resend records to DNS.
4. Verify in both dashboards. DNS can take minutes to hours.
5. Create the `editor@` alias in ImprovMX and send yourself a test.
6. Set the three required Vercel environment variables, redeploy.
7. Subscribe through the live form and confirm the contact appears under
   Audience → Contacts in Resend.
8. Merge the PR — only once `editor@` is confirmed working.
9. Add Gmail send-as via `smtp.resend.com` if you want to reply as `editor@`.
10. Send the first Broadcast to a test audience of one before the real list.

## Checking your work

```bash
dig MX  thehelmandhorizon.com          +short   # expect mx1/mx2.improvmx.com ONLY
dig TXT thehelmandhorizon.com          +short   # expect the improvmx SPF
dig MX  send.thehelmandhorizon.com     +short   # expect feedback-smtp...amazonses.com
dig TXT send.thehelmandhorizon.com     +short   # expect the amazonses SPF
dig TXT resend._domainkey.thehelmandhorizon.com +short
dig TXT _dmarc.thehelmandhorizon.com   +short
```

The first command is the one that matters. If it returns anything other than
the two ImprovMX hosts — an `amazonses` or `inbound-smtp` host in particular —
something has taken the root MX and inbound mail is no longer reaching you.

## Double opt-in

Subscribing does not put anyone on the list directly. `/api/subscribe` creates
the contact with `unsubscribed: true` and emails a confirmation link.
`/api/confirm` verifies the link and flips the contact to active, then redirects
to `/confirmed`, or to `/confirm-failed` if the link is bad or stale.

The link carries the address, an expiry, and an HMAC over both, so there is no
database: a link cannot be forged, edited to confirm a different address, or
replayed after seven days. `CONFIRM_SECRET` is the signing key. Leave it unset
and a distinct key is derived from `RESEND_API_KEY` — which means **rotating the
API key invalidates confirmation links still in flight**. Set `CONFIRM_SECRET`
explicitly (any long random string) if that matters to you.

Two consequences worth knowing:

- **An unconfirmed contact stays in Resend as unsubscribed.** It will not be
  sent anything. Contacts that sit unconfirmed for a long time are worth
  clearing out periodically.
- **A confirmed subscriber re-entering their address is left alone.** The
  handler checks first, so nobody removes themselves by accident, and the form
  tells them they are already on the list.

Confirmation links are opened by clicking, so a security scanner or an email
client that pre-fetches links can in principle confirm on the reader's behalf.
The usual defence is to make the landing page require a button press. That was
not done here: it costs a click for every real subscriber, and the exposure is
someone being subscribed who did submit the form themselves.

## Unsubscribe

The site promises one-click unsubscribe in every issue. Resend Broadcasts
handle this: include the `{{{RESEND_UNSUBSCRIBE_URL}}}` variable in the
broadcast footer. Under the global Contacts model the link opens a preference
page where the reader can either opt out of specific **Topics** or unsubscribe
from everything you send, and Resend records it against the contact.

If you later send more than one kind of email, create a Topic per kind and
scope each Broadcast to one. That way a reader who only wants out of the
monthly edition is not forced to leave altogether.

Do not hand-roll any of this — an unsubscribe link that does not work is a spam
complaint and, for a commercial newsletter, a legal exposure.

## Sources

- [Resend: how to avoid conflicts with your MX records](https://resend.com/docs/knowledge-base/how-do-i-avoid-conflicting-with-my-mx-records)
- [Resend: receiving emails](https://resend.com/docs/dashboard/receiving/introduction)
- [Resend: send with SMTP](https://resend.com/docs/send-with-smtp)
- [ImprovMX: MX records](https://improvmx.com/guides/mx-records/)
