# Flux - GitOps for the collector

Second half of CD: CI already pushes new images to GHCR
(`feature/gitops-cd`, merged). This is what watches the registry and
actually deploys new tags, instead of `kubectl apply` run by hand.

## What's here

Five Flux custom resources, drafted but not yet applied to any
cluster:

- `gitrepository.yaml` - the source Flux reconciles from. SSH-based
  with a write-capable deploy key, not a plain read-only HTTPS clone -
  ImageUpdateAutomation needs to push commits back, not just read.
- `kustomization.yaml` (Flux's own CRD, not the plain one in `k8s/`) -
  tells Flux to apply `k8s/pvc.yaml` and `k8s/cronjob.yaml`.
- `imagerepository.yaml` - watches `ghcr.io/upsidwn/network-inventory-collector`.
- `imagepolicy.yaml` - picks the newest image by the `:build-<N>`
  tag's run number, not `:latest` or the sha- tags (neither sorts
  meaningfully as "newest").
- `imageupdateautomation.yaml` - the actual loop: new image found ->
  edit `cronjob.yaml`'s tag -> commit -> push to main for real.

The app's own Secret (`collector-creds`) deliberately stays out of
this - it's not in git at all (see `k8s/secret.yaml.example`), so Flux
has nothing to reconcile there. Bringing real secrets into a GitOps
flow properly needs SOPS/age encryption, not set up yet - noted as a
follow-up, not solved here.

## Setup, in order (all live, needs the actual cluster)

1. **Install Flux** on the k3s node:
   ```
   curl -s https://fluxcd.io/install.sh | sudo bash
   flux install
   ```
2. **Check the GHCR package is pullable.** GitHub Actions-published
   packages default to private regardless of the repo's own
   visibility. On GitHub: repo -> Packages -> `network-inventory-collector`
   -> Package settings -> change visibility to public. (If it has to
   stay private, `imagerepository.yaml` needs a `secretRef` added
   instead - noted in that file.)
3. **Generate a write-capable deploy key** and register it:
   ```
   ssh-keygen -t ed25519 -C "flux-msp-automation-lab" -f flux-deploy-key -N ""
   ```
   Add `flux-deploy-key.pub` as a Deploy Key on the repo (Settings ->
   Deploy keys -> Add deploy key -> check "Allow write access").
   Then create the Secret Flux reads it from:
   ```
   flux create secret git flux-git-deploy-key \
     --namespace=flux-system \
     --url=ssh://git@github.com/upsidwn/msp-automation-lab \
     --private-key-file=./flux-deploy-key
   ```
4. **Apply these five manifests**:
   ```
   kubectl apply -f gitrepository.yaml -f kustomization.yaml \
     -f imagerepository.yaml -f imagepolicy.yaml -f imageupdateautomation.yaml
   ```
5. **Confirm it's actually working**, don't just assume:
   ```
   flux get sources git
   flux get kustomizations
   flux get images all
   ```
6. **Real end-to-end test**: push a trivial change to main, watch CI
   push a new `:build-N` tag, then watch Flux pick it up and commit
   the bump back to this repo on its own - a real commit authored by
   `fluxcdbot` should show up in `git log`, not just a cluster-side
   change.

## Status

Manifests drafted, nothing applied yet - none of the above has run
against a real cluster.
