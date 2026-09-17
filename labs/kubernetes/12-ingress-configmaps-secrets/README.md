# Assignment 12 — Ingress, ConfigMaps & Secrets

> **Provenance.** The course's official homework document covers sessions 2-8 only and contains
> nothing for the Kubernetes sessions. The five tasks below were derived from the material actually
> taught in `session-12-ingress-configmaps-secrets` and are written in the same style as the official
> homework.

Every command in this file was executed against a live cluster on the machine described below, and
every `text` block is the real terminal output, copied unedited. Where a command from the course lab
guide does **not** work on this host, the failure is shown as it happened and a working alternative
is given rather than a fabricated success.

| | |
|---|---|
| Host OS | macOS (Darwin 25.5.0, arm64 / Apple Silicon) |
| Cluster | minikube v1.39.0, `--driver=docker`, container runtime `containerd://2.3.4` |
| Kubernetes | client v1.37.0 / server v1.37.0 |
| Node | `minikube`, internal IP `192.168.49.2`, Debian 12, kernel 6.12.76-linuxkit (arm64) |
| Ingress controller | `ingress-nginx` v1.15.1 via `minikube addons enable ingress` |
| Images | `busybox:1.36`, `nginx:alpine` — all arm64-native |
| Namespace | everything lives in `hw12`; the final section deletes it |

---

## Read this before you copy commands out of the lab guide

`session-12-ingress-configmaps-secrets/lab.md`, Part 6, tells you to test the Ingress like this:

```bash
INGRESS_IP=$(minikube ip)
curl -s -H "Host: yatri.local" http://${INGRESS_IP}/
```

**On macOS with the docker driver that command cannot work**, and it is not a configuration mistake
you can fix. The node is a container inside the Docker Desktop Linux VM, and `192.168.49.2` is an
address on a bridge network *inside* that VM. macOS has no route to it. The full evidence is in
[Task 3](#task-3--ingress-two-paths-one-host-two-services), and three working alternatives are
shown there. The lab guide is correct for the cloud instance the course uses (where Docker runs on
the same Linux kernel as your shell); it is simply wrong for a Mac.

---

## Table of contents

1. [Task 1 — ConfigMap: literals, files, `envFrom` and volumes](#task-1--configmap-literals-files-envfrom-and-volumes)
2. [Task 2 — Secret: `secretKeyRef`, base64, and the trailing-newline bug](#task-2--secret-secretkeyref-base64-and-the-trailing-newline-bug)
3. [Task 3 — Ingress: two paths, one host, two services](#task-3--ingress-two-paths-one-host-two-services)
4. [Task 4 — Live update: the env-var vs volume experiment](#task-4--live-update-the-env-var-vs-volume-experiment)
5. [Task 5 — Troubleshooting: a 404 and a missing Secret key](#task-5--troubleshooting-a-404-and-a-missing-secret-key)
6. [Reference tables](#reference-tables)
7. [Interview questions](#interview-questions)
8. [Cleanup](#cleanup)

Manifests referenced throughout live in [`manifests/`](manifests/).

---

## Setup

```bash
kubectl create namespace hw12
kubectl get ns hw12
```

```text
namespace/hw12 created
NAME   STATUS   AGE
hw12   Active   0s
```

(The same namespace is available declaratively as
[`manifests/00-namespace.yaml`](manifests/00-namespace.yaml).)

Every command from here on carries `-n hw12`. The cluster is shared, so nothing outside this
namespace is touched except the `ingress-nginx` addon, which is enabled once and left enabled.

---

## Task 1 — ConfigMap: literals, files, `envFrom` and volumes

### 1.1 Create one ConfigMap from literals and one from a file

```bash
kubectl create configmap yatri-app-config -n hw12 \
  --from-literal=ENVIRONMENT=production \
  --from-literal=LOG_LEVEL=INFO \
  --from-literal=APP_PORT=5000 \
  --from-literal=DEFAULT_CURRENCY=INR \
  --from-literal=MAX_BOOKING_DAYS=30

cat manifests/app.properties
kubectl create configmap yatri-file-config -n hw12 --from-file=manifests/app.properties
kubectl get configmap -n hw12
```

```text
configmap/yatri-app-config created
booking.max.days=30
booking.currency=INR
cache.ttl.seconds=300
feature.dark.mode=true
configmap/yatri-file-config created
NAME                DATA   AGE
kube-root-ca.crt    1      2m18s
yatri-app-config    5      0s
yatri-file-config   1      0s
```

`DATA` counts **keys**, not bytes. The literal ConfigMap has five keys; the file-based one has
exactly one key, because `--from-file` uses the *filename* as the key and the *entire file content*
as the value.

### 1.2 The two shapes are visibly different

```bash
kubectl describe configmap yatri-app-config  -n hw12
kubectl describe configmap yatri-file-config -n hw12
```

```text
Name:         yatri-app-config
Namespace:    hw12
Labels:       <none>
Annotations:  <none>

Data
====
APP_PORT:
----
5000

DEFAULT_CURRENCY:
----
INR

ENVIRONMENT:
----
production

LOG_LEVEL:
----
INFO

MAX_BOOKING_DAYS:
----
30


BinaryData
====

Events:  <none>
```

```text
Name:         yatri-file-config
Namespace:    hw12
Labels:       <none>
Annotations:  <none>

Data
====
app.properties:
----
booking.max.days=30
booking.currency=INR
cache.ttl.seconds=300
feature.dark.mode=true



BinaryData
====

Events:  <none>
```

The same thing in YAML makes the structural difference unmistakable:

```bash
kubectl get configmap yatri-file-config -n hw12 -o yaml
```

```text
apiVersion: v1
data:
  app.properties: |
    booking.max.days=30
    booking.currency=INR
    cache.ttl.seconds=300
    feature.dark.mode=true
kind: ConfigMap
metadata:
  creationTimestamp: "2026-09-17T17:00:36Z"
  name: yatri-file-config
  namespace: hw12
  resourceVersion: "1331"
  uid: b4db2824-560e-4340-9e7a-90c7f925cd0d
```

One key, one multi-line string. That matters for injection: a `--from-file` ConfigMap consumed as
environment variables would give you a single variable called `app.properties` whose value is a blob
containing newlines. File-shaped config belongs in a **volume**; flat key/value config can go either
way.

Reading a single key without eyeballing YAML:

```bash
kubectl get configmap yatri-app-config -n hw12 -o jsonpath='{.data.ENVIRONMENT}'; echo ""
```

```text
production
```

### 1.3 Capture the imperative command as a manifest

Imperative `create` is fine for a lab, but homework has to be reproducible, so the same command with
`--dry-run=client -o yaml` was saved as [`manifests/01-app-config.yaml`](manifests/01-app-config.yaml):

```bash
kubectl create configmap yatri-app-config -n hw12 \
  --from-literal=ENVIRONMENT=production \
  --from-literal=LOG_LEVEL=INFO \
  --from-literal=APP_PORT=5000 \
  --from-literal=DEFAULT_CURRENCY=INR \
  --from-literal=MAX_BOOKING_DAYS=30 \
  --dry-run=client -o yaml
```

```text
apiVersion: v1
data:
  APP_PORT: "5000"
  DEFAULT_CURRENCY: INR
  ENVIRONMENT: production
  LOG_LEVEL: INFO
  MAX_BOOKING_DAYS: "30"
kind: ConfigMap
metadata:
  name: yatri-app-config
  namespace: hw12
```

Note the quoting: `5000` and `30` come back as **strings**. ConfigMap values are always strings —
`data` is `map[string]string`. Writing `APP_PORT: 5000` unquoted in a hand-written manifest is a
validation error, and it is the single most common ConfigMap YAML mistake.

### 1.4 Inject the same ConfigMap two ways at once

[`manifests/03-backend.yaml`](manifests/03-backend.yaml) consumes `yatri-app-config` **twice** — as
environment variables and as a mounted volume — so the two mechanisms can be compared inside one
container. The relevant parts:

```yaml
envFrom:
  - configMapRef:
      name: yatri-app-config
volumeMounts:
  - name: app-config-volume
    mountPath: /etc/yatri-config
    readOnly: true
  - name: file-config-volume
    mountPath: /etc/yatri-file
    readOnly: true
volumes:
  - name: app-config-volume
    configMap:
      name: yatri-app-config
  - name: file-config-volume
    configMap:
      name: yatri-file-config
```

```bash
kubectl apply -f manifests/03-backend.yaml
kubectl apply -f manifests/04-frontend.yaml
kubectl rollout status deployment/yatri-backend  -n hw12
kubectl rollout status deployment/yatri-frontend -n hw12
kubectl get pods,svc -n hw12
```

```text
deployment.apps/yatri-backend created
service/yatri-backend-svc created
deployment.apps/yatri-frontend created
service/yatri-frontend-svc created
Waiting for deployment "yatri-backend" rollout to finish: 0 of 2 updated replicas are available...
Waiting for deployment "yatri-backend" rollout to finish: 1 of 2 updated replicas are available...
deployment "yatri-backend" successfully rolled out
deployment "yatri-frontend" successfully rolled out
NAME                              READY   STATUS    RESTARTS   AGE   IP            NODE
yatri-backend-9fc699cc7-9wr99     1/1     Running   0          1s    10.244.0.36   minikube
yatri-backend-9fc699cc7-glgt7     1/1     Running   0          1s    10.244.0.35   minikube
yatri-frontend-675449c7c8-lft4t   1/1     Running   0          1s    10.244.0.37   minikube
yatri-frontend-675449c7c8-vxq2h   1/1     Running   0          1s    10.244.0.38   minikube

NAME                 TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)   AGE
yatri-backend-svc    ClusterIP   10.103.99.94     <none>        80/TCP    1s
yatri-frontend-svc   ClusterIP   10.103.140.224   <none>        80/TCP    1s
```

### 1.5 Injection method A — environment variables

```bash
kubectl exec -n hw12 deployment/yatri-backend -- env \
  | grep -E "ENVIRONMENT|LOG_LEVEL|APP_PORT|DEFAULT_CURRENCY|MAX_BOOKING_DAYS|POSTGRES"
```

```text
DEFAULT_CURRENCY=INR
ENVIRONMENT=production
LOG_LEVEL=INFO
MAX_BOOKING_DAYS=30
POSTGRES_USER=yatri_admin
POSTGRES_PASSWORD=secretpassword
POSTGRES_DB=yatri_production_db
```

One `envFrom: configMapRef` line produced five environment variables. The `POSTGRES_*` values come
from the Secret and are covered in Task 2 — note that by the time they reach the process they are
**ordinary environment variables**, indistinguishable from the ConfigMap ones.

### 1.6 Injection method B — a mounted volume, and the `..data` symlink

```bash
kubectl exec -n hw12 deployment/yatri-backend -- ls -la /etc/yatri-config
```

```text
total 12
drwxrwxrwx    3 root     root          4096 Sep 17 17:01 .
drwxr-xr-x    1 root     root          4096 Sep 17 17:01 ..
drwxr-xr-x    2 root     root          4096 Sep 17 17:01 ..2026_09_17_17_01_25.1217244453
lrwxrwxrwx    1 root     root            32 Sep 17 17:01 ..data -> ..2026_09_17_17_01_25.1217244453
lrwxrwxrwx    1 root     root            15 Sep 17 17:01 APP_PORT -> ..data/APP_PORT
lrwxrwxrwx    1 root     root            23 Sep 17 17:01 DEFAULT_CURRENCY -> ..data/DEFAULT_CURRENCY
lrwxrwxrwx    1 root     root            18 Sep 17 17:01 ENVIRONMENT -> ..data/ENVIRONMENT
lrwxrwxrwx    1 root     root            16 Sep 17 17:01 LOG_LEVEL -> ..data/LOG_LEVEL
lrwxrwxrwx    1 root     root            23 Sep 17 17:01 MAX_BOOKING_DAYS -> ..data/MAX_BOOKING_DAYS
```

**This is the most important detail in Task 1.** Nothing you can `cat` here is a regular file. Every
key is a symlink to `..data/<KEY>`, and `..data` is itself a symlink to a timestamped directory that
holds the real files:

```bash
kubectl exec -n hw12 deployment/yatri-backend -- ls -la /etc/yatri-config/..data/
```

```text
total 28
drwxr-xr-x    2 root     root          4096 Sep 17 17:01 .
drwxrwxrwx    3 root     root          4096 Sep 17 17:01 ..
-rw-r--r--    1 root     root             4 Sep 17 17:01 APP_PORT
-rw-r--r--    1 root     root             3 Sep 17 17:01 DEFAULT_CURRENCY
-rw-r--r--    1 root     root            10 Sep 17 17:01 ENVIRONMENT
-rw-r--r--    1 root     root             4 Sep 17 17:01 LOG_LEVEL
-rw-r--r--    1 root     root             2 Sep 17 17:01 MAX_BOOKING_DAYS
```

**Why the indirection matters.** When the ConfigMap changes, the kubelet writes a brand-new
timestamped directory with the complete new contents and then swaps the `..data` symlink in a single
`rename(2)`. A rename is atomic on POSIX, so a reader can never observe a half-written config
directory or a mix of old and new keys — it sees either all of the old values or all of the new ones.
That is what makes live updates safe, and Task 4 shows the timestamped directory name actually
changing. The consequences for your application code:

- Do **not** hold an open file descriptor and expect it to follow the update — the old inode is
  deleted out from under you. Re-`open()` the path on each read, or watch the directory.
- `inotify` on the *file* will not fire the way you expect; watch the *directory* for the symlink
  swap, which is what config-reloader sidecars do.
- The dotted prefix (`..`) is deliberate: `ls` and shell globs such as `/etc/yatri-config/*` skip
  dot-entries, so an app that iterates the directory sees exactly its five keys and none of the
  plumbing. The command below proves it:

```bash
kubectl exec -n hw12 deployment/yatri-backend -- \
  sh -c 'for f in /etc/yatri-config/*; do echo "$f = $(cat $f)"; done'
```

```text
/etc/yatri-config/APP_PORT = 5000
/etc/yatri-config/DEFAULT_CURRENCY = INR
/etc/yatri-config/ENVIRONMENT = production
/etc/yatri-config/LOG_LEVEL = INFO
/etc/yatri-config/MAX_BOOKING_DAYS = 30
```

The `--from-file` ConfigMap mounts the same way, but produces the original file:

```bash
kubectl exec -n hw12 deployment/yatri-backend -- ls -la /etc/yatri-file
kubectl exec -n hw12 deployment/yatri-backend -- cat /etc/yatri-file/app.properties
```

```text
total 12
drwxrwxrwx    3 root     root          4096 Sep 17 17:01 .
drwxr-xr-x    1 root     root          4096 Sep 17 17:01 ..
drwxr-xr-x    2 root     root          4096 Sep 17 17:01 ..2026_09_17_17_01_25.3512884557
lrwxrwxrwx    1 root     root            32 Sep 17 17:01 ..data -> ..2026_09_17_17_01_25.3512884557
lrwxrwxrwx    1 root     root            21 Sep 17 17:01 app.properties -> ..data/app.properties
booking.max.days=30
booking.currency=INR
cache.ttl.seconds=300
feature.dark.mode=true
```

That is the `nginx.conf` / `application.properties` pattern: the pod gets a real config file at a
real path, and the image never has to contain it.

```bash
kubectl exec -n hw12 deployment/yatri-backend -- sh -c 'mount | grep yatri'
```

```text
/dev/vda1 on /etc/yatri-config type ext4 (ro,relatime,discard)
/dev/vda1 on /etc/yatri-file type ext4 (ro,relatime,discard)
```

Mounted read-only, from the node's own filesystem (the kubelet materialises the data under
`/var/lib/kubelet/pods/<uid>/volumes/`), not from the API server at read time.

---

## Task 2 — Secret: `secretKeyRef`, base64, and the trailing-newline bug

### 2.1 Create an Opaque Secret

[`manifests/02-db-secret.yaml`](manifests/02-db-secret.yaml) — demo credentials only, nothing here is
a real password:

```bash
cat manifests/02-db-secret.yaml
kubectl apply -f manifests/02-db-secret.yaml
kubectl get secret yatri-db-secret -n hw12
```

```text
apiVersion: v1
kind: Secret
metadata:
  name: yatri-db-secret
  namespace: hw12
  labels:
    app: yatri-backend
type: Opaque
data:
  POSTGRES_USER: eWF0cmlfYWRtaW4=
  POSTGRES_PASSWORD: c2VjcmV0cGFzc3dvcmQ=
  POSTGRES_DB: eWF0cmlfcHJvZHVjdGlvbl9kYg==
secret/yatri-db-secret created
NAME              TYPE     DATA   AGE
yatri-db-secret   Opaque   3      0s
```

`Opaque` simply means "arbitrary user-defined key/value data". The other built-in types
(`kubernetes.io/tls`, `kubernetes.io/dockerconfigjson`, `kubernetes.io/service-account-token`)
enforce required key names; `Opaque` enforces nothing.

### 2.2 `describe` masks the values — and that is the entire protection it offers

```bash
kubectl describe secret yatri-db-secret -n hw12
```

```text
Name:         yatri-db-secret
Namespace:    hw12
Labels:       app=yatri-backend
Annotations:  <none>

Type:  Opaque

Data
====
POSTGRES_DB:        19 bytes
POSTGRES_PASSWORD:  14 bytes
POSTGRES_USER:      11 bytes
```

Only lengths. Nobody reading over your shoulder learns the password from `describe`. Now watch that
protection evaporate.

### 2.3 Base64 is encoding, not encryption

```bash
kubectl get secret yatri-db-secret -n hw12 -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 --decode; echo ""
```

```text
secretpassword
```

Every key at once, no jsonpath gymnastics:

```bash
kubectl get secret yatri-db-secret -n hw12 \
  -o go-template='{{range $k,$v := .data}}{{$k}}={{$v | base64decode}}{{"\n"}}{{end}}'
```

```text
POSTGRES_DB=yatri_production_db
POSTGRES_PASSWORD=secretpassword
POSTGRES_USER=yatri_admin
```

No key, no password, no decryption step. Base64 exists so that arbitrary binary (a TLS private key,
a keystore) can survive a JSON round-trip — it is a transport encoding, and it is reversible by
anyone, always.

### 2.4 So what actually protects a Secret? RBAC.

The real access control is the API server's authorisation layer. Proof, with a ServiceAccount bound
to a Role that grants ConfigMaps but not Secrets ([`manifests/10-secret-rbac.yaml`](manifests/10-secret-rbac.yaml)):

```bash
kubectl apply -f manifests/10-secret-rbac.yaml
kubectl auth can-i get secret/yatri-db-secret -n hw12
kubectl auth can-i get configmaps -n hw12 --as=system:serviceaccount:hw12:yatri-app-sa
kubectl auth can-i get secrets    -n hw12 --as=system:serviceaccount:hw12:yatri-app-sa
kubectl auth can-i list secrets   -n hw12 --as=system:serviceaccount:hw12:yatri-app-sa
kubectl get secret yatri-db-secret -n hw12 --as=system:serviceaccount:hw12:yatri-app-sa
```

```text
serviceaccount/yatri-app-sa created
role.rbac.authorization.k8s.io/yatri-config-reader created
rolebinding.rbac.authorization.k8s.io/yatri-config-reader-binding created
yes
yes
no
no
Error from server (Forbidden): secrets "yatri-db-secret" is forbidden: User "system:serviceaccount:hw12:yatri-app-sa" cannot get resource "secrets" in API group "" in the namespace "hw12"
```

```bash
kubectl auth can-i --list -n hw12 --as=system:serviceaccount:hw12:yatri-app-sa | head -8
```

```text
Resources                                       Non-Resource URLs                      Resource Names   Verbs
selfsubjectreviews.authentication.k8s.io        []                                     []               [create]
selfsubjectaccessreviews.authorization.k8s.io   []                                     []               [create]
selfsubjectrulesreviews.authorization.k8s.io    []                                     []               [create]
configmaps                                      []                                     []               [get list watch]
clustertrustbundles.certificates.k8s.io         []                                     []               [get list watch]
                                                [/.well-known/openid-configuration/]   []               [get]
                                                [/.well-known/openid-configuration]    []               [get]
```

My own kubeconfig user is cluster-admin, so it decoded the password in 2.3 in one command. The
restricted identity is refused at the API server before base64 is ever relevant. The correct mental
model is: **a Secret is a ConfigMap that RBAC, audit policy, and etcd encryption treat differently.**
It is not a ConfigMap with cryptography bolted on.

The three additional controls that make Secrets meaningfully safer in production:

1. **Encryption at rest for etcd.** By default a Secret is written to etcd base64-encoded and
   otherwise in the clear, so anyone with an etcd snapshot or a disk image has every password in the
   cluster. Configuring `--encryption-provider-config` on the API server with an `aescbc` or
   `kms` provider encrypts `secrets` before they are persisted. A KMS provider (AWS KMS, GCP KMS,
   Vault) is the production answer, because it keeps the data-encryption key off the disk entirely.
   This is a CIS Kubernetes Benchmark requirement and it is **off by default** in minikube, kubeadm
   and most managed clusters unless you opt in.
2. **Do not commit the YAML.** A `data:` block in git is a leaked password, base64 or not. Use
   Sealed Secrets, SOPS, or an external store (Vault, AWS Secrets Manager) with the External Secrets
   Operator.
3. **Prefer files to environment variables.** Environment variables leak into crash dumps, `/proc/1/environ`,
   child processes and logging frameworks that dump the environment on startup. A mounted Secret has
   a smaller blast radius, and it is the only option that can be rotated without a restart.

### 2.5 Injecting with `secretKeyRef`

```yaml
env:
  - name: POSTGRES_USER
    valueFrom:
      secretKeyRef:
        name: yatri-db-secret
        key: POSTGRES_USER
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: yatri-db-secret
        key: POSTGRES_PASSWORD
```

`secretKeyRef` picks **one key at a time** and lets you rename it on the way in — useful when the
Secret is shared and each app expects a different variable name. `envFrom: secretRef` would inject
every key using its own name, which is convenient and also how you accidentally import a key you did
not want. The result inside the container was already shown in 1.5:
`POSTGRES_PASSWORD=secretpassword`.

### 2.6 The `echo` vs `echo -n` trailing-newline bug

The classic silent failure. `echo` appends `\n`; `base64` faithfully encodes that byte:

```bash
echo    "mypassword" | base64
echo -n "mypassword" | base64
```

```text
bXlwYXNzd29yZAo=
bXlwYXNzd29yZA==
```

There is the `Ao=` the lab guide warns about. The `o=` is the tail of the encoded `\n`.

**A correction to the course material.** `lab.md` says the correct encoding "ends cleanly in `=`
(no `Ao=`)". That is only true for inputs of certain lengths. The suffix depends on the input length
modulo 3, because base64 packs 3 bytes into 4 characters and pads the remainder:

```bash
for s in mypassword secretpassword yatri_admin; do
  n=$(printf '%s' "$s" | wc -c | tr -d ' ')
  m=$(( (n + 1) % 3 ))
  printf '%-16s len=%2s  len+1 mod 3=%s  with newline: %-24s without: %s\n' \
    "$s" "$n" "$m" "$(printf '%s\n' "$s" | base64)" "$(printf '%s' "$s" | base64)"
done
```

```text
mypassword       len=10  len+1 mod 3=2  with newline: bXlwYXNzd29yZAo=         without: bXlwYXNzd29yZA==
secretpassword   len=14  len+1 mod 3=0  with newline: c2VjcmV0cGFzc3dvcmQK     without: c2VjcmV0cGFzc3dvcmQ=
yatri_admin      len=11  len+1 mod 3=0  with newline: eWF0cmlfYWRtaW4K         without: eWF0cmlfYWRtaW4=
```

For `secretpassword` the buggy encoding ends in `QK` with **no padding at all**, and the correct one
ends in a single `=`. Pattern-matching on `Ao=` will therefore miss the bug most of the time. Do not
eyeball the suffix — count the bytes:

```bash
echo    "secretpassword" | wc -c
echo -n "secretpassword" | wc -c
echo    "secretpassword" | xxd | tail -1
echo -n "secretpassword" | xxd | tail -1
```

```text
      15
      14
00000000: 7365 6372 6574 7061 7373 776f 7264 0a    secretpassword.
00000000: 7365 6372 6574 7061 7373 776f 7264       secretpassword
```

`0a` is the newline. That is the whole bug.

### 2.7 Reproduce the bug end to end, inside a real pod

Byte counts alone are theory. [`manifests/09-newline-bug.yaml`](manifests/09-newline-bug.yaml)
creates a deliberately wrong Secret (`c2VjcmV0cGFzc3dvcmQK`, encoded with plain `echo`) alongside the
correct one and injects both into one busybox pod:

```bash
kubectl apply -f manifests/09-newline-bug.yaml
kubectl wait --for=condition=Ready pod/newline-bug-demo -n hw12 --timeout=120s
kubectl get secret yatri-db-secret yatri-db-secret-bad -n hw12 \
  -o go-template='{{range .items}}{{.metadata.name}}: {{range $k,$v := .data}}{{$k}}={{len ($v | base64decode)}} bytes {{end}}{{"\n"}}{{end}}'
```

```text
secret/yatri-db-secret-bad created
pod/newline-bug-demo created
pod/newline-bug-demo condition met
yatri-db-secret: POSTGRES_DB=19 bytes POSTGRES_PASSWORD=14 bytes POSTGRES_USER=11 bytes 
yatri-db-secret-bad: POSTGRES_PASSWORD=15 bytes 
```

14 bytes versus 15. `kubectl describe secret` would have shown you that too — the byte count in
`describe` output is the cheapest possible check for this bug.

What the application actually receives:

```bash
kubectl exec -n hw12 newline-bug-demo -- sh -c 'printf "%s" "$GOOD_PASSWORD" | wc -c; printf "%s" "$BAD_PASSWORD" | wc -c'
kubectl exec -n hw12 newline-bug-demo -- sh -c 'printf "%s" "$GOOD_PASSWORD" | od -c | head -2'
kubectl exec -n hw12 newline-bug-demo -- sh -c 'printf "%s" "$BAD_PASSWORD"  | od -c | head -2'
```

```text
14
15
0000000   s   e   c   r   e   t   p   a   s   s   w   o   r   d
0000016
0000000   s   e   c   r   e   t   p   a   s   s   w   o   r   d  \n
0000017
```

And the comparison a database performs on login:

```bash
kubectl exec -n hw12 newline-bug-demo -- sh -c \
 'if [ "$GOOD_PASSWORD" = "secretpassword" ]; then echo "GOOD_PASSWORD matches"; else echo "GOOD_PASSWORD does NOT match"; fi;
  if [ "$BAD_PASSWORD"  = "secretpassword" ]; then echo "BAD_PASSWORD matches";  else echo "BAD_PASSWORD does NOT match";  fi'
```

```text
GOOD_PASSWORD matches
BAD_PASSWORD does NOT match
```

This is why the bug is so expensive to debug: the Secret exists, the pod starts, the environment
variable is populated, `echo $PASSWORD` prints something that *looks* correct in a terminal — and
PostgreSQL returns `FATAL: password authentication failed`. The one invisible byte is only ever
visible through `od`, `xxd`, `wc -c`, or the byte count in `kubectl describe secret`.

Two ways to never have the problem:

```bash
kubectl create secret generic yatri-db-secret -n hw12 \
  --from-literal=POSTGRES_PASSWORD=secretpassword
```

`--from-literal` never adds a newline. Or use `stringData:` in the manifest, which takes plain text
and lets the API server do the encoding:

```yaml
stringData:
  POSTGRES_PASSWORD: secretpassword
```

---

## Task 3 — Ingress: two paths, one host, two services

### 3.1 Enable the controller

```bash
minikube addons enable ingress
kubectl get pods -n ingress-nginx
kubectl get svc  -n ingress-nginx
kubectl get ingressclass
```

```text
* ingress is an addon maintained by Kubernetes. For any concerns contact minikube on GitHub.
You can view the list of minikube maintainers at: https://github.com/kubernetes/minikube/blob/master/OWNERS
* After the addon is enabled, please run "minikube tunnel" and your ingress resources would be available at "127.0.0.1"
  - Using image registry.k8s.io/ingress-nginx/controller:v1.15.1
  - Using image registry.k8s.io/ingress-nginx/kube-webhook-certgen:v1.6.9
  - Using image registry.k8s.io/ingress-nginx/kube-webhook-certgen:v1.6.9
* Verifying ingress addon...
* The 'ingress' addon is enabled

NAME                                       READY   STATUS      RESTARTS        AGE
ingress-nginx-admission-create-9ztp5       0/1     Completed   0               3m51s
ingress-nginx-admission-patch-sbxrg        0/1     Completed   2 (3m17s ago)   3m51s
ingress-nginx-controller-d7cd8c989-m4p54   1/1     Running     0               3m51s

NAME                                 TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)                      AGE
ingress-nginx-controller             NodePort    10.108.216.35   <none>        80:30762/TCP,443:31135/TCP   3m52s
ingress-nginx-controller-admission   ClusterIP   10.100.11.204   <none>        443/TCP                      3m52s

NAME              CONTROLLER             PARAMETERS   AGE
nginx (default)   k8s.io/ingress-nginx   <none>       3m52s
```

The controller pod is `1/1 Running`. Three things to notice:

- The two `Completed` jobs are the admission-webhook certificate generator, not failures. The `patch`
  job restarted twice before succeeding — normal while the API server settles.
- An **IngressClass** named `nginx` now exists and is marked `(default)`. `spec.ingressClassName:
  nginx` in the Ingress is what binds a rule to this controller; without a class, a cluster running
  two controllers has no way to know which one owns the rule.
- minikube itself prints the macOS caveat: *"please run `minikube tunnel` and your ingress resources
  would be available at 127.0.0.1"*. That message is the addon telling you `minikube ip` will not be
  reachable here.

### 3.2 The routing rules

[`manifests/05-ingress.yaml`](manifests/05-ingress.yaml) — one host, two paths, two Services:

```yaml
spec:
  ingressClassName: nginx
  rules:
    - host: yatri.local
      http:
        paths:
          - path: /api(/|$)(.*)
            pathType: ImplementationSpecific
            backend:
              service:
                name: yatri-backend-svc
                port:
                  number: 80
          - path: /
            pathType: Prefix
            backend:
              service:
                name: yatri-frontend-svc
                port:
                  number: 80
```

The regex `/api(/|$)(.*)` with `rewrite-target: /$2` captures everything after `/api` into group 2
and forwards only that to the backend, so the backend never has to know it is mounted under `/api`.
`pathType` must be `ImplementationSpecific` for a regex — `Prefix` compares path *segments* literally
and would treat `(` and `)` as characters to match.

```bash
kubectl apply -f manifests/05-ingress.yaml
kubectl get ingress -n hw12
kubectl describe ingress yatri-ingress -n hw12
```

```text
ingress.networking.k8s.io/yatri-ingress created
NAME            CLASS   HOSTS         ADDRESS   PORTS   AGE
yatri-ingress   nginx   yatri.local             80      8s

Name:             yatri-ingress
Labels:           app=yatri-app
Namespace:        hw12
Address:          
Ingress Class:    nginx
Default backend:  <default>
Rules:
  Host         Path  Backends
  ----         ----  --------
  yatri.local  
               /api(/|$)(.*)   yatri-backend-svc:80 (10.244.0.35:5000,10.244.0.36:5000)
               /               yatri-frontend-svc:80 (10.244.0.38:80,10.244.0.37:80)
Annotations:   nginx.ingress.kubernetes.io/rewrite-target: /$2
               nginx.ingress.kubernetes.io/ssl-redirect: false
               nginx.ingress.kubernetes.io/use-regex: true
Events:
  Type    Reason  Age   From                      Message
  ----    ------  ----  ----                      -------
  Normal  Sync    8s    nginx-ingress-controller  Scheduled for sync
```

`ADDRESS` is empty immediately after apply — the controller fills in `status.loadBalancer` on its
next sync. Note that `describe` resolves each backend to **live endpoint IPs**. That single line is
the fastest Ingress diagnostic there is: if it shows endpoints, the Service and its pods are fine and
any failure is in routing; if it shows an error or an empty list, the problem is below the Ingress.
A minute later:

```bash
kubectl get ingress -n hw12
```

```text
NAME            CLASS   HOSTS         ADDRESS        PORTS   AGE
yatri-ingress   nginx   yatri.local   192.168.49.2   80      68s
```

### 3.3 The documented test, run honestly on macOS

This is the command from `lab.md` Part 6, run exactly as written:

```bash
echo "minikube ip = $(minikube ip)"
ping -c 3 -W 2000 192.168.49.2
curl -s -m 10 -o /dev/null -w 'http_code=%{http_code}\n' -H "Host: yatri.local" http://192.168.49.2/
```

```text
minikube ip = 192.168.49.2
PING 192.168.49.2 (192.168.49.2): 56 data bytes
Request timeout for icmp_seq 0
Request timeout for icmp_seq 1

--- 192.168.49.2 ping statistics ---
3 packets transmitted, 0 packets received, 100.0% packet loss
ping exit code: 2
http_code=000
curl exit code: 28
```

```bash
curl -v -m 10 -H "Host: yatri.local" http://192.168.49.2/
```

```text
*   Trying 192.168.49.2:80...
* Connection timed out after 10005 milliseconds
* Closing connection
curl: (28) Connection timed out after 10005 milliseconds
```

`http_code=000` with exit 28 is a connect timeout: the TCP handshake never completed. The NodePort
form fails identically:

```bash
curl -s -m 10 -o /dev/null -w 'http_code=%{http_code}\n' -H "Host: yatri.local" http://192.168.49.2:30762/
```

```text
http_code=000
curl exit code: 28
```

**Why.** The node is a Docker container, and with Docker Desktop that container runs inside a Linux
VM. `192.168.49.2` belongs to a bridge network inside that VM. Only the ports Docker explicitly
publishes cross the VM boundary to macOS:

```bash
docker ps --filter name=minikube --format '{{.Names}}  {{.Status}}  {{.Ports}}'
netstat -rn -f inet | grep -E '192.168.49|Destination'
```

```text
minikube  Up 8 minutes  127.0.0.1:62156->22/tcp, 127.0.0.1:62153->2376/tcp, 127.0.0.1:62157->5000/tcp, 127.0.0.1:62155->8443/tcp, 127.0.0.1:62154->32443/tcp
Destination        Gateway            Flags               Netif Expire
```

Published ports: SSH (22), the Docker daemon (2376), the registry (5000), the API server (8443) and
32443. **Port 80 is not among them, and neither is NodePort 30762.** The routing table has no entry
for `192.168.49.0/24` at all, which is why even `ping` fails. On a Linux host — the cloud instance
the course uses — Docker's bridge is on the same kernel as your shell, the route exists, and
`lab.md`'s command works. It is the extra VM hop on macOS (and on Docker Desktop for Windows) that
breaks it, and no amount of `minikube` configuration changes that while the docker driver is in use.

### 3.4 Method 1 — `minikube ssh` (the most faithful test)

Run the exact same curl from inside the node, where `192.168.49.2` is a local address:

```bash
minikube ssh -- 'curl -s -H "Host: yatri.local" http://192.168.49.2/ | grep -i "<title>"'
minikube ssh -- 'curl -s -H "Host: yatri.local" http://192.168.49.2/api/'
minikube ssh -- 'curl -s -o /dev/null -w "/     -> %{http_code}\n" -H "Host: yatri.local" http://192.168.49.2/ ;
                 curl -s -o /dev/null -w "/api/ -> %{http_code}\n" -H "Host: yatri.local" http://192.168.49.2/api/'
```

```text
<title>Welcome to nginx!</title>
Yatri Backend API
=================
ENVIRONMENT      : production
LOG_LEVEL        : INFO
DEFAULT_CURRENCY : INR
POSTGRES_USER    : yatri_admin
POSTGRES_DB      : yatri_production_db
POD              : yatri-backend-9fc699cc7-glgt7
/     -> 200
/api/ -> 200
```

**Both paths verified.** `/` reached the nginx frontend, `/api/` reached the busybox backend, through
one host, one IP and one controller pod. This is the preferred method because nothing about the
request is changed — same IP, same port 80, same `Host` header as the lab guide specifies. Only the
shell it runs in is different.

### 3.5 Method 2 — `kubectl port-forward` (test from the Mac itself)

```bash
kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 30120:80 &
curl -s -m 10 -H "Host: yatri.local" http://localhost:30120/ | grep -i "<title>"
curl -s -m 10 -H "Host: yatri.local" http://localhost:30120/api/
curl -s -m 10 -D - -o /dev/null -H "Host: yatri.local" http://localhost:30120/api/
```

```text
Forwarding from 127.0.0.1:30120 -> 80
Forwarding from [::1]:30120 -> 80
<title>Welcome to nginx!</title>
Yatri Backend API
=================
ENVIRONMENT      : production
LOG_LEVEL        : INFO
DEFAULT_CURRENCY : INR
POSTGRES_USER    : yatri_admin
POSTGRES_DB      : yatri_production_db
POD              : yatri-backend-9fc699cc7-glgt7
HTTP/1.1 200 OK
Date: Thu, 17 Sep 2026 17:03:33 GMT
Content-Type: text/html
Content-Length: 232
Connection: keep-alive
Accept-Ranges: bytes
Last-Modified: Thu, 17 Sep 2026 17:01:25 GMT
ETag: "6aac1ce5-e8"
```

`port-forward` tunnels over the API server connection, which macOS *can* reach (`127.0.0.1:8443` is
published). This is the method to use for a browser: forward the port, add `127.0.0.1 yatri.local` to
`/etc/hosts`, and `http://yatri.local:30120/` works. The `Host` header still has to say `yatri.local`
— that is what the Ingress rule matches on, and `curl -H` is doing by hand what `/etc/hosts` plus a
browser would do for you.

### 3.6 Method 3 — from a pod inside the cluster

```bash
kubectl exec -n hw12 newline-bug-demo -- wget -qO- --header 'Host: yatri.local' \
  http://ingress-nginx-controller.ingress-nginx.svc.cluster.local/       | grep -i '<title>'
kubectl exec -n hw12 newline-bug-demo -- wget -qO- --header 'Host: yatri.local' \
  http://ingress-nginx-controller.ingress-nginx.svc.cluster.local/api/
kubectl exec -n hw12 newline-bug-demo -- wget -qO- --header 'Host: yatri.local' \
  http://ingress-nginx-controller.ingress-nginx.svc.cluster.local/api
```

```text
<title>Welcome to nginx!</title>
Yatri Backend API
=================
ENVIRONMENT      : production
LOG_LEVEL        : INFO
DEFAULT_CURRENCY : INR
POSTGRES_USER    : yatri_admin
POSTGRES_DB      : yatri_production_db
POD              : yatri-backend-9fc699cc7-9wr99
Yatri Backend API
=================
ENVIRONMENT      : production
LOG_LEVEL        : INFO
DEFAULT_CURRENCY : INR
POSTGRES_USER    : yatri_admin
POSTGRES_DB      : yatri_production_db
POD              : yatri-backend-9fc699cc7-glgt7
```

`/api` with no trailing slash matches too, because the regex is `/api(/|$)(.*)` — the `$` alternative
exists precisely for that case. Dropping it is a common bug that makes `/api` 404 while `/api/`
works.

The controller load-balances across both backend pods:

```bash
for i in 1 2 3 4 5 6; do
  kubectl exec -n hw12 newline-bug-demo -- wget -qO- --header 'Host: yatri.local' \
    http://ingress-nginx-controller.ingress-nginx.svc.cluster.local/api/ | grep POD
done
```

```text
POD              : yatri-backend-9fc699cc7-glgt7
POD              : yatri-backend-9fc699cc7-9wr99
POD              : yatri-backend-9fc699cc7-9wr99
POD              : yatri-backend-9fc699cc7-9wr99
POD              : yatri-backend-9fc699cc7-glgt7
POD              : yatri-backend-9fc699cc7-glgt7
```

Worth knowing: ingress-nginx balances across **pod endpoints directly**, not through the Service's
ClusterIP. `kubectl describe ingress` showing `10.244.0.35:5000,10.244.0.36:5000` is literally the
upstream list nginx was given. That is why an Ingress can do sticky sessions and per-pod canary
weighting, which kube-proxy's Service load balancing cannot.

### 3.7 Confirmed in the controller's own access log

```bash
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller --tail=5
```

```text
192.168.49.2 - - [17/Sep/2026:17:03:16 +0000] "GET / HTTP/1.1" 200 896 "-" "curl/7.88.1" 75 0.001 [hw12-yatri-frontend-svc-80] [] 10.244.0.38:80 896 0.000 200 d5908c1ba04fe427f091e7ea69868ac3
192.168.49.2 - - [17/Sep/2026:17:03:17 +0000] "GET /api/ HTTP/1.1" 200 232 "-" "curl/7.88.1" 79 0.000 [hw12-yatri-backend-svc-80] [] 10.244.0.35:5000 232 0.000 200 44323f0e98b15b7e10b7b0fd0b9f15e4
127.0.0.1 - - [17/Sep/2026:17:03:33 +0000] "GET / HTTP/1.1" 200 896 "-" "curl/8.7.1" 74 0.001 [hw12-yatri-frontend-svc-80] [] 10.244.0.37:80 896 0.001 200 09eca9d93e5c6a43dd64a41fe1d15e18
10.244.0.40 - - [17/Sep/2026:17:03:50 +0000] "GET / HTTP/1.1" 200 896 "-" "Wget" 74 0.001 [hw12-yatri-frontend-svc-80] [] 10.244.0.37:80 896 0.001 200 29b085dc9b8a824d12902f3ac55f4cc6
10.244.0.40 - - [17/Sep/2026:17:03:50 +0000] "GET /api/ HTTP/1.1" 200 232 "-" "Wget" 78 0.000 [hw12-yatri-backend-svc-80] [] 10.244.0.36:5000 232 0.000 200 3f67f270cb0fcd2ce41f28271e6037be
```

All three methods in one log, distinguishable by source IP: `192.168.49.2` is `minikube ssh`,
`127.0.0.1` is `port-forward`, `10.244.0.40` is the in-cluster pod. The bracketed field
`[hw12-yatri-frontend-svc-80]` is the **upstream name** — namespace, service, port — and it is the
field that makes Task 5 easy to diagnose.

---

## Task 4 — Live update: the env-var vs volume experiment

This is the central experiment of the assignment. The same ConfigMap key, `ENVIRONMENT`, is consumed
by one container in two ways: as an environment variable through `envFrom`, and as a file through a
volume mount. Change the key once and watch the two paths behave completely differently.

Timing matters here, so the whole sequence was run as a single driver script rather than as separate
commands — otherwise the elapsed time would include however long it took to type the next command.
The `###` lines inside the output blocks below are that script's own progress labels, not command
output.

### 4.1 Baseline

```bash
POD=$(kubectl get pod -n hw12 -l app=yatri-backend -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n hw12 $POD -- printenv ENVIRONMENT
kubectl exec -n hw12 $POD -- cat /etc/yatri-config/ENVIRONMENT
kubectl exec -n hw12 $POD -- readlink /etc/yatri-config/..data
```

```text
target pod: yatri-backend-9fc699cc7-9wr99
### t=0 baseline (before the patch)
env var       : production
mounted file  : production
..data target : ..2026_09_17_17_01_25.1217244453
```

### 4.2 Patch the ConfigMap

```bash
kubectl patch configmap yatri-app-config -n hw12 --type merge -p '{"data":{"ENVIRONMENT":"staging"}}'
kubectl get cm yatri-app-config -n hw12 -o jsonpath='{.data.ENVIRONMENT}'
```

```text
### patching the ConfigMap
patch issued at 22:34:15
configmap/yatri-app-config patched
stored value now: staging
```

The stored object changed instantly. No pod was restarted, no rollout was triggered — a ConfigMap
update is not a workload event.

### 4.3 Immediately afterwards: neither consumer has moved

```text
### immediately after the patch (same running pod, no restart)
env var       : production
mounted file  : production
```

### 4.4 Poll the mounted file until the kubelet syncs it

```bash
while true; do
  EL=$(( $(date +%s) - START ))
  VAL=$(kubectl exec -n hw12 $POD -- cat /etc/yatri-config/ENVIRONMENT)
  ENV=$(kubectl exec -n hw12 $POD -- printenv ENVIRONMENT)
  printf 't+%-4ss  mounted file = %-12s  env var = %s\n' "$EL" "$VAL" "$ENV"
  [ "$VAL" = "staging" ] && break
  sleep 5
done
```

```text
### polling the mounted file every 5s until the kubelet syncs it
t+0   s  mounted file = production    env var = production
t+5   s  mounted file = production    env var = production
t+10  s  mounted file = production    env var = production
t+15  s  mounted file = production    env var = production
t+20  s  mounted file = production    env var = production
t+25  s  mounted file = production    env var = production
t+31  s  mounted file = production    env var = production
t+36  s  mounted file = production    env var = production
t+41  s  mounted file = production    env var = production
t+46  s  mounted file = production    env var = production
t+51  s  mounted file = production    env var = production
t+56  s  mounted file = production    env var = production
t+62  s  mounted file = production    env var = production
t+67  s  mounted file = production    env var = production
t+72  s  mounted file = production    env var = production
t+77  s  mounted file = staging       env var = production

mounted volume updated after 77s with ZERO restarts
```

**Measured: 77 seconds.** No restart, no rollout, no API call from the application. The kubelet
noticed on its own and swapped the files under the running process. The delay is the sum of the
kubelet's `--sync-frequency` (1 minute by default) and its ConfigMap/Secret cache TTL, so anything
from a few seconds up to about 2 minutes is normal. **Kubernetes gives you no guarantee about the
latency of this update** — do not design a system that needs the new value within a bounded time.

And the `..data` symlink proves the atomic swap described in Task 1.6:

```bash
kubectl exec -n hw12 $POD -- readlink /etc/yatri-config/..data
kubectl exec -n hw12 $POD -- printenv ENVIRONMENT
kubectl get pod -n hw12 $POD -o jsonpath='{.status.containerStatuses[0].restartCount}'
kubectl get pod -n hw12 $POD
```

```text
### after the volume updated
..data target : ..2026_09_17_17_05_31.3749712049
env var       : production
restarts      : 0
pod age/status:
NAME                            READY   STATUS    RESTARTS   AGE
yatri-backend-9fc699cc7-9wr99   1/1     Running   0          4m8s
```

The target moved from `..2026_09_17_17_01_25.1217244453` to `..2026_09_17_17_05_31.3749712049` — a
new directory was written and the symlink re-pointed. `RESTARTS 0`, `AGE 4m8s`: this is the original
container, still running, now reading different configuration.

**Meanwhile the environment variable is still `production`.** It was resolved once, by the kubelet,
when the container was created, and handed to `execve()`. There is no mechanism on Linux for anything
outside a process to change that process's environment afterwards. This is not a Kubernetes
limitation; it is how Unix works.

### 4.5 Only a restart moves the environment variable

```bash
kubectl exec -n hw12 deployment/yatri-backend -- printenv ENVIRONMENT
kubectl rollout restart deployment/yatri-backend -n hw12
kubectl rollout status  deployment/yatri-backend -n hw12
kubectl get pods -n hw12 -l app=yatri-backend
kubectl exec -n hw12 deployment/yatri-backend -- printenv ENVIRONMENT
kubectl exec -n hw12 deployment/yatri-backend -- cat /etc/yatri-config/ENVIRONMENT
```

```text
### env var is still stale on the running pods
production
### rollout restart
restart issued at 22:36:07
deployment.apps/yatri-backend restarted
Waiting for deployment "yatri-backend" rollout to finish: 1 out of 2 new replicas have been updated...
Waiting for deployment "yatri-backend" rollout to finish: 1 out of 2 new replicas have been updated...
Waiting for deployment "yatri-backend" rollout to finish: 1 out of 2 new replicas have been updated...
Waiting for deployment "yatri-backend" rollout to finish: 1 old replicas are pending termination...
Waiting for deployment "yatri-backend" rollout to finish: 1 old replicas are pending termination...
deployment "yatri-backend" successfully rolled out
rollout complete at 22:36:08
### new pods
NAME                             READY   STATUS        RESTARTS   AGE
yatri-backend-85b949bcd4-9pdjl   1/1     Running       0          0s
yatri-backend-85b949bcd4-tt467   1/1     Running       0          1s
yatri-backend-9fc699cc7-9wr99    1/1     Terminating   0          4m44s
yatri-backend-9fc699cc7-glgt7    1/1     Terminating   0          4m44s
### env var after the restart
staging
### mounted file after the restart
staging
```

New ReplicaSet (`85b949bcd4` replaces `9fc699cc7`), new pods, new `execve()`, new environment. And
because the backend renders its page at container start, the value is now visible through the
Ingress as well:

```bash
minikube ssh -- 'curl -s -H "Host: yatri.local" http://192.168.49.2/api/'
```

```text
Yatri Backend API
=================
ENVIRONMENT      : staging
LOG_LEVEL        : INFO
DEFAULT_CURRENCY : INR
POSTGRES_USER    : yatri_admin
POSTGRES_DB      : yatri_production_db
POD              : yatri-backend-85b949bcd4-tt467
```

`kubectl rollout restart` works by stamping
`spec.template.metadata.annotations.kubectl.kubernetes.io/restartedAt` with the current time. That
changes the pod template hash, so the Deployment controller does an ordinary rolling update — the
same graceful, one-pod-at-a-time replacement as any other change. It is not a `kill -9`.

### 4.6 What this means in practice

| | `envFrom` / `env` | volume mount |
|---|---|---|
| Value at container start | resolved by kubelet, passed to `execve()` | files written to the pod directory |
| ConfigMap changes | **never** reaches the running process | file contents replaced, here after **77 s** |
| Restart needed | yes — `rollout restart` or delete the pod | no |
| Update is atomic | n/a | yes, `..data` symlink swapped with `rename(2)` |
| Latency | as long as it takes you to notice | kubelet sync period, unbounded in principle |
| App must | nothing | re-read the file, or watch the directory |
| Good for | values that define the process: ports, DSNs, feature flags fixed at boot | values you want to change live: log level, rate limits, nginx.conf |
| Trap | silently stale config after a ConfigMap edit | app that reads the file once at startup gets no benefit at all |
| `subPath` mount | n/a | **breaks updates entirely** — a `subPath` mount is a one-time copy and never refreshes |

The two production patterns worth remembering:

1. **Force the restart deliberately.** Annotate the pod template with a hash of the ConfigMap
   (`checksum/config: {{ .Values | sha256sum }}` in Helm, or a Kustomize `configMapGenerator`, which
   appends a content hash to the ConfigMap name). Any config change then produces a new pod template
   and a normal rolling update. This is the right default: it is explicit, auditable, and
   rollback-able.
2. **Or make the app reload.** Read config from a file on every use, or watch the mount directory
   and reload on change, and you get zero-downtime config changes for free — this is how nginx,
   Prometheus and Envoy sidecars do it.

The `subPath` warning in the table above deserves emphasis, because it is a real production outage
pattern: `mountPath: /etc/nginx/nginx.conf` + `subPath: nginx.conf` is the obvious way to inject a
single file without hiding the rest of the directory, and it **permanently disables live updates**
for that file. Mount the directory instead, or accept that you must restart.

---

## Task 5 — Troubleshooting: a 404 and a missing Secret key

### 5a — Four ways to get an Ingress error, and how to tell them apart

Everything below runs against the working `yatri-ingress` from Task 3 plus one deliberately broken
drill Ingress, [`manifests/06-broken-ingress.yaml`](manifests/06-broken-ingress.yaml), on host
`shop.local`. The drill Ingress is fixed one step at a time, and each step exposes a different
failure mode.

#### Failure 1: the wrong `Host` header → 404

The rule says `host: yatri.local`. Ask for `yatri.localhost`:

```bash
minikube ssh -- 'curl -s -i -H "Host: yatri.localhost" http://192.168.49.2/'
```

```text
HTTP/1.1 404 Not Found
Date: Thu, 17 Sep 2026 17:04:27 GMT
Content-Type: text/html
Content-Length: 146
Connection: keep-alive

<html>
<head><title>404 Not Found</title></head>
<body>
<center><h1>404 Not Found</h1></center>
<hr><center>nginx</center>
</body>
</html>
```

The same request with the correct header returns 200, and omitting `-H` entirely (so curl sends
`Host: 192.168.49.2`) also 404s:

```bash
minikube ssh -- 'curl -s -o /dev/null -w "%{http_code}\n" -H "Host: yatri.local" http://192.168.49.2/'
minikube ssh -- 'curl -s -o /dev/null -w "%{http_code}\n" http://192.168.49.2/'
```

```text
200
404
```

A host-based Ingress rule is matched on the `Host` header, not on the IP you connected to. One IP
serves every host in the cluster, and the header is the only thing that distinguishes them. In a
browser this is `/etc/hosts` plus DNS; with curl it is `-H "Host: ..."` or `--resolve`.

#### The diagnostic nobody teaches: this 404 is not in the access log

```bash
minikube ssh -- 'curl -s -o /dev/null -w "http_code=%{http_code}\n" -H "Host: yatri.localhost" http://192.168.49.2/UNIQUEPROBE7788'
minikube ssh -- 'curl -s -o /dev/null -w "http_code=%{http_code}\n" -H "Host: yatri.local"     http://192.168.49.2/UNIQUEPROBE9911'
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller | grep -c UNIQUEPROBE7788
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller | grep -c UNIQUEPROBE9911
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller | grep UNIQUEPROBE9911
```

```text
http_code=404
http_code=200
wrong-host probe lines in access log: 0
correct-host probe lines in access log: 1
192.168.49.2 - - [17/Sep/2026:17:05:24 +0000] "GET /UNIQUEPROBE9911 HTTP/1.1" 200 896 "-" "curl/7.88.1" 90 0.000 [hw12-yatri-frontend-svc-80] [] 10.244.0.38:80 896 0.001 200 ff7c42f37986d796374ef068c4488924
```

Both requests were served by the controller; only one was logged. A request whose `Host` matches no
Ingress rule lands in nginx's catch-all `server` block, which answers 404 with access logging
disabled. **If you are getting a 404 and there is no line for your request in the controller log at
all, the host did not match any rule.** That single observation collapses a whole class of
investigations — it means you should be checking `spec.rules[].host`, DNS, and your `Host` header,
not the Service or the pods.

#### Failure 2: a Service name typo → 503, not 404

The drill Ingress points at `yatri-frontend-service`. The real Service is `yatri-frontend-svc`:

```bash
kubectl apply -f manifests/06-broken-ingress.yaml
kubectl get ingress -n hw12
```

```text
ingress.networking.k8s.io/yatri-ingress-broken created
NAME                   CLASS   HOSTS         ADDRESS        PORTS   AGE
yatri-ingress          nginx   yatri.local   192.168.49.2   80      4m44s
yatri-ingress-broken   nginx   shop.local    192.168.49.2   80      10s
```

`kubectl get ingress` shows a perfectly healthy object with an address. It validates, it syncs, it
reports no error — **Kubernetes does not check that the backend Service exists.** `describe` is where
it shows:

```bash
kubectl describe ingress yatri-ingress-broken -n hw12
```

```text
Name:             yatri-ingress-broken
Labels:           app=yatri-app
Namespace:        hw12
Address:          192.168.49.2
Ingress Class:    nginx
Default backend:  <default>
Rules:
  Host        Path  Backends
  ----        ----  --------
  shop.local  
              /   yatri-frontend-service:80 (<error: services "yatri-frontend-service" not found>)
Annotations:  nginx.ingress.kubernetes.io/ssl-redirect: false
Events:
  Type    Reason  Age               From                      Message
  ----    ------  ----              ----                      -------
  Normal  Sync    6s (x2 over 10s)  nginx-ingress-controller  Scheduled for sync
```

`<error: services "yatri-frontend-service" not found>` — that is the whole diagnosis. The request:

```bash
minikube ssh -- 'curl -s -i -H "Host: shop.local" http://192.168.49.2/'
```

```text
HTTP/1.1 503 Service Temporarily Unavailable
Date: Thu, 17 Sep 2026 17:06:52 GMT
Content-Type: text/html
Content-Length: 190
Connection: keep-alive

<html>
<head><title>503 Service Temporarily Unavailable</title></head>
<body>
<center><h1>503 Service Temporarily Unavailable</h1></center>
<hr><center>nginx</center>
</body>
</html>
```

**503, not 404** — worth being precise about, because the two are diagnosed in opposite directions.
The host and path *did* match a rule, so nginx knows where the request should go; it has no healthy
upstream to send it to. 404 means "no rule matched"; 503 means "a rule matched and its backend is
empty". A tutorial that promises a 404 from a Service-name typo is wrong, and believing it sends you
looking at the wrong half of the stack. The controller log says both things explicitly:

```bash
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller --tail=2
```

```text
192.168.49.2 - - [17/Sep/2026:17:06:52 +0000] "GET / HTTP/1.1" 503 190 "-" "curl/7.88.1" 74 0.000 [hw12-yatri-frontend-service-80] [] - - - - 58db21505346d20657c5063fdf24c44a
W0917 17:06:53.516379       7 controller.go:1135] Error obtaining Endpoints for Service "hw12/yatri-frontend-service": no object matching key "hw12/yatri-frontend-service" in local store
```

The upstream name is `hw12-yatri-frontend-service-80` — the name you asked for — and every field
after it is `-`, meaning no upstream was contacted. The `W` line names the missing object outright.
A missing Service and a Service with a broken selector produce the *same* 503, so always confirm
which one you have:

```bash
kubectl get svc -n hw12
kubectl get endpointslices -n hw12
```

```text
NAME                 TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)   AGE
yatri-backend-svc    ClusterIP   10.103.99.94     <none>        80/TCP    5m28s
yatri-frontend-svc   ClusterIP   10.103.140.224   <none>        80/TCP    5m28s

NAME                       ADDRESSTYPE   PORTS   ENDPOINTS                 AGE
yatri-backend-svc-hmgtq    IPv4          5000    10.244.0.42,10.244.0.43   5m28s
yatri-frontend-svc-jq8pp   IPv4          80      10.244.0.38,10.244.0.37   5m28s
```

Services exist with healthy endpoints, under the name `-svc`. The Ingress asked for `-service`.

**Fix — point the rule at the Service that exists:**

```bash
kubectl patch ingress yatri-ingress-broken -n hw12 --type=json \
  -p '[{"op":"replace","path":"/spec/rules/0/http/paths/0/backend/service/name","value":"yatri-frontend-svc"}]'
kubectl describe ingress yatri-ingress-broken -n hw12 | sed -n '/^Rules:/,/^Annotations:/p'
minikube ssh -- 'curl -s -o /dev/null -w "shop.local/ -> %{http_code}\n" -H "Host: shop.local" http://192.168.49.2/'
```

```text
ingress.networking.k8s.io/yatri-ingress-broken patched
Rules:
  Host        Path  Backends
  ----        ----  --------
  shop.local  
              /   yatri-frontend-svc:80 (10.244.0.38:80,10.244.0.37:80)
Annotations:  nginx.ingress.kubernetes.io/ssl-redirect: false
shop.local/ -> 200
```

`describe` now resolves real endpoint IPs and the route returns 200.

#### Failure 3: the wrong path → 404, and this one *is* logged

Narrow the now-working rule to `/shop` only, then request `/`:

```bash
kubectl patch ingress yatri-ingress-broken -n hw12 --type=json \
  -p '[{"op":"replace","path":"/spec/rules/0/http/paths/0/path","value":"/shop"}]'
kubectl describe ingress yatri-ingress-broken -n hw12 | sed -n '/^Rules:/,/^Annotations:/p'
minikube ssh -- 'curl -s -o /dev/null -w "code=%{http_code} size=%{size_download}\n" -H "Host: shop.local" http://192.168.49.2/'
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller --tail=1
```

```text
Rules:
  Host        Path  Backends
  ----        ----  --------
  shop.local  
              /shop   yatri-frontend-svc:80 (10.244.0.38:80,10.244.0.37:80)
Annotations:  nginx.ingress.kubernetes.io/ssl-redirect: false

code=404 size=146

192.168.49.2 - - [17/Sep/2026:17:07:33 +0000] "GET / HTTP/1.1" 404 146 "-" "curl/7.88.1" 74 0.000 [upstream-default-backend] [] 127.0.0.1:8181 146 0.000 404 e8a7f8d25b622079d4f40ffa3837195e
```

The body is byte-for-byte the one from Failure 1 — but this time the host **did** match, so a
`server` block exists, logging is on, and the request is recorded with upstream
`[upstream-default-backend]` → `127.0.0.1:8181`, the controller's own default backend. Host matched,
path did not. Same status code, same page, completely different fix.

#### Failure 4: a 404 that did not come from the Ingress at all

`/shop` now matches the rule and is proxied to the frontend nginx, which has no `/shop` file:

```bash
minikube ssh -- 'curl -s -i -H "Host: shop.local" http://192.168.49.2/shop'
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller --tail=1
```

```text
HTTP/1.1 404 Not Found
Date: Thu, 17 Sep 2026 17:07:52 GMT
Content-Type: text/html
Content-Length: 153
Connection: keep-alive

<html>
<head><title>404 Not Found</title></head>
<body>
<center><h1>404 Not Found</h1></center>
<hr><center>nginx/1.31.6</center>
</body>
</html>

192.168.49.2 - - [17/Sep/2026:17:07:52 +0000] "GET /shop HTTP/1.1" 404 153 "-" "curl/7.88.1" 78 0.000 [hw12-yatri-frontend-svc-80] [] 10.244.0.37:80 153 0.001 404 f1cedc8c155a1585502a398868cdbde9
```

Nearly the same page — but **153 bytes and `nginx/1.31.6`** instead of **146 bytes and bare `nginx`**,
and the log names a real upstream at a real pod IP. Routing worked perfectly; the *application*
returned the 404. The same distinction appears on the main Ingress, where `/api/health` is rewritten
to `/health` and busybox httpd has no such file:

```bash
minikube ssh -- 'curl -s -i -H "Host: yatri.local" http://192.168.49.2/api/health'
```

```text
HTTP/1.1 404 Not Found
Date: Thu, 17 Sep 2026 17:04:28 GMT
Content-Type: text/html
Transfer-Encoding: chunked
Connection: keep-alive

<HTML><HEAD><TITLE>404 Not Found</TITLE></HEAD>
<BODY><H1>404 Not Found</H1>
The requested URL was not found
</BODY></HTML>
```

Uppercase HTML and chunked encoding: that is busybox httpd, not nginx. **Read the 404 body before you
touch the Ingress** — it usually tells you which process produced it.

**Fix — a prefix the backend does not serve needs a rewrite:**

```bash
kubectl annotate ingress yatri-ingress-broken -n hw12 \
  nginx.ingress.kubernetes.io/use-regex=true \
  nginx.ingress.kubernetes.io/rewrite-target='/$2' --overwrite
kubectl patch ingress yatri-ingress-broken -n hw12 --type=json \
  -p '[{"op":"replace","path":"/spec/rules/0/http/paths/0/path","value":"/shop(/|$)(.*)"},
       {"op":"replace","path":"/spec/rules/0/http/paths/0/pathType","value":"ImplementationSpecific"}]'
minikube ssh -- 'curl -s -o /dev/null -w "shop.local/shop  -> %{http_code}\n" -H "Host: shop.local" http://192.168.49.2/shop'
minikube ssh -- 'curl -s -H "Host: shop.local" http://192.168.49.2/shop/ | grep -i "<title>"'
kubectl delete -f manifests/06-broken-ingress.yaml
```

```text
ingress.networking.k8s.io/yatri-ingress-broken annotated
ingress.networking.k8s.io/yatri-ingress-broken patched
shop.local/shop  -> 200
<title>Welcome to nginx!</title>
ingress.networking.k8s.io "yatri-ingress-broken" deleted from hw12 namespace
```

All four failure modes, side by side:

| Symptom | Body | Access log | Cause | Fix |
|---|---|---|---|---|
| 404, 146 bytes, `<hr><center>nginx</center>` | ingress-nginx catch-all | **no log line at all** | `Host` matches no rule | fix `spec.rules[].host`, DNS, or the `Host` header |
| 404, 146 bytes, identical body | ingress-nginx default backend | `[upstream-default-backend]` → `127.0.0.1:8181` | host matched, path did not | fix `path` / `pathType` |
| 404, any other body | your application | real upstream `[ns-svc-port]` at a pod IP | routing fine, app returned 404 | fix the app, or add a rewrite |
| 503, 190 bytes | ingress-nginx | real upstream, then `- - - -` | Service missing or has no endpoints | fix the Service name, selector, or readiness |

**A 404/503 checklist, in the order that finds the fault fastest:**

1. `kubectl logs -n ingress-nginx deployment/ingress-nginx-controller | tail` — is the request logged
   at all? No line → the `Host` matched no rule. Stop here.
2. Read the upstream field. `[upstream-default-backend]` → path did not match. A real `[ns-svc-port]`
   with `- - - -` → 503, no endpoints. A real upstream with a real pod IP → routing worked, the app
   answered.
3. `kubectl describe ingress <name>` — do the backends resolve to endpoint IPs, or is there an
   `<error: ... not found>`?
4. `kubectl get svc,endpointslices -n <ns>` — does the Service exist, and does it have endpoints?
   Empty endpoints is a selector or readiness-probe problem, not an Ingress problem.
5. Check `ingressClassName`. A rule with no class, in a cluster whose controller does not run with
   `--watch-ingress-without-class`, is ignored silently and produces exactly the unlogged 404 from
   step 1.
6. Read the 404 body. `nginx` with no version → ingress-nginx. Anything else → your application.

### 5b — A pod stuck in `CreateContainerConfigError`

[`manifests/07-broken-secret-pod.yaml`](manifests/07-broken-secret-pod.yaml) asks for
`POSTGRES_PASSWRD` (missing `O`) from a Secret that has `POSTGRES_PASSWORD`:

```bash
grep -n "key:" manifests/07-broken-secret-pod.yaml
kubectl get secret yatri-db-secret -n hw12 -o go-template='{{range $k,$v := .data}}{{$k}}{{"\n"}}{{end}}'
kubectl apply -f manifests/07-broken-secret-pod.yaml
kubectl get pod yatri-secret-consumer -n hw12
```

```text
22:              key: POSTGRES_USER
27:              key: POSTGRES_PASSWRD
POSTGRES_DB
POSTGRES_PASSWORD
POSTGRES_USER
pod/yatri-secret-consumer created
NAME                    READY   STATUS                       RESTARTS   AGE
yatri-secret-consumer   0/1     CreateContainerConfigError   0          12s
```

`CreateContainerConfigError` is a specific and helpful status: the pod was **scheduled**, the image
was **pulled**, and the kubelet then failed while assembling the container's configuration. It is not
`ImagePullBackOff` (registry/tag problem), not `CrashLoopBackOff` (the container started and exited),
and not `Pending` (no node). If you see it, the cause is almost always a missing ConfigMap, a missing
Secret, or a missing key inside one of them.

The status message names the exact key:

```bash
kubectl get pod yatri-secret-consumer -n hw12 \
  -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}{"\n"}{.status.containerStatuses[0].state.waiting.message}{"\n"}'
```

```text
CreateContainerConfigError
couldn't find key POSTGRES_PASSWRD in Secret hw12/yatri-db-secret
```

And so do the events:

```bash
kubectl describe pod yatri-secret-consumer -n hw12 | tail -8
```

```text
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  12s                default-scheduler  Successfully assigned hw12/yatri-secret-consumer to minikube
  Normal   Pulled     10s (x2 over 11s)  kubelet            spec.containers{app}: Container image "busybox:1.36" already present on machine and can be accessed by the pod
  Warning  Failed     10s (x2 over 11s)  kubelet            spec.containers{app}: Error: couldn't find key POSTGRES_PASSWRD in Secret hw12/yatri-db-secret
```

`Pulled` then `Failed`, `x2` and climbing: the kubelet retries with backoff forever. The pod never
progresses and never gives up.

```bash
kubectl get pod yatri-secret-consumer -n hw12
kubectl get pod yatri-secret-consumer -n hw12 \
  -o jsonpath='{range .spec.containers[0].env[*]}{.name}{" <- "}{.valueFrom.secretKeyRef.name}{"/"}{.valueFrom.secretKeyRef.key}{"\n"}{end}'
```

```text
NAME                    READY   STATUS                       RESTARTS   AGE
yatri-secret-consumer   0/1     CreateContainerConfigError   0          44s
POSTGRES_USER <- yatri-db-secret/POSTGRES_USER
POSTGRES_PASSWORD <- yatri-db-secret/POSTGRES_PASSWRD
```

That jsonpath is worth keeping: it prints every `secretKeyRef` in a pod as
`VAR <- secret/key`, which you can compare by eye against the Secret's key list. Note also
`RESTARTS 0` — the container never started, so there is nothing to restart and `kubectl logs` returns
nothing useful.

#### The fix

```bash
diff manifests/07-broken-secret-pod.yaml manifests/08-fixed-secret-pod.yaml
kubectl delete pod yatri-secret-consumer -n hw12
kubectl apply -f manifests/08-fixed-secret-pod.yaml
kubectl wait --for=condition=Ready pod/yatri-secret-consumer -n hw12 --timeout=120s
kubectl get pod yatri-secret-consumer -n hw12
kubectl logs yatri-secret-consumer -n hw12
kubectl exec -n hw12 yatri-secret-consumer -- printenv POSTGRES_USER POSTGRES_PASSWORD
```

```text
27c27
<               key: POSTGRES_PASSWRD
---
>               key: POSTGRES_PASSWORD
pod "yatri-secret-consumer" deleted from hw12 namespace
pod/yatri-secret-consumer created
pod/yatri-secret-consumer condition met
NAME                    READY   STATUS    RESTARTS   AGE
yatri-secret-consumer   1/1     Running   0          2s
started with user=yatri_admin
yatri_admin
secretpassword
```

`1/1 Running`. The pod had to be recreated because `spec.containers[].env` is immutable on a live
Pod — a Deployment would have handled this with a rolling update instead.

Two things worth knowing about this failure mode:

- **The kubelet keeps retrying, so the pod self-heals if the data appears.** Creating the missing key
  in the Secret (without touching the pod) also clears the error at the next retry. That is useful
  when the real fault is a Secret that a CI job has not written yet, and it is why pods that reference
  a not-yet-created ConfigMap eventually start on their own.
- **`optional: true` turns the hard failure into a soft one.** Under `secretKeyRef` it lets the
  container start with the variable simply unset. Convenient, and a good way to convert a loud
  startup failure into a silent runtime one — use it only when the application genuinely has a
  default.

---

## Reference tables

### ConfigMap vs Secret

| | ConfigMap | Secret |
|---|---|---|
| Purpose | non-sensitive configuration | credentials, keys, certificates |
| Storage in etcd | plain text | base64, and **plain text unless encryption-at-rest is configured** |
| `kubectl describe` | prints every value | prints key names and byte counts only |
| `kubectl get -o yaml` | plain values | base64 values — decodable by anyone who can `get` |
| Encoding required | none | base64 in `data:`, or plain text in `stringData:` |
| Size limit | 1 MiB | 1 MiB |
| Mounted on the node | disk | **tmpfs (RAM)**, so it never touches node disk and vanishes with the pod |
| Sent to a node | to every node that runs a pod using it | only to nodes running a pod that references it |
| Consumed via | `envFrom`/`configMapRef`, `configMapKeyRef`, volume | `envFrom`/`secretRef`, `secretKeyRef`, volume, `imagePullSecrets` |
| Types | none | `Opaque`, `kubernetes.io/tls`, `kubernetes.io/dockerconfigjson`, `kubernetes.io/basic-auth`, … |
| Access control | RBAC | RBAC — and this is the *only* real protection |
| Audit | ordinary | value is redacted in API audit logs |
| Safe in git | yes | **no**, ever — use SOPS, Sealed Secrets, or an external store |
| `immutable: true` | supported | supported — also reduces API-server watch load at scale |

The honest one-line summary: **a Secret is a ConfigMap that RBAC, the audit log, tmpfs and etcd
encryption treat differently.** The base64 is not a security feature and never was.

### `env` / `envFrom` vs volume mount

| | Environment variables | Volume mount |
|---|---|---|
| Syntax | `envFrom: configMapRef` (all keys), `env.valueFrom.configMapKeyRef` / `secretKeyRef` (one key) | `volumes[].configMap` / `.secret` + `volumeMounts[]` |
| What the container sees | `KEY=value` in its environment | one file per key, named after the key |
| Multi-line / binary values | painful to impossible | natural |
| Rename a key on the way in | yes, with `secretKeyRef`/`configMapKeyRef` | yes, with `items[].key` + `items[].path` |
| Subset of keys | yes, one `env` entry per key | yes, with `items:` |
| Updates when the source changes | **never** | yes, after the kubelet sync (**77 s measured here**) |
| Update mechanism | none — requires a new container | new timestamped dir + atomic `..data` symlink swap |
| Needs a restart | yes | no |
| `subPath` | n/a | works, but **permanently disables updates for that file** |
| File permissions | n/a | `defaultMode`, `items[].mode` |
| Missing key at start | `CreateContainerConfigError`, pod never starts | key is simply absent from the directory |
| `optional: true` | starts with the variable unset | starts with the file absent |
| Leaks into | `/proc/<pid>/environ`, crash dumps, child processes, startup logs | only the mount path |
| Best for | ports, DSNs, feature flags fixed at boot; 12-factor apps | `nginx.conf`, TLS certs, anything reloadable, anything large |

### The paths a request takes to a pod

| Mechanism | Layer | Entry point | Per-service cost | Routes on |
|---|---|---|---|---|
| ClusterIP | L4 | in-cluster only | none | Service IP |
| NodePort | L4 | `<nodeIP>:30000-32767` | one port per Service | port number |
| LoadBalancer | L4 | cloud LB | **one LB per Service** | LB IP |
| Ingress | **L7** | one LB / one controller | shared by every rule | `Host` header **and** URL path |

That last row is the entire argument for Ingress: five microservices behind five `LoadBalancer`
Services means five cloud load balancers and five bills; behind one Ingress it means one, plus
host/path routing, TLS termination and rewrites that a L4 Service cannot do at all.

---

## Interview questions

**1. Is a Kubernetes Secret encrypted?**
No. It is base64-encoded, which is reversible by anyone with `get secret` permission —
`kubectl get secret x -o jsonpath='{.data.PASSWORD}' | base64 --decode` prints the password. What
actually protects it is (a) RBAC on the `secrets` resource, (b) encryption at rest for etcd via
`--encryption-provider-config`, ideally with a KMS provider, and (c) not committing the manifest to
git. Secrets do get real handling that ConfigMaps do not: they are mounted on tmpfs rather than disk,
only sent to nodes that need them, and redacted in audit logs.

**2. I changed a ConfigMap. Why is my pod still using the old value?**
Because you injected it as an environment variable. Environment variables are resolved by the kubelet
once, at container creation, and passed to `execve()`; nothing can change a running process's
environment from outside. You need a new container: `kubectl rollout restart deployment/<name>`. If
the same key had been mounted as a volume it would have updated in place — measured at 77 seconds in
Task 4, with zero restarts.

**3. How does a mounted ConfigMap update without a restart, and why the strange `..data` symlink?**
The kubelet writes the new contents into a fresh timestamped directory and then re-points the
`..data` symlink with a single `rename(2)`, which is atomic on POSIX. Every user-visible key is a
symlink through `..data`, so a reader sees either all of the old values or all of the new ones and
never a partial write. The `..` prefix hides the plumbing from `ls` and shell globs. The catch: your
application has to actually re-read the file; if it reads config once at startup, a volume mount buys
you nothing.

**4. Ingress vs LoadBalancer Service — when do you use which?**
A `LoadBalancer` Service is L4 and gives one cloud load balancer per Service — five microservices
means five load balancers and five bills. Ingress is L7: one controller behind one load balancer,
with routing by `Host` header and URL path, TLS termination, rewrites, rate limiting and canary
weighting as annotations. Use a `LoadBalancer` for non-HTTP traffic (a database, gRPC streams,
anything TCP/UDP) and Ingress for HTTP.

**5. I applied an Ingress and nothing happens. Why?**
An Ingress object is only data. Something has to read it: an Ingress **controller**. Without one, the
rules sit in etcd doing nothing. And with one installed, the rule still has to be claimed — check
`spec.ingressClassName` against `kubectl get ingressclass`. A rule with no class, in a cluster whose
controller does not run with `--watch-ingress-without-class`, is silently ignored.

**6. Ingress returns 404. Walk me through it.**
First check whether the request appears in the controller's access log at all. If it does not, the
`Host` header matched no rule — the catch-all server answers 404 without logging (demonstrated in
Task 5). If it is logged with upstream `[upstream-default-backend]`, the host matched but the path
did not. If it is logged with a real upstream and a real pod IP, routing worked and your application
returned the 404 — check the response body, since an app's 404 page rarely looks like nginx's. Then
`describe ingress` to confirm backends resolve to endpoint IPs.

**7. And a 503?**
A 503 means a rule matched but nginx has no healthy upstream: the Service does not exist, the name is
misspelled, or the Service has no endpoints because its selector matches nothing or the pods are not
Ready. `kubectl describe ingress` shows `<error: services "..." not found>` for a missing Service;
`kubectl get endpointslices` shows an empty list for a selector or readiness problem. Note that a
Service-name typo produces 503, **not** 404 — a lot of tutorials get this wrong.

**8. A pod is stuck in `CreateContainerConfigError`. What is it and what causes it?**
The pod was scheduled and the image was pulled, but the kubelet could not assemble the container's
configuration. Almost always a missing ConfigMap, a missing Secret, or a missing key inside one —
`kubectl get pod <p> -o jsonpath='{.status.containerStatuses[0].state.waiting.message}'` names the key
exactly, e.g. `couldn't find key POSTGRES_PASSWRD in Secret hw12/yatri-db-secret`. `kubectl logs`
tells you nothing because the container never started. The kubelet retries forever, so the pod also
self-heals if the missing data is created later. `optional: true` downgrades the failure to "variable
simply unset".

**9. What is the `echo` vs `echo -n` trap?**
`echo "password" | base64` encodes a trailing `\n`, so the application receives an extra byte and
authentication fails with a password that looks correct in every log and terminal. Always
`echo -n`, or better, avoid manual encoding entirely: `kubectl create secret generic --from-literal=`
and `stringData:` both do the encoding for you. To detect it, compare the byte count in
`kubectl describe secret` against the real length, or `od -c` the value inside the pod. Do not
pattern-match on the `Ao=` suffix — that only appears for inputs whose length+1 is 2 mod 3.

**10. `envFrom` or a volume — how do you choose?**
Environment variables for values that define the process at boot (ports, DSNs, feature flags) and for
12-factor apps that expect them. Volumes for anything multi-line or binary (`nginx.conf`, TLS
certificates), anything you want to change without a restart, and anything sensitive — a mounted
Secret does not leak into `/proc/<pid>/environ`, crash dumps, child processes or a framework that
dumps the environment on startup. The standard production compromise is env vars plus a
`checksum/config` annotation on the pod template so any ConfigMap change triggers a normal rolling
update.

**11. What does `rewrite-target: /$2` actually do?**
With `path: /api(/|$)(.*)` and `use-regex: "true"`, nginx captures everything after `/api` into group
2 and forwards only that to the backend, so `/api/users` arrives as `/users`. The backend never needs
to know it is mounted under a prefix. Two things to get right: `pathType` must be
`ImplementationSpecific` (a `Prefix` path compares path segments literally and would treat the
parentheses as characters), and the `(/|$)` alternative is what makes `/api` with no trailing slash
match as well as `/api/`.

**12. Can two Ingresses share a host?**
Yes — ingress-nginx merges rules for the same host across objects, which is how teams in separate
namespaces publish different paths under one domain. It is also a foot-gun: conflicting paths are
resolved by a first-created-wins rule, and a second Ingress declaring `path: /` can quietly take over
traffic from another team. Annotations that configure the `server` block rather than a `location` are
taken from one Ingress only.

**13. Why is `kubectl rollout restart` safe in production?**
It does not kill anything. It stamps
`spec.template.metadata.annotations.kubectl.kubernetes.io/restartedAt` with the current timestamp,
which changes the pod-template hash and makes the Deployment controller perform an ordinary rolling
update, honouring `maxUnavailable`, `maxSurge`, readiness probes and `terminationGracePeriodSeconds`.
Task 4 shows the ReplicaSet changing from `9fc699cc7` to `85b949bcd4` with no window where zero pods
were Ready.

**14. Where do ConfigMap and Secret updates *not* propagate?**
Four places: environment variables (ever), any volume mounted with `subPath` (a one-time copy), a
ConfigMap or Secret marked `immutable: true` (which cannot be changed at all — you create a new one),
and anything your application read once into memory at startup. The `subPath` case is the nastiest,
because mounting a single file like `/etc/nginx/nginx.conf` is the obvious thing to do and it
silently freezes that file for the life of the container.

---

## Cleanup

Everything created by this assignment lives in one namespace, so teardown is one command. Before
deleting, the full inventory:

```bash
kubectl get all -n hw12
kubectl get configmap,secret,ingress,sa,role,rolebinding -n hw12
```

```text
NAME                                  READY   STATUS    RESTARTS   AGE
pod/newline-bug-demo                  1/1     Running   0          15m
pod/yatri-backend-85b949bcd4-9pdjl    1/1     Running   0          11m
pod/yatri-backend-85b949bcd4-tt467    1/1     Running   0          11m
pod/yatri-frontend-675449c7c8-lft4t   1/1     Running   0          15m
pod/yatri-frontend-675449c7c8-vxq2h   1/1     Running   0          15m
pod/yatri-secret-consumer             1/1     Running   0          10m

NAME                         TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)   AGE
service/yatri-backend-svc    ClusterIP   10.103.99.94     <none>        80/TCP    15m
service/yatri-frontend-svc   ClusterIP   10.103.140.224   <none>        80/TCP    15m

NAME                             READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/yatri-backend    2/2     2            2           15m
deployment.apps/yatri-frontend   2/2     2            2           15m

NAME                                        DESIRED   CURRENT   READY   AGE
replicaset.apps/yatri-backend-85b949bcd4    2         2         2       11m
replicaset.apps/yatri-backend-9fc699cc7     0         0         0       15m
replicaset.apps/yatri-frontend-675449c7c8   2         2         2       15m

NAME                          DATA   AGE
configmap/kube-root-ca.crt    1      18m
configmap/yatri-app-config    5      16m
configmap/yatri-file-config   1      16m

NAME                         TYPE     DATA   AGE
secret/yatri-db-secret       Opaque   3      15m
secret/yatri-db-secret-bad   Opaque   1      15m

NAME                                      CLASS   HOSTS         ADDRESS        PORTS   AGE
ingress.networking.k8s.io/yatri-ingress   nginx   yatri.local   192.168.49.2   80      15m

NAME                          AGE
serviceaccount/default        18m
serviceaccount/yatri-app-sa   8m31s

NAME                                                 CREATED AT
role.rbac.authorization.k8s.io/yatri-config-reader   2026-09-17T17:08:40Z

NAME                                                                ROLE                       AGE
rolebinding.rbac.authorization.k8s.io/yatri-config-reader-binding   Role/yatri-config-reader   8m31s
```

Note `replicaset.apps/yatri-backend-9fc699cc7   0   0   0` — the pre-restart ReplicaSet from Task 4,
scaled to zero but retained so `kubectl rollout undo` still works.

```bash
time kubectl delete namespace hw12
kubectl get ns hw12
kubectl get all -n hw12
```

```text
namespace "hw12" deleted
kubectl delete namespace hw12  0.03s user 0.02s system 0% cpu 42.413 total

Error from server (NotFound): namespaces "hw12" not found
No resources found in hw12 namespace.
```

`NotFound` — confirmed gone. The 42 seconds is graceful termination: the namespace controller deletes
every object in the namespace and waits out each pod's `terminationGracePeriodSeconds` before the
namespace itself leaves `Terminating`.

The Ingress controller is **left enabled on purpose** — it is a cluster-wide addon in its own
namespace, shared with other work on this cluster, and disabling it would remove the IngressClass
every other Ingress on the cluster depends on:

```bash
minikube addons list | grep -i ingress
kubectl get pods -n ingress-nginx
```

```text
│ ingress                     │ minikube │ enabled ✅ │ Kubernetes                             │
│ ingress-dns                 │ minikube │ disabled   │ minikube                               │

NAME                                       READY   STATUS      RESTARTS      AGE
ingress-nginx-admission-create-9ztp5       0/1     Completed   0             19m
ingress-nginx-admission-patch-sbxrg        0/1     Completed   2 (19m ago)   19m
ingress-nginx-controller-d7cd8c989-m4p54   1/1     Running     0             19m
```

Deleting the namespace already removed the `yatri-ingress` object, so the controller is back to
serving nothing from this assignment. The cluster and the node are untouched: no `minikube stop`, no
`minikube delete`.

---

## Files

```text
12-ingress-configmaps-secrets/
├── README.md
└── manifests/
    ├── 00-namespace.yaml            Namespace hw12
    ├── 01-app-config.yaml           ConfigMap from literals (exported with --dry-run=client)
    ├── 02-db-secret.yaml            Opaque Secret, demo credentials only
    ├── 03-backend.yaml              Deployment + Service: envFrom, secretKeyRef and two volume mounts
    ├── 04-frontend.yaml             Deployment + Service: nginx:alpine behind path /
    ├── 05-ingress.yaml              One host, two paths, two Services
    ├── 06-broken-ingress.yaml       Task 5a drill: Service name typo
    ├── 07-broken-secret-pod.yaml    Task 5b drill: secretKeyRef to a key that does not exist
    ├── 08-fixed-secret-pod.yaml     Task 5b fix
    ├── 09-newline-bug.yaml          Good and bad Secret side by side in one pod
    ├── 10-secret-rbac.yaml          ServiceAccount + Role proving RBAC is the real control
    └── app.properties               Source file for --from-file
```

## Checklist

- [x] ConfigMap created from literals with `--from-literal` and from a file with `--from-file`.
- [x] Same ConfigMap injected as environment variables (`envFrom`) and as a mounted volume.
- [x] `..data` symlink structure captured and explained, including why it makes updates atomic.
- [x] Opaque Secret created, injected with `secretKeyRef`, decoded with `base64 --decode`.
- [x] `echo` vs `echo -n` bug shown at the byte level and reproduced inside a running pod.
- [x] RBAC demonstrated as the real access control; encryption at rest explained.
- [x] Ingress controller enabled and confirmed `1/1 Running`.
- [x] Two paths under one host routed to two Services; **both** verified 200 by three methods.
- [x] The course lab's `minikube ip` curl shown failing on macOS, with the reason and three fixes.
- [x] ConfigMap live update: env var stayed stale, volume updated in **77 s** with zero restarts.
- [x] `kubectl rollout restart` shown to be the only thing that moves an environment variable.
- [x] Ingress 404 reproduced three ways and 503 once, each diagnosed and fixed.
- [x] `CreateContainerConfigError` reproduced from a missing Secret key, diagnosed, fixed to Running.
- [x] Namespace `hw12` deleted and verified `NotFound`; ingress addon left enabled.
