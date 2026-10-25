# deploy/home-ops

Manifests for the home-ops repo, kept here so they are reviewed with the app. Nothing here is
applied from this repo. The steps to copy and verify them are in
[`docs/DEPLOY.md`](../../docs/DEPLOY.md).

```
selfhosted/polished/ks.yaml                       Flux Kustomization (kopiur backup, 2Gi)
selfhosted/polished/app/kustomization.yaml
selfhosted/polished/app/ocirepository.yaml        bjw-s app-template 5.2.1
selfhosted/polished/app/helmrelease.yaml          init container migrate, app, envoy-external route
selfhosted/polished/app/externalsecret.yaml       POLISHED_SESSION_SECRET from 1Password item polished
selfhosted/polished/app/pocketidoidcclient.yaml   Pocket ID client, writes polished-oidc-credentials
```

Copy `selfhosted/polished` to `kubernetes/apps/selfhosted/polished` and add
`- ./polished/ks.yaml` to `kubernetes/apps/selfhosted/kustomization.yaml`.
