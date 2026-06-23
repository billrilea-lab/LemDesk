# LEMdesk Pro — Commerce & Stripe Setup

## Pricing

- **Starter:** Free (MIT) — [github.com/billrilea-lab/LemDesk](https://github.com/billrilea-lab/LemDesk)
- **Pro:** $19/mo founding member — [lemdev.com/pricing.html](https://lemdev.com/pricing.html)
- **Team:** Custom — hello@lemdev.com

## License model (implemented)

Pro menu bar checks for a license key at:

```
~/.config/lemdesk/license.key
```

Or environment variable:

```bash
export LEMDESK_PRO_LICENSE="LEMP-…"
```

**Development bypass:**

```bash
python3 bot.py lemdesk-pro --dev
# or
export LEMDESK_PRO_DEV=1
```

### Install generates a machine founding key

```bash
python3 bot.py lemdesk-install
# writes ~/.config/lemdesk/license.key
```

### Manual license

```bash
python3 bot.py lemdesk-license --set "LEMP-FOUNDING-…"
python3 bot.py lemdesk-license --status
```

## Stripe setup (you do this in Stripe Dashboard)

1. Create [Stripe account](https://dashboard.stripe.com)
2. **Product:** LEMdesk Pro — $19/month recurring
3. **Payment Link** → copy URL
4. Add link to `lemdev-site/pricing.html` (replace `#waitlist` CTA or add secondary button)
5. **After payment** — Stripe → Customer metadata or receipt email template:

   ```
   Your LEMdesk Pro license key:
   LEMP-FOUNDING-XXXXXXXX
   ```

6. **Fulfillment options:**
   - **Manual (now):** Email key from hello@lemdev.com when FormSubmit/Stripe fires
   - **Semi-auto:** Zapier Stripe → email with key from Google Sheet
   - **Auto (later):** Webhook → `license.lemdesk.com/api/activate` issues signed keys

### Suggested key format for Stripe customers

```
LEMP-FOUNDING-{LAST8OFSTRIPESESSION}
```

Validate in `lemdesk_pro/license.py` — keys matching `LEMP-` + 24+ chars pass.

## Go-to-market checklist

- [ ] Stripe Payment Link live
- [ ] Update pricing.html with "Subscribe" button
- [ ] Email template with license + install instructions
- [ ] 60s demo video on demo.html
- [ ] Friend beta (5 installs via `lemdesk-install`)

## Install instructions for paying customers

```bash
git clone https://github.com/billrilea-lab/LemDesk.git
cd LemDesk
python3 bot.py lemdesk-install
python3 bot.py lemdesk-license --set "LEMP-YOUR-KEY"
python3 bot.py lemdesk-pro
```

## Revenue → compute

| Subscribers | MRR | Buys |
|-------------|-----|------|
| 10 | $190 | Mac Mini RAM upgrade |
| 26 | $494 | GPU / second machine |
| 50 | $950 | Small homelab |
