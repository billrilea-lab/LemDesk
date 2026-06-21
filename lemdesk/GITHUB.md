# GitHub setup for LEMdesk + lemdev.com

## Option A — Standalone public repo (recommended for YouTube)

```bash
chmod +x scripts/publish_lemdesk_github.sh
./scripts/publish_lemdesk_github.sh          # exports to $TMPDIR/lemdesk-publish
./scripts/publish_lemdesk_github.sh --create # needs: gh auth login
```

Default repo: `billrilea-lab/LemDesk`. Override: `LEMdesk_GITHUB_REPO=yourorg/yourrepo`.

## Option B — Monorepo (this Cursor-Crypto repo)

Keep LEMdesk beside the trading bot. Point the website at the standalone repo for clones; use monorepo for your own dev.

## GitHub Pages for lemdev.com

1. Push this repo (or a `lemdev-site-only` repo) to GitHub.
2. Settings → Pages → Source: **GitHub Actions**.
3. Workflow `.github/workflows/deploy-lemdev-site.yml` deploys `lemdev-site/` on push to `main`.

### GoDaddy DNS (lemdev.com on GoDaddy, site on GitHub Pages)

| Type | Name | Value |
|------|------|--------|
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| CNAME | `www` | `<your-user>.github.io` |

In GitHub repo Settings → Pages → Custom domain: `lemdev.com` (enable HTTPS).

### GoDaddy static upload (no Pages)

Use `lemdev-site-upload.zip` — see `lemdev-site/GODADDY_UPLOAD.md`.

## What not to commit

- `.env`, API keys, `lemdesk/incoming/*` scrape staging
- Optional: exclude large generated corpus if you want users to run `lemdesk-sync` first
