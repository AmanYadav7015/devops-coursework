# Task 1: Every Important Helm Command, Executed and Explained

Everything on this page was run against a live minikube cluster (Kubernetes v1.37.0) using
**Helm v4.3.0**. All output blocks are copied from the terminal, not typed from memory.

Every release is installed into the namespace `hw15` so that this lab never collides with
anything else running on the shared cluster.

```bash
kubectl create namespace hw15
```

```text
namespace/hw15 created
```

---

## Version check first — this matters

```bash
helm version
```

```text
version.BuildInfo{Version:"v4.3.0", GitCommit:"bec5b06ed841fe5269972d864d5177944fd5970f", GitTreeState:"clean", GoVersion:"go1.27.1", KubeClientVersion:"v1.37"}
```

Nearly every Helm tutorial you will find online was written for Helm 3. This machine runs
Helm 4. The commands are the same, but several outputs are different, and two flags that
Helm 3 tutorials use have been removed. Each difference is called out inline below with a
**Helm 4 difference** note, and they are collected in the root
[README](../README.md#helm-3-vs-helm-4-what-actually-changed).

---

## 1. `helm create` — scaffold a brand new chart

```bash
helm create scaffold-demo
```

```text
Creating scaffold-demo
```

`helm create` writes a complete, working, installable chart. It is the fastest way to see
what Helm expects a chart to look like.

```bash
find scaffold-demo -print | sort | sed 's|[^/]*/|  |g'
```

```text
scaffold-demo
  .helmignore
  Chart.yaml
  charts
  templates
    NOTES.txt
    _helpers.tpl
    deployment.yaml
    hpa.yaml
    httproute.yaml
    ingress.yaml
    service.yaml
    serviceaccount.yaml
    tests
      test-connection.yaml
  values.yaml
```

What each piece is for:

| Path | Purpose |
|---|---|
| `Chart.yaml` | Chart metadata: name, version, appVersion, type. Helm refuses to load a directory without it. |
| `values.yaml` | The default configuration. Everything a user is allowed to tune lives here. |
| `templates/` | Go templates that render into Kubernetes manifests. |
| `templates/_helpers.tpl` | Named template definitions. Files starting with `_` never render to a manifest on their own. |
| `templates/NOTES.txt` | Printed to the user after `install`/`upgrade`. Also a template. |
| `templates/tests/` | Pods annotated `helm.sh/hook: test`, run on demand by `helm test`. |
| `charts/` | Subchart dependencies get vendored here. Empty for a new chart. |
| `.helmignore` | Patterns excluded when the chart is packaged into a `.tgz`. |

**Helm 4 difference:** the scaffold now includes `templates/httproute.yaml`, a Gateway API
`HTTPRoute` guarded by `httpRoute.enabled`. The Helm 3 scaffold only produced an `Ingress`.

```bash
sed -n '1,9p' scaffold-demo/templates/httproute.yaml
```

```text
{{- if .Values.httpRoute.enabled -}}
{{- $fullName := include "scaffold-demo.fullname" . -}}
{{- $svcPort := .Values.service.port -}}
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: {{ $fullName }}
  labels:
    {{- include "scaffold-demo.labels" . | nindent 4 }}
```

---

## 2. `helm lint` — static checks before you touch the cluster

```bash
helm lint scaffold-demo
```

```text
==> Linting scaffold-demo
[INFO] Chart.yaml: icon is recommended

1 chart(s) linted, 0 chart(s) failed
```

`helm lint` parses `Chart.yaml`, renders the templates with the default values, and checks
that the result is valid YAML with the required Kubernetes fields present. It never talks
to a cluster. Severity ladder is `[INFO]` (advice) → `[WARNING]` (suspicious) →
`[ERROR]` (chart will not install). Only `[ERROR]` makes the chart count as failed, which
is why `0 chart(s) failed` is printed even though an `[INFO]` was raised.

---

## 3. `helm template` — render the manifests, send nothing anywhere

```bash
helm template demo scaffold-demo -n hw15
```

```text
---
# Source: scaffold-demo/templates/serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: demo-scaffold-demo
  labels:
    helm.sh/chart: scaffold-demo-0.1.0
    app.kubernetes.io/name: scaffold-demo
    app.kubernetes.io/instance: demo
    app.kubernetes.io/version: "1.16.0"
    app.kubernetes.io/managed-by: Helm
automountServiceAccountToken: true

---
# Source: scaffold-demo/templates/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: demo-scaffold-demo
  labels:
    helm.sh/chart: scaffold-demo-0.1.0
    app.kubernetes.io/name: scaffold-demo
    app.kubernetes.io/instance: demo
    app.kubernetes.io/version: "1.16.0"
    app.kubernetes.io/managed-by: Helm
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: http
      protocol: TCP
      name: http
  selector:
    app.kubernetes.io/name: scaffold-demo
    app.kubernetes.io/instance: demo

---
# Source: scaffold-demo/templates/deployment.yaml
...
```

That is 103 lines in total, from four template files:

```bash
helm template demo scaffold-demo -n hw15 | grep -n "^# Source"
```

```text
2:# Source: scaffold-demo/templates/serviceaccount.yaml
16:# Source: scaffold-demo/templates/service.yaml
39:# Source: scaffold-demo/templates/deployment.yaml
83:# Source: scaffold-demo/templates/tests/test-connection.yaml
```

This is the "aha" command. The chart author writes `{{ include "scaffold-demo.fullname" . }}`
and `{{ .Values.service.port }}`; `helm template` shows you the plain Kubernetes YAML that
those actually turn into, with the release name `demo` substituted everywhere. If a rendered
manifest is wrong, the bug is in the template or the values, not in Kubernetes.

Note the `# Source:` comment above every document — Helm injects it so you can trace any
line of output back to the template file it came from.

**Note on the test pod:** `helm template` renders `tests/test-connection.yaml` too, because
`helm template` is a pure text renderer and does not sort hooks out of the stream. A real
install does not create it; see `helm get hooks` below.

---

## 4. `helm install --dry-run --debug` — the full install pipeline, stopped before the API call

```bash
helm install demo scaffold-demo -n hw15 --dry-run --debug
```

```text
level=WARN msg="--dry-run is deprecated and should be replaced with '--dry-run=client'"
level=DEBUG msg="Original chart version" version=""
level=DEBUG msg="Chart path" path=/Users/aman/Desktop/devops-heros/coursework-labs/15-helm/scaffold-demo
level=DEBUG msg="number of dependencies in the chart" chart=scaffold-demo dependencies=0
NAME: demo
LAST DEPLOYED: Wed Oct  7 18:00:03 2026
NAMESPACE: hw15
STATUS: pending-install
REVISION: 1
DESCRIPTION: Dry run complete
USER-SUPPLIED VALUES:
{}

COMPUTED VALUES:
affinity: {}
autoscaling:
  enabled: false
  maxReplicas: 100
  minReplicas: 1
  targetCPUUtilizationPercentage: 80
fullnameOverride: ""
httpRoute:
  annotations: {}
  enabled: false
  hostnames:
  - chart-example.local
  parentRefs:
  - name: gateway
    sectionName: http
...
```

**Helm 4 difference 1:** plain `--dry-run` now emits a deprecation warning. Helm 4 wants
`--dry-run=client` or `--dry-run=server`.

**Helm 4 difference 2:** `--debug` output is structured key/value logging
(`level=DEBUG msg="Chart path" path=...`). Helm 3 printed free-form lines like
`install.go:200: [debug] Original chart version: ""`. If you are grepping debug output in a
script, that script will need rewriting.

The output has five labelled sections that `helm template` does not give you:

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

* `USER-SUPPLIED VALUES` — only what you passed with `--set`/`-f`.
* `COMPUTED VALUES` — the full merge of chart defaults plus your overrides. This is what the
  templates actually see in `.Values`.
* `HOOKS` — resources carrying a `helm.sh/hook` annotation, **separated out** from the
  manifest. `helm template` leaves them mixed in.
* `MANIFEST` — the non-hook resources that would be applied.
* `NOTES` — the rendered `NOTES.txt`.

So the ranking is: `helm template` = rendering only; `--dry-run` = rendering plus release
bookkeeping (revision number, status, hook/manifest split, notes) but no write to the
cluster; real install = all of that plus the API calls and the stored release record.
The full three-way comparison with a worked example is in the root
[README](../README.md#helm-template-vs---dry-run-vs-install).

---

## 5. `helm install` — create a release

```bash
helm install demo scaffold-demo -n hw15
```

```text
NAME: demo
LAST DEPLOYED: Wed Oct  7 18:00:11 2026
NAMESPACE: hw15
STATUS: deployed
REVISION: 1
DESCRIPTION: Install complete
NOTES:
1. Get the application URL by running these commands:
  export POD_NAME=$(kubectl get pods --namespace hw15 -l "app.kubernetes.io/name=scaffold-demo,app.kubernetes.io/instance=demo" -o jsonpath="{.items[0].metadata.name}")
  export CONTAINER_PORT=$(kubectl get pod --namespace hw15 $POD_NAME -o jsonpath="{.spec.containers[0].ports[0].containerPort}")
  echo "Visit http://127.0.0.1:8080 to use your application"
  kubectl --namespace hw15 port-forward $POD_NAME 8080:$CONTAINER_PORT
```

`demo` is the **release name** — the name of this particular installation of the chart. The
same chart can be installed many times into the same cluster under different release names.
`REVISION: 1` is the first entry in this release's history.

**Helm 4 difference:** the `DESCRIPTION:` line (`Install complete`) is new in the Helm 4
install/upgrade summary. Helm 3 only showed it in `helm history`.

What landed in the cluster:

```bash
kubectl get all -n hw15
```

```text
NAME                                      READY   STATUS              RESTARTS   AGE
pod/demo-scaffold-demo-54d8755956-6f8mt   0/1     ContainerCreating   0          5s

NAME                         TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
service/demo-scaffold-demo   ClusterIP   10.108.45.223   <none>        80/TCP    5s

NAME                                 READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/demo-scaffold-demo   0/1     1            0           5s

NAME                                            DESIRED   CURRENT   READY   AGE
replicaset.apps/demo-scaffold-demo-54d8755956   1         1         0       5s
```

---

## 6. `helm list` — what is installed

```bash
helm list -n hw15
```

```text
NAME	NAMESPACE	REVISION	UPDATED                             	STATUS  	CHART              	APP VERSION
demo	hw15     	1       	2026-10-07 18:00:11.903769 +0530 IST	deployed	scaffold-demo-0.1.0	1.16.0
```

`helm list` reads Secrets of type `helm.sh/release.v1` in the namespace — Helm keeps its
release records in the cluster itself, not on your laptop. That is why any machine with
cluster access sees the same releases.

Machine-readable form:

```bash
helm list -n hw15 -o json
```

```text
[{"name":"demo","namespace":"hw15","revision":"1","updated":"2026-10-07 18:00:11.903769 +0530 IST","status":"deployed","chart":"scaffold-demo-0.1.0","app_version":"1.16.0"}]
```

**Helm 4 difference — a removed flag.** Helm 3's `helm list -a` / `--all` (show releases in
every state, not just `deployed`) is gone:

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

Helm 4 replaces it with one flag per state. From `helm list --help`:

```text
  -A, --all-namespaces       list releases across all namespaces
      --deployed             show deployed releases
      --failed               show failed releases
      --pending              show pending releases
      --superseded           show superseded releases
      --uninstalled          show uninstalled releases (if 'helm uninstall --keep-history' was used)
      --uninstalling         show releases that are currently being uninstalled
```

So the Helm 3 muscle memory `helm list -a` becomes, for example:

```bash
helm list -n hw15 --failed
```

```text
NAME	NAMESPACE	REVISION	UPDATED                            	STATUS	CHART             	APP VERSION
web 	hw15     	1       	2026-10-07 18:02:04.89732 +0530 IST	failed	webapp-chart-0.1.0	1.24
```

(that `web` release is the deliberately broken install from the troubleshooting section.)

`-A` / `--all-namespaces` still works and is unchanged.

---

## 7. `helm status` — the release plus the live objects

```bash
helm status demo -n hw15
```

```text
NAME: demo
LAST DEPLOYED: Wed Oct  7 18:00:11 2026
NAMESPACE: hw15
STATUS: deployed
REVISION: 1
DESCRIPTION: Install complete
RESOURCES:
==> v1/Deployment
NAME                 READY   UP-TO-DATE   AVAILABLE   AGE
demo-scaffold-demo   0/1     1            0           6s

==> v1/Pod(related)
NAME                                  READY   STATUS              RESTARTS   AGE
demo-scaffold-demo-54d8755956-6f8mt   0/1     ContainerCreating   0          6s

==> v1/ServiceAccount
NAME                 AGE
demo-scaffold-demo   6s

==> v1/Service
NAME                 TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
demo-scaffold-demo   ClusterIP   10.108.45.223   <none>        80/TCP    6s


NOTES:
1. Get the application URL by running these commands:
  export POD_NAME=$(kubectl get pods --namespace hw15 -l "app.kubernetes.io/name=scaffold-demo,app.kubernetes.io/instance=demo" -o jsonpath="{.items[0].metadata.name}")
  ...
```

`helm status` is `helm list` for one release plus a live `kubectl get` of everything the
release owns, grouped by kind, and the notes replayed. The `v1/Pod(related)` block is pods
Helm did not create directly but that belong to a Deployment it did create — useful, because
the thing that is actually broken is almost always a pod.

---

## 8. `helm get` — read back what Helm stored

`helm get` is a group of subcommands, not a single command:

```bash
helm get --help
```

```text
Available Commands:
  all         download all information for a named release
  hooks       download all hooks for a named release
  manifest    download the manifest for a named release
  metadata    This command fetches metadata for a given release
  notes       download the notes for a named release
  values      download the values file for a named release
```

### `helm get values` — what the user asked for

```bash
helm get values demo -n hw15
```

```text
USER-SUPPLIED VALUES:
null
```

`null` is correct: nothing was overridden at install time, so the user-supplied set is empty.
This subcommand deliberately does **not** show chart defaults — it answers "what did somebody
type", which is what you want when a release behaves differently from the chart.

```bash
helm get values demo -n hw15 --all
```

```text
COMPUTED VALUES:
affinity: {}
autoscaling:
  enabled: false
  maxReplicas: 100
  minReplicas: 1
  targetCPUUtilizationPercentage: 80
fullnameOverride: ""
httpRoute:
  annotations: {}
  enabled: false
  hostnames:
  - chart-example.local
  parentRefs:
  - name: gateway
    sectionName: http
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /headers
image:
  pullPolicy: IfNotPresent
  repository: nginx
  tag: ""
imagePullSecrets: []
ingress:
  annotations: {}
  className: ""
  enabled: false
...
```

`--all` adds the chart defaults so you see the merged map the templates actually read.

### `helm get manifest` — the rendered YAML Helm applied

This is the subcommand that makes templating click.

```bash
helm get manifest demo -n hw15
```

```text
---
# Source: scaffold-demo/templates/serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: demo-scaffold-demo
  labels:
    helm.sh/chart: scaffold-demo-0.1.0
    app.kubernetes.io/name: scaffold-demo
    app.kubernetes.io/instance: demo
    app.kubernetes.io/version: "1.16.0"
    app.kubernetes.io/managed-by: Helm
automountServiceAccountToken: true

---
# Source: scaffold-demo/templates/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: demo-scaffold-demo
  labels:
    helm.sh/chart: scaffold-demo-0.1.0
    app.kubernetes.io/name: scaffold-demo
    app.kubernetes.io/instance: demo
    app.kubernetes.io/version: "1.16.0"
    app.kubernetes.io/managed-by: Helm
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: http
      protocol: TCP
      name: http
  selector:
    app.kubernetes.io/name: scaffold-demo
    app.kubernetes.io/instance: demo

---
# Source: scaffold-demo/templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-scaffold-demo
  labels:
    helm.sh/chart: scaffold-demo-0.1.0
    app.kubernetes.io/name: scaffold-demo
    app.kubernetes.io/instance: demo
    app.kubernetes.io/version: "1.16.0"
    app.kubernetes.io/managed-by: Helm
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: scaffold-demo
      app.kubernetes.io/instance: demo
  template:
    metadata:
      labels:
        helm.sh/chart: scaffold-demo-0.1.0
        app.kubernetes.io/name: scaffold-demo
        app.kubernetes.io/instance: demo
        app.kubernetes.io/version: "1.16.0"
        app.kubernetes.io/managed-by: Helm
    spec:
      serviceAccountName: demo-scaffold-demo
      containers:
        - name: scaffold-demo
          image: "nginx:1.16.0"
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 80
              protocol: TCP
          livenessProbe:
            httpGet:
              path: /
              port: http
          readinessProbe:
            httpGet:
              path: /
              port: http
```

Read that against the template. `values.yaml` has `image.tag: ""` and `Chart.yaml` has
`appVersion: "1.16.0"`, and the template says
`image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"`.
The rendered result is `image: "nginx:1.16.0"` — the `default` filter fell back to the chart's
appVersion. You can only see that by reading the rendered manifest.

Compare the source list with `helm template`:

```bash
helm get manifest demo -n hw15 | grep -n "^# Source"
```

```text
2:# Source: scaffold-demo/templates/serviceaccount.yaml
16:# Source: scaffold-demo/templates/service.yaml
39:# Source: scaffold-demo/templates/deployment.yaml
```

Three sources, not four. The test pod is **not** in the manifest, because it is a hook.

### `helm get hooks` — the resources Helm runs at lifecycle points

```bash
helm get hooks demo -n hw15
```

```text
---
# Source: scaffold-demo/templates/tests/test-connection.yaml
apiVersion: v1
kind: Pod
metadata:
  name: "demo-scaffold-demo-test-connection"
  labels:
    helm.sh/chart: scaffold-demo-0.1.0
    app.kubernetes.io/name: scaffold-demo
    app.kubernetes.io/instance: demo
    app.kubernetes.io/version: "1.16.0"
    app.kubernetes.io/managed-by: Helm
  annotations:
    "helm.sh/hook": test
spec:
  containers:
    - name: wget
      image: busybox
      command: ['wget']
      args: ['demo-scaffold-demo:80']
  restartPolicy: Never
```

The `"helm.sh/hook": test` annotation is what moved this pod out of the manifest and into the
hook set. It is created only when you run `helm test demo -n hw15`. Other hook values are
`pre-install`, `post-install`, `pre-upgrade`, `post-upgrade`, `pre-delete`, `post-delete` and
`pre-rollback`/`post-rollback` — the usual home for database migration Jobs.

### `helm get notes` — replay the post-install message

```bash
helm get notes demo -n hw15
```

```text
NOTES:
1. Get the application URL by running these commands:
  export POD_NAME=$(kubectl get pods --namespace hw15 -l "app.kubernetes.io/name=scaffold-demo,app.kubernetes.io/instance=demo" -o jsonpath="{.items[0].metadata.name}")
  export CONTAINER_PORT=$(kubectl get pod --namespace hw15 $POD_NAME -o jsonpath="{.spec.containers[0].ports[0].containerPort}")
  echo "Visit http://127.0.0.1:8080 to use your application"
  kubectl --namespace hw15 port-forward $POD_NAME 8080:$CONTAINER_PORT
```

Useful two weeks after the install when you have scrolled past the original output.

### `helm get metadata` — the release record itself

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

**Helm 4 difference — the big one.** `APPLY_METHOD: server-side apply`. Helm 4 uses
Kubernetes **server-side apply** by default. Helm 3 built a three-way-merge patch on the
client from (old manifest, new manifest, live object) and sent that. Under SSA the API
server tracks field ownership, so Helm now only owns the fields it actually sets — which is
why Helm 4 coexists far better with HPAs, mutating webhooks and other controllers that write
to the same objects. It also changes the wording of failures: a failed apply now reports
`server-side apply failed for object ...` (see the troubleshooting section in the root README).

---

## 9. `helm upgrade` — change a release in place

```bash
helm upgrade demo scaffold-demo -n hw15 --set replicaCount=3 --set image.tag=1.25-alpine
```

```text
Release "demo" has been upgraded. Happy Helming!
NAME: demo
LAST DEPLOYED: Wed Oct  7 18:00:38 2026
NAMESPACE: hw15
STATUS: deployed
REVISION: 2
DESCRIPTION: Upgrade complete
NOTES:
1. Get the application URL by running these commands:
  ...
```

`REVISION` went from 1 to 2. Nothing was deleted; a second release record was written.

Proof that `--set` actually landed:

```bash
helm get values demo -n hw15
```

```text
USER-SUPPLIED VALUES:
image:
  tag: 1.25-alpine
replicaCount: 3
```

`--set image.tag=1.25-alpine` uses dotted path syntax to reach into nested YAML; Helm turns
it back into a nested map. And the live cluster agrees:

```bash
kubectl get pods -n hw15 -o custom-columns='NAME:.metadata.name,IMAGE:.spec.containers[0].image,STATUS:.status.phase'
```

```text
NAME                                  IMAGE               STATUS
demo-scaffold-demo-54d8755956-6f8mt   nginx:1.16.0        Running
demo-scaffold-demo-7d755d876b-5r7xn   nginx:1.25-alpine   Running
demo-scaffold-demo-7d755d876b-7sfj5   nginx:1.25-alpine   Running
demo-scaffold-demo-7d755d876b-sbsjh   nginx:1.25-alpine   Running
```

Caught mid-rollout: three new `nginx:1.25-alpine` pods are up and the single old
`nginx:1.16.0` pod has not finished terminating yet. That is the normal Deployment rolling
update, which Helm does not manage itself — it just updates the Deployment and lets the
Deployment controller do the work.

---

## 10. `helm history` — the revision ledger

```bash
helm history demo -n hw15
```

```text
REVISION	UPDATED                 	STATUS    	CHART              	APP VERSION	DESCRIPTION
1       	Wed Oct  7 18:00:11 2026	superseded	scaffold-demo-0.1.0	1.16.0     	Install complete
2       	Wed Oct  7 18:00:38 2026	deployed  	scaffold-demo-0.1.0	1.16.0     	Upgrade complete
```

One row per revision. Exactly one row is `deployed`; everything older is `superseded`. The
revision numbers in this table are the only valid arguments to `helm rollback`.

---

## 11. `helm rollback` — go back to an earlier revision

```bash
helm rollback demo 1 -n hw15
```

```text
Rollback was a success! Happy Helming!
```

```bash
helm history demo -n hw15
```

```text
REVISION	UPDATED                 	STATUS    	CHART              	APP VERSION	DESCRIPTION
1       	Wed Oct  7 18:00:11 2026	superseded	scaffold-demo-0.1.0	1.16.0     	Install complete
2       	Wed Oct  7 18:00:38 2026	superseded	scaffold-demo-0.1.0	1.16.0     	Upgrade complete
3       	Wed Oct  7 18:00:49 2026	deployed  	scaffold-demo-0.1.0	1.16.0     	Rollback to 1
```

Revision 2 was **not** deleted — it became `superseded`, and a brand-new revision 3 appeared
with the description `Rollback to 1`. A rollback is just an upgrade whose input is an old
revision's values and manifest. Task 2 drills into this.

The cluster followed:

```bash
kubectl get pods -n hw15 -o custom-columns='NAME:.metadata.name,IMAGE:.spec.containers[0].image,STATUS:.status.phase'
```

```text
NAME                                  IMAGE          STATUS
demo-scaffold-demo-54d8755956-cs8h7   nginx:1.16.0   Running
```

One pod, `nginx:1.16.0` — exactly revision 1's configuration.

```bash
helm get values demo -n hw15
```

```text
USER-SUPPLIED VALUES:
null
```

The `--set` values are gone too, because revision 1 had no user-supplied values.

---

## 12. `helm repo` — where charts come from

```bash
helm repo list
```

```text
no repositories to show
```

Helm 3 and 4 ship with **no** repositories configured. You add them yourself.

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
```

```text
"bitnami" has been added to your repositories
```

```bash
helm repo list
```

```text
NAME   	URL
bitnami	https://charts.bitnami.com/bitnami
```

```bash
helm repo update
```

```text
Hang tight while we grab the latest from your chart repositories...
...Successfully got an update from the "bitnami" chart repository
Update Complete. ⎈Happy Helming!⎈
```

A chart repository is just an HTTP server hosting `.tgz` chart archives plus an `index.yaml`
catalogue. `helm repo add` fetches that index once and caches it; `helm repo update`
re-fetches it. If `helm search repo` cannot find a chart you know exists, you have a stale
cache — run `helm repo update` first.

Helm's own config paths on this machine (visible in any `--help`):

```text
--repository-config   /Users/aman/Library/Preferences/helm/repositories.yaml
--repository-cache    /Users/aman/Library/Caches/helm/repository
```

---

## 13. `helm search` — find a chart

### `helm search repo` — search the local cache of repos you added

```bash
helm search repo nginx
```

```text
NAME                            	CHART VERSION	APP VERSION	DESCRIPTION
bitnami/nginx                   	25.2.1       	1.31.6     	NGINX Open Source is a web server that can be a...
bitnami/nginx-ingress-controller	12.0.7       	1.13.1     	NGINX Ingress Controller is an Ingress controll...
bitnami/nginx-intel             	2.1.15       	0.4.9      	DEPRECATED NGINX Open Source for Intel is a lig...
```

Two different version columns, and people confuse them constantly:

* **CHART VERSION** — the version of the packaging (`version:` in `Chart.yaml`). This is what
  you pin with `--version`.
* **APP VERSION** — the version of the software inside (`appVersion:`). Informational only.

`--versions` lists every published chart version, which is what you need when pinning:

```bash
helm search repo bitnami/postgresql --versions | head -8
```

```text
NAME                 	CHART VERSION	APP VERSION	DESCRIPTION
bitnami/postgresql   	18.12.4      	18.6.0     	PostgreSQL (Postgres) is an open source object-...
bitnami/postgresql   	18.12.3      	18.6.0     	PostgreSQL (Postgres) is an open source object-...
bitnami/postgresql   	18.12.2      	18.6.0     	PostgreSQL (Postgres) is an open source object-...
bitnami/postgresql   	18.12.1      	18.6.0     	PostgreSQL (Postgres) is an open source object-...
bitnami/postgresql   	18.12.0      	18.6.0     	PostgreSQL (Postgres) is an open source object-...
bitnami/postgresql   	18.11.6      	18.6.0     	PostgreSQL (Postgres) is an open source object-...
bitnami/postgresql   	18.11.5      	18.6.0     	PostgreSQL (Postgres) is an open source object-...
```

### `helm search hub` — search Artifact Hub, no repo needed

```bash
helm search hub wordpress --max-col-width 55 | head -12
```

```text
URL                                                    	CHART VERSION	APP VERSION        	DESCRIPTION
https://artifacthub.io/packages/helm/slybase-wordpre...	5.5.40       	7.0.1              	Using the official WordPress image. This chart provi...
https://artifacthub.io/packages/helm/wordpress-ng/wo...	1.0.11       	7.1.3              	WordPress is the world's most popular blogging and c...
https://artifacthub.io/packages/helm/quench-wordpres...	0.0.25       	7.1.3              	Hardened WordPress CMS (PHP-FPM + nginx) on a 0-CVE ...
https://artifacthub.io/packages/helm/wordpress-maria...	1.0.2        	1.0.0              	A Helm chart for deploying Wordpress+Mariadb stack o...
https://artifacthub.io/packages/helm/kube-wordpress/...	0.1.0        	1.1                	this is my wordpress package
https://artifacthub.io/packages/helm/bitnami/wordpress 	34.1.3       	7.1.3              	WordPress is the world's most popular blogging and c...
https://artifacthub.io/packages/helm/helmforge/wordp...	3.0.9        	7.1.2              	A Helm chart for deploying WordPress on Kubernetes w...
https://artifacthub.io/packages/helm/shubham-wordpre...	0.1.0        	1.16.0             	A Helm chart for Kubernetes
https://artifacthub.io/packages/helm/sb-helm-charts/...	0.4.0        	6.8                	The world's most popular CMS - WordPress with MySQL/...
https://artifacthub.io/packages/helm/bysamio/wordpress 	2.0.2        	6.9.0              	A Helm chart for WordPress using BySamio non-root Do...
https://artifacthub.io/packages/helm/groundhog2k/wor...	0.16.6       	7.1.2-apache       	A Helm chart for Wordpress on Kubernetes
```

`search hub` queries the public Artifact Hub API over the internet and returns **URLs**, not
installable `repo/chart` references, because the repo may not be on your machine. `search repo`
searches only what you have added, offline, and returns names you can install directly.

Once a repo is added you can inspect a chart without installing it:

```bash
helm show chart bitnami/nginx | head -20
```

```text
annotations:
  fips: "true"
  images: |
    - name: git
      version: 2.56.0
      image: registry-1.docker.io/bitnami/git:latest
    - name: nginx
      version: 1.31.6
      image: registry-1.docker.io/bitnami/nginx:latest
    - name: nginx-exporter
      version: 1.5.3
      image: registry-1.docker.io/bitnami/nginx-exporter:latest
  licenses: Apache-2.0
  tanzuCategory: clusterUtility
apiVersion: v2
appVersion: 1.31.6
dependencies:
- name: common
  repository: oci://registry-1.docker.io/bitnamicharts
  tags:
```

Note the dependency line: modern Bitnami charts pull their `common` library chart from an
**OCI registry** (`oci://registry-1.docker.io/bitnamicharts`), not from an HTTP chart repo.
OCI is now the preferred distribution mechanism and needs no `helm repo add` at all —
`helm install x oci://registry-1.docker.io/bitnamicharts/nginx` works directly.

---

## 14. `helm uninstall` — remove a release

```bash
helm uninstall demo -n hw15
```

```text
release "demo" uninstalled
```

```bash
helm list -n hw15
```

```text
NAME	NAMESPACE	REVISION	UPDATED	STATUS	CHART	APP VERSION
```

```bash
helm history demo -n hw15
```

```text
Error: release: not found
```

By default `helm uninstall` deletes the release's Kubernetes objects **and** its whole
history. There is no `helm rollback` after an uninstall. If you want the history kept so you
can `helm rollback` the release back into existence, uninstall with `--keep-history`; the
release then shows up under `helm list --uninstalled`.

---

## Command summary

| Command | Talks to cluster? | What it does |
|---|---|---|
| `helm create NAME` | no | Scaffold a working chart on disk |
| `helm lint CHART` | no | Static validation of chart + rendered YAML |
| `helm template REL CHART` | no | Render templates to stdout |
| `helm install REL CHART --dry-run` | no (client) | Render + release bookkeeping, no write |
| `helm install REL CHART` | yes | Apply manifests, store release revision 1 |
| `helm list` | yes | Releases in a namespace (reads release Secrets) |
| `helm status REL` | yes | One release + live objects + notes |
| `helm get values REL` | yes | User-supplied (or `--all`: computed) values |
| `helm get manifest REL` | yes | The rendered YAML that was applied |
| `helm get hooks REL` | yes | Hook resources, split out of the manifest |
| `helm get notes REL` | yes | Rendered NOTES.txt |
| `helm get metadata REL` | yes | Release record: chart, revision, apply method |
| `helm upgrade REL CHART` | yes | New revision with new values/chart |
| `helm history REL` | yes | Revision ledger |
| `helm rollback REL N` | yes | New revision reproducing revision N |
| `helm uninstall REL` | yes | Delete objects and (by default) history |
| `helm repo add/list/update` | no | Manage chart repository sources |
| `helm search repo/hub` | repo: no, hub: internet | Find charts |
| `helm show chart/values` | no | Inspect a chart without installing |
