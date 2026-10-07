# Task 3: Mini Project — Package and Deploy the Notes App with Helm

Two charts live under [`../charts/`](../charts):

* **Part A — [`notes-chart`](../charts/notes-chart)**: the mini project exactly as specified in
  `session-15-helm/mini-project/README.md`, built and run end to end.
* **Part B — [`webapp-chart`](../charts/webapp-chart)**: a chart I wrote myself, going beyond the
  mini project with `_helpers.tpl`, conditionals, ranges, a `NOTES.txt` and a
  `values-prod.yaml`. It is the chart used throughout [Task 2](../02-rollback/README.md).

Everything ran against minikube (Kubernetes v1.37.0) with Helm v4.3.0 in namespace `hw15`.

**One deviation from the brief, stated up front:** the mini project specifies
`nodePort: 30090`. This cluster is shared with other labs running at the same time, and
NodePorts are a cluster-wide resource — two Services cannot bind the same one. The charts
here use **30151** (notes-chart) and **30150** (webapp-chart), which are inside the port range
assigned to this lab. Nothing else was changed.

---

# Part A: The Notes App mini project

## Chart layout

```bash
find charts/notes-chart -print | sort
```

```text
charts/notes-chart
charts/notes-chart/Chart.yaml
charts/notes-chart/templates
charts/notes-chart/templates/configmap.yaml
charts/notes-chart/templates/deployment.yaml
charts/notes-chart/templates/service.yaml
charts/notes-chart/values-prod.yaml
charts/notes-chart/values.yaml
```

Four templates-worth of ideas in a chart you can read in one screen. That is the point of the
mini project: no `_helpers.tpl`, no conditionals, just `{{ .Release.Name }}` and
`{{ .Values.x }}` so the substitution is obvious.

### `Chart.yaml`

```yaml
apiVersion: v2
name: notes-chart
description: A simple Notes application Helm chart
type: application
version: 0.1.0
appVersion: "1.0"
```

### `values.yaml` (development defaults)

```yaml
replicaCount: 1

image:
  repository: nginx
  tag: "1.24"

service:
  port: 80
  nodePort: 30151

app:
  name: notes-app
  environment: development
```

### `values-prod.yaml` (production override)

```yaml
replicaCount: 3

image:
  repository: nginx
  tag: "1.25"

service:
  port: 80
  nodePort: 30151

app:
  name: notes-app
  environment: production
```

Three values differ: `replicaCount`, `image.tag` and `app.environment`. Those three
differences are the whole dev-vs-prod story, and the templates never change.

### The templates

`templates/configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Release.Name }}-config
data:
  APP_NAME: {{ .Values.app.name | quote }}
  ENVIRONMENT: {{ .Values.app.environment | quote }}
```

`templates/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-deploy
  labels:
    app: {{ .Release.Name }}
    environment: {{ .Values.app.environment }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}
    spec:
      containers:
        - name: notes
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          ports:
            - containerPort: {{ .Values.service.port }}
          envFrom:
            - configMapRef:
                name: {{ .Release.Name }}-config
```

`templates/service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Release.Name }}-svc
spec:
  type: NodePort
  selector:
    app: {{ .Release.Name }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.port }}
      nodePort: {{ .Values.service.nodePort }}
```

Two template habits worth copying from this chart:

* `| quote` on ConfigMap values. Without it, `ENVIRONMENT: production` is fine but a value
  like `1.25` or `yes` or `on` would be parsed by YAML as a number or a boolean, and
  `ConfigMap.data` only accepts strings. `| quote` makes the type unambiguous.
* `envFrom.configMapRef` keyed on `{{ .Release.Name }}-config`, which is the same expression
  used for the ConfigMap's own name. Rename the release and both move together.

---

## Step 8: Lint

```bash
helm lint charts/notes-chart
```

```text
==> Linting charts/notes-chart
[INFO] Chart.yaml: icon is recommended

1 chart(s) linted, 0 chart(s) failed
```

The brief predicted `1 chart(s) linted, 0 chart(s) failed` and that is what came back. The
extra `[INFO] Chart.yaml: icon is recommended` is advisory — adding an `icon:` URL to
`Chart.yaml` silences it. `[INFO]` never fails a lint.

---

## Step 9: Render locally

```bash
helm template notes-dev charts/notes-chart -n hw15
```

```text
---
# Source: notes-chart/templates/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: notes-dev-config
data:
  APP_NAME: "notes-app"
  ENVIRONMENT: "development"

---
# Source: notes-chart/templates/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: notes-dev-svc
spec:
  type: NodePort
  selector:
    app: notes-dev
  ports:
    - port: 80
      targetPort: 80
      nodePort: 30151

---
# Source: notes-chart/templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: notes-dev-deploy
  labels:
    app: notes-dev
    environment: development
spec:
  replicas: 1
  selector:
    matchLabels:
      app: notes-dev
  template:
    metadata:
      labels:
        app: notes-dev
    spec:
      containers:
        - name: notes
          image: "nginx:1.24"
          ports:
            - containerPort: 80
          envFrom:
            - configMapRef:
                name: notes-dev-config
```

Every `{{ }}` is gone. `{{ .Release.Name }}` became `notes-dev` in six places, and it became
`notes-dev` because that is the name given on the command line — not because it is written
anywhere in the chart. That is what makes a chart reusable: install it twice under two names
and you get two independent sets of objects.

Helm also reordered the documents. It applies resources in a fixed **install order** by kind
(Namespace, ConfigMap, Secret, Service, … then Deployment, … ) so that a Deployment never
references a ConfigMap that does not exist yet. The alphabetical file order on disk is
irrelevant.

---

## Step 10: Install (development)

```bash
helm install notes-dev charts/notes-chart -n hw15
```

```text
NAME: notes-dev
LAST DEPLOYED: Wed Oct  7 18:13:27 2026
NAMESPACE: hw15
STATUS: deployed
REVISION: 1
DESCRIPTION: Install complete
TEST SUITE: None
```

The brief expected `NAME / STATUS: deployed / REVISION: 1` and all three match. Helm 4 adds
`DESCRIPTION:` and `TEST SUITE: None`; the latter means the chart defines no `helm test`
hooks, which is true — `notes-chart` has no `templates/tests/` directory.

### Verify

```bash
kubectl get pods -n hw15 -l app=notes-dev
```

```text
NAME                                READY   STATUS    RESTARTS   AGE
notes-dev-deploy-74956bd987-r9t4d   1/1     Running   0          14s
```

```bash
kubectl get services -n hw15
```

```text
NAME               TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE
notes-dev-svc      NodePort   10.109.0.104   <none>        80:30151/TCP   14s
web-webapp-chart   NodePort   10.96.152.14   <none>        80:30150/TCP   8m6s
```

```bash
kubectl get configmaps -n hw15
```

```text
NAME                      DATA   AGE
kube-root-ca.crt          1      13m
notes-dev-config          2      14s
web-webapp-chart-config   5      8m6s
```

(`web-*` is the Task 2 release sharing the namespace; `kube-root-ca.crt` is created by
Kubernetes in every namespace.)

The app actually answers. The minikube node IP is not routable from the macOS host on this
setup, so the NodePort is curled from inside the node:

```bash
minikube ssh -- "curl -sI http://localhost:30151 | head -2"
```

```text
HTTP/1.1 200 OK
Server: nginx/1.24.0
```

And the ConfigMap really became environment variables in the container:

```bash
kubectl exec -n hw15 deploy/notes-dev-deploy -- env | grep -E 'APP_NAME|ENVIRONMENT'
```

```text
ENVIRONMENT=development
APP_NAME=notes-app
```

That is the full chain working: `values.yaml` → template → ConfigMap object → `envFrom` →
process environment.

---

## Step 11: Upgrade to production values

```bash
helm upgrade notes-dev charts/notes-chart -n hw15 -f charts/notes-chart/values-prod.yaml
```

```text
Release "notes-dev" has been upgraded. Happy Helming!
NAME: notes-dev
LAST DEPLOYED: Wed Oct  7 18:13:47 2026
NAMESPACE: hw15
STATUS: deployed
REVISION: 2
DESCRIPTION: Upgrade complete
TEST SUITE: None
```

### Verify 3 pods are running

```bash
kubectl get pods -n hw15 -l app=notes-dev -o custom-columns='NAME:.metadata.name,IMAGE:.spec.containers[0].image,READY:.status.containerStatuses[0].ready,STATUS:.status.phase'
```

```text
NAME                               IMAGE        READY   STATUS
notes-dev-deploy-bbcc464b4-b5c7j   nginx:1.25   true    Running
notes-dev-deploy-bbcc464b4-h27dz   nginx:1.25   true    Running
notes-dev-deploy-bbcc464b4-pkqhh   nginx:1.25   true    Running
```

Three pods, and the image moved from `1.24` to `1.25` at the same time.

```bash
kubectl get cm notes-dev-config -n hw15 -o jsonpath='{.data}{"\n"}'
kubectl exec -n hw15 deploy/notes-dev-deploy -- env | grep -E 'APP_NAME|ENVIRONMENT'
minikube ssh -- "curl -sI http://localhost:30151 | head -2"
```

```text
{"APP_NAME":"notes-app","ENVIRONMENT":"production"}
APP_NAME=notes-app
ENVIRONMENT=production
HTTP/1.1 200 OK
Server: nginx/1.25.5
```

### A real wrinkle this chart exposes

The first `curl` immediately after the upgrade returned nothing at all; it only succeeded on
a retry a few seconds later. `notes-chart` has **no readiness probe**, so Kubernetes treats a
pod as ready the moment its container starts and will route traffic to it — and will remove
old pods from the Service — before nginx is actually listening. For a one-second startup it
is a blink; for a real application it is a visible outage on every deploy. The `webapp-chart`
in Part B adds `readinessProbe`/`livenessProbe` for exactly this reason.

---

## Step 12: Check release history

```bash
helm history notes-dev -n hw15
```

```text
REVISION	UPDATED                 	STATUS    	CHART            	APP VERSION	DESCRIPTION
1       	Wed Oct  7 18:13:27 2026	superseded	notes-chart-0.1.0	1.0        	Install complete
2       	Wed Oct  7 18:13:47 2026	deployed  	notes-chart-0.1.0	1.0        	Upgrade complete
```

Matches the expected `1 superseded / 2 deployed` exactly.

---

## Step 13: Simulate a bad upgrade

```bash
helm upgrade notes-dev charts/notes-chart -n hw15 -f charts/notes-chart/values-prod.yaml --set image.tag=broken-tag-does-not-exist
```

```text
Release "notes-dev" has been upgraded. Happy Helming!
NAME: notes-dev
LAST DEPLOYED: Wed Oct  7 18:15:32 2026
NAMESPACE: hw15
STATUS: deployed
REVISION: 3
DESCRIPTION: Upgrade complete
TEST SUITE: None
```

Note that `-f values-prod.yaml` is passed again. `--set` alone would have reverted
`replicaCount` and `app.environment` to the chart defaults, because `helm upgrade` computes
values from *chart defaults + what you pass this time* — it does not inherit the previous
revision's values unless you add `--reuse-values`.

```bash
kubectl get pods -n hw15 -l app=notes-dev -o custom-columns='NAME:.metadata.name,IMAGE:.spec.containers[0].image,READY:.status.containerStatuses[0].ready,REASON:.status.containerStatuses[0].state.waiting.reason'
```

```text
NAME                                IMAGE                             READY   REASON
notes-dev-deploy-79b4dbdffd-225g9   nginx:broken-tag-does-not-exist   false   ErrImagePull
notes-dev-deploy-bbcc464b4-b5c7j    nginx:1.25                        true    <none>
notes-dev-deploy-bbcc464b4-h27dz    nginx:1.25                        true    <none>
notes-dev-deploy-bbcc464b4-pkqhh    nginx:1.25                        true    <none>
```

The brief predicts a single pod in `ImagePullBackOff`. What really happens is slightly more
interesting: the Deployment's rolling-update strategy brings up **one** new pod, that pod
fails to pull, and because it never becomes available the rollout refuses to touch the three
healthy `1.25` pods. `ErrImagePull` is the first failure and it becomes `ImagePullBackOff`
once the kubelet starts backing off between retries — same condition, different stage.

```bash
kubectl get deploy notes-dev-deploy -n hw15
```

```text
NAME               READY   UP-TO-DATE   AVAILABLE   AGE
notes-dev-deploy   3/3     1            3           2m10s
```

`READY 3/3` but `UP-TO-DATE 1`: the fleet is healthy, the *new version* is not. Reading only
`READY` would hide this completely.

```bash
kubectl get events -n hw15 --sort-by=.lastTimestamp | grep broken-tag | tail -3
```

```text
4s   Normal    Pulling   pod/notes-dev-deploy-79b4dbdffd-225g9   Pulling image "nginx:broken-tag-does-not-exist"
3s   Warning   Failed    pod/notes-dev-deploy-79b4dbdffd-225g9   Failed to pull image "nginx:broken-tag-does-not-exist": rpc error: code = NotFound desc = failed to pull and unpack image "docker.io/library/nginx:broken-tag-does-not-exist": failed to resolve reference "docker.io/library/nginx:broken-tag-does-not-exist": docker.io/library/nginx:broken-tag-does-not-exist: not found
2s   Normal    BackOff   pod/notes-dev-deploy-79b4dbdffd-225g9   Back-off pulling image "nginx:broken-tag-does-not-exist"
```

Traffic is unaffected the whole time, because the old pods were never removed:

```bash
minikube ssh -- "curl -sI http://localhost:30151 | head -2"
```

```text
HTTP/1.1 200 OK
Server: nginx/1.25.5
```

```bash
helm history notes-dev -n hw15
```

```text
REVISION	UPDATED                 	STATUS    	CHART            	APP VERSION	DESCRIPTION
1       	Wed Oct  7 18:13:27 2026	superseded	notes-chart-0.1.0	1.0        	Install complete
2       	Wed Oct  7 18:13:47 2026	superseded	notes-chart-0.1.0	1.0        	Upgrade complete
3       	Wed Oct  7 18:15:32 2026	deployed  	notes-chart-0.1.0	1.0        	Upgrade complete
```

Revision 3 is `deployed` as far as Helm is concerned. **Revision 2 is the last good one.**

---

## Step 14: Rollback to revision 2

```bash
helm rollback notes-dev 2 -n hw15
```

```text
Rollback was a success! Happy Helming!
```

```bash
kubectl rollout status deploy/notes-dev-deploy -n hw15 --timeout=120s
```

```text
deployment "notes-dev-deploy" successfully rolled out
```

```bash
kubectl get pods -n hw15 -l app=notes-dev -o custom-columns='NAME:.metadata.name,IMAGE:.spec.containers[0].image,READY:.status.containerStatuses[0].ready,STATUS:.status.phase'
```

```text
NAME                               IMAGE        READY   STATUS
notes-dev-deploy-bbcc464b4-b5c7j   nginx:1.25   true    Running
notes-dev-deploy-bbcc464b4-h27dz   nginx:1.25   true    Running
notes-dev-deploy-bbcc464b4-pkqhh   nginx:1.25   true    Running
```

```bash
kubectl get deploy notes-dev-deploy -n hw15
```

```text
NAME               READY   UP-TO-DATE   AVAILABLE   AGE
notes-dev-deploy   3/3     3            3           2m28s
```

`UP-TO-DATE` is back to 3 — the stuck rollout is resolved. The broken pod is gone and the
three healthy pods were never restarted (same pod names as before the bad upgrade), because
rolling back to revision 2 restored the exact pod template they were already running.

```bash
helm get values notes-dev -n hw15
```

```text
USER-SUPPLIED VALUES:
app:
  environment: production
  name: notes-app
image:
  repository: nginx
  tag: "1.25"
replicaCount: 3
service:
  nodePort: 30151
  port: 80
```

```bash
helm get manifest notes-dev -n hw15 | grep -E 'replicas:|image:|ENVIRONMENT:'
```

```text
  ENVIRONMENT: "production"
  replicas: 3
          image: "nginx:1.25"
```

The rollback restored both the **values** and the **rendered manifest** of revision 2.

```bash
helm history notes-dev -n hw15
```

```text
REVISION	UPDATED                 	STATUS    	CHART            	APP VERSION	DESCRIPTION
1       	Wed Oct  7 18:13:27 2026	superseded	notes-chart-0.1.0	1.0        	Install complete
2       	Wed Oct  7 18:13:47 2026	superseded	notes-chart-0.1.0	1.0        	Upgrade complete
3       	Wed Oct  7 18:15:32 2026	superseded	notes-chart-0.1.0	1.0        	Upgrade complete
4       	Wed Oct  7 18:15:47 2026	deployed  	notes-chart-0.1.0	1.0        	Rollback to 2
```

Four rows. Revision 3 was not deleted and revision 2 was not reactivated — a new revision 4
was appended with `DESCRIPTION: Rollback to 2`.

---

## Step 15: Clean up

See the [cleanup section of the root README](../README.md#cleanup), where every release
created by this lab is uninstalled and the namespace removed, with verification output.

---

## Part A scorecard

| Mini project step | Done | Evidence |
|---|---|---|
| Created the chart directory and files | yes | `charts/notes-chart/` |
| `helm lint` | yes | `1 chart(s) linted, 0 chart(s) failed` |
| `helm template` renders all `{{ }}` | yes | every placeholder resolved |
| `helm install` (development) | yes | REVISION 1, pod `Running`, `nginx/1.24.0` answering |
| `values.yaml` and `values-prod.yaml` | yes | 1 pod/`1.24`/dev vs 3 pods/`1.25`/prod |
| `helm upgrade` with different values | yes | REVISION 2, 3 pods on `nginx:1.25` |
| `helm history` | yes | superseded/deployed ladder at each stage |
| Simulated bad upgrade | yes | `ErrImagePull` on `nginx:broken-tag-does-not-exist` |
| `helm rollback` to a healthy revision | yes | REVISION 4 `Rollback to 2`, 3 healthy pods |
| `helm uninstall` cleanup | yes | root README cleanup section |

---

# Part B: My own chart — `webapp-chart`

`notes-chart` is deliberately minimal. `webapp-chart` is what the same idea looks like once it
has to survive contact with more than one environment. It adds everything the brief asks for:
`_helpers.tpl`, conditionals, ranges, a `NOTES.txt`, and a `values-prod.yaml` override.

```bash
find charts/webapp-chart -print | sort
```

```text
charts/webapp-chart
charts/webapp-chart/.helmignore
charts/webapp-chart/Chart.yaml
charts/webapp-chart/templates
charts/webapp-chart/templates/NOTES.txt
charts/webapp-chart/templates/_helpers.tpl
charts/webapp-chart/templates/configmap.yaml
charts/webapp-chart/templates/deployment.yaml
charts/webapp-chart/templates/ingress.yaml
charts/webapp-chart/templates/service.yaml
charts/webapp-chart/values-prod.yaml
charts/webapp-chart/values.yaml
```

## `Chart.yaml`

```yaml
apiVersion: v2
name: webapp-chart
description: A parameterised nginx web application chart used for the Session 15 Helm lab
type: application
version: 0.1.0
appVersion: "1.24"
keywords:
  - webapp
  - nginx
  - lab
maintainers:
  - name: Aman Yadav
```

`version` is the chart's own version and is what `--version` pins. `appVersion` is the version
of the software being shipped and is what appears in the `APP VERSION` column of
`helm list` / `helm history`. Bumping the image tag through values does **not** change
`appVersion`, which is why the `APP VERSION` column stayed `1.24` through all seven revisions
in Task 2.

## `_helpers.tpl` — named templates

```text
{{- define "webapp-chart.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "webapp-chart.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "webapp-chart.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "webapp-chart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "webapp-chart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "webapp-chart.labels" -}}
helm.sh/chart: {{ include "webapp-chart.chart" . }}
{{ include "webapp-chart.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
environment: {{ .Values.app.environment }}
{{- end -}}
```

Why each piece exists:

* The leading `_` in the filename tells Helm this file produces no manifest of its own. It is
  evaluated so the `define` blocks register, then discarded.
* `trunc 63` — Kubernetes names and label values are capped at 63 characters. A long release
  name plus a long chart name would otherwise produce an object the API server rejects.
* `trimSuffix "-"` — truncating at 63 can leave a trailing hyphen, which is also invalid. This
  cleans it up.
* `if contains $name .Release.Name` — if you install this chart as release `webapp-chart`, the
  naive `printf "%s-%s"` would give `webapp-chart-webapp-chart`. This avoids the stutter.
* **`selectorLabels` is deliberately a subset of `labels`.** A Deployment's
  `spec.selector.matchLabels` is immutable after creation. If the full label set — which
  includes `helm.sh/chart` and `environment`, both of which change — were used as the
  selector, any chart version bump would make the upgrade fail outright. Only the two stable
  identity labels go in the selector.
* `.Release.Service` renders as `Helm`; `include` calls a named template, and unlike
  `template` it returns a string, which is what makes `| nindent 4` possible.

## Conditionals

Three of them, each doing a different job.

**Whole-resource toggle** — `templates/ingress.yaml` is wrapped end to end:

```text
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
...
{{- end }}
```

When the condition is false the file renders to whitespace and Helm emits no document at all.
Proved in [Task 2 stage 6](../02-rollback/README.md#a-conditional-proved-by-its-absence-and-then-its-presence).

**Optional block inside a resource** — `templates/deployment.yaml`:

```text
{{- if .Values.resources }}
resources:
  {{- toYaml .Values.resources | nindent 12 }}
{{- end }}
```

`values.yaml` sets `resources: {}` and an empty map is falsy in Go templates, so dev pods get
no `resources:` key at all rather than an empty one. `values-prod.yaml` fills it in and the
block appears. `toYaml` serialises an arbitrary values sub-tree so the chart does not have to
name `cpu`/`memory`/`requests`/`limits` individually.

**Branch on a value** — `templates/service.yaml`:

```text
{{- if eq .Values.service.type "NodePort" }}
nodePort: {{ .Values.service.nodePort }}
{{- end }}
```

`nodePort` is only legal on a `NodePort` or `LoadBalancer` Service. Setting
`service.type=ClusterIP` would otherwise render an invalid Service.

`NOTES.txt` branches too, so the post-install message tells you how to actually reach the app:

```text
{{- if eq .Values.service.type "NodePort" }}
Reach the application (the node IP is not routable from macOS, so curl from the node):
  minikube ssh -- curl -s -o /dev/null -w '%{http_code}\n' http://localhost:{{ .Values.service.nodePort }}
{{- else }}
Reach the application with a port-forward:
  kubectl port-forward svc/{{ include "webapp-chart.fullname" . }} 8080:{{ .Values.service.port }} -n {{ .Release.Namespace }}
{{- end }}
```

## Ranges

Three, over two different shapes of data.

**Over a map** — `templates/configmap.yaml` turns arbitrary user keys into ConfigMap entries:

```text
data:
  APP_ENVIRONMENT: {{ .Values.app.environment | quote }}
  APP_COLOUR: {{ .Values.app.colour | quote }}
  {{- range $key, $value := .Values.config }}
  {{ $key }}: {{ $value | quote }}
  {{- end }}
```

The chart does not know what `LOG_LEVEL` or `FEATURE_FLAGS` are. A user can add a key to
`config:` in their values file and it appears in the ConfigMap — and in the pod's
environment via `envFrom` — with no template change.

**Over a map, again** — pod labels in `templates/deployment.yaml`:

```text
{{- range $key, $value := .Values.podLabels }}
{{ $key }}: {{ $value | quote }}
{{- end }}
```

**Over a list** — explicit env vars, where order and structure matter:

```text
{{- if .Values.env }}
env:
  {{- range .Values.env }}
  - name: {{ .name }}
    value: {{ .value | quote }}
  {{- end }}
{{- end }}
```

Inside `range` over a list, `.` is rebound to the current element, which is why it is
`{{ .name }}` and not `{{ .Values.env.name }}`. Reaching back out to the root context from
inside a range needs `$` — e.g. `{{ $.Release.Name }}`.

`NOTES.txt` ranges as well, to list the injected config keys:

```text
Configuration keys injected from the ConfigMap:
{{- range $key, $value := .Values.config }}
  - {{ $key }}
{{- end }}
```

Which rendered, at install, as:

```text
Configuration keys injected from the ConfigMap:
  - FEATURE_FLAGS
  - LOG_LEVEL
  - MAX_UPLOAD_MB
```

Note the keys came out alphabetically, not in `values.yaml` order. Go templates iterate maps
in sorted key order, deliberately, so that rendering is deterministic — otherwise every
`helm upgrade` would produce a different manifest and churn resources for no reason.

## The `checksum/config` annotation

```text
template:
  metadata:
    annotations:
      checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
```

This renders the ConfigMap template a second time, hashes the result, and stamps the hash onto
the pod template. Changing a ConfigMap value therefore changes the pod template, which makes
the Deployment roll new pods. Without it, editing config values updates the ConfigMap object
but leaves the running pods holding the old environment indefinitely — a classic "I changed
the config and nothing happened". Proof that it works, with real ReplicaSet hashes, is in
[Task 2 stage 6](../02-rollback/README.md#bonus-the-checksumconfig-annotation-earning-its-keep).

## `values.yaml` vs `values-prod.yaml`

```yaml
replicaCount: 2

nameOverride: ""
fullnameOverride: ""

image:
  repository: nginx
  tag: "1.24-alpine"
  pullPolicy: IfNotPresent

service:
  type: NodePort
  port: 80
  nodePort: 30150

app:
  environment: development
  colour: blue

config:
  LOG_LEVEL: debug
  FEATURE_FLAGS: "search,export"
  MAX_UPLOAD_MB: "25"

env:
  - name: APP_MODE
    value: standalone
  - name: APP_REGION
    value: ap-south-1

podLabels: {}

resources: {}

ingress:
  enabled: false
  className: nginx
  host: webapp.hw15.local
```

```yaml
replicaCount: 3

image:
  repository: nginx
  tag: "1.27-alpine"
  pullPolicy: IfNotPresent

service:
  type: NodePort
  port: 80
  nodePort: 30150

app:
  environment: production
  colour: green

config:
  LOG_LEVEL: warn
  FEATURE_FLAGS: "search"
  MAX_UPLOAD_MB: "100"

podLabels:
  tier: frontend
  costcentre: platform

resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    cpu: 200m
    memory: 128Mi
```

`values-prod.yaml` omits `env:` and `ingress:` entirely. It does not need them: `-f` is a
**deep merge** onto the chart defaults, not a replacement, so the two `env` entries and the
`ingress.enabled: false` from `values.yaml` survive. Only what you restate is overridden.

## Where this chart is exercised

The full install → upgrade → break → rollback run, the `--set` and `-f` precedence proofs, and
the `NOTES.txt` output all live in **[Task 2](../02-rollback/README.md)**, which is a seven-revision
workout of this chart against the live cluster.
