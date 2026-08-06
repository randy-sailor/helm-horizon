# Email setup — Resend + ImprovMX

> **Before merging:** the site now publishes `editor@thehelmandhorizon.com` in
> every footer, the About masthead, and the corrections and error messages. That
> alias does not exist until you create it in ImprovMX and the MX records
> resolve. Merging this branch before then means the site advertises an address
> that bounces. Create the alias first, confirm with
> `dig MX thehelmandhorizon.com +short`, then merge.

Two services, two jobs, and one rule that matters more than the rest.

| Service | Job | Owns |
| --- | --- | --- |
| **Resend** | Sends the monthly edition to subscribers | `send.thehelmandhorizon.com` |
| **ImprovMX** | Receives mail at `@thehelmandhorizon.com` and forwards it | `thehelmandhorizon.com` (root) |

## The rule: keep Resend off the root domain

A hostname can have exactly one set of MX records. ImprovMX needs the root
domain's MX records to receive mail. Resend also asks for an MX record, for
bounce and complaint feedback.

**If you point Resend at `thehelmandhorizon.com`, its MX record replaces
ImprovMX's and inbound mail to the domain stops arriving.** Not immediately
obvious either — sending keeps working, so the failure looks unrelated.

Putting Resend on the `send.` subdomain avoids the collision entirely, and it
is what [Resend recommends](https://github.com/resend/resend-skills/blob/main/skills/resend/references/domains.md)
for exactly this reason. It also isolates reputation: if newsletter sending
ever gets a domain flagged, your actual address is unaffected.

So in Resend, add the domain as **`send.thehelmandhorizon.com`**, not
`thehelmandhorizon.com`.

## DNS records

Add these wherever `thehelmandhorizon.com`'s DNS lives (Vercel, or your
registrar if the nameservers point elsewhere).

### ImprovMX — receiving, on the root

| Type | Name / Host | Value | Priority |
| --- | --- | --- | --- |
| MX | `@` | `mx1.improvmx.com` | 10 |
| MX | `@` | `mx2.improvmx.com` | 20 |
| TXT | `@` | `v=spf1 include:spf.improvmx.com ~all` | — |

### Resend — sending, on the `send.` subdomain

Resend generates these when you add the domain. Copy the values from its
dashboard rather than from here — **the DKIM key is unique to your domain and
cannot be guessed**, and the MX hostname is region-specific.

| Type | Name / Host | Value | Priority |
| --- | --- | --- | --- |
| MX | `send` | `feedback-smtp.<region>.amazonses.com` (from Resend) | 10 |
| TXT | `send` | `v=spf1 include:amazonses.com ~all` (from Resend) | — |
| TXT | `resend._domainkey.send` | the long DKIM value from Resend | — |

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
   `resend._domainkey.send.thehelmandhorizon.com` can become
   `...thehelmandhorizon.com.thehelmandhorizon.com`. Enter just
   `resend._domainkey.send`, or use a trailing dot.

On Cloudflare, set all of these to **DNS only** (grey cloud). Proxying breaks
DKIM verification.

## Sending *from* the domain

ImprovMX forwarding is one-directional: mail arrives and is forwarded, but
replying from your normal inbox still sends from that inbox's address.

To send as `editor@thehelmandhorizon.com` you need **ImprovMX SMTP, which is a
paid feature** — [Premium, $9/month](https://improvmx.com/pricing) at the time
of writing, with a 6,000/month send limit. You create SMTP credentials in
ImprovMX, add their DKIM and DMARC records, then add the address to Gmail under
*Settings → Accounts → Send mail as* using `smtp.improvmx.com`.

Without a paid plan you can receive at the domain but not send from it. There
is no free path to sending from a custom domain without running a mail server,
which is the thing you said you wanted to avoid.

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

| Variable | Value |
| --- | --- |
| `RESEND_API_KEY` | Resend API key — **create it with sending permission only** |
| `RESEND_AUDIENCE_ID` | The Resend audience the subscribe form adds contacts to |
| `SUBMIT_FROM` | `Helm & Horizon <newsletter@send.thehelmandhorizon.com>` |
| `EDITOR_EMAIL` | `editor@thehelmandhorizon.com` |

The API key is a secret: it belongs only in Vercel's environment variables,
never in this repository. `.env` is already gitignored.

## Order of operations

1. Add the domain in Resend as `send.thehelmandhorizon.com`, pick the region.
2. Add the ImprovMX records **and** the Resend records to DNS.
3. Verify in both dashboards. DNS can take minutes to hours.
4. Create the Resend audience, copy its ID.
5. Set the four Vercel environment variables, redeploy.
6. Subscribe yourself through the live form and confirm the contact appears.
7. Upgrade ImprovMX to Premium and configure SMTP if you want to send as
   `editor@`.
8. Send the first Broadcast to a test audience of one before the real list.

## Checking your work

```bash
dig MX  thehelmandhorizon.com          +short   # expect mx1/mx2.improvmx.com
dig TXT thehelmandhorizon.com          +short   # expect the improvmx SPF
dig MX  send.thehelmandhorizon.com     +short   # expect feedback-smtp...amazonses.com
dig TXT send.thehelmandhorizon.com     +short   # expect the amazonses SPF
dig TXT resend._domainkey.send.thehelmandhorizon.com +short
dig TXT _dmarc.thehelmandhorizon.com   +short
```

If the first command returns anything other than the ImprovMX hosts, something
has taken the root MX — that is the collision described at the top.

## Unsubscribe

The site promises one-click unsubscribe in every issue. Resend Broadcasts
handle this: include the `{{{RESEND_UNSUBSCRIBE_URL}}}` variable in the
broadcast footer and Resend manages the opt-out against the audience. Do not
hand-roll it — an unsubscribe link that does not work is a spam complaint and,
for a commercial newsletter, a legal exposure.
