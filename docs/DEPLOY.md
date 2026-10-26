# Deploying polished to home-ops

The manifests are in `deploy/home-ops/selfhosted/polished/`. Nothing here is applied from this
repo; home-ops is edited by hand, on a branch.

## 1. Secrets (1Password)

Create the 1Password item `polished` in the vault the `onepassword-connect` store reads, with
one field, `SESSION_SECRET`:

```sh
openssl rand -hex 32     # paste as SESSION_SECRET
```

The ExternalSecret turns it into `POLISHED_SESSION_SECRET` in the Secret `polished-secret`
(at least 32 characters). The OIDC client id and secret need no item: the `PocketIDOIDCClient`
writes the Secret `polished-oidc-credentials` itself.

## 2. Publish the image

1. Push this repo to `github.com/janpuc/polished` (already public). The `Release` workflow runs
   on `main`: lint and test, then builds `ghcr.io/janpuc/polished:edge` and `:sha-<short>`.
2. release-please keeps a release PR open (`chore(main): release 0.2.0` as of 2026-10-25).
   Merge it. The merge tags `v0.2.0` and the same workflow publishes `:0.2.0`, `:0.2`, `:0` and
   `:latest`. Use whatever version the PR names in the steps below.
3. Make the package public (the web UI is the only way):
   <https://github.com/users/janpuc/packages/container/polished/settings>, "Change visibility".
   home-ops uses no image pull secrets, so a private package would sit in `ImagePullBackOff`.
   The alternative is a pull secret, which this setup does not have.
4. Get the digest of the release tag:

   ```sh
   docker buildx imagetools inspect ghcr.io/janpuc/polished:0.2.0 | grep -m1 Digest
   ```

For Renovate: the repo needs the `OP_SERVICE_ACCOUNT_TOKEN` Actions secret (same as serendip)
and the GitHub App installed on it. The workflow is parked in `.github/disabled/renovate.yaml` so
its hourly schedule does not fail before the secret exists; once both are in place:

```sh
gh secret set OP_SERVICE_ACCOUNT_TOKEN -R janpuc/polished
git mv .github/disabled/renovate.yaml .github/workflows/renovate.yaml
git commit -m "ci: enable Renovate" && git push
```

## 3. Copy the manifests into home-ops

```sh
cd ~/Development/home-ops
git switch -c feat/polished
cp -R ~/Development/polished/deploy/home-ops/selfhosted/polished kubernetes/apps/selfhosted/polished
```

Add one line to `kubernetes/apps/selfhosted/kustomization.yaml`, after `medibrowserr`:

```yaml
  - ./polished/ks.yaml
```

In `kubernetes/apps/selfhosted/polished/app/helmrelease.yaml`, replace
`0.1.0@sha256:REPLACE_AFTER_FIRST_RELEASE` with the released tag and digest from step 2.4
(e.g. `0.2.0@sha256:…`) (it appears
once; the init container and the app share it through a YAML anchor). Commit on the branch and
open a PR.

## 4. Verify with Flux

After the merge, reconcile the `flux-system` Git source and check:

```sh
flux get ks polished -n flux-system
flux get hr polished -n selfhosted
kubectl -n selfhosted get pods,pvc,externalsecret,pocketidoidcclient -l app.kubernetes.io/instance=polished
kubectl -n selfhosted get secret polished-secret polished-oidc-credentials
kubectl -n selfhosted logs deploy/polished -c migrate    # "applied 001_catalog.sql" ...
curl -fsS https://polished.janpuc.com/healthz
```

`/healthz` answers `{"status":"ok","version":"0.2.0","schema":<n>}` (the released version). Without a session,
`/` redirects to `/auth/login`.

## 5. First login checklist

- [ ] Sign in with Pocket ID in Safari; a user outside `ID-Users`/`ID-Admin` gets the 403 page.
- [ ] Open the installed home-screen app (PWA) and sign in again there: Safari and the PWA keep
      separate cookies, so each signs in once.
- [ ] `/sync` shows the catch-up run (it starts on its own about a minute after the first start)
      and 372 shades. The first run then reads every shade's colour from cdn.shopify.com at one
      picture every 0.5 s, about 7 minutes; until then tips are a neutral grey.
- [ ] After that run, a shade page shows "Released ..." and its official collection, and the Shades list
      has the "Release date, newest first" sort and ten "Not in the shop" shades (Holo Taco's release
      sheet; the log says `release sheet applied`, or `release sheet skipped` and why).
- [ ] Scan a bottle on `/lookup` (the camera needs https, so only on the real hostname) and
      pick its shade.
- [ ] Make a wheel, write its address on an NFC tag with NFC Tools (Wheels, the wheel, Tag and
      QR code), and tap the tag with the iPhone: Safari opens the wheel.
- [ ] Build a stack in the layer builder and save it.
- [ ] Gatus lists `polished` (condition `[STATUS] == 200` on `/healthz`).

## Notes

- **Migrations** run in the init container `migrate` (same image), because the server never
  migrates on start: it only reports the schema version on `/healthz`. A failed migration
  stops the pod before the app starts. The init container gets the same `envFrom` as the app
  because the settings loader validates the OIDC variables in every command (`migrate` fails
  with `POLISHED_AUTH_MODE=oidc needs POLISHED_OIDC_CLIENT_ID ...` otherwise).
- **Reverse proxy headers**: no `--proxy-headers` / `--forwarded-allow-ips` setting is needed.
  The app builds every absolute URL (OIDC redirect, QR and tag URLs, the Origin check) from
  `POLISHED_PUBLIC_URL`, the session cookie is `Secure` because the mode is `oidc`, and nothing
  reads `request.client` or `X-Forwarded-*`. Envoy passes the original `Host` through, which the
  post-login `next=` check compares. uvicorn's default (trust forwarded headers from 127.0.0.1
  only) therefore never matters; access logs show the pod-network peer address.
- **Backups**: the kopiur component creates the PVC `polished` (2Gi) and the snapshots; the app
  mounts it through `existingClaim`. `KOPIUR_COPYMETHOD: Direct` copies the live SQLite file; if
  a restore ever fails, switch to `Snapshot`.
- **No zeroscaler**: the in-process daily sync needs the pod running.
