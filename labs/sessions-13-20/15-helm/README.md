# Session 15 Homework: Helm

All three homework tasks, executed end to end against a live minikube cluster with
**Helm v4.3.0**. Every command in these files was run; every output block is the real
terminal output.

| Task | Page | What it covers |
|---|---|---|
| 1 | [01-helm-commands/README.md](01-helm-commands/README.md) | `create`, `lint`, `template`, `install` (+`--dry-run --debug`), `list`, `status`, `get` (values/manifest/hooks/notes/metadata), `upgrade`, `history`, `rollback`, `uninstall`, `repo`, `search` |
| 2 | [02-rollback/README.md](02-rollback/README.md) | The full rollback workflow: install → verify → upgrade → verify → upgrade → verify → rollback → verify, seven revisions, every stage checked against the running pods |
| 3 | [03-mini-project/README.md](03-mini-project/README.md) | Part A: the Notes App mini project. Part B: `webapp-chart`, a chart written from scratch with helpers, conditionals, ranges and NOTES.txt |

Charts:

| Path | What it is |
|---|---|
| [`scaffold-demo/`](scaffold-demo) | Untouched output of `helm create`, kept so the Helm 4 scaffold can be inspected |
| [`charts/notes-chart/`](charts/notes-chart) | The mini project chart |
| [`charts/webapp-chart/`](charts/webapp-chart) | My own chart: `_helpers.tpl`, conditionals, ranges, NOTES.txt, `values-prod.yaml` |

## Environment

```bash
helm version
kubectl version --output=yaml | head -10
```

```text
version.BuildInfo{Version:"v4.3.0", GitCommit:"bec5b06ed841fe5269972d864d5177944fd5970f", GitTreeState:"clean", GoVersion:"go1.27.1", KubeClientVersion:"v1.37"}
clientVersion:
  buildDate: "2026-08-26T10:44:20Z"
  compiler: gc
  gitCommit: f54c212e3a2f75d674b717a9b29052b20b60aefc
  gitTreeState: clean
  gitVersion: v1.37.0
  goVersion: go1.27.0
  major: "1"
  minor: "37"
  platform: darwin/arm64
```

minikube with the docker driver, Kubernetes v1.37.0, containerd. All work is confined to the
namespace `hw15` and NodePorts 30150–30151, because the cluster is shared.

**Platform note that affects every "verify" step:** the minikube node IP `192.168.49.2` is not
routable from the macOS host with the docker driver — the node lives inside the Docker Desktop
VM. NodePorts are therefore curled from inside the node with
`minikube ssh -- "curl ... http://localhost:<port>"`, which is why that form appears throughout
instead of `curl http://192.168.49.2:30150`.

---

## Helm 3 vs Helm 4: what actually changed

Almost every Helm tutorial, including the session material, assumes Helm 3. This machine runs
Helm 4.3.0. Below is every difference that actually showed up while doing this homework, with
the output that revealed it. None of these are problems — but if you follow a Helm 3 tutorial
line by line you will hit them.

### 1. Server-side apply is the default

```bash
helm get metadata demo -n hw15
```

```text
NAME: demo
CHART: scaffold-demo
VERSION: 0.1.0
APP_VERSION: 1.16.0
ANNOTATIONS:
LABELS: modifiedAt=1791376211,name=demo,owner=helm,status=deployed,version=1
DEPENDENCIES:
NAMESPACE: hw15
REVISION: 1
STATUS: deployed
DEPLOYED_AT: 2026-10-07T18:00:11+05:30
APPLY_METHOD: server-side apply
```

`APPLY_METHOD` is a Helm 4 field, and its value is `server-side apply`. Helm 3 computed a
three-way-merge patch on the client (old manifest vs new manifest vs live object) and PATCHed
it. Helm 4 sends the desired object to the API server with SSA and lets the server reconcile
field ownership.

Why it matters in practice: under SSA the API server records which manager owns which field,
so Helm stops fighting other controllers that write to the same object (HPAs changing
`replicas`, mutating webhooks injecting sidecars, service meshes). It also changes error
wording — apply failures now say `server-side apply failed for object …`:

```text
Error: INSTALLATION FAILED: server-side apply failed for object hw15/web-webapp-chart /v1, Kind=Service: Service "web-webapp-chart" is invalid: spec.ports[0].nodePort: Invalid value: 99999: provided port is not in the valid range. The range of valid ports is 30000-32767
```

### 2. `helm list -a` / `--all` has been removed

```bash
helm list -n hw15 -a
```

```text
Error: unknown shorthand flag: 'a' in -a
```

```bash
helm list -n hw15 --all
```

```text
Error: unknown flag: --all
```

Helm 3's catch-all "show every state" flag is replaced by one flag per state:
`--deployed`, `--failed`, `--pending`, `--superseded`, `--uninstalled`, `--uninstalling`.
`-A` / `--all-namespaces` is unaffected. Any Helm 3 script containing `helm list -a` will
break on Helm 4.

### 3. Bare `--dry-run` is deprecated

```bash
helm install demo scaffold-demo -n hw15 --dry-run --debug
```

```text
level=WARN msg="--dry-run is deprecated and should be replaced with '--dry-run=client'"
```

It still works, but Helm 4 wants `--dry-run=client` or `--dry-run=server` spelled out.

### 4. `--debug` output is structured logging

Helm 4:

```text
level=DEBUG msg="Original chart version" version=""
level=DEBUG msg="Chart path" path=/Users/aman/Desktop/devops-heros/coursework-labs/15-helm/scaffold-demo
level=DEBUG msg="number of dependencies in the chart" chart=scaffold-demo dependencies=0
```

Helm 3 printed free-form lines like `install.go:200: [debug] Original chart version: ""`.
Scripts that grep debug output need rewriting; humans get machine-parseable key/value pairs.

### 5. Install/upgrade summaries gained `DESCRIPTION:` and `TEST SUITE:`

```text
NAME: notes-dev
LAST DEPLOYED: Wed Oct  7 18:13:27 2026
NAMESPACE: hw15
STATUS: deployed
REVISION: 1
DESCRIPTION: Install complete
TEST SUITE: None
```

Helm 3 showed `DESCRIPTION` only in `helm history`. `TEST SUITE: None` means the chart defines
no `helm.sh/hook: test` resources.

### 6. `helm create` scaffolds a Gateway API HTTPRoute

```text
scaffold-demo/templates/
  NOTES.txt
  _helpers.tpl
  deployment.yaml
  hpa.yaml
  httproute.yaml      <-- new in the Helm 4 scaffold
  ingress.yaml
  service.yaml
  serviceaccount.yaml
  tests/test-connection.yaml
```

`httproute.yaml` is gated behind `httpRoute.enabled: false`, so it renders nothing by default,
but it signals where Helm expects ingress to go next.

### 7. Template errors are multi-line and readable

```bash
helm template notes-dev brokenchart
```

```text
Error: notes-chart/templates/configmap.yaml:6:22
  executing "notes-chart/templates/configmap.yaml" at <.Values.app.naem.first>:
    nil pointer evaluating interface {}.first
```

Helm 3 crammed the same information into one long `Error: template: …` line. The file, the
line:column, the failing expression and the reason are now on separate lines.

### 8. An observed caveat: server-side dry-run did not catch everything

This one is a real, reproducible observation on this version and cluster, not a documented
change. Two invalid manifests were pushed through every validation path:

```bash
helm template demo scaffold-demo -n hw15 --set replicaCount=three --validate >/dev/null; echo "exit=$?"
helm install demo scaffold-demo -n hw15 --dry-run=server --set replicaCount=three >/dev/null; echo "exit=$?"
helm template demo scaffold-demo -n hw15 --set replicaCount=three | kubectl apply -n hw15 --dry-run=server -f -
```

```text
exit=0
exit=0
Error from server (BadRequest): error when creating "STDIN": Deployment in version "v1" cannot be handled as a Deployment: json: cannot unmarshal string into Go struct field DeploymentSpec.spec.replicas of type int32
```

Same story with an out-of-range NodePort: `helm template`, `helm template --validate` and
`helm install --dry-run=server` all exited 0, while the real `helm install` failed:

```text
Error: INSTALLATION FAILED: server-side apply failed for object hw15/web-webapp-chart /v1, Kind=Service: Service "web-webapp-chart" is invalid: spec.ports[0].nodePort: Invalid value: 99999: provided port is not in the valid range. The range of valid ports is 30000-32767
```

**Takeaway:** on Helm v4.3.0 against Kubernetes v1.37, do not treat `--dry-run=server` as
proof that an install will succeed. If you want genuine API-server validation in CI, pipe
`helm template` into `kubectl apply --dry-run=server -f -`, which caught both cases.

---

## `helm template` vs `--dry-run` vs `install`

These three are constantly confused. They sit on a ladder, each doing strictly more than the
one before.

| | `helm template` | `helm install --dry-run` | `helm install` |
|---|---|---|---|
| Renders templates | yes | yes | yes |
| Needs a cluster connection | no | no (`=client`), yes (`=server`) | yes |
| Values merge (`-f`, `--set`) applied | yes | yes | yes |
| Prints USER-SUPPLIED / COMPUTED VALUES | no | yes | no |
| Hooks separated from the manifest | no (mixed in) | yes (own `HOOKS:` section) | yes (not in manifest) |
| Renders `NOTES.txt` | no | yes | yes |
| Assigns a revision number | no | yes (always `1`, `pending-install`) | yes (real) |
| Writes objects to the cluster | no | no | yes |
| Stores a release Secret | no | no | yes |
| Appears in `helm list` / `helm history` | no | no | yes |
| Can be rolled back | n/a | n/a | yes |
| Catches invalid Kubernetes fields | no | not reliably (see caveat above) | yes — at apply time |
| Typical use | GitOps rendering, `kubectl apply -f -`, diffing | "what would this change?" before a real install | actually deploying |

### The same chart through all three

**`helm template`** — four `# Source` blocks, including the test hook, because it is a pure
text renderer:

```bash
helm template demo scaffold-demo -n hw15 | grep -n "^# Source"
```

```text
2:# Source: scaffold-demo/templates/serviceaccount.yaml
16:# Source: scaffold-demo/templates/service.yaml
39:# Source: scaffold-demo/templates/deployment.yaml
83:# Source: scaffold-demo/templates/tests/test-connection.yaml
```

**`--dry-run --debug`** — the same content, but organised into labelled sections:

```bash
helm install demo scaffold-demo -n hw15 --dry-run --debug | grep -n "^USER-SUPPLIED\|^COMPUTED\|^HOOKS:\|^MANIFEST:\|^NOTES:"
```

```text
11:USER-SUPPLIED VALUES:
14:COMPUTED VALUES:
78:HOOKS:
101:MANIFEST:
185:NOTES:
```

…with a release header that a real install would also print, except the status gives it away:

```text
NAME: demo
LAST DEPLOYED: Wed Oct  7 18:00:03 2026
NAMESPACE: hw15
STATUS: pending-install
REVISION: 1
DESCRIPTION: Dry run complete
```

`STATUS: pending-install` and `DESCRIPTION: Dry run complete` are how you tell a dry run from
the real thing at a glance. The revision is always 1 — a dry run does not look up the current
revision.

**A real install** — the manifest Helm stored has only three sources, because the hook is not
part of it:

```bash
helm get manifest demo -n hw15 | grep -n "^# Source"
```

```text
2:# Source: scaffold-demo/templates/serviceaccount.yaml
16:# Source: scaffold-demo/templates/service.yaml
39:# Source: scaffold-demo/templates/deployment.yaml
```

…and only the real install leaves a trace:

```bash
helm list -n hw15
```

```text
NAME	NAMESPACE	REVISION	UPDATED                             	STATUS  	CHART              	APP VERSION
demo	hw15     	1       	2026-10-07 18:00:11.903769 +0530 IST	deployed	scaffold-demo-0.1.0	1.16.0
```

Rule of thumb: use `helm template` when you want YAML, `--dry-run` when you want to know what
Helm would do, and `install`/`upgrade` when you want it done.

---

## Troubleshooting: real failures hit while doing this homework

Every error below was produced on purpose or by accident during this lab. The output is real.

### 1. `cannot reuse a name that is still in use`

```bash
helm install notes-dev charts/notes-chart -n hw15
```

```text
level=ERROR msg="release name check failed" error="cannot reuse a name that is still in use"
Error: INSTALLATION FAILED: release name check failed: cannot reuse a name that is still in use
```

A release with that name already exists in that namespace. **Fix:** `helm upgrade` it, use a
different release name, or — the idempotent form that belongs in CI —
`helm upgrade --install notes-dev charts/notes-chart -n hw15`.

### 2. `"nosuch" has no deployed releases`

```bash
helm upgrade nosuch charts/notes-chart -n hw15
```

```text
Error: UPGRADE FAILED: "nosuch" has no deployed releases
```

Upgrading something that was never installed. Also appears when the previous install **failed**
(status `failed`, never `deployed`) — in that case `helm uninstall` the broken release first,
then install again. `helm upgrade --install` avoids the first case entirely.

### 3. `release: not found` — the namespace trap

```bash
helm status notes-dev
```

```text
Error: release: not found
```

Nothing is wrong with the release; the `-n hw15` was omitted so Helm looked in `default`. Helm
release records are namespaced Secrets. **Fix:** always pass `-n`, or run `helm list -A` to
find where a release actually lives.

### 4. `release has no 99 version`

```bash
helm rollback notes-dev 99 -n hw15
```

```text
Error: release has no 99 version
```

The revision number must come from `helm history`. Note also that `--history-max` (default 10)
prunes old revisions, so a number you saw last week may no longer exist.

### 5. `nil pointer evaluating interface {}.first` — a typo in a values path

```bash
helm template notes-dev brokenchart
```

```text
Error: notes-chart/templates/configmap.yaml:6:22
  executing "notes-chart/templates/configmap.yaml" at <.Values.app.naem.first>:
    nil pointer evaluating interface {}.first
```

`.Values.app.naem` is a typo, so it evaluates to nil, and reaching `.first` on nil explodes.
Templates resolve missing keys to nil silently — only dereferencing the nil fails. `helm lint`
catches the same thing and escalates it to `[ERROR]`:

```bash
helm lint brokenchart
```

```text
==> Linting brokenchart
[INFO] Chart.yaml: icon is recommended
[ERROR] templates/: notes-chart/templates/configmap.yaml:6:22
  executing "notes-chart/templates/configmap.yaml" at <.Values.app.naem.first>:
    nil pointer evaluating interface {}.first

Error: 1 chart(s) linted, 1 chart(s) failed
```

**Fixes:** `{{ .Values.app.name | default "notes-app" }}` for an optional value, or
`{{ required "app.name is required" .Values.app.name }}` to fail loudly with a message a human
can act on.

### 6. `YAML parse error … did not find expected key` — `indent` vs `nindent`

Changing `{{- toYaml .Values.resources | nindent 12 }}` to
`{{ toYaml .Values.resources | indent 12 }}`:

```bash
helm template web brokenchart2 -f brokenchart2/values-prod.yaml
```

```text
Error: YAML parse error on webapp-chart/templates/deployment.yaml: error converting YAML to JSON: yaml: line 45: did not find expected key

Use --debug flag to render out invalid YAML
```

Helm tells you to use `--debug`, and that is exactly the right move — it prints the broken YAML
instead of refusing:

```bash
helm template web brokenchart2 -f brokenchart2/values-prod.yaml --debug
```

```text
          resources:
                        limits:
              cpu: 200m
              memory: 128Mi
            requests:
              cpu: 50m
              memory: 64Mi
          readinessProbe:
```

The first line is double-indented. `indent N` prefixes **every** line with N spaces, including
the first — which already sits after whatever whitespace precedes `{{`. `nindent N` emits a
newline first, then indents every line, so the leading whitespace in the template is irrelevant.
**Rule: use `nindent` with a `{{-` on the left.** The 90% case of "my chart renders invalid
YAML" is this.

### 7. `provided port is not in the valid range` — a failed apply leaves resources behind

```bash
helm install web charts/webapp-chart -n hw15 --set service.nodePort=99999
```

```text
Error: INSTALLATION FAILED: server-side apply failed for object hw15/web-webapp-chart /v1, Kind=Service: Service "web-webapp-chart" is invalid: spec.ports[0].nodePort: Invalid value: 99999: provided port is not in the valid range. The range of valid ports is 30000-32767
```

The install failed, but it did not fail cleanly:

```bash
kubectl get all,configmap -n hw15
```

```text
NAME                                   READY   STATUS    RESTARTS   AGE
pod/web-webapp-chart-b6ddc8ddd-55wws   1/1     Running   0          12s
pod/web-webapp-chart-b6ddc8ddd-r24mn   1/1     Running   0          12s

NAME                               READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/web-webapp-chart   2/2     2            2           12s

NAME                                DATA   AGE
configmap/kube-root-ca.crt          1      2m33s
configmap/web-webapp-chart-config   5      12s
```

A ConfigMap and a running Deployment, and a release stuck in `failed`:

```bash
helm list -n hw15 --failed
```

```text
NAME	NAMESPACE	REVISION	UPDATED                            	STATUS	CHART             	APP VERSION
web 	hw15     	1       	2026-10-07 18:02:04.89732 +0530 IST	failed	webapp-chart-0.1.0	1.24
```

**Fix:** `helm uninstall web -n hw15` to clean up, then reinstall. Helm is not transactional by
default; `--atomic` makes it behave as if it were, by uninstalling (on install) or rolling back
(on upgrade) when the operation fails.

### 8. `provided port is already allocated` — two releases, one NodePort

```bash
helm install notes-clash charts/notes-chart -n hw15
```

```text
Error: INSTALLATION FAILED: server-side apply failed for object hw15/notes-clash-svc /v1, Kind=Service: Service "notes-clash-svc" is invalid: spec.ports[0].nodePort: Invalid value: 30151: provided port is already allocated
```

NodePorts are a **cluster-wide** resource, not a namespaced one. Two releases of the same chart
with a hardcoded `nodePort` cannot coexist anywhere in the cluster. This is the strongest
argument for not pinning `nodePort` in a chart's defaults at all — leave it unset and let
Kubernetes allocate, or require the operator to supply it. The same partial-apply mess as #7
was left behind and needed `helm uninstall notes-clash -n hw15`.

### 9. `exists and cannot be imported into the current release`

Create a ConfigMap by hand, then install a chart that wants to own that name:

```bash
kubectl create configmap notes-x-config -n hw15 --from-literal=APP_NAME=manual
helm install notes-x charts/notes-chart -n hw15 --set service.nodePort=30152
```

```text
Error: INSTALLATION FAILED: unable to continue with install: ConfigMap "notes-x-config" in namespace "hw15" exists and cannot be imported into the current release: invalid ownership metadata; label validation error: missing key "app.kubernetes.io/managed-by": must be set to "Helm"; annotation validation error: missing key "meta.helm.sh/release-name": must be set to "notes-x"; annotation validation error: missing key "meta.helm.sh/release-namespace": must be set to "hw15"

Error: uninstall: Release not loaded: notes-x: release: not found
```

Helm refuses to take over an object it does not own. The error message is also the fix — it
names the exact three pieces of metadata needed to adopt the resource:

```bash
kubectl label  configmap notes-x-config -n hw15 app.kubernetes.io/managed-by=Helm
kubectl annotate configmap notes-x-config -n hw15 meta.helm.sh/release-name=notes-x
kubectl annotate configmap notes-x-config -n hw15 meta.helm.sh/release-namespace=hw15
```

Note the second error: because the install never created a release record, `helm uninstall`
cannot clean up. The leftover object has to be removed with `kubectl`. This is the usual
symptom of "somebody `kubectl apply`'d this before we Helm-ified it".

### 10. `namespaces "hw15-nope" not found`

```bash
helm install notes-ns charts/notes-chart -n hw15-nope
```

```text
Error: INSTALLATION FAILED: create: failed to create: namespaces "hw15-nope" not found
```

Helm does not create the namespace for you. **Fix:** `kubectl create namespace` first, or pass
`--create-namespace`.

### 11. Helm says `deployed`, the app is broken

```bash
helm upgrade notes-dev charts/notes-chart -n hw15 -f charts/notes-chart/values-prod.yaml --set image.tag=broken-tag-does-not-exist
helm list -n hw15
```

```text
Release "notes-dev" has been upgraded. Happy Helming!
STATUS: deployed
REVISION: 3
```

```bash
kubectl get deploy notes-dev-deploy -n hw15
kubectl get pods -n hw15 -l app=notes-dev -o custom-columns='NAME:.metadata.name,IMAGE:.spec.containers[0].image,READY:.status.containerStatuses[0].ready,REASON:.status.containerStatuses[0].state.waiting.reason'
```

```text
NAME               READY   UP-TO-DATE   AVAILABLE   AGE
notes-dev-deploy   3/3     1            3           2m10s

NAME                                IMAGE                             READY   REASON
notes-dev-deploy-79b4dbdffd-225g9   nginx:broken-tag-does-not-exist   false   ErrImagePull
notes-dev-deploy-bbcc464b4-b5c7j    nginx:1.25                        true    <none>
notes-dev-deploy-bbcc464b4-h27dz    nginx:1.25                        true    <none>
notes-dev-deploy-bbcc464b4-pkqhh    nginx:1.25                        true    <none>
```

Without `--wait`, Helm's job ends when the API accepts the manifests. Pod startup is somebody
else's problem. **The giveaway is `READY 3/3` with `UP-TO-DATE 1`** — the fleet is healthy, the
new version is not; the rolling update is stuck because the new pod never became available.

**Fixes:** `--wait --timeout 2m` to make Helm block until resources are ready, `--atomic` to
make it roll back automatically on timeout, and `kubectl rollout status` in the pipeline right
after the Helm command regardless.

### 12. `helm upgrade --set` silently reverted everything else

Starting from a release installed with `-f values-prod.yaml` (3 replicas, production):

```bash
helm upgrade notes-dev charts/notes-chart -n hw15 --set image.tag="1.26"
helm get manifest notes-dev -n hw15 | grep -E 'replicas:|image:|ENVIRONMENT:'
```

```text
  ENVIRONMENT: "development"
  replicas: 1
          image: "nginx:1.26"
```

Only the tag was changed, but the replica count went 3 → 1 and the environment went production
→ development. `helm upgrade` recomputes values from **chart defaults + what you pass on this
invocation**. It does not inherit the previous revision's values. This is the single most
dangerous Helm footgun: the command looks surgical and is not.

**Fix A — pass the same files every time** (preferred; your values files are the source of
truth and belong in git):

```bash
helm upgrade notes-dev charts/notes-chart -n hw15 -f charts/notes-chart/values-prod.yaml --set image.tag="1.26"
```

**Fix B — `--reuse-values`**, which merges your `--set` onto the previous revision's values:

```bash
helm upgrade notes-dev charts/notes-chart -n hw15 --reuse-values --set image.tag="1.26"
helm get manifest notes-dev -n hw15 | grep -E 'replicas:|image:|ENVIRONMENT:'
```

```text
  ENVIRONMENT: "production"
  replicas: 3
          image: "nginx:1.26"
```

`--reuse-values` is convenient but it makes the release's state depend on its history rather
than on a file you can read, so it is a poor fit for CI.

### 13. `helm rollback` with no revision number rolled *into* the outage

```bash
helm rollback web -n hw15
helm history web -n hw15
```

```text
Rollback was a success! Happy Helming!
...
4       	Wed Oct  7 18:09:18 2026	superseded	webapp-chart-0.1.0	1.24       	Rollback to 2
5       	Wed Oct  7 18:09:36 2026	deployed  	webapp-chart-0.1.0	1.24       	Rollback to 3
```

Omitting the revision means "the previous revision" — literally revision − 1, which after an
earlier rollback is the broken one. Full write-up in
[Task 2 stage 5](02-rollback/README.md#stage-5-the-trap--helm-rollback-with-no-revision-number).
**Always read `helm history` and pass the number.**

### 14. A rolling update dropped traffic for a moment

The very first `curl` after upgrading `notes-chart` returned nothing; a retry seconds later
worked. `notes-chart` defines no `readinessProbe`, so Kubernetes considers a pod ready as soon
as its container process starts and adds it to the Service endpoints before nginx is listening
— while removing old pods. **Fix:** every chart that fronts a Service should ship a
`readinessProbe`, as `webapp-chart` does.

---

## Interview questions

### Fundamentals

**1. What problem does Helm solve?**
Raw Kubernetes YAML is static. The moment the same application has to run in dev and prod with
different replica counts, image tags and config, you end up with duplicated manifest trees that
drift. Helm adds three things: **templating** (one manifest set, many value sets),
**packaging** (a versioned, shareable chart with metadata and dependencies), and **release
lifecycle** (install/upgrade/rollback with a revision history stored in the cluster).
`kubectl apply` has no concept of "this group of 14 objects is one application at version 3".

**2. Chart vs release vs revision.**
A **chart** is the package on disk or in a repo. A **release** is one installation of that
chart into a cluster under a name; the same chart can be installed many times as different
releases. A **revision** is one version of a release — each install, upgrade and rollback
appends a new revision. In `helm install web ./webapp-chart`: `webapp-chart` is the chart,
`web` is the release, and the install produced revision 1.

**3. Where does Helm store release state? Why does that matter?**
In the cluster, as Secrets of type `helm.sh/release.v1`, one per revision, in the release's
namespace:

```text
NAME                        TYPE                 DATA   AGE
sh.helm.release.v1.web.v1   helm.sh/release.v1   1      4m17s
sh.helm.release.v1.web.v2   helm.sh/release.v1   1      3m58s
...
sh.helm.release.v1.web.v6   helm.sh/release.v1   1      8s
```

It matters because Helm is a stateless client: there is no Tiller (Helm 2), no server
component, no local database. Anyone with cluster access sees the same releases, CI can
upgrade a release a developer installed, and losing your laptop loses nothing.

**4. `appVersion` vs `version` in `Chart.yaml`.**
`version` is the chart's own semantic version — bump it when you change templates or defaults;
it is what `--version` pins and what appears in the `CHART` column. `appVersion` is the version
of the software being deployed, is informational, and need not be semver. In Task 2 the image
went 1.24 → 1.27 across seven revisions while `APP VERSION` stayed `1.24`, because only values
changed, not `Chart.yaml`.

**5. What is `_helpers.tpl` for, and why the underscore?**
It holds `define` blocks — named templates reused across manifests, like `fullname` and the
standard label set. Files whose names start with `_` are evaluated but never rendered into a
manifest of their own, so the definitions register without producing an empty document.

**6. `include` vs `template`.**
`template` is a Go built-in that writes its output directly to the stream; you cannot pipe it.
`include` is Helm's version that **returns a string**, so it can be piped:
`{{- include "webapp-chart.labels" . | nindent 4 }}`. Since almost every helper needs indenting
to fit where it is used, use `include` essentially always.

**7. `indent` vs `nindent`.**
`indent N` prefixes every line with N spaces. `nindent N` emits a newline first and then does
the same. Because template output usually begins right after existing whitespace on the line,
`indent` double-indents the first line and produces invalid YAML; `nindent` with `{{-` on the
left is the correct idiom. This is the single most common cause of "my chart renders broken
YAML" — demonstrated with real output in troubleshooting #6.

### Values and rendering

**8. Values precedence, highest wins.**
`--set` / `--set-string` / `--set-file` → `-f`/`--values` files (later `-f` beats earlier) →
the chart's own `values.yaml` → a parent chart's values for a subchart. Overriding is a **deep
merge**, not a replacement: `values-prod.yaml` in this lab omits `env` and `ingress` entirely
and still inherits them from `values.yaml`. Demonstrated with real renders in
[Task 2 stage 6](02-rollback/README.md#rendering-only--three-runs-of-the-same-chart).

**9. How do you prove an override actually landed?**
Three levels, in increasing strength: `helm get values <rel>` (what was asked for),
`helm get manifest <rel>` (what Helm actually rendered and applied), and `kubectl get` on the
live object (what the cluster has). Only the last one survives the question "did the apply
succeed?".

**10. Difference between `helm template`, `--dry-run` and `install`.**
See the [comparison table](#helm-template-vs---dry-run-vs-install). Summary: `template` is a
pure renderer that needs no cluster; `--dry-run` runs the whole install pipeline including
value merging, hook/manifest separation and NOTES rendering, then stops before writing;
`install` writes the objects and records a release. Only `install` appears in `helm list`.

**11. Why is `helm template` the command that makes templating click?**
Because it shows the Kubernetes YAML your `{{ }}` actually produces. Reading
`image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"`
tells you nothing about which branch of `default` wins; `helm get manifest` showing
`image: "nginx:1.16.0"` tells you the tag was empty and the appVersion was used. Use
`-s templates/ingress.yaml` to render one file out of a large chart.

**12. What does `{{- ` do?**
The hyphen chomps whitespace on that side of the action, including the newline. `{{-` strips
whitespace before the action, `-}}` after it. Without it, every conditional and loop leaves
blank lines that may break YAML indentation.

**13. Why are maps rendered in sorted key order?**
Go templates iterate maps in sorted key order deliberately, to make rendering deterministic.
If order were random, every `helm upgrade` would produce a textually different manifest and
churn resources for no reason. Visible in this lab: `range` over `.Values.config` emitted
`FEATURE_FLAGS, LOG_LEVEL, MAX_UPLOAD_MB` alphabetically, not in values-file order.

**14. Why should `selectorLabels` be a subset of `labels`?**
A Deployment's `spec.selector.matchLabels` is immutable after creation. The full label set
includes `helm.sh/chart` and, in this chart, `environment` — both of which change. If those
were in the selector, bumping the chart version would make every upgrade fail. Only stable
identity labels (`app.kubernetes.io/name`, `app.kubernetes.io/instance`) belong in a selector.

### Lifecycle

**15. Walk through a rollback. Does it delete the bad revision?**
No — and this is the question people get wrong. `helm rollback <release> <n>` creates a **new**
revision whose content is a copy of revision `n`. Nothing is deleted and revision `n` is not
reactivated:

```text
REVISION	STATUS    	DESCRIPTION
1       	superseded	Install complete
2       	superseded	Upgrade complete
3       	superseded	Upgrade complete
4       	deployed  	Rollback to 2
```

Four rows after rolling back from 3 to 2. The history is append-only, which is why you can roll
back a rollback.

**16. What happens if you omit the revision number?**
Helm rolls back to revision − 1, "the previous release". After an earlier rollback that is the
broken revision, so bare `helm rollback <rel>` during an incident can roll you straight back
into the outage. Proven with real output in
[Task 2 stage 5](02-rollback/README.md#stage-5-the-trap--helm-rollback-with-no-revision-number).

**17. Can you always roll back?**
No, for three reasons. (a) `--history-max` defaults to 10, so old revisions get pruned.
(b) `helm uninstall` without `--keep-history` destroys the history entirely —
`helm history` then returns `Error: release: not found`. (c) Rollback only restores Helm's
manifest; it cannot undo a database migration a `pre-upgrade` hook ran, data a PVC overwrote,
or a message the app published. Rollback is a deployment tool, not a time machine.

**18. Why did Helm report success on an upgrade that broke the app?**
Without `--wait`, Helm's contract is "the API server accepted these manifests and I recorded a
revision". Pod scheduling and image pulls happen asynchronously afterwards. An
`ImagePullBackOff` is invisible to Helm. Use `--wait --timeout`, use `--atomic` to roll back
automatically on failure, and run `kubectl rollout status` after the Helm command anyway.

**19. `--atomic`, `--wait`, `--cleanup-on-fail`, `--force` — what do they do?**
`--wait` blocks until the release's resources report ready (or timeout). `--atomic` implies
`--wait` and, on failure, rolls back the upgrade (or uninstalls a failed install) so you are
never left half-applied. `--cleanup-on-fail` deletes resources the failed operation newly
created. `--force` replaces resources via delete+recreate instead of patching — it causes
downtime and should be a last resort for immutable-field errors.

**20. What is `helm upgrade --install` for?**
It installs if the release is absent and upgrades if it is present, making the command
idempotent. That is what belongs in a CI pipeline, where you cannot know whether this is the
first deploy.

**21. What are Helm hooks?**
Resources annotated `helm.sh/hook: <event>` — `pre-install`, `post-install`, `pre-upgrade`,
`post-upgrade`, `pre-delete`, `post-delete`, `pre-rollback`, `post-rollback`, `test`. Helm
pulls them out of the main manifest and applies them at the right lifecycle point, in
`helm.sh/hook-weight` order. The classic use is a Job that runs database migrations before the
new code rolls out. Because they are not in the manifest, they do not appear in
`helm get manifest`; `helm get hooks` shows them, and `helm uninstall` does not remove them
unless `helm.sh/hook-delete-policy` says so.

**22. How does `helm test` work?**
`helm create` scaffolds `templates/tests/test-connection.yaml`, a Pod annotated
`helm.sh/hook: test` that wgets the Service. `helm test <release>` creates it and reports pass
or fail based on the pod's exit code. It is a post-deploy smoke test that ships with the chart.

### Charts and repositories

**23. `helm repo add` vs OCI registries.**
A classic chart repo is an HTTP server with `index.yaml` plus `.tgz` files; you `helm repo add`
it and `helm repo update` to refresh the cached index. OCI registries store charts as OCI
artifacts and need no `helm repo add` at all —
`helm install x oci://registry-1.docker.io/bitnamicharts/nginx` works directly. OCI is the
direction of travel; Bitnami's own charts already pull their `common` dependency from
`oci://registry-1.docker.io/bitnamicharts`.

**24. `helm search repo` vs `helm search hub`.**
`search repo` searches the locally cached indexes of repos you added — offline, fast, and
returns installable `repo/chart` names. `search hub` queries the public Artifact Hub API over
the internet across thousands of repos and returns **URLs**, because the repo is probably not
configured on your machine. If `search repo` cannot find something you know exists, run
`helm repo update` — your cache is stale.

**25. What is `Chart.lock` / the `charts/` directory?**
Dependencies declared in `Chart.yaml` are fetched by `helm dependency update` into `charts/`
as `.tgz` files, and the resolved versions are pinned in `Chart.lock`. `helm dependency build`
then reinstalls exactly what the lock file says — the Helm equivalent of `package-lock.json`.

**26. How do you make a chart fail fast on a missing required value?**
`{{ required "image.repository is required" .Values.image.repository }}`. Without it, a missing
value renders as an empty string and you get a subtly broken object instead of an error. The
companion is `{{ .Values.x | default "something" }}` for genuinely optional values.

**27. What does the `checksum/config` annotation on a pod template achieve?**
```text
checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
```
It hashes the rendered ConfigMap into the pod template, so changing a config value changes the
pod spec and the Deployment rolls new pods. Without it, Helm updates the ConfigMap object and
the running pods keep the old environment indefinitely — the classic "I changed the config and
nothing happened".

### Helm 4 specifics

**28. What changed in Helm 4 that would break a Helm 3 script?**
Mainly: `helm list -a`/`--all` was removed in favour of `--deployed`/`--failed`/`--pending`/
`--superseded`/`--uninstalled`/`--uninstalling`; bare `--dry-run` is deprecated in favour of
`--dry-run=client|server`; and `--debug` now emits structured `level=DEBUG msg="…" key=value`
logging instead of free-form lines, so anything grepping debug output needs rewriting.

**29. What is server-side apply and why does Helm 4 default to it?**
Instead of the client computing a three-way-merge patch (Helm 3), the desired object is sent to
the API server, which tracks **field ownership** per manager. Helm then only owns the fields it
actually sets, so it stops fighting HPAs, mutating webhooks and other controllers that write to
the same objects, and conflicts are reported explicitly rather than silently reverted.
`helm get metadata <rel>` shows `APPLY_METHOD: server-side apply`.

**30. How would you validate a chart in CI?**
`helm lint` for chart structure and template errors; `helm template` to confirm it renders;
then `helm template … | kubectl apply --dry-run=server -f -` for real API-server validation.
That last step matters: on Helm v4.3.0 here, both `helm install --dry-run=server` and
`helm template --validate` returned success for manifests the API server rejected on real
apply (an out-of-range NodePort and a string where an int was required), while the `kubectl`
pipe caught both. For stricter guarantees, add a `values.schema.json` so Helm validates values
against a JSON schema before rendering.

---

## Cleanup

Everything this lab created in the cluster is removed here, with real verification output.

### What existed before cleanup

```bash
helm list -A
```

```text
NAME     	NAMESPACE	REVISION	UPDATED                            	STATUS  	CHART             	APP VERSION
notes-dev	hw15     	7       	2026-10-07 18:18:57.96976 +0530 IST	deployed	notes-chart-0.1.0 	1.0
web      	hw15     	7       	2026-10-07 18:10:16.26748 +0530 IST	deployed	webapp-chart-0.1.0	1.24
```

Only releases in `hw15`, both created by this lab. (`demo`, `notes-clash` and `notes-x` were
already uninstalled in Tasks 1 and 3; `notes-x` never produced a release record at all because
its install failed before Helm wrote one.)

### Uninstall the releases

```bash
helm uninstall notes-dev web -n hw15
```

```text
release "notes-dev" uninstalled
release "web" uninstalled
```

```bash
helm list -n hw15
kubectl get secret -n hw15 -l owner=helm
kubectl get all -n hw15
```

```text
NAME	NAMESPACE	REVISION	UPDATED	STATUS	CHART	APP VERSION

No resources found in hw15 namespace.

No resources found in hw15 namespace.
```

No releases, no release Secrets, no workloads. `helm uninstall` without `--keep-history`
removed every revision Secret (seven per release) along with the objects.

### Delete the namespace

```bash
kubectl delete namespace hw15
kubectl get ns hw15
```

```text
namespace "hw15" deleted
Error from server (NotFound): namespaces "hw15" not found
```

### Remove the chart repository added in Task 1

```bash
helm repo remove bitnami
helm repo list
```

```text
"bitnami" has been removed from your repositories
no repositories to show
```

Back to the state Task 1 started from (`no repositories to show`).

### Final state

```bash
helm list -A
```

```text
NAME	NAMESPACE	REVISION	UPDATED	STATUS	CHART	APP VERSION
```

No Helm releases anywhere in the cluster. The chart sources in this folder are untouched and
can be reinstalled at any time with the commands in Tasks 2 and 3.
