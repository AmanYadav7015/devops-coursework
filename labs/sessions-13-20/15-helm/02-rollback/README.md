# Task 2: The Full Helm Rollback Workflow

install → verify → upgrade → verify → upgrade again → verify → rollback → verify

Every stage below shows `helm history` so the REVISION numbers tell the story, and every stage
is checked against the **actually running pods** (image tag, replica count, and the
`Server:` header nginx sends back), not just against what Helm claims.

The chart under test is my own [`charts/webapp-chart`](../charts/webapp-chart) — see
[Task 3](../03-mini-project/README.md#part-b-my-own-chart--webapp-chart) for how it is built.
Namespace `hw15`, NodePort `30150`.

Two things this task is designed to make undeniable:

1. **A rollback creates a NEW revision. It never deletes one.**
2. **`helm rollback <release> <n>` takes a revision number straight out of `helm history`** —
   and if you omit the number it does something you probably did not want.

---

## Stage 0: Pre-flight

```bash
helm lint charts/webapp-chart
```

```text
==> Linting charts/webapp-chart
[INFO] Chart.yaml: icon is recommended

1 chart(s) linted, 0 chart(s) failed
```

```bash
helm template web charts/webapp-chart -n hw15 | grep -E '^  replicas:|image: "|APP_ENVIRONMENT:'
```

```text
  APP_ENVIRONMENT: "development"
  replicas: 2
          image: "nginx:1.24-alpine"
```

Baseline established before anything touches the cluster: 2 replicas, `nginx:1.24-alpine`,
environment `development`.

---

## Stage 1: `helm install` → REVISION 1

```bash
helm install web charts/webapp-chart -n hw15
```

```text
NAME: web
LAST DEPLOYED: Wed Oct  7 18:05:35 2026
NAMESPACE: hw15
STATUS: deployed
REVISION: 1
DESCRIPTION: Install complete
TEST SUITE: None
NOTES:
Release   : web
Namespace : hw15
Revision  : 1
Chart     : webapp-chart-0.1.0
Image     : nginx:1.24-alpine
Replicas  : 2
Env       : development

This release is running with DEVELOPMENT values. Resource requests and limits are empty.

Configuration keys injected from the ConfigMap:
  - FEATURE_FLAGS
  - LOG_LEVEL
  - MAX_UPLOAD_MB

Reach the application (the node IP is not routable from macOS, so curl from the node):

  minikube ssh -- curl -s -o /dev/null -w '%{http_code}\n' http://localhost:30150
  minikube service web-webapp-chart -n hw15 --url

Inspect this release:

  helm status web -n hw15
  helm get manifest web -n hw15
  helm history web -n hw15
```

### Verify stage 1 against the cluster

```bash
kubectl get pods -n hw15 -o custom-columns='NAME:.metadata.name,IMAGE:.spec.containers[0].image,READY:.status.containerStatuses[0].ready,STATUS:.status.phase'
```

```text
NAME                               IMAGE               READY   STATUS
web-webapp-chart-b6ddc8ddd-7wg6j   nginx:1.24-alpine   true    Running
web-webapp-chart-b6ddc8ddd-c8l9w   nginx:1.24-alpine   true    Running
```

```bash
kubectl get deploy,svc -n hw15
```

```text
NAME                               READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/web-webapp-chart   2/2     2            2           6s

NAME                       TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE
service/web-webapp-chart   NodePort   10.96.152.14   <none>        80:30150/TCP   6s
```

The node IP `192.168.49.2` is not routable from macOS on this setup (docker driver), so the
NodePort is curled from inside the node:

```bash
minikube ssh -- "curl -sI http://localhost:30150 | head -2"
```

```text
HTTP/1.1 200 OK
Server: nginx/1.24.0
```

`nginx/1.24.0` is the application itself confirming which image is serving traffic. This is
the strongest possible verification — not Helm's word, not even the pod spec, but the
response of the running process.

The ConfigMap reached the container too:

```bash
POD=$(kubectl get pod -n hw15 -l app.kubernetes.io/instance=web -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n hw15 $POD -- env | grep -E 'APP_|LOG_LEVEL|FEATURE_FLAGS|MAX_UPLOAD' | sort
```

```text
APP_COLOUR=blue
APP_ENVIRONMENT=development
APP_MODE=standalone
APP_REGION=ap-south-1
FEATURE_FLAGS=search,export
LOG_LEVEL=debug
MAX_UPLOAD_MB=25
```

### History at stage 1

```bash
helm history web -n hw15
```

```text
REVISION	UPDATED                 	STATUS  	CHART             	APP VERSION	DESCRIPTION
1       	Wed Oct  7 18:05:35 2026	deployed	webapp-chart-0.1.0	1.24       	Install complete
```

One revision. `deployed`.

---

## Stage 2: `helm upgrade -f values-prod.yaml` → REVISION 2

```bash
helm upgrade web charts/webapp-chart -n hw15 -f charts/webapp-chart/values-prod.yaml
```

```text
Release "web" has been upgraded. Happy Helming!
NAME: web
LAST DEPLOYED: Wed Oct  7 18:05:54 2026
NAMESPACE: hw15
STATUS: deployed
REVISION: 2
DESCRIPTION: Upgrade complete
TEST SUITE: None
NOTES:
Release   : web
Namespace : hw15
Revision  : 2
Chart     : webapp-chart-0.1.0
Image     : nginx:1.27-alpine
Replicas  : 3
Env       : production

This release is running with PRODUCTION values. Resource requests and limits are set.
...
```

The NOTES.txt conditional flipped from the DEVELOPMENT branch to the PRODUCTION branch, which
is the first sign the override took.

### Verify stage 2 against the cluster

```bash
kubectl get pods -n hw15 -o custom-columns='NAME:.metadata.name,IMAGE:.spec.containers[0].image,READY:.status.containerStatuses[0].ready,STATUS:.status.phase'
```

```text
NAME                               IMAGE               READY   STATUS
web-webapp-chart-dcbbc77fc-bjtt7   nginx:1.27-alpine   true    Running
web-webapp-chart-dcbbc77fc-tjmwj   nginx:1.27-alpine   true    Running
web-webapp-chart-dcbbc77fc-wm94b   nginx:1.27-alpine   true    Running
```

2 pods on `1.24-alpine` became **3 pods on `1.27-alpine`**. Both the replica count and the
image tag changed, exactly as `values-prod.yaml` specifies.

```bash
kubectl get deploy web-webapp-chart -n hw15 -o jsonpath='replicas={.spec.replicas} image={.spec.template.spec.containers[0].image} resources={.spec.template.spec.containers[0].resources}{"\n"}'
```

```text
replicas=3 image=nginx:1.27-alpine resources={"limits":{"cpu":"200m","memory":"128Mi"},"requests":{"cpu":"50m","memory":"64Mi"}}
```

The `{{- if .Values.resources }}` conditional in the deployment template now renders, because
`values-prod.yaml` supplies a non-empty `resources` map where `values.yaml` has `{}`.

The `{{- range $key, $value := .Values.podLabels }}` loop also fired:

```bash
kubectl get pods -n hw15 -l app.kubernetes.io/instance=web -o jsonpath='{range .items[0]}{.metadata.name}{"\n"}{.metadata.labels}{"\n"}{end}'
```

```text
web-webapp-chart-dcbbc77fc-bjtt7
{"app.kubernetes.io/instance":"web","app.kubernetes.io/name":"webapp-chart","costcentre":"platform","pod-template-hash":"dcbbc77fc","tier":"frontend"}
```

`tier=frontend` and `costcentre=platform` came from the prod values file through the range.

ConfigMap contents changed with it:

```bash
kubectl get cm web-webapp-chart-config -n hw15 -o jsonpath='{.data}{"\n"}'
```

```text
{"APP_COLOUR":"green","APP_ENVIRONMENT":"production","FEATURE_FLAGS":"search","LOG_LEVEL":"warn","MAX_UPLOAD_MB":"100"}
```

And the app agrees:

```bash
minikube ssh -- "curl -sI http://localhost:30150 | head -2"
```

```text
HTTP/1.1 200 OK
Server: nginx/1.27.5
```

### History at stage 2

```bash
helm history web -n hw15
```

```text
REVISION	UPDATED                 	STATUS    	CHART             	APP VERSION	DESCRIPTION
1       	Wed Oct  7 18:05:35 2026	superseded	webapp-chart-0.1.0	1.24       	Install complete
2       	Wed Oct  7 18:05:54 2026	deployed  	webapp-chart-0.1.0	1.24       	Upgrade complete
```

Revision 1 is still there. Its status flipped from `deployed` to `superseded`. Helm never
throws a revision away on upgrade — this is the whole reason rollback is possible.

Note `APP VERSION` stays `1.24` in every row: that column comes from `appVersion:` in
`Chart.yaml`, which I did not change. It is not the image tag.

---

## Stage 3: a second upgrade, deliberately broken → REVISION 3

This is the realistic failure: somebody ships a tag that does not exist in the registry.

```bash
helm upgrade web charts/webapp-chart -n hw15 -f charts/webapp-chart/values-prod.yaml --set image.tag=1.99-does-not-exist
```

```text
Release "web" has been upgraded. Happy Helming!
NAME: web
LAST DEPLOYED: Wed Oct  7 18:06:29 2026
NAMESPACE: hw15
STATUS: deployed
REVISION: 3
DESCRIPTION: Upgrade complete
TEST SUITE: None
```

**Helm reports success.** Read that again:

```bash
helm list -n hw15
```

```text
NAME	NAMESPACE	REVISION	UPDATED                             	STATUS  	CHART             	APP VERSION
web 	hw15     	3       	2026-10-07 18:06:29.940535 +0530 IST	deployed	webapp-chart-0.1.0	1.24
```

`STATUS: deployed`. Helm's job without `--wait` is to apply the manifests and record a
revision. It did both successfully. Whether the resulting pods actually start is between the
Deployment controller and the kubelet, and Helm never looked. **This is why "verify" is a
separate step in the workflow and not a formality.**

### Verify stage 3 against the cluster — this is where the truth is

```bash
kubectl get pods -n hw15 -o custom-columns='NAME:.metadata.name,IMAGE:.spec.containers[0].image,READY:.status.containerStatuses[0].ready,REASON:.status.containerStatuses[0].state.waiting.reason'
```

```text
NAME                               IMAGE                       READY   REASON
web-webapp-chart-8f84769b4-n4cr2   nginx:1.99-does-not-exist   false   ImagePullBackOff
web-webapp-chart-dcbbc77fc-bjtt7   nginx:1.27-alpine           true    <none>
web-webapp-chart-dcbbc77fc-tjmwj   nginx:1.27-alpine           true    <none>
web-webapp-chart-dcbbc77fc-wm94b   nginx:1.27-alpine           true    <none>
```

```bash
kubectl get deploy web-webapp-chart -n hw15
```

```text
NAME               READY   UP-TO-DATE   AVAILABLE   AGE
web-webapp-chart   3/3     1            3           3m6s
```

`READY 3/3` but `UP-TO-DATE 1`. The rolling update started one new pod, that pod never became
ready, so the Deployment's `maxUnavailable` budget stopped it from killing any old pod. The
app is still serving on the old image — the rollout is **stuck**, not dead. If you only look
at `READY 3/3` you will declare victory on a release that never shipped.

```bash
kubectl rollout status deploy/web-webapp-chart -n hw15 --timeout=20s
```

```text
Waiting for deployment "web-webapp-chart" rollout to finish: 1 out of 3 new replicas have been updated...
error: timed out waiting for the condition
```

```bash
kubectl get events -n hw15 --sort-by=.lastTimestamp | grep -i -E 'pull|fail' | tail -5
```

```text
29s         Normal    Pulling   pod/web-webapp-chart-8f84769b4-n4cr2   Pulling image "nginx:1.99-does-not-exist"
26s         Warning   Failed    pod/web-webapp-chart-8f84769b4-n4cr2   Failed to pull image "nginx:1.99-does-not-exist": rpc error: code = NotFound desc = failed to pull and unpack image "docker.io/library/nginx:1.99-does-not-exist": failed to resolve reference "docker.io/library/nginx:1.99-does-not-exist": docker.io/library/nginx:1.99-does-not-exist: not found
26s         Warning   Failed    pod/web-webapp-chart-8f84769b4-n4cr2   Error: ErrImagePull
4s          Warning   Failed    pod/web-webapp-chart-8f84769b4-n4cr2   Error: ImagePullBackOff
4s          Normal    BackOff   pod/web-webapp-chart-8f84769b4-n4cr2   Back-off pulling image "nginx:1.99-does-not-exist"
```

Helm did record the bad input faithfully:

```bash
helm get values web -n hw15
```

```text
USER-SUPPLIED VALUES:
app:
  colour: green
  environment: production
config:
  FEATURE_FLAGS: search
  LOG_LEVEL: warn
  MAX_UPLOAD_MB: "100"
image:
  pullPolicy: IfNotPresent
  repository: nginx
  tag: 1.99-does-not-exist
podLabels:
  costcentre: platform
  tier: frontend
replicaCount: 3
resources:
  limits:
    cpu: 200m
    memory: 128Mi
  requests:
    cpu: 50m
    memory: 64Mi
service:
  nodePort: 30150
  port: 80
  type: NodePort
```

Everything from `-f values-prod.yaml` **and** the `--set` override is listed as
"user-supplied", because from Helm's point of view both are the same thing: values the
operator provided on top of the chart defaults.

### History at stage 3

```bash
helm history web -n hw15
```

```text
REVISION	UPDATED                 	STATUS    	CHART             	APP VERSION	DESCRIPTION
1       	Wed Oct  7 18:05:35 2026	superseded	webapp-chart-0.1.0	1.24       	Install complete
2       	Wed Oct  7 18:05:54 2026	superseded	webapp-chart-0.1.0	1.24       	Upgrade complete
3       	Wed Oct  7 18:06:29 2026	deployed  	webapp-chart-0.1.0	1.24       	Upgrade complete
```

Three revisions. **Revision 2 is the last known-good one.** That number is the argument to
the next command.

---

## Stage 4: `helm rollback web 2` → REVISION 4

```bash
helm rollback web 2 -n hw15
```

```text
Rollback was a success! Happy Helming!
```

```bash
kubectl rollout status deploy/web-webapp-chart -n hw15 --timeout=120s
```

```text
deployment "web-webapp-chart" successfully rolled out
```

### Verify stage 4 against the cluster

```bash
kubectl get pods -n hw15 -o custom-columns='NAME:.metadata.name,IMAGE:.spec.containers[0].image,READY:.status.containerStatuses[0].ready,STATUS:.status.phase'
```

```text
NAME                               IMAGE               READY   STATUS
web-webapp-chart-dcbbc77fc-bjtt7   nginx:1.27-alpine   true    Running
web-webapp-chart-dcbbc77fc-tjmwj   nginx:1.27-alpine   true    Running
web-webapp-chart-dcbbc77fc-wm94b   nginx:1.27-alpine   true    Running
```

```bash
kubectl get deploy web-webapp-chart -n hw15
```

```text
NAME               READY   UP-TO-DATE   AVAILABLE   AGE
web-webapp-chart   3/3     3            3           3m52s
```

`UP-TO-DATE` is 3 again — the rollout is no longer stuck. The broken pod is gone.

```bash
minikube ssh -- "curl -sI http://localhost:30150 | head -2"
```

```text
HTTP/1.1 200 OK
Server: nginx/1.27.5
```

```bash
helm get values web -n hw15 | grep -A3 "^image:"
```

```text
image:
  pullPolicy: IfNotPresent
  repository: nginx
  tag: 1.27-alpine
```

The bad tag is gone from the release's recorded values as well as from the cluster — the
rollback restored revision 2's **values** and **manifest**, not just the pods.

A look at the ReplicaSets shows how Kubernetes actually did it:

```bash
kubectl get rs -n hw15 -o custom-columns='NAME:.metadata.name,DESIRED:.spec.replicas,CURRENT:.status.replicas,IMAGE:.spec.template.spec.containers[0].image'
```

```text
NAME                         DESIRED   CURRENT   IMAGE
web-webapp-chart-8f84769b4   0         0         nginx:1.99-does-not-exist
web-webapp-chart-b6ddc8ddd   0         0         nginx:1.24-alpine
web-webapp-chart-dcbbc77fc   3         3         nginx:1.27-alpine
```

Helm rewrote the Deployment's pod template back to revision 2's content; the Deployment
controller recognised that template hash, found the existing `dcbbc77fc` ReplicaSet, scaled it
back up and scaled the broken `8f84769b4` to zero. Helm does not scale pods itself.

### History at stage 4 — the key output of this whole task

```bash
helm history web -n hw15
```

```text
REVISION	UPDATED                 	STATUS    	CHART             	APP VERSION	DESCRIPTION
1       	Wed Oct  7 18:05:35 2026	superseded	webapp-chart-0.1.0	1.24       	Install complete
2       	Wed Oct  7 18:05:54 2026	superseded	webapp-chart-0.1.0	1.24       	Upgrade complete
3       	Wed Oct  7 18:06:29 2026	superseded	webapp-chart-0.1.0	1.24       	Upgrade complete
4       	Wed Oct  7 18:09:18 2026	deployed  	webapp-chart-0.1.0	1.24       	Rollback to 2
```

**There are four rows, not three.** The rollback:

* did **not** delete revision 3;
* did **not** reactivate revision 2 (it is still `superseded`);
* created a **new revision 4** whose `DESCRIPTION` records where its content came from:
  `Rollback to 2`.

A Helm rollback is an upgrade whose input happens to be an old revision. The history is
append-only.

Storage-level proof — Helm keeps one Secret per revision in the namespace:

```bash
kubectl get secret -n hw15 -l owner=helm
```

```text
NAME                        TYPE                 DATA   AGE
sh.helm.release.v1.web.v1   helm.sh/release.v1   1      4m17s
sh.helm.release.v1.web.v2   helm.sh/release.v1   1      3m58s
sh.helm.release.v1.web.v3   helm.sh/release.v1   1      3m22s
sh.helm.release.v1.web.v4   helm.sh/release.v1   1      34s
sh.helm.release.v1.web.v5   helm.sh/release.v1   1      16s
sh.helm.release.v1.web.v6   helm.sh/release.v1   1      8s
```

Six Secrets for six revisions (v5 and v6 come from stage 5 below). Nothing was overwritten.
`helm history` is just a rendering of these objects, which is also why release history
survives you reinstalling the Helm CLI or switching laptops.

---

## Stage 5: the trap — `helm rollback` with no revision number

The revision argument is optional. From `helm rollback --help`:

```text
This command rolls back a release to a previous revision.

The first argument of the rollback command is the name of a release, and the
second is a revision (version) number. If this argument is omitted or set to
0, it will roll back to the previous release.

To see revision numbers, run 'helm history RELEASE'.

Usage:
  helm rollback <RELEASE> [REVISION] [flags]
```

"the previous release" means **revision − 1**, not "the last good one". After stage 4 we are
on revision 4, so the previous revision is 3 — the broken one.

```bash
helm rollback web -n hw15
```

```text
Rollback was a success! Happy Helming!
```

```bash
helm history web -n hw15
```

```text
REVISION	UPDATED                 	STATUS    	CHART             	APP VERSION	DESCRIPTION
1       	Wed Oct  7 18:05:35 2026	superseded	webapp-chart-0.1.0	1.24       	Install complete
2       	Wed Oct  7 18:05:54 2026	superseded	webapp-chart-0.1.0	1.24       	Upgrade complete
3       	Wed Oct  7 18:06:29 2026	superseded	webapp-chart-0.1.0	1.24       	Upgrade complete
4       	Wed Oct  7 18:09:18 2026	superseded	webapp-chart-0.1.0	1.24       	Rollback to 2
5       	Wed Oct  7 18:09:36 2026	deployed  	webapp-chart-0.1.0	1.24       	Rollback to 3
```

`Rollback to 3`. Helm cheerfully rolled **forward into the outage**:

```bash
kubectl get pods -n hw15 -o custom-columns='NAME:.metadata.name,IMAGE:.spec.containers[0].image,READY:.status.containerStatuses[0].ready,REASON:.status.containerStatuses[0].state.waiting.reason'
```

```text
NAME                               IMAGE                       READY   REASON
web-webapp-chart-8f84769b4-sf7ld   nginx:1.99-does-not-exist   false   ErrImagePull
web-webapp-chart-dcbbc77fc-bjtt7   nginx:1.27-alpine           true    <none>
web-webapp-chart-dcbbc77fc-tjmwj   nginx:1.27-alpine           true    <none>
web-webapp-chart-dcbbc77fc-wm94b   nginx:1.27-alpine           true    <none>
```

Lesson: during an incident, **always read `helm history` and pass the explicit revision
number**. Bare `helm rollback <release>` is only safe when you are certain the immediately
preceding revision is the good one, and after any previous rollback it is not.

Recovering is the same command with the number supplied — this time the last good revision is
4 (the one that reproduced revision 2):

```bash
helm rollback web 4 -n hw15
```

```text
Rollback was a success! Happy Helming!
```

```bash
kubectl rollout status deploy/web-webapp-chart -n hw15 --timeout=120s
```

```text
deployment "web-webapp-chart" successfully rolled out
```

```bash
helm history web -n hw15
```

```text
REVISION	UPDATED                 	STATUS    	CHART             	APP VERSION	DESCRIPTION
1       	Wed Oct  7 18:05:35 2026	superseded	webapp-chart-0.1.0	1.24       	Install complete
2       	Wed Oct  7 18:05:54 2026	superseded	webapp-chart-0.1.0	1.24       	Upgrade complete
3       	Wed Oct  7 18:06:29 2026	superseded	webapp-chart-0.1.0	1.24       	Upgrade complete
4       	Wed Oct  7 18:09:18 2026	superseded	webapp-chart-0.1.0	1.24       	Rollback to 2
5       	Wed Oct  7 18:09:36 2026	superseded	webapp-chart-0.1.0	1.24       	Rollback to 3
6       	Wed Oct  7 18:09:44 2026	deployed  	webapp-chart-0.1.0	1.24       	Rollback to 4
```

```bash
kubectl get pods -n hw15 -o custom-columns='NAME:.metadata.name,IMAGE:.spec.containers[0].image,READY:.status.containerStatuses[0].ready,STATUS:.status.phase'
```

```text
NAME                               IMAGE               READY   STATUS
web-webapp-chart-dcbbc77fc-bjtt7   nginx:1.27-alpine   true    Running
web-webapp-chart-dcbbc77fc-tjmwj   nginx:1.27-alpine   true    Running
web-webapp-chart-dcbbc77fc-wm94b   nginx:1.27-alpine   true    Running
```

```bash
minikube ssh -- "curl -sI http://localhost:30150 | head -2"
```

```text
HTTP/1.1 200 OK
Server: nginx/1.27.5
```

Healthy again, and the history now has six append-only rows describing every single thing
that happened.

---

## Stage 6: proving `--set` and `-f` really land in the rendered manifest

The brief asks for this explicitly, so here it is against both the renderer and a real
release.

### Rendering only — three runs of the same chart

```bash
helm template web charts/webapp-chart -n hw15 | grep -E '^  replicas:|image: "|APP_ENVIRONMENT:|LOG_LEVEL:'
```

```text
  APP_ENVIRONMENT: "development"
  LOG_LEVEL: "debug"
  replicas: 2
          image: "nginx:1.24-alpine"
```

```bash
helm template web charts/webapp-chart -n hw15 -f charts/webapp-chart/values-prod.yaml | grep -E '^  replicas:|image: "|APP_ENVIRONMENT:|LOG_LEVEL:'
```

```text
  APP_ENVIRONMENT: "production"
  LOG_LEVEL: "warn"
  replicas: 3
          image: "nginx:1.27-alpine"
```

```bash
helm template web charts/webapp-chart -n hw15 -f charts/webapp-chart/values-prod.yaml --set replicaCount=7 --set config.LOG_LEVEL=trace | grep -E '^  replicas:|image: "|APP_ENVIRONMENT:|LOG_LEVEL:'
```

```text
  APP_ENVIRONMENT: "production"
  LOG_LEVEL: "trace"
  replicas: 7
          image: "nginx:1.27-alpine"
```

Precedence, demonstrated rather than asserted:

`chart values.yaml` ◀ `-f values-prod.yaml` ◀ `--set`

* `replicas` went 2 → 3 (file beat the chart default) → 7 (`--set` beat the file).
* `LOG_LEVEL` went `debug` → `warn` → `trace` the same way, through a `range` over
  `.Values.config`, so `--set` reached a key that the template never names explicitly.
* `image` stayed `1.27-alpine` through the last run because nothing overrode it again —
  overrides are a deep merge, not a replacement of the whole values tree.

### A conditional, proved by its absence and then its presence

```bash
helm template web charts/webapp-chart -n hw15 | grep -n "^# Source"
```

```text
2:# Source: webapp-chart/templates/configmap.yaml
22:# Source: webapp-chart/templates/service.yaml
47:# Source: webapp-chart/templates/deployment.yaml
```

No Ingress, because `values.yaml` has `ingress.enabled: false` and the whole template is
wrapped in `{{- if .Values.ingress.enabled }}`.

```bash
helm template web charts/webapp-chart -n hw15 --set ingress.enabled=true --set ingress.host=webapp.hw15.local | grep -n "^# Source"
```

```text
2:# Source: webapp-chart/templates/configmap.yaml
22:# Source: webapp-chart/templates/service.yaml
47:# Source: webapp-chart/templates/deployment.yaml
103:# Source: webapp-chart/templates/ingress.yaml
```

```bash
helm template web charts/webapp-chart -n hw15 --set ingress.enabled=true --set ingress.host=webapp.hw15.local -s templates/ingress.yaml
```

```text
---
# Source: webapp-chart/templates/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web-webapp-chart
  labels:
    helm.sh/chart: webapp-chart-0.1.0
    app.kubernetes.io/name: webapp-chart
    app.kubernetes.io/instance: web
    app.kubernetes.io/version: "1.24"
    app.kubernetes.io/managed-by: Helm
    environment: development
spec:
  ingressClassName: nginx
  rules:
    - host: webapp.hw15.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: web-webapp-chart
                port:
                  number: 80
```

`-s templates/ingress.yaml` (`--show-only`) renders a single template — invaluable when a
chart produces 400 lines and you only care about one object.

### A real release, with `-f` and `--set` together → REVISION 7

```bash
helm upgrade web charts/webapp-chart -n hw15 -f charts/webapp-chart/values-prod.yaml --set replicaCount=4 --set app.colour=red
```

```text
Release "web" has been upgraded. Happy Helming!
NAME: web
LAST DEPLOYED: Wed Oct  7 18:10:16 2026
NAMESPACE: hw15
STATUS: deployed
REVISION: 7
DESCRIPTION: Upgrade complete
TEST SUITE: None
```

The override in the manifest Helm actually stored:

```bash
helm get manifest web -n hw15 | grep -E '^  replicas:|image: "|APP_COLOUR:|APP_ENVIRONMENT:'
```

```text
  APP_ENVIRONMENT: "production"
  APP_COLOUR: "red"
  replicas: 4
          image: "nginx:1.27-alpine"
```

`APP_ENVIRONMENT: production` came from `-f`, `APP_COLOUR: red` and `replicas: 4` came from
`--set`, and `image` came from `-f`. The same values in the live cluster:

```bash
kubectl get deploy web-webapp-chart -n hw15 -o jsonpath='replicas={.spec.replicas} image={.spec.template.spec.containers[0].image}{"\n"}'
kubectl get cm web-webapp-chart-config -n hw15 -o jsonpath='{.data}{"\n"}'
```

```text
replicas=4 image=nginx:1.27-alpine
{"APP_COLOUR":"red","APP_ENVIRONMENT":"production","FEATURE_FLAGS":"search","LOG_LEVEL":"warn","MAX_UPLOAD_MB":"100"}
```

### Bonus: the `checksum/config` annotation earning its keep

The deployment template carries:

```text
annotations:
  checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
```

```bash
kubectl get rs -n hw15 --no-headers -o custom-columns='NAME:.metadata.name,DESIRED:.spec.replicas,IMAGE:.spec.template.spec.containers[0].image,CHECKSUM:.spec.template.metadata.annotations.checksum/config'
```

```text
web-webapp-chart-86975fb998   4     nginx:1.27-alpine           a47edd2b45043959d1dadd3a983cb9275f5b5876b40302b4734dfe57bbe3725b
web-webapp-chart-8f84769b4    0     nginx:1.99-does-not-exist   31cd4024b04d044accae9a18e0a952d737e603a6dc665543affd0e49f94ffdcb
web-webapp-chart-b6ddc8ddd    0     nginx:1.24-alpine           55d0072440f3c846c70ef3571fb117262acf3356e50a7463ff919b238eb4fe96
web-webapp-chart-dcbbc77fc    0     nginx:1.27-alpine           31cd4024b04d044accae9a18e0a952d737e603a6dc665543affd0e49f94ffdcb
```

Notice `8f84769b4` and `dcbbc77fc` share checksum `31cd4024…` — the broken upgrade changed
only the image tag, not the ConfigMap. The newest ReplicaSet has a different checksum
`a47edd2b…` because `--set app.colour=red` changed the ConfigMap. Without this annotation,
changing only ConfigMap values would leave the pods running with the old environment until
someone restarted them by hand; the checksum forces a rolling restart whenever the rendered
ConfigMap changes.

---

## Workflow summary

| Stage | Command | Revision after | Image running | Replicas | App healthy |
|---|---|---|---|---|---|
| 1 | `helm install web charts/webapp-chart` | 1 | `nginx:1.24-alpine` | 2 | yes (`nginx/1.24.0`) |
| 2 | `helm upgrade -f values-prod.yaml` | 2 | `nginx:1.27-alpine` | 3 | yes (`nginx/1.27.5`) |
| 3 | `helm upgrade --set image.tag=1.99-does-not-exist` | 3 | 3 old + 1 `ImagePullBackOff` | 3 wanted | rollout stuck |
| 4 | `helm rollback web 2` | 4 (`Rollback to 2`) | `nginx:1.27-alpine` | 3 | yes (`nginx/1.27.5`) |
| 5a | `helm rollback web` (no number) | 5 (`Rollback to 3`) | broken again | 3 wanted | rollout stuck |
| 5b | `helm rollback web 4` | 6 (`Rollback to 4`) | `nginx:1.27-alpine` | 3 | yes (`nginx/1.27.5`) |
| 6 | `helm upgrade -f … --set replicaCount=4 --set app.colour=red` | 7 | `nginx:1.27-alpine` | 4 | yes |

Seven commands, seven revisions, zero revisions destroyed.

## Operational notes worth remembering

* **`helm upgrade --atomic --wait --timeout 2m`** would have turned stage 3 into an automatic
  rollback: Helm waits for the resources to become ready and, on timeout, rolls back for you.
  The cost is that the command blocks for the timeout. The deliberate choice here was to run
  without it so the stuck state was visible and the rollback could be done by hand.
* **`helm upgrade --install`** (often written `helm upgrade -i`) installs if the release does
  not exist and upgrades if it does. It is what belongs in a CI pipeline, since it is
  idempotent.
* **`--history-max`** (default 10) caps how many revisions Helm keeps. Once you pass it the
  oldest revisions are pruned, so "roll back to revision 2" may stop being possible on a
  release that is upgraded many times a day.
* **`helm rollback --cleanup-on-fail`** deletes resources the rollback itself created if the
  rollback fails, which prevents a half-applied rollback from leaving orphans behind.
* Rollback restores **Helm's manifest**. It cannot undo side effects that live outside that
  manifest — a database migration run by a `pre-upgrade` hook, a PVC whose data was rewritten,
  or an external system the app called. Rollback is a deployment tool, not a time machine.
