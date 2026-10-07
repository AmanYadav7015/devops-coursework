# Session 17 — Complete CI/CD & DevSecOps

**Official task:** Build a complete CI/CD + DevSecOps pipeline. CI/CD: application build, unit
testing, Docker image build, container registry, Kubernetes deployment. Security: SAST, SCA, secret
scanning, container image scanning, security gates. Expected flow:
`Code -> Build -> Unit Test -> SAST -> SCA -> Secret Scan -> Docker Build -> Container Image Scan ->
Security Gate -> Push Image -> Deploy to Kubernetes`. Deliverables: application, Dockerfile, GitHub
Actions workflow, security tools configuration, Kubernetes manifests, successful pipeline output,
screenshots, complete README.

Everything below was executed. The pipeline ran six times on GitHub-hosted runners in a public
repository, the image it produced is a real public package on GHCR, and that exact image digest is
running on the local minikube cluster. Every block of output in this document was pulled back out of
those runs with `gh`, or captured from a terminal on this laptop.

| | |
| --- | --- |
| Repository | <https://github.com/AmanYadav7015/devops-coursework> |
| Branch | `session-17-devsecops-ci` |
| Application | `labs/17-devsecops/` |
| Workflow | `.github/workflows/session17-devsecops.yml` |
| Runner | `ubuntu-latest` (GitHub-hosted), `linux/amd64` |
| Published image | `ghcr.io/amanyadav7015/devops-coursework/claim-check-api` |
| Image digest | `sha256:12b1027d1eaf70a631fe38a94e5542c8d3023f7128af4d700b440b827a9de38b` |
| Local cluster namespace | `hw17`, NodePort `30170` |
| Local tools | trivy 0.75.0, gitleaks 8.30.1, bandit 1.9.4, pip-audit 2.10.1 |

### Files in this folder

```text
README.md                           this walkthrough
app/__init__.py                     service name
app/claims.py                       expense-claim validation and pricing rules
app/server.py                       Flask HTTP surface
tests/test_claims.py                16 tests over the rules
tests/test_server.py                10 tests over the HTTP endpoints
Dockerfile                          two-stage build, no package manager in the runtime layer
.dockerignore                       build-context exclusions
.gitleaksignore                     the one accepted secret-scan finding, by fingerprint
requirements.txt                    pinned runtime dependencies
requirements-dev.txt                test, lint and security tooling
setup.cfg                           flake8 and pytest configuration
security/bandit.yaml                SAST configuration
security/gitleaks.toml              secret-scanning rules and allowlist
security/trivy.yaml                 image and dependency scanning policy
security/.trivyignore               accepted image findings (currently empty)
k8s/namespace.yaml                  namespace hw17
k8s/deployment.yaml                 2 replicas, probes, non-root, read-only root filesystem
k8s/service.yaml                    NodePort 30170
workflows/session17-devsecops.yml   the pipeline (deployed at .github/workflows/ in the repository)
insecure-baseline/                  the deliberately vulnerable starting point, kept for comparison
  app/claims.py                     MD5 fingerprint, random reference
  app/server.py                     eval, shell=True, yaml.load, verify=False, debug=True
  Dockerfile                        single stage, Debian 11 base, runs as root
  requirements.txt                  the out-of-date pins the dependency scanners flagged
  requirements-2022.txt             the even older pins that no longer install at all
run-output/                         captured evidence
  bandit-insecure-full.txt          12 findings on the insecure baseline
  bandit-secure-full.txt            0 findings after remediation
  pip-audit-vulnerable.txt          75 advisories across 9 packages
  pip-audit-fixed.txt               no known vulnerabilities
  trivy-fs-vulnerable.txt           15 HIGH/CRITICAL dependency findings with CVE ids
  trivy-fs-fixed.txt                0 findings
  gitleaks-detected.txt             5 secret types detected, values masked
  github-push-protection-block.txt  GitHub refusing a push that contained a webhook URL
  trivy-image-gate-bullseye.txt     the gate failing on the old base image
  trivy-image-gate-trixie.txt       the gate passing on the hardened image
  run2-37630551638-full.log         SAST gate blocking
  run3-37630958303-full.log         SCA gate blocking
  run4-gate-blocked-...-full.log    the image security gate blocking
  run5-37632022533-full.log         gate passing, image pushed to GHCR
  run6-...-full.log                 the all-green run
  k8s-hw17-deployed.txt             the deployment running on minikube
  k8s-hw17-http.txt                 real HTTP responses from the NodePort
  k8s-hw17-rollout.txt              a rolling update driven by kubectl set image
```

The deliverable list asks for screenshots. A screenshot of a terminal cannot be grepped, diffed or
verified, so what is here instead is the machine-readable equivalent: complete run logs and JSON job
graphs pulled from GitHub's API after the runs finished, plus the raw scanner transcripts. The run
URLs are live.

---

## 1. The shape of the thing

A pipeline that *runs* security tools is not a DevSecOps pipeline. A pipeline that lets a security
tool *stop a release* is. The difference is one line of exit-code handling, and it is the only part
of this lab that is genuinely hard to fake — which is why most of the evidence below is of things
going **red**.

The eleven stages are wired as a strict chain, exactly as the task specifies:

```text
1 Build  ->  2 Unit Test  ->  3 SAST  ->  4 SCA  ->  5 Secret Scan  ->  6 Docker Build
                                                                            |
                           10 Deploy  <-  9 Push to GHCR  <-  8 Security Gate  <-  7 Image Scan
```

Every arrow is a `needs:` edge. A stage that fails leaves everything downstream `skipped`, not
`failure` — skipped jobs never get a runner, so a broken build costs nothing and, more importantly,
cannot reach the registry. Six real runs below show four different stages doing exactly that.

One job sits outside the chain: `3b SAST (CodeQL)`, which branches off `2 Unit Test` and runs beside
the main line. It reports into the repository's Security tab and never blocks. Section 5.2 explains
why a second SAST tool earns its keep even without gating.

---

## 2. The application

`claim-check-api` is a small Flask service that validates and prices employee expense claims. It is
deliberately small but not a toy: it has pure business logic worth testing, an HTTP surface, 26 unit
tests, and — crucially for this lab — enough surface area to host realistic security defects.

```text
app/claims.py   category caps, reimbursement rates, receipt penalty, approval threshold,
                a salted fingerprint over a claim, a unique claim reference, batch totals
app/server.py   GET  /health, GET /version, GET /fx
                POST /claims/validate, /claims/price, /claims/batch, /policy/apply
tests/          26 tests: 16 over the rules, 10 over the endpoints
```

```bash
cd labs/17-devsecops && pytest
```

```text
tests/test_claims.py::test_validate_claim_accepts_a_normal_claim PASSED  [  3%]
tests/test_claims.py::test_price_claim_caps_the_category PASSED          [ 38%]
tests/test_claims.py::test_fingerprint_is_stable_and_salted PASSED       [ 50%]
tests/test_claims.py::test_issue_reference_is_unique_and_prefixed PASSED [ 53%]
tests/test_server.py::test_policy_endpoint_parses_yaml PASSED            [ 92%]
tests/test_server.py::test_fx_endpoint_reports_no_upstream PASSED        [100%]

============================== 26 passed in 0.18s ==============================
```

Bare `pytest` works rather than only `python -m pytest` because `setup.cfg` carries
`pythonpath = .` under `[tool:pytest]`. The `-m` form puts the current directory on `sys.path`; the
console script does not, and the runner uses the console script.

### 2.1 The insecure baseline

The first commit on this branch shipped a version of the same application carrying eight real
defects, listed here with the scanner that catches each one:

| Defect in `insecure-baseline/` | Caught by |
| --- | --- |
| `hashlib.md5()` over claim data | bandit B324, CodeQL `py/weak-sensitive-data-hashing` |
| `random.choice()` for a claim reference | bandit B311 |
| `FALLBACK_TOKEN = "claim-check-default-salt"` | bandit B105, gitleaks custom rule |
| `yaml.load(document, Loader=yaml.Loader)` | bandit B506, CodeQL `py/unsafe-deserialization` |
| `eval(expression)` on a request body | bandit B307, CodeQL `py/code-injection` |
| `subprocess.check_output("getent hosts " + host, shell=True)` | bandit B602, CodeQL `py/command-line-injection` |
| `requests.get(url, verify=False)` with no timeout | bandit B501, B113 |
| `app.run(host="0.0.0.0", debug=True)` | bandit B201, B104, CodeQL `py/flask-debug` |

All 26 tests pass against that version. That is the point: **a green test suite says nothing about
whether the code is safe.** The tests and the scanners are answering different questions.

---

## 3. The workflow

Full file: [`workflows/session17-devsecops.yml`](workflows/session17-devsecops.yml), deployed in the
repository at `.github/workflows/session17-devsecops.yml` — a workflow only runs from that path.

### 3.1 Triggers

```yaml
on:
  push:
    branches:
      - session-17-devsecops-ci
    paths:
      - 'labs/17-devsecops/**'
      - '.github/workflows/session17-devsecops.yml'
  workflow_dispatch:
    inputs:
      gate_severity:
        description: 'Severities that block the pipeline at the image gate'
        type: choice
        options:
          - HIGH,CRITICAL
          - CRITICAL
        default: HIGH,CRITICAL
      skip_push:
        description: 'Run every check but do not publish the image'
        type: boolean
        default: false
```

The `paths` filter keeps a change to another lab from burning runner minutes here. The dispatch
inputs are not decoration — `gate_severity` is read straight into the gate's `--severity` flag, so
the policy can be tightened or loosened by a human without editing YAML, and section 10 shows a real
dispatch run doing it.

### 3.2 Workflow-level settings

```yaml
permissions:
  contents: read

concurrency:
  group: session17-${{ github.ref }}
  cancel-in-progress: true

env:
  APP_DIR: labs/17-devsecops
  IMAGE_NAME: claim-check-api
  TRIVY_VERSION: 0.75.0
  GITLEAKS_VERSION: 8.30.1
  PYTHON_VERSION: '3.13'
```

`permissions: contents: read` at the top narrows the automatic `GITHUB_TOKEN` to the minimum, and two
jobs widen it for exactly what they need: `security-events: write` on the two jobs that publish to
the Security tab, and `packages: write` on the single job that pushes to GHCR. Nothing else in the
run can write a package, even if a step is compromised.

Pinning `TRIVY_VERSION` and `GITLEAKS_VERSION` to the versions installed on this laptop is what makes
the local numbers and the CI numbers directly comparable. A scanner that silently floats to `latest`
turns every result into a moving target.

### 3.3 The scanners are installed, not wrapped

```yaml
      - name: Install trivy
        run: |
          curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
            | sudo sh -s -- -b /usr/local/bin "v${TRIVY_VERSION}"
          trivy --version
```

There are marketplace actions for trivy and gitleaks. This pipeline installs the binaries directly
instead, for two reasons: the command in the workflow is then character-for-character the command you
can run on your laptop, and there is no third-party action in the supply chain of the job whose entire
purpose is to police the supply chain.

### 3.4 The image is built once and carried forward

`6 Docker Build` has no `actions/checkout`. It downloads the package that `1 Build` assembled, builds
from that, exports the result with `docker save | gzip`, and uploads it. `7 Image Scan`,
`8 Security Gate` and `9 Push to GHCR` each download that tarball and `docker load` it.

This matters more here than in an ordinary CI pipeline. If the gate scanned one image and the push
published a rebuild, the gate would be scanning something that no longer exists. Section 9 shows the
digest the gate approved and the digest running in Kubernetes, and they are the same string.

---

## 4. Stage 1 and 2 — Build, then Unit Test

`1 Build` installs the pinned runtime dependencies, byte-compiles the package, imports it and prints
its route table, then assembles `dist/` containing `app/`, `Dockerfile`, `requirements.txt` and a
`build-info.txt` stamped with the version, the commit and the run id. That directory is uploaded as
the artifact every later job builds from.

It also computes the two version strings the rest of the pipeline uses:

```bash
APP_VERSION="1.0.${GITHUB_RUN_NUMBER}+${GITHUB_SHA::7}"
IMAGE_TAG="1.0.${GITHUB_RUN_NUMBER}-${GITHUB_SHA::7}"
OWNER_REPO=$(echo "${GITHUB_REPOSITORY}" | tr '[:upper:]' '[:lower:]')
IMAGE_REPO="ghcr.io/${OWNER_REPO}/${IMAGE_NAME}"
```

Two separators and one lowercase conversion, each avoiding a failure that is otherwise only
discoverable on a runner. `+` is legal SemVer build metadata and illegal in a Docker tag, so the
image tag uses `-`. And `${GITHUB_REPOSITORY}` is `AmanYadav7015/devops-coursework` — GHCR rejects
an uppercase repository component, so it is lowercased before it becomes part of an image reference.

`2 Unit Test` lints and then runs the suite with coverage:

```text
Name              Stmts   Miss  Cover   Missing
TOTAL               124     10    92%
============================== 26 passed in 0.69s ==============================
```

---

## 5. Stage 3 — SAST

SAST reads source code and looks for dangerous constructs. It never runs the program, so it sees
every branch, including the ones the tests never reach.

### 5.1 bandit — the gating tool

Run locally against the insecure baseline first, because a scanner you have never seen produce a
finding is a scanner you do not understand:

```bash
bandit -r insecure-baseline/app -f screen
```

```text
>> Issue: [B324:hashlib] Use of weak MD5 hash for security. Consider usedforsecurity=False
   Severity: High   Confidence: High
   CWE: CWE-327 (https://cwe.mitre.org/data/definitions/327.html)
   Location: insecure-baseline/app/claims.py:96:13
95	    )
96	    digest = hashlib.md5((salt + payload).encode("utf-8")).hexdigest()
97	    return digest[:32]

--------------------------------------------------
>> Issue: [B602:subprocess_popen_with_shell_equals_true] subprocess call with shell=True identified, security issue.
   Severity: High   Confidence: High
   CWE: CWE-78 (https://cwe.mitre.org/data/definitions/78.html)
   Location: insecure-baseline/app/server.py:108:13
107	    host = request.args.get("host", "localhost")
108	    output = subprocess.check_output("getent hosts " + host, shell=True)
109	    return jsonify({"host": host, "resolved": output.decode("utf-8").strip()})

--------------------------------------------------
>> Issue: [B501:request_with_no_cert_validation] Call to requests with verify=False disabling SSL certificate checks, security issue.
   Severity: High   Confidence: High
   CWE: CWE-295 (https://cwe.mitre.org/data/definitions/295.html)
   Location: insecure-baseline/app/server.py:116:15
115	    upstream = requests.get(FX_ENDPOINT, verify=False)

--------------------------------------------------
>> Issue: [B201:flask_debug_true] A Flask app appears to be run with debug=True, which exposes the Werkzeug debugger and allows the execution of arbitrary code.
   Severity: High   Confidence: Medium
   CWE: CWE-94 (https://cwe.mitre.org/data/definitions/94.html)
   Location: insecure-baseline/app/server.py:121:4
121	    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5017")), debug=True)

Run metrics:
	Total issues (by severity):
		Low: 4
		Medium: 4
		High: 4
```

Twelve findings, four of them HIGH. The complete transcript is in
[`run-output/bandit-insecure-full.txt`](run-output/bandit-insecure-full.txt). The full list by id:

| Severity | Test | Location | What it means |
| --- | --- | --- | --- |
| HIGH | B324 | `claims.py:96` | MD5 over claim data — collisions are cheap, so two different claims can be made to share a fingerprint |
| HIGH | B602 | `server.py:108` | `shell=True` with a query parameter concatenated in — `?host=x;id` runs `id` |
| HIGH | B501 | `server.py:116` | `verify=False` turns TLS into obfuscation |
| HIGH | B201 | `server.py:121` | the Werkzeug debugger is a remote Python console |
| MEDIUM | B506 | `server.py:87` | `yaml.load` with the unsafe loader constructs arbitrary Python objects |
| MEDIUM | B307 | `server.py:99` | `eval()` on a request body |
| MEDIUM | B113 | `server.py:116` | outbound call with no timeout — one slow upstream exhausts the worker pool |
| MEDIUM | B104 | `server.py:121` | binds every interface |
| LOW | B311 | `claims.py:104` | `random` is predictable, so claim references are guessable |
| LOW | B105 | `server.py:22` | a default salt baked into the source |
| LOW | B404 | `server.py:2` | `subprocess` imported at all |
| LOW | B110 | `server.py:100` | `except Exception: pass` swallows the evidence |

The policy is **MEDIUM and above blocks**, expressed with bandit's own severity flag:

```yaml
      - name: Enforce the SAST policy
        working-directory: ${{ env.APP_DIR }}
        run: |
          echo "policy: any finding of MEDIUM severity or above blocks the pipeline"
          bandit -c security/bandit.yaml -r app -ll -q -f screen
          echo "SAST policy satisfied"
```

`-ll` is "report MEDIUM and above", and bandit exits `1` when it reports anything. The step before it
runs the same scan with `--exit-zero` and three output formats, so the full picture is always in the
log and in an artifact even when the gate is about to fail. Reporting and enforcing are deliberately
separate steps: the report must never be the thing that fails, or you lose the report exactly when
you need it.

**The gate firing for real** — run
[37630551638](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37630551638), commit
`da35a33`:

```bash
gh run view 37630551638 -R AmanYadav7015/devops-coursework --json jobs --jq '.jobs[]|"\(.name): \(.conclusion)"'
```

```text
1 Build: success
2 Unit Test: success
3 SAST (bandit): failure
3b SAST (CodeQL): success
4 SCA: skipped
5 Secret Scan: skipped
6 Docker Build: skipped
7 Container Image Scan: skipped
8 Security Gate: skipped
9 Push Image to GHCR: skipped
10 Deploy to Kubernetes: skipped
Pipeline summary: failure
```

Build green, 26 tests green, and nothing after SAST ran at all. The remediation was commit `d649c6f`
— SHA-256 for the fingerprint, `secrets.token_hex` for the reference, `yaml.safe_load`, the `eval`
and shell-out endpoints deleted outright, certificate validation and a 3-second timeout restored, and
the development server bound to `127.0.0.1` with the debugger off.

```bash
bandit -c security/bandit.yaml -r app -f screen
```

```text
Run metrics:
	Total issues (by severity):
		Undefined: 0
		Low: 0
		Medium: 0
		High: 0
```

And the same thing in CI on the green run:

```text
	Total lines of code: 176
	Total issues (by severity):
		Low: 0
		Medium: 0
		High: 0
policy: any finding of MEDIUM severity or above blocks the pipeline
SAST policy satisfied
```

### 5.2 CodeQL — the second opinion

The session material uses GitHub CodeQL for SAST. This pipeline runs it too, as a non-gating job
beside the chain, scoped to this lab:

```yaml
      - name: Initialize CodeQL
        uses: github/codeql-action/init@v3
        with:
          languages: python
          config: |
            paths:
              - labs/17-devsecops/app
```

On the insecure baseline it produced this, read back from the code-scanning API:

```bash
gh api "repos/AmanYadav7015/devops-coursework/code-scanning/alerts?ref=refs/heads/session-17-devsecops-ci&per_page=50" \
  --jq '.[]|"\(.rule.security_severity_level)\t\(.rule.id)\t\(.most_recent_instance.location.path):\(.most_recent_instance.location.start_line)"'
```

```text
high	py/weak-sensitive-data-hashing	labs/17-devsecops/app/claims.py:96
high	py/flask-debug	labs/17-devsecops/app/server.py:121
critical	py/command-line-injection	labs/17-devsecops/app/server.py:108
critical	py/unsafe-deserialization	labs/17-devsecops/app/server.py:87
critical	py/code-injection	labs/17-devsecops/app/server.py:99
medium	py/stack-trace-exposure	labs/17-devsecops/app/server.py:89
medium	py/stack-trace-exposure	labs/17-devsecops/app/server.py:80
medium	py/stack-trace-exposure	labs/17-devsecops/app/server.py:69
medium	py/stack-trace-exposure	labs/17-devsecops/app/server.py:49
```

Look at what CodeQL says that bandit does not. bandit flagged `shell=True` on line 108 because
`shell=True` is on a blocklist — it would say the same about `subprocess.check_output("date",
shell=True)`, which is harmless. CodeQL calls line 108 **`py/command-line-injection`, critical**,
because it tracked the taint: `request.args.get("host")` is attacker-controlled, it flows unmodified
into the command string, and the sink executes it. Same for `py/code-injection` on the `eval` and
`py/unsafe-deserialization` on the `yaml.load`. One tool pattern-matches; the other proves
reachability.

CodeQL also found four `py/stack-trace-exposure` alerts that bandit has no rule for. Three of them
were returning a validation exception's message to the caller, which was then changed to return a
dedicated `detail` attribute, and one was genuinely leaking a YAML parser error, which was removed.

bandit is the gate because it is fast (a few seconds), deterministic, and configurable with a
severity threshold. CodeQL is deeper and slower and its findings often need triage, so it reports
into the Security tab where a human reads them. Using both is not redundancy, as the table in section
11 shows.

---

## 6. Stage 4 — SCA

SAST reads code you wrote. SCA reads code you imported, which in a Python web service is roughly
98% of the bytes that end up running. Two tools run here, because they disagree in useful ways.

### 6.1 Two tools, two databases

The baseline `requirements.txt` on this branch pinned eight packages at versions that were current at
some point and are not current now.

```bash
pip-audit -r insecure-baseline/requirements-2022.txt --no-deps
```

```text
Found 75 known vulnerabilities in 9 packages
Name     Version   ID              Fix Versions
-------- --------- --------------- -------------
flask    2.2.2     PYSEC-2023-62   2.2.5,2.3.2
flask    2.2.2     PYSEC-2026-2151 3.1.3
werkzeug 2.2.2     PYSEC-2023-57   2.2.3
werkzeug 2.2.2     PYSEC-2023-221  2.3.8,3.0.1
werkzeug 2.2.2     CVE-2026-102598 3.1.9
jinja2   3.0.3     PYSEC-2026-1473 3.1.3
pyyaml   5.3.1     PYSEC-2021-142  5.4
requests 2.25.1    PYSEC-2023-74   2.31.0
urllib3  1.26.4    PYSEC-2021-108  1.26.5
urllib3  1.26.4    PYSEC-2026-4177 2.8.0
certifi  2022.12.7 PYSEC-2023-135  2023.7.22
gunicorn 20.0.4    PYSEC-2026-1434 22.0.0
idna     2.10      PYSEC-2024-60   3.7
```

(Abbreviated — the full 75-line table is in
[`run-output/pip-audit-vulnerable.txt`](run-output/pip-audit-vulnerable.txt).)

Note `idna 2.10`, which is not in that requirements file at all. It arrives as a dependency of
`requests 2.25.1`, and pip-audit reports it even under `--no-deps`. Reproduced against a one-line
file containing only `requests==2.25.1`:

```bash
printf 'requests==2.25.1\n' > probe/requirements.txt
pip-audit -r probe/requirements.txt --no-deps | grep -c idna
```

```text
4
```

That is worth knowing before you trust a clean report: `--no-deps` is not a promise that the tool
only looked at the lines you wrote.

trivy reads the same file and reports differently, because it carries severities:

```bash
trivy fs --scanners vuln --severity HIGH,CRITICAL insecure-baseline/requirements-2022.txt
```

```text
requirements.txt (pip)
======================
Total: 15 (HIGH: 14, CRITICAL: 1)

┌──────────┬────────────────┬──────────┬────────┬───────────────────┬────────────────┐
│ Library  │ Vulnerability  │ Severity │ Status │ Installed Version │ Fixed Version  │
├──────────┼────────────────┼──────────┼────────┼───────────────────┼────────────────┤
│ Flask    │ CVE-2023-30861 │ HIGH     │ fixed  │ 2.2.2             │ 2.3.2, 2.2.5   │
│ PyYAML   │ CVE-2020-14343 │ CRITICAL │        │ 5.3.1             │ 5.4            │
│ Werkzeug │ CVE-2023-25577 │ HIGH     │        │ 2.2.2             │ 2.2.3          │
│          │ CVE-2024-34069 │          │        │                   │ 3.0.3          │
│ certifi  │ CVE-2023-37920 │          │        │ 2022.12.7         │ 2023.7.22      │
│ gunicorn │ CVE-2024-1135  │          │        │ 20.0.4            │ 22.0.0         │
│          │ CVE-2024-6827  │          │        │                   │                │
│ urllib3  │ CVE-2021-33503 │          │        │ 1.26.4            │ 1.26.5         │
│          │ CVE-2023-43804 │          │        │                   │ 2.0.6, 1.26.17 │
│          │ CVE-2025-66418 │          │        │                   │ 2.6.0          │
│          │ CVE-2025-66471 │          │        │                   │                │
│          │ CVE-2026-21441 │          │        │                   │ 2.6.3          │
│          │ CVE-2026-44431 │          │        │                   │ 2.7.0          │
│          │ CVE-2026-97687 │          │        │                   │ 2.8.0          │
│          │ CVE-2026-97689 │          │        │                   │                │
└──────────┴────────────────┴──────────┴────────┴───────────────────┴────────────────┘
```

Real CVE ids worth naming, because each one is a different *kind* of supply-chain risk:

- **CVE-2020-14343** (PyYAML < 5.4, CRITICAL) — `yaml.load` with the full loader can construct
  arbitrary Python objects. This is the library-side half of the bandit B506 finding in section 5.1:
  the insecure baseline used the unsafe loader *and* pinned a PyYAML that made it worse.
- **CVE-2024-1135** and **CVE-2024-6827** (gunicorn < 22.0.0, HIGH) — HTTP request smuggling through
  mishandled `Transfer-Encoding`. This is in the WSGI server that fronts the application in
  production, so it is exploitable without touching application code at all.
- **CVE-2023-30861** (Flask < 2.2.5, HIGH) — a missing `Vary: Cookie` header lets a caching proxy
  serve one user's session cookie to another.
- **CVE-2024-34069** (Werkzeug < 3.0.3, HIGH) — the debugger PIN can be bypassed, which is the same
  exposure bandit's B201 warns about, reachable through a dependency rather than your own call.
- **CVE-2026-97687 / CVE-2026-97689** (urllib3 < 2.8.0, HIGH) — proxy TLS override and a chunk-parser
  memory exhaustion. These two come back in section 7: the `python:3.13-slim` base image ships a pip
  that vendors a vulnerable urllib3, so the same CVE ids appear in the *image* scan.

### 6.2 The dependency set that could not be installed at all

The very first push failed before any scanner ran, in `1 Build`:

```bash
gh run view 37630214394 -R AmanYadav7015/devops-coursework --log-failed
```

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    from app.server import app; print('routes:')
  File "/home/runner/work/devops-coursework/devops-coursework/labs/17-devsecops/app/server.py", line 4, in <module>
    import requests
  File "/opt/hostedtoolcache/Python/3.13.15/x64/lib/python3.13/site-packages/requests/__init__.py", line 43, in <module>
    import urllib3
  File "/opt/hostedtoolcache/Python/3.13.15/x64/lib/python3.13/site-packages/urllib3/__init__.py", line 11, in <module>
    from . import exceptions
  File "/opt/hostedtoolcache/Python/3.13.15/x64/lib/python3.13/site-packages/urllib3/exceptions.py", line 3, in <module>
    from .packages.six.moves.http_client import IncompleteRead as httplib_IncompleteRead
ModuleNotFoundError: No module named 'urllib3.packages.six.moves'
```

`urllib3 1.26.4` vendors `six`, and `six.moves` relies on import machinery that Python 3.12 removed.
The package installs and then cannot be imported.

This is the most under-appreciated argument for keeping dependencies current, and it is not a
security argument. **Deferred upgrades compound.** A patch you skip in year one is a patch you cannot
apply in year three without also moving the interpreter, which means also moving the base image,
which means a change too large to land under incident pressure. The pins were replaced with
`Flask==3.0.0 / Werkzeug==3.0.1 / Jinja2==3.1.3 / PyYAML==6.0.2 / requests==2.31.0 / urllib3==2.0.7 /
certifi==2023.5.7 / gunicorn==20.0.4` — still out of date, still carrying ten HIGH advisories, but
installable, so the pipeline could get far enough to prove the SCA gate.

### 6.3 The gate firing for real

Run [37630958303](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37630958303),
commit `d649c6f`:

```bash
gh run view 37630958303 -R AmanYadav7015/devops-coursework --json jobs --jq '.jobs[]|"\(.name): \(.conclusion)"'
```

```text
1 Build: success
2 Unit Test: success
3 SAST (bandit): success
3b SAST (CodeQL): success
4 SCA: failure
5 Secret Scan: skipped
6 Docker Build: skipped
7 Container Image Scan: skipped
8 Security Gate: skipped
9 Push Image to GHCR: skipped
10 Deploy to Kubernetes: skipped
Pipeline summary: failure
```

```text
Found 51 known vulnerabilities in 7 packages
Name     Version  ID              Fix Versions
-------- -------- --------------- -------------
flask    3.0.0    PYSEC-2026-2151 3.1.3
werkzeug 3.0.1    PYSEC-2026-2043 3.0.3
werkzeug 3.0.1    CVE-2026-102598 3.1.9
jinja2   3.1.3    PYSEC-2026-1474 3.1.4
```

SAST was green this time. The chain stopped one stage later, and nothing downstream consumed a
runner.

One behaviour worth calling out: pip-audit runs before trivy in that job, so when pip-audit exits
non-zero the trivy step is reported `skipped`:

```text
Audit the pinned dependencies with pip-audit: failure
Audit the pinned dependencies with trivy: skipped
```

That is the ordinary semantics of steps in a job, and it is a deliberate trade. Running every scanner
regardless and aggregating at the end gives a fuller report; stopping at the first failure gives a
shorter feedback loop. For a gate whose answer is binary, short wins.

Both steps also set `set -o pipefail`, because the command is piped into `tee`. Without it the shell
reports `tee`'s exit code, `tee` always succeeds, and the gate silently stops gating — a bug that
looks like a working pipeline.

### 6.4 Clean, after the bump

Commit `93abcae` moved every pin to the current release. Both tools, in the green CI run:

```text
No known vulnerabilities found
```

```text
┌──────────────────┬──────┬─────────────────┐
│      Target      │ Type │ Vulnerabilities │
├──────────────────┼──────┼─────────────────┤
│ requirements.txt │ pip  │        0        │
└──────────────────┴──────┴─────────────────┘
```

Note which version `urllib3` landed on: `2.8.0`, the fixed version for CVE-2026-97687 and
CVE-2026-97689. That specific choice is what lets the image gate in section 8 go green, because those
two CVEs are also present in the base image's vendored copy.

---

## 7. Stage 5 — Secret scanning

### 7.1 Proving the scanner fires, without committing a secret

The obvious way to demonstrate a secret scanner is to commit a secret. That is a bad habit to
practise even with fake values, because a repository's history is forever and the next person to copy
the pattern may not use a fake value. So the positive case was built in a throwaway directory outside
the repository, with randomly generated placeholders, and deleted afterwards.

```bash
cd /tmp/leak-demo
openssl genrsa -out config/deploy_key.pem 2048
git init -q . && git add -A && git commit -qm "throwaway fixture used only to prove the scanner fires"
gitleaks git . --no-banner -v
```

```text
Finding:     SLACK_WEBHOOK=https://hooks.slack.com/services/T0000****/B0000****/XXXX****
Secret:      https://hooks.slack.com/services/T0000****/B0000****/XXXX****
RuleID:      slack-webhook-url
Entropy:     3.400964
File:        config/ci.env
Line:        2
Commit:      178d8c0b2769e30b6405c0cd1470e5fba878b54d
Fingerprint: 178d8c0b2769e30b6405c0cd1470e5fba878b54d:config/ci.env:slack-webhook-url:2

Finding:     GITHUB_PAT=ghp_************************************
RuleID:      github-pat
Entropy:     4.771928
File:        config/ci.env
Line:        1

Finding:     AWS_SECRET_ACCESS_KEY = "****************************************"
RuleID:      generic-api-key
Entropy:     5.071928
File:        config/settings.py
Line:        4

Finding:     ...WS_ACCESS_KEY_ID = "AKIA****************
RuleID:      aws-access-token
Entropy:     3.621928
File:        config/settings.py
Line:        3

Finding:     -----BEGIN PRIVATE KEY-----
            <2048-bit RSA key body removed from this transcript>
RuleID:      private-key
Entropy:     6.032217
File:        config/deploy_key.pem
Line:        1

INF 1 commits scanned.
WRN leaks found: 5
```

Five rules fired on five different credential shapes. The values are masked in this document and in
[`run-output/gitleaks-detected.txt`](run-output/gitleaks-detected.txt); the directory itself has been
deleted. Interesting detail in that output: the AWS *secret* key was caught by `generic-api-key`
on entropy, not by an AWS-specific rule. Pattern rules catch the key id because `AKIA` is a fixed
prefix; the secret half is just 40 random characters, so only entropy analysis finds it.

### 7.2 The AWS documentation key is deliberately not detected

The brief for this lab suggested `AKIAIOSFODNN7EXAMPLE`, AWS's own documentation example. It does not
work, and finding out why is more useful than the demonstration would have been.

```bash
printf 'AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"\n' > probe-doc-key.txt
gitleaks dir probe-doc-key.txt --no-banner -v
```

```text
INF scanned ~43 bytes (43 bytes) in 1.07ms
INF no leaks found
```

```bash
printf 'AWS_ACCESS_KEY_ID = "AKIAQYLPMN5HGZZZ4RT7"\n' > probe-random-key.txt
gitleaks dir probe-random-key.txt --no-banner -v
```

```text
Finding:     ...WS_ACCESS_KEY_ID = "AKIAQYLPMN5HGZZZ4RT7
Secret:      AKIAQYLPMN5HGZZZ4RT7
RuleID:      aws-access-token
Entropy:     3.984184
Line:        1

WRN leaks found: 1
```

Two strings of identical shape — `AKIA` plus sixteen uppercase alphanumerics — and only one is
reported. gitleaks' default configuration allowlists the well-known documentation examples, because
they appear in millions of tutorials and flagging them would train everyone to ignore the tool. The
second string was generated from `/dev/urandom` and is not a credential for anything.

The lesson is about **allowlists as a first-class part of a scanner's behaviour**, not an
afterthought. A scanner with no allowlist produces noise, people stop reading it, and the one real
finding scrolls past. Which leads directly to the next two subsections, where this repository has to
make exactly that trade twice.

### 7.3 GitHub push protection blocked the very first push

Before any of this reached CI, GitHub refused the push outright:

```bash
git push -u origin session-17-devsecops-ci
```

```text
remote: error: GH013: Repository rule violations found for refs/heads/session-17-devsecops-ci.
remote:
remote: - GITHUB PUSH PROTECTION
remote:   —————————————————————————————————————————
remote:     Resolve the following violations before pushing again
remote:
remote:     - Push cannot contain secrets
remote:
remote:       —— Slack Incoming Webhook URL ————————————————————————
remote:        locations:
remote:          - commit: 2ba6167067488a0bc1ec750b7d078d6ef8ac4bf9
remote:            path: .github/workflows/session17-devsecops.yml:279
remote:
remote:        (?) To push, remove secret from commit(s) or follow this URL to allow the secret.
remote:        https://github.com/AmanYadav7015/devops-coursework/security/secret-scanning/unblock-secret/3KMvaiznzLsVNu9Ew05XWzvgyUf
remote:
To https://github.com/AmanYadav7015/devops-coursework.git
 ! [remote rejected] session-17-devsecops-ci -> session-17-devsecops-ci (push declined due to repository rule violations)
error: failed to push some refs to 'https://github.com/AmanYadav7015/devops-coursework.git'
```

The offending line was in the workflow's own positive-control step: a hardcoded placeholder Slack
webhook URL used to make gitleaks fire inside CI. The value was fake. GitHub's push protection does
not know that and should not guess, so it blocked the whole ref — not the file, the **ref**. Nothing
reached the server.

There is an unblock link, and clicking it would have been the wrong move. The right fix is to stop
the literal from existing in the file:

```bash
rand() { head -c 64 /dev/urandom | base32 | tr -d '=' | tr '[:lower:]' '[:upper:]' | head -c "$1"; }
HOOK_HOST="hooks.$(printf 'sla'; printf 'ck').com"
{
  printf 'AWS_ACCESS_KEY_ID = "AKIA%s"\n' "$(rand 16)"
  printf 'DEPLOY_HOOK = "https://%s/services/T%s/B%s/%s"\n' "$HOOK_HOST" "$(rand 8)" "$(rand 8)" "$(rand 24)"
} > "$CONTROL/planted.py"
```

The repository now contains no complete webhook URL; the runner assembles one at execution time from
fragments and random data. The push went through, and the control still works — here it is firing on
a GitHub-hosted runner:

```text
planted a randomly generated placeholder credential in /tmp/tmp.aokUG9O5Dv
RuleID:      aws-access-token
File:        /tmp/tmp.aokUG9O5Dv/planted.py
Fingerprint: /tmp/tmp.aokUG9O5Dv/planted.py:aws-access-token:1
RuleID:      slack-webhook-url
File:        /tmp/tmp.aokUG9O5Dv/planted.py
Fingerprint: /tmp/tmp.aokUG9O5Dv/planted.py:slack-webhook-url:2
WRN leaks found: 2
control passed, gitleaks exits non-zero when a secret is present
```

The step inverts the exit code deliberately:

```yaml
          if gitleaks dir "$CONTROL" --no-banner -v; then
            echo "::error::the secret scanner did not fire on a planted secret, the control failed"
            rm -rf "$CONTROL"
            exit 1
          fi
```

A security scan that always passes and a security scan that is silently broken look identical in a
log. This step is the difference. If a bad `-c` path, a mangled config or a failed download leaves
gitleaks unable to detect anything, the control fails the job before the real scan gets to report
"clean".

### 7.4 The real scans, and the one finding that had to be triaged

Two scans run against the repository: the working tree, and every commit that touched this lab.

```yaml
      - name: Scan the working tree
        run: |
          gitleaks dir "${APP_DIR}" -c "${APP_DIR}/security/gitleaks.toml" -i "${APP_DIR}" --no-banner -v \
            --report-format json --report-path "${APP_DIR}/reports/gitleaks-tree.json"

      - name: Scan every commit that touched this lab
        run: |
          gitleaks git . -c "${APP_DIR}/security/gitleaks.toml" -i "${APP_DIR}" --no-banner -v \
            --log-opts "--all -- ${APP_DIR}" \
            --report-format json --report-path "${APP_DIR}/reports/gitleaks-history.json"
```

`--log-opts "--all -- ${APP_DIR}"` scopes the history scan to commits touching this lab. Without it
the job scans the whole repository's history, which belongs to other sessions.

`security/gitleaks.toml` extends the default ruleset rather than replacing it, and adds two rules for
mistakes specific to this application:

```toml
[extend]
useDefault = true

[[rules]]
id = "claim-check-hardcoded-salt"
description = "Hardcoded fingerprint salt for claim-check-api"
regex = '''(?i)(claim_token_salt|token_salt|fallback_token)\s*[:=]\s*["'][^"'\n]{8,}["']'''
keywords = ["claim_token_salt", "token_salt", "fallback_token"]

[[rules]]
id = "claim-check-kubeconfig-blob"
description = "Base64 kubeconfig pasted into the repository"
regex = '''(?i)kube[_-]?config\s*[:=]\s*["']?[A-Za-z0-9+/]{200,}={0,2}'''
keywords = ["kubeconfig", "kube_config", "kube-config"]
```

The first rule did its job, and created the only genuinely interesting problem in this section. The
insecure baseline committed in `071ddd8` contained `FALLBACK_TOKEN = "claim-check-default-salt"`.
Commit `d649c6f` removed it. The working tree is clean. The history is not:

```bash
gitleaks git . -c labs/17-devsecops/security/gitleaks.toml --no-banner -v --log-opts "--all -- labs/17-devsecops"
```

```text
Finding:     FALLBACK_TOKEN = "claim-check-default-salt"
Secret:      FALLBACK_TOKEN
RuleID:      claim-check-hardcoded-salt
Entropy:     3.378783
File:        labs/17-devsecops/app/server.py
Line:        22
Commit:      071ddd8b91f90fbe3b05d3ebe85698b4f7e98cc3
Fingerprint: 071ddd8b91f90fbe3b05d3ebe85698b4f7e98cc3:labs/17-devsecops/app/server.py:claim-check-hardcoded-salt:22
Link:        https://github.com/AmanYadav7015/devops-coursework/blob/071ddd8b91f90fbe3b05d3ebe85698b4f7e98cc3/labs/17-devsecops/app/server.py#L22

INF 1 commits scanned.
WRN leaks found: 1
```

**Deleting the line is not enough.** The session material says this in a bullet point; here it is as
a job that fails until it is dealt with.

The decision was to accept it, recorded by fingerprint in `.gitleaksignore`:

```text
071ddd8b91f90fbe3b05d3ebe85698b4f7e98cc3:labs/17-devsecops/app/server.py:claim-check-hardcoded-salt:22
```

The justification, which belongs in the README rather than in the file: the value was never a
credential for anything. It was a default salt in a teaching application that has never been deployed
anywhere but a laptop, and the running deployment reads its salt from a Kubernetes Secret (section
9.2 shows `salt_configured: true` with a value generated from `/dev/urandom` at deploy time). The
fingerprint pins the acceptance to exactly one commit, one file, one rule and one line — reintroduce
the same string anywhere else and it fires again.

**If it had been a real credential, this would have been the wrong answer.** The sequence would have
been: revoke it first, rotate the replacement into a secret manager, then decide about history,
knowing that rewriting history on a pushed branch invalidates every clone and that anyone who fetched
the branch already has the value. Revocation is the only step that actually ends the exposure;
everything else is tidying.

With the baseline in place, both scans are clean on the green run:

```text
INF scanned ~17052 bytes (17.05 KB) in 10.1ms
INF no leaks found
```

```text
INF 5 commits scanned.
INF no leaks found
```

---

## 8. Stages 6, 7 and 8 — Docker build, image scan, security gate

### 8.1 Why the image is scanned separately from the dependencies

Section 6 proved `requirements.txt` was clean. That tells you nothing about the image, which also
contains a Debian userland, OpenSSL, a C library, and whatever the base image's `pip` bundles. The
image is what runs; the image is what gets scanned.

### 8.2 The base image comparison

Two images, identical application code and identical `requirements.txt`, differing only in the
Dockerfile. Both scanned with the same trivy 0.75.0 on the same machine.

```bash
trivy image --scanners vuln -f json session17-claim-check:base-bullseye | summarise
trivy image --scanners vuln -f json session17-claim-check:base-trixie   | summarise
```

| | **old base** `python:3.11-slim-bullseye`, single stage | **hardened** `python:3.13-slim`, two stages |
| --- | --- | --- |
| Operating system | Debian 11 (bullseye), end of life | Debian 13 (trixie), supported |
| Runs as | `uid=0(root)` | `uid=10001(claims)` |
| Package manager in runtime layer | pip, setuptools, wheel present | removed |
| CRITICAL | **7** | **0** |
| HIGH | **95** | **44** |
| MEDIUM | 165 | 58 |
| LOW | 144 | 61 |
| UNKNOWN | 6 | 2 |
| **Total findings** | **417** | **165** |
| **Fixable CRITICAL** | **2** | **0** |
| **Fixable HIGH** | **33** | **0** |
| **Fixable, all severities** | **104** | **0** |
| Image size | 51.1 MB (arm64 local) / 144 MB (amd64 CI) | 45.6 MB (arm64 local) / 123 MB (amd64 CI) |
| Gate verdict | **exit 1 — blocked** | **exit 0 — published** |

Those numbers are from this laptop (arm64). The GitHub runner (amd64) reported **exactly the same**
counts for both images — 7/95/165/144, 417 total, 104 fixable for the old base, and 0/44/58/61, 165
total, 0 fixable for the hardened one. That agreement is itself worth having: the architecture
changed and the vulnerability set did not, because these are package-version findings, not binary
analysis.

The blocking findings on the old base, in full:

```bash
trivy image --scanners vuln --ignore-unfixed --severity HIGH,CRITICAL session17-claim-check:base-bullseye
```

```text
### target: session17-claim-check:base-bullseye (debian 11.11)   type: debian  count: 32
  CRITICAL  CVE-2026-33845     libgnutls30            3.7.1-5+deb11u7 -> 3.7.1-5+deb11u10
  CRITICAL  CVE-2026-42010     libgnutls30            3.7.1-5+deb11u7 -> 3.7.1-5+deb11u10
  HIGH      CVE-2025-68973     gpgv                   2.2.27-2+deb11u2 -> 2.2.27-2+deb11u3
  HIGH      CVE-2025-32988     libgnutls30            3.7.1-5+deb11u7 -> 3.7.1-5+deb11u8
  HIGH      CVE-2025-32990     libgnutls30            3.7.1-5+deb11u7 -> 3.7.1-5+deb11u8
  HIGH      CVE-2026-33846     libgnutls30            3.7.1-5+deb11u7 -> 3.7.1-5+deb11u10
  HIGH      CVE-2026-3833      libgnutls30            3.7.1-5+deb11u7 -> 3.7.1-5+deb11u10
  HIGH      CVE-2026-42009     libgnutls30            3.7.1-5+deb11u7 -> 3.7.1-5+deb11u10
  HIGH      CVE-2026-40355     libgssapi-krb5-2       1.18.3-6+deb11u7 -> 1.18.3-6+deb11u8
  HIGH      CVE-2026-40356     libgssapi-krb5-2       1.18.3-6+deb11u7 -> 1.18.3-6+deb11u8
  HIGH      CVE-2026-40355     libk5crypto3           1.18.3-6+deb11u7 -> 1.18.3-6+deb11u8
  HIGH      CVE-2026-40356     libk5crypto3           1.18.3-6+deb11u7 -> 1.18.3-6+deb11u8
  HIGH      CVE-2026-40355     libkrb5-3              1.18.3-6+deb11u7 -> 1.18.3-6+deb11u8
  HIGH      CVE-2026-40356     libkrb5-3              1.18.3-6+deb11u7 -> 1.18.3-6+deb11u8
  HIGH      CVE-2026-40355     libkrb5support0        1.18.3-6+deb11u7 -> 1.18.3-6+deb11u8
  HIGH      CVE-2026-40356     libkrb5support0        1.18.3-6+deb11u7 -> 1.18.3-6+deb11u8
  HIGH      CVE-2025-6020      libpam-modules         1.4.0-9+deb11u1 -> 1.4.0-9+deb11u2
  HIGH      CVE-2025-6020      libpam-modules-bin     1.4.0-9+deb11u1 -> 1.4.0-9+deb11u2
  HIGH      CVE-2025-6020      libpam-runtime         1.4.0-9+deb11u1 -> 1.4.0-9+deb11u2
  HIGH      CVE-2025-6020      libpam0g               1.4.0-9+deb11u1 -> 1.4.0-9+deb11u2
  HIGH      CVE-2025-69421     libssl1.1              1.1.1w-0+deb11u3 -> 1.1.1w-0+deb11u5
  HIGH      CVE-2026-28387     libssl1.1              1.1.1w-0+deb11u3 -> 1.1.1w-0+deb11u7
  HIGH      CVE-2026-28388     libssl1.1              1.1.1w-0+deb11u3 -> 1.1.1w-0+deb11u7
  HIGH      CVE-2026-28389     libssl1.1              1.1.1w-0+deb11u3 -> 1.1.1w-0+deb11u7
  HIGH      CVE-2026-28390     libssl1.1              1.1.1w-0+deb11u3 -> 1.1.1w-0+deb11u7
  HIGH      CVE-2026-45447     libssl1.1              1.1.1w-0+deb11u3 -> 1.1.1w-0+deb11u8
  HIGH      CVE-2025-69421     openssl                1.1.1w-0+deb11u3 -> 1.1.1w-0+deb11u5
  HIGH      CVE-2026-28387     openssl                1.1.1w-0+deb11u3 -> 1.1.1w-0+deb11u7
  HIGH      CVE-2026-28388     openssl                1.1.1w-0+deb11u3 -> 1.1.1w-0+deb11u7
  HIGH      CVE-2026-28389     openssl                1.1.1w-0+deb11u3 -> 1.1.1w-0+deb11u7
  HIGH      CVE-2026-28390     openssl                1.1.1w-0+deb11u3 -> 1.1.1w-0+deb11u7
  HIGH      CVE-2026-45447     openssl                1.1.1w-0+deb11u3 -> 1.1.1w-0+deb11u8
### target: Python   type: python-pkg  count: 3
  HIGH      CVE-2024-6345      setuptools             65.5.1 -> 70.0.0
  HIGH      CVE-2025-47273     setuptools             65.5.1 -> 78.1.1
  HIGH      CVE-2026-24049     wheel                  0.45.1 -> 0.46.2
```

Thirty-five blocking findings, and not one of them is in code anyone on this project wrote. Six
distinct OpenSSL CVEs and five GnuTLS CVEs in the TLS stack of a service whose job includes making an
outbound HTTPS call. `CVE-2025-6020` in `libpam` is a local privilege escalation — which only matters
because that image runs as root, which is the second half of the problem.

The trivy warning in the gate's log names the real root cause:

```text
WARN	This OS version is no longer supported by the distribution	family="debian" version="11.11"
WARN	The vulnerability detection may be insufficient because security updates are not provided
```

There are no patches coming. The only remediation for an end-of-life base is to stop using it.

### 8.3 The three findings that `apt-get upgrade` could never have fixed

Look again at the `python-pkg` block: `setuptools 65.5.1` and `wheel 0.45.1`, found at
`/usr/local/lib/python3.11/site-packages`. They are not Debian packages and not application
dependencies. They are the Python build tooling that ships inside the `python:*-slim` base image.

The hardened Dockerfile removes them, because a runtime image has no business carrying a package
installer:

```dockerfile
RUN pip install --no-cache-dir --no-index --find-links=/tmp/wheels -r requirements.txt \
 && rm -rf /tmp/wheels \
 && rm -rf /usr/local/lib/python3.*/site-packages/pip \
           /usr/local/lib/python3.*/site-packages/pip-*.dist-info \
           /usr/local/lib/python3.*/site-packages/setuptools \
           /usr/local/lib/python3.*/site-packages/setuptools-*.dist-info \
           /usr/local/lib/python3.*/site-packages/pkg_resources \
           /usr/local/lib/python3.*/site-packages/wheel \
           /usr/local/lib/python3.*/site-packages/wheel-*.dist-info \
           /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.* \
           /usr/local/bin/wheel \
 && find /usr/local -name '__pycache__' -type d -prune -exec rm -rf {} +
```

That one `rm -rf` is why the hardened image reports **0 fixable findings** rather than 4. For the
record, the four it removes on a current base are `msgpack` and `urllib3` vendored inside `pip`, plus
`setuptools` — including CVE-2026-97687 and CVE-2026-97689, the same two urllib3 advisories the SCA
stage found in `requirements.txt`. The same CVE, in the same image, from two completely different
supply chains: one you control with a pin, one you control by deleting the component.

The rest of the hardening: two stages so the wheel-building toolchain never reaches the runtime layer,
a dedicated uid, and a `HEALTHCHECK`.

```text
id=sha256:a6213f2625f07a951f4e5a8b416dbc3522bb6b8b9746baa11bad130d06e7ed40 size=128620379 user=10001 entrypoint=[gunicorn --bind 0.0.0.0:5017 --workers 2 --access-logfile - app.server:app]
uid=10001(claims) gid=10001(claims) groups=10001(claims)
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
```

against the old build in the same step of the previous run:

```text
id=sha256:f80a175f9a7ecd70d147d8d9b52fcd392b5d188488d67b7cc51c05ac2a9815bf size=151256393 user= entrypoint=[python -m gunicorn --bind 0.0.0.0:5017 --workers 2 app.server:app]
uid=0(root) gid=0(root) groups=0(root)
PRETTY_NAME="Debian GNU/Linux 11 (bullseye)"
```

### 8.4 Detect and enforce are two different jobs

`7 Container Image Scan` reports everything and never fails. `8 Security Gate` decides.

```yaml
      - name: Enforce the image policy
        env:
          GATE_SEVERITY: ${{ inputs.gate_severity || 'HIGH,CRITICAL' }}
        run: |
          echo "policy: block on ${GATE_SEVERITY} findings that have a fix available"
          trivy image \
            --scanners vuln \
            --severity "${GATE_SEVERITY}" \
            --ignore-unfixed \
            --exit-code 1 \
            "${IMAGE_NAME}:${{ needs.build.outputs.image-tag }}"
          echo "gate passed, the image may be published"
```

`--exit-code 1` is what turns a report into a gate: trivy returns `1` when it finds anything matching
the filter, the step fails, the job fails, and `needs:` strands `9 Push Image` and `10 Deploy`.

`--ignore-unfixed` is the policy decision that makes the gate usable. The hardened image still carries
**44 HIGH** findings with no fix available from Debian. A gate that blocked on those would block
forever on every image in existence, and a gate that can never pass gets switched off within a week —
which is strictly worse than no gate, because now nobody is looking. Gating on *fixable* findings asks
an answerable question: is there an upgrade you have not taken? The 44 unfixed findings are not
ignored; they are in the `7 Image Scan` report, in the artifact, and uploaded as SARIF to the
repository's Security tab, where they are triaged rather than enforced.

`inputs.gate_severity || 'HIGH,CRITICAL'` means the threshold defaults correctly on a `push` (where
the `inputs` context is empty) and is operator-selectable on a `workflow_dispatch`.

### 8.5 The gate blocking a release, for real

This is the central capture of the whole lab. Run
[37631386888](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37631386888), commit
`93abcae` — code clean, dependencies clean, no secrets, image built from Debian 11:

```bash
gh run view 37631386888 -R AmanYadav7015/devops-coursework --json jobs --jq '.jobs[]|"\(.name): \(.conclusion)"'
```

```text
1 Build: success
2 Unit Test: success
3 SAST (bandit): success
3b SAST (CodeQL): success
4 SCA: success
5 Secret Scan: success
6 Docker Build: success
7 Container Image Scan: success
8 Security Gate: failure
9 Push Image to GHCR: skipped
10 Deploy to Kubernetes: skipped
Pipeline summary: failure
```

The image scan reported, in the same run:

```text
severity   all   fixable
CRITICAL      7        2
HIGH         95       33
MEDIUM      165       40
LOW         144       25
UNKNOWN       6        4
TOTAL       417      104
```

and the gate then refused it:

```text
policy: block on HIGH,CRITICAL findings that have a fix available
INFO	Detected OS	family="debian" version="11.11"
WARN	This OS version is no longer supported by the distribution	family="debian" version="11.11"
Total: 32 (HIGH: 30, CRITICAL: 2)
Total: 3 (HIGH: 3, CRITICAL: 0)
##[error]Process completed with exit code 1.
```

Seven stages green, and the image was still not published. Nothing reached GHCR, nothing reached
Kubernetes. That is the whole point of the lab in one job graph.

The remediation was commit `d61a7fa`, the two-stage Dockerfile on `python:3.13-slim`, and the same
job on the next run:

```text
policy: block on HIGH,CRITICAL findings that have a fix available
gate passed, the image may be published
```

```text
severity   all   fixable
CRITICAL      0        0
HIGH         44        0
MEDIUM       58        0
LOW          61        0
UNKNOWN       2        0
TOTAL       165        0
```

---

## 9. Stage 9 — Push to GHCR

```yaml
  push-image:
    name: 9 Push Image to GHCR
    needs:
      - build
      - security-gate
    if: inputs.skip_push != true
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
```

No registry credential was created for this lab. `secrets.GITHUB_TOKEN` is minted automatically for
each run, scoped to this repository, and expires when the run ends — and it only has write access to
packages because this one job asks for `packages: write`. The workflow-level default is
`contents: read`, so no other job in the run could publish anything.

The real push, from run [37633505564](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37633505564):

```text
Packages: write
Logging into ghcr.io...
Login Succeeded!
The push refers to repository [ghcr.io/amanyadav7015/devops-coursework/claim-check-api]
digest=ghcr.io/amanyadav7015/devops-coursework/claim-check-api@sha256:426e41e7c2f01d48d47214a714551cc134e0bd2153ae33993ed0d4387f93ea01
package reference : ghcr.io/amanyadav7015/devops-coursework/claim-check-api:1.0.7-1ecb2ab
package reference : ghcr.io/amanyadav7015/devops-coursework/claim-check-api:session17-latest
packages page     : https://github.com/AmanYadav7015/devops-coursework/pkgs/container/claim-check-api
```

And the package genuinely exists, pulled anonymously from this laptop with no credentials at all:

```bash
docker pull ghcr.io/amanyadav7015/devops-coursework/claim-check-api:1.0.5-d61a7fa
```

```text
Digest: sha256:12b1027d1eaf70a631fe38a94e5542c8d3023f7128af4d700b440b827a9de38b
Status: Downloaded newer image for ghcr.io/amanyadav7015/devops-coursework/claim-check-api:1.0.5-d61a7fa
```

That the anonymous pull works is itself a finding worth stating. GHCR packages published by Actions
inherit the repository's visibility, and this repository is public, so the image is public. The pull
needed no login. If the package were meant to be private, that would need checking explicitly rather
than assumed — "it is in a registry" and "it is not readable by strangers" are independent facts.

Two tags are pushed per run: the immutable `1.0.<run>-<sha7>`, and the moving `session17-latest`.
Deployments reference the immutable one; `session17-latest` exists only so that a human can grab the
most recent build without looking up a number.

One small honesty note on reproducibility. Commits `d61a7fa` and `1ecb2ab` have identical Dockerfiles
and identical application code — only the workflow changed between them — and yet they produced
different image digests (`sha256:12b1027d…` and `sha256:426e41e7…`). A `docker build` writes layer
timestamps, so the same inputs do not give you the same bytes. This is why a pipeline must carry the
built artifact forward rather than rebuild it: the thing the gate approved is identifiable only by
digest.

---

## 10. Stage 10 — Kubernetes

### 10.1 The honest limitation

The target cluster is minikube on this laptop. A GitHub-hosted runner is a disposable VM in Azure.
It has no route to `192.168.49.2`, and there is no configuration that would give it one short of a
tunnel or a self-hosted runner. Rather than assert that, the deploy job measures it:

```bash
curl -ksS --max-time 15 https://192.168.49.2:8443/version
```

```text
target cluster: minikube node 192.168.49.2:8443 on the student laptop
curl: (28) Connection timed out after 15002 milliseconds
curl exited 28, the GitHub-hosted runner has no route to a private RFC1918 address
the rollout is therefore performed from the laptop, see the README
```

The step fails the job if that curl ever *succeeds*, because a runner that can reach a private
address means something is misconfigured and the assumption in this README has gone stale.

What the deploy job does instead is everything that can honestly be done without the cluster. It
renders the manifests with the digest-bearing image reference, validates them offline, prints them,
prints the exact commands the cluster side will run, and uploads the rendered YAML as an artifact.

```text
rendered/namespace.yaml - Namespace hw17 is valid
rendered/service.yaml - Service claim-check-api is valid
rendered/deployment.yaml - Deployment claim-check-api is valid
Summary: 3 resources found in 3 files - Valid: 3, Invalid: 0, Errors: 0, Skipped: 0
```

```text
kubectl apply -f k8s/namespace.yaml
kubectl apply -f rendered/service.yaml
kubectl apply -f rendered/deployment.yaml
kubectl -n hw17 set image deployment/claim-check-api claim-check-api=ghcr.io/amanyadav7015/devops-coursework/claim-check-api:1.0.7-1ecb2ab
kubectl -n hw17 rollout status deployment/claim-check-api --timeout=120s
kubectl -n hw17 get deployment,pod,svc -o wide
```

Getting that validation to work offline took two failed runs and is worth recording, because the
obvious answer is wrong. `kubectl apply --dry-run=client` is not an offline validator:

```text
error validating "rendered/deployment.yaml": error validating data: failed to download openapi:
Get "http://localhost:8080/openapi/v2?timeout=32s": dial tcp [::1]:8080: connect: connection refused
```

Adding `--validate=false` removes the schema fetch and then fails one step earlier, in discovery:

```text
unable to recognize "rendered/deployment.yaml": Get "http://localhost:8080/api?timeout=32s":
dial tcp [::1]:8080: connect: connection refused
```

`--dry-run=client` means "do not persist the object", not "do not talk to the API server". kubectl
needs discovery to map `apps/v1 Deployment` to a resource before it can do anything at all. The tool
for schema validation without a cluster is `kubeconform`, which checks against the published
Kubernetes JSON schemas.

### 10.2 The deployment, running

The rollout was performed from this laptop against the shared minikube cluster, in namespace `hw17`,
using the image the pipeline gated and published.

```bash
kubectl apply -f rendered/namespace.yaml
kubectl -n hw17 create secret generic claim-check-salt --from-literal=salt="$(tr -dc 'a-f0-9' </dev/urandom | head -c 32)" --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f rendered/service.yaml
kubectl apply -f rendered/deployment.yaml
kubectl -n hw17 rollout status deployment/claim-check-api --timeout=180s
```

```text
namespace/hw17 created
secret/claim-check-salt created
service/claim-check-api created
deployment.apps/claim-check-api created
Waiting for deployment "claim-check-api" rollout to finish: 0 of 2 updated replicas are available...
Waiting for deployment "claim-check-api" rollout to finish: 1 of 2 updated replicas are available...
deployment "claim-check-api" successfully rolled out
```

```bash
kubectl -n hw17 get deployment,pod,svc -o wide
```

```text
NAME                              READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS        IMAGES                                                                  SELECTOR
deployment.apps/claim-check-api   2/2     2            2           11m   claim-check-api   ghcr.io/amanyadav7015/devops-coursework/claim-check-api:1.0.7-1ecb2ab   app=claim-check-api

NAME                                   READY   STATUS    RESTARTS   AGE   IP             NODE       NOMINATED NODE   READINESS GATES
pod/claim-check-api-5dc4f566b8-cq4h8   1/1     Running   0          14s   10.244.0.163   minikube   <none>           <none>
pod/claim-check-api-5dc4f566b8-rtgxf   1/1     Running   0          31s   10.244.0.162   minikube   <none>           <none>

NAME                      TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE   SELECTOR
service/claim-check-api   NodePort   10.105.34.120   <none>        5017:30170/TCP   11m   app=claim-check-api
```

The chain of custody, end to end:

```bash
kubectl -n hw17 get pods -o jsonpath='{range .items[*]}{.metadata.name}{"  "}{.status.containerStatuses[0].imageID}{"\n"}{end}'
```

```text
claim-check-api-5dc4f566b8-cq4h8  ghcr.io/amanyadav7015/devops-coursework/claim-check-api@sha256:426e41e7c2f01d48d47214a714551cc134e0bd2153ae33993ed0d4387f93ea01
claim-check-api-5dc4f566b8-rtgxf  ghcr.io/amanyadav7015/devops-coursework/claim-check-api@sha256:426e41e7c2f01d48d47214a714551cc134e0bd2153ae33993ed0d4387f93ea01
```

`sha256:426e41e7…` is the digest `9 Push Image to GHCR` printed in run 37633505564, which is the
image `8 Security Gate` approved, which is the tarball `6 Docker Build` produced. One artifact,
scanned once, gated once, published once, running now.

The pod security context survives admission:

```text
claim-check-api-5dc4f566b8-cq4h8  runAsUser=10001  readOnlyRootFilesystem=true  allowPrivilegeEscalation=false  capabilitiesDropped=["ALL"]
```

```bash
kubectl -n hw17 exec "$POD" -- id
kubectl -n hw17 exec "$POD" -- sh -c 'touch /srv/should-not-work'
```

```text
uid=10001(claims) gid=10001(claims) groups=10001(claims)
touch: cannot touch '/srv/should-not-work': Read-only file system
```

Non-root, immutable filesystem, no capabilities, no privilege escalation. The only writable path is
the `emptyDir` mounted at `/tmp`.

### 10.3 Over the wire

Per this environment's platform constraint, `192.168.49.2` is not reachable from macOS, because the
minikube node runs inside the Docker Desktop VM. Requests are made from inside the node.

```bash
minikube ssh -- "curl -s http://192.168.49.2:30170/health"
minikube ssh -- "curl -s http://192.168.49.2:30170/version"
minikube ssh -- "curl -s -X POST http://192.168.49.2:30170/claims/price -H 'Content-Type: application/json' -d '{\"employee\":\"asha\",\"category\":\"training\",\"amount\":25000,\"receipts\":3}'"
minikube ssh -- "curl -s -X POST http://192.168.49.2:30170/claims/batch -H 'Content-Type: application/json' -d '{\"claims\":[...]}'"
```

```text
{"service":"claim-check-api","status":"ok"}

{"commit":"1ecb2ab","salt_configured":true,"service":"claim-check-api","version":"1.0.7+1ecb2ab"}

{"category":"training","claimed":25000.0,"employee":"asha","fingerprint":"9e8b49c17391c2b1fd40512f1ec3040d","needs_approval":true,"reasons":["reimbursement above 10000.00 needs manager approval"],"reference":"CLM-F46C7552728B8BD4","reimbursed":22500.0}

{"count":2,"needs_approval":false,"total_reimbursed":4800.0}

the eval endpoint from the insecure baseline: HTTP 404
the shell-out endpoint from the insecure baseline: HTTP 404
```

```bash
curl -sS --max-time 8 http://192.168.49.2:30170/health
```

```text
curl: (28) Connection timed out after 8002 milliseconds
curl exit 28
```

Three things that output proves. `"commit":"1ecb2ab"` and `"version":"1.0.7+1ecb2ab"` come from
environment variables the deploy rendered from the pipeline's own outputs, so the running service can
name the build that produced it. `"salt_configured":true` means the container read the Kubernetes
Secret — that value is 32 random hex characters generated at deploy time and is not in the repository,
which is the fix for the gitleaks finding in section 7.4. And the two `404`s are the insecure
baseline's `eval` and shell-out endpoints, confirming the remediated code is what is actually serving
traffic, not just what is in the repository.

### 10.4 A rolling update

```bash
kubectl -n hw17 set image deployment/claim-check-api claim-check-api=ghcr.io/amanyadav7015/devops-coursework/claim-check-api:session17-latest
kubectl -n hw17 rollout status deployment/claim-check-api --timeout=180s
kubectl -n hw17 get rs -o 'custom-columns=NAME:.metadata.name,DESIRED:.spec.replicas,READY:.status.readyReplicas,IMAGE:.spec.template.spec.containers[0].image'
```

```text
deployment.apps/claim-check-api image updated
Waiting for deployment "claim-check-api" rollout to finish: 1 out of 2 new replicas have been updated...
Waiting for deployment "claim-check-api" rollout to finish: 1 old replicas are pending termination...
deployment "claim-check-api" successfully rolled out

NAME                         DESIRED   READY    IMAGE
claim-check-api-5b4bc857d4   0         <none>   ghcr.io/amanyadav7015/devops-coursework/claim-check-api:1.0.5-d61a7fa
claim-check-api-999895ddc    2         2        ghcr.io/amanyadav7015/devops-coursework/claim-check-api:session17-latest
```

`maxUnavailable: 0` with `maxSurge: 1` is why the service never dropped below two ready replicas
during the swap, and why `rollout status` reports "1 out of 2 new replicas have been updated" before
"1 old replicas are pending termination" — the new pod has to pass its readiness probe before the old
one is allowed to go. The old ReplicaSet is kept at zero replicas, which is what makes
`kubectl rollout undo` instant.

---

## 11. Every run on this branch

```bash
gh run list -R AmanYadav7015/devops-coursework --branch session-17-devsecops-ci --limit 12 \
  --json databaseId,conclusion,event,headSha,createdAt,displayTitle \
  --jq '.[]|"\(.databaseId)\t\(.event)\t\(.conclusion)\t\(.headSha[0:7])\t\(.createdAt)\t\(.displayTitle)"' | sort -t$'\t' -k5
```

```text
37630214394	push	failure	071ddd8	2026-10-07T13:39:15Z	Session 17: DevSecOps pipeline for the claim-check-api service
37630551638	push	failure	da35a33	2026-10-07T13:41:46Z	Pin dependencies that still install on Python 3.13
37630958303	push	failure	d649c6f	2026-10-07T13:44:47Z	Remediate every static analysis finding in the application
37631386888	push	failure	93abcae	2026-10-07T13:47:57Z	Bump every dependency past its advisory and baseline the history finding
37632022533	push	failure	d61a7fa	2026-10-07T13:52:41Z	Rebuild the image on a supported base and drop the build tooling from it
37632783425	push	failure	b197877	2026-10-07T13:58:11Z	Validate the manifests offline with kubeconform
37633505564	push	success	1ecb2ab	2026-10-07T14:03:20Z	Drop kubectl from the offline manifest check
37634173204	workflow_dispatch	success	1ecb2ab	2026-10-07T14:08:09Z	Session 17 DevSecOps Pipeline
```

| Run | Event | Result | Stopped at | What it proves |
| --- | --- | --- | --- | --- |
| [37630214394](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37630214394) | push | failure | `1 Build` | dependency pins old enough to be unimportable on a current interpreter |
| [37630551638](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37630551638) | push | failure | `3 SAST` | the SAST gate blocks on 4 HIGH and 4 MEDIUM findings |
| [37630958303](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37630958303) | push | failure | `4 SCA` | the SCA gate blocks on 51 advisories across 7 packages |
| [37631386888](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37631386888) | push | failure | `8 Security Gate` | **the image gate blocks a clean-code release and strands the push and the deploy** |
| [37632022533](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37632022533) | push | failure | `10 Deploy` | the gate passes and GHCR receives the image; `kubectl --dry-run=client` needs an API server |
| [37632783425](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37632783425) | push | failure | `10 Deploy` | `--validate=false` does not help either, discovery still needs a cluster |
| [37633505564](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37633505564) | push | **success** | — | all eleven stages, GHCR push, manifests validated offline |
| [37634173204](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37634173204) | workflow_dispatch | **success** | — | manual trigger, operator-selected gate threshold, publishing suppressed |

Three failures caused by a security gate doing its job, three caused by genuine engineering mistakes,
one green push and one green dispatch. Six fixes, each one a separate commit with the reason in the
message.

### 11.1 The green run's job graph in wall-clock time

```bash
gh run view 37633505564 -R AmanYadav7015/devops-coursework --json jobs --jq '.jobs[]|"\(.name)\t\(.conclusion)\t\(.startedAt)\t\(.completedAt)"'
```

```text
1 Build                   success  2026-10-07T14:03:24Z  2026-10-07T14:03:33Z
2 Unit Test               success  2026-10-07T14:03:37Z  2026-10-07T14:04:02Z
3b SAST (CodeQL)          success  2026-10-07T14:04:05Z  2026-10-07T14:05:05Z
3 SAST (bandit)           success  2026-10-07T14:04:06Z  2026-10-07T14:04:21Z
4 SCA                     success  2026-10-07T14:04:26Z  2026-10-07T14:04:49Z
5 Secret Scan             success  2026-10-07T14:04:52Z  2026-10-07T14:05:00Z
6 Docker Build            success  2026-10-07T14:05:05Z  2026-10-07T14:05:33Z
7 Container Image Scan    success  2026-10-07T14:05:37Z  2026-10-07T14:06:14Z
8 Security Gate           success  2026-10-07T14:06:19Z  2026-10-07T14:06:41Z
9 Push Image to GHCR      success  2026-10-07T14:06:45Z  2026-10-07T14:07:10Z
10 Deploy to Kubernetes   success  2026-10-07T14:07:13Z  2026-10-07T14:07:38Z
Pipeline summary          success  2026-10-07T14:07:43Z  2026-10-07T14:07:46Z
```

Total wall clock: **4 minutes 27 seconds** for eleven stages, four security scanners, an image build,
a registry push and a manifest validation. Read the timestamps and the chain is visible: every job
starts three to five seconds after the previous one finishes, because every job declares `needs:` on
the one before it. The only exception is `3b SAST (CodeQL)`, which starts at `14:04:05` alongside
`3 SAST (bandit)` at `14:04:06` and runs for a minute without holding anything up — it is the one job
not in the chain, and it is also the slowest, which is exactly why it is not in the chain.

Six of the ~4.5 minutes' overhead is scanner installation and database download. `8 Security Gate`
spends roughly 5 seconds of its 22 pulling a 120 MB trivy vulnerability database:

```text
INFO	[vulndb] Downloading artifact...	repo="mirror.gcr.io/aquasec/trivy-db:2"
119.53 MiB / 119.53 MiB [--------------------------------] 100.00% 40.25 MiB p/s 3.2s
```

Each job gets a fresh VM, so `7 Image Scan` and `8 Security Gate` download that database separately.
In a pipeline that ran often, that database would be cached.

### 11.2 Artifacts

```bash
gh api repos/AmanYadav7015/devops-coursework/actions/runs/37633505564/artifacts \
  --jq '.artifacts[]|"\(.name)\t\(.size_in_bytes)\t\(.expired)"'
```

```text
secret-scan-report	294	false
claim-check-api-image	47559133	false
rendered-k8s-manifests	1383	false
image-scan-report	133527	false
sast-bandit-report	1280	false
unit-test-report	1548	false
sca-report	446	false
claim-check-api-package	3846	false
```

Every scanner uploads its report with `if: always()`, so the evidence survives the job that failed.
A security finding you cannot retrieve after the build went red is not evidence.

### 11.3 The manual trigger

```bash
gh workflow run session17-devsecops.yml -R AmanYadav7015/devops-coursework \
  --ref session-17-devsecops-ci -f gate_severity=CRITICAL -f skip_push=true
```

```text
https://github.com/AmanYadav7015/devops-coursework/actions/runs/37634173204
```

Both inputs took effect. The gate ran at the operator's threshold:

```text
  GATE_SEVERITY: CRITICAL
policy: block on CRITICAL findings that have a fix available
gate passed, the image may be published
```

and publishing was suppressed by the job-level `if:`:

```text
8 security-gate            success
9 push-image               skipped
10 deploy                  skipped
```

`skipped` is not `failure`. The summary job's failure condition is
`contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled')`, so a deliberately
suppressed publish leaves the run green while a blocked one turns it red — which is the distinction
run 37631386888 and run 37634173204 demonstrate side by side.

---

## 12. Tool comparison

| | bandit | CodeQL | pip-audit | trivy fs | trivy image | gitleaks | GitHub push protection |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Category | SAST | SAST | SCA | SCA | image scan | secret scan | secret scan |
| Reads | your Python source | your Python source | `requirements.txt` | `requirements.txt` | image layers | files and git history | the push itself |
| Technique | AST pattern match | taint-tracking data flow | version vs advisory | version vs advisory | package inventory vs advisory | regex + entropy | server-side regex |
| Database | rules built into the tool | queries built into the tool | PyPI advisories + OSV | trivy-db (NVD, distro, GHSA) | same | rules in the tool + your TOML | GitHub partner patterns |
| Severity model | LOW/MEDIUM/HIGH | security-severity + CVSS | none, every advisory is equal | CRITICAL..UNKNOWN | CRITICAL..UNKNOWN | none, a match is a match | none |
| Fixable vs not | n/a | n/a | gives fix versions | `--ignore-unfixed` | `--ignore-unfixed` | n/a | n/a |
| Found here | 12 findings, 4 HIGH | 9 alerts, 3 critical | 75 then 51 advisories | 15 HIGH/CRITICAL | 417 findings, 104 fixable | 5 rules on the fixture | 1 webhook URL |
| Speed in this pipeline | 15s incl. install | 60s | 23s incl. install | same job | 37s incl. 120MB db | 8s incl. install | instant, at push time |
| Gates in this pipeline | yes, MEDIUM+ | no, reports to Security tab | yes, any advisory | yes, HIGH/CRITICAL | no, reports | yes, any match | yes, blocks the ref |
| Blind to | anything not in its rule set; dependencies | the OS; dependencies | severity, so it cannot be thresholded | code logic | code logic | a secret it has no pattern for | anything not a partner pattern |

The row that matters is the last one. **Every tool here is blind to most of what the others see.**
bandit cannot tell you that `urllib3` is out of date. pip-audit cannot tell you that OpenSSL in the
base image is unpatched. trivy cannot tell you that you called `eval()` on a request body. gitleaks
cannot tell you anything about any of that. Five scanners is not belt and braces, it is five
different questions, and the only reason the final image is defensible is that all five were asked.

Two secondary observations from running them side by side:

**pip-audit has no severity model, and that is a design constraint, not an oversight.** It reports
every advisory for a pinned version. That makes it an excellent "are you current?" check and a poor
basis for a threshold policy: you cannot say "block on HIGH" because it does not know what HIGH
means. trivy, reading the same file, knew that one of the fifteen findings was CRITICAL. This pipeline
uses pip-audit as an absolute gate (any advisory blocks) and trivy as a severity gate, and they agree
on the clean state.

**The same CVE can arrive by two routes.** CVE-2026-97687 and CVE-2026-97689 in urllib3 were found by
`trivy fs` in `requirements.txt`, fixed by pinning `urllib3==2.8.0` — and found again by
`trivy image` inside `pip`'s vendored copy in the base image, where no pin could reach them. One
needed a version bump; the other needed deleting pip from the runtime layer.

---

## 13. Security tool configuration

Four files, all under `security/`.

**`security/bandit.yaml`** keeps the SAST scan pointed at application code only. The test suite is
full of constructs that look alarming out of context, and `insecure-baseline/` is deliberately
insecure, so scanning either would produce findings that can never be fixed — the fastest way to
teach a team to ignore a scanner.

```yaml
exclude_dirs:
  - ./tests
  - ./insecure-baseline
  - ./.venv
  - ./run-output
```

**`security/gitleaks.toml`** extends the default ruleset with two project-specific rules (shown in
full in section 7.4) and allowlists three paths:

```toml
[allowlist]
description = "Documented fixtures: the deliberately insecure reference copy and the masked scanner transcripts"
paths = [
  '''(^|/)17-devsecops/run-output/''',
  '''(^|/)17-devsecops/insecure-baseline/''',
  '''(^|/)17-devsecops/README\.md$''',
]
```

`insecure-baseline/` exists to hold known-bad code. `run-output/` holds scanner transcripts, and a
transcript of a secret scanner finding a secret necessarily contains the string it found. This README
is on the list for the same reason, and it is the entry worth being uncomfortable about: allowlisting
a whole file means a credential genuinely pasted into it would be missed. The narrower alternative is
a `regexes` entry matching the one literal, but that would also suppress the history finding in
section 7.4 and defeat the point of triaging it by fingerprint. The trade taken here is to allowlist
by path and to keep the only live-code path — `app/` — covered with no exceptions at all.

**`security/trivy.yaml`** writes the image policy down in one place so it is reviewable as a file
rather than buried in a shell line:

```yaml
scan:
  scanners:
    - vuln
severity:
  - HIGH
  - CRITICAL
vulnerability:
  ignore-unfixed: true
exit-code: 1
```

**`security/.trivyignore`** is empty, deliberately. It exists so that accepting an image finding is a
reviewable diff against a file that is normally empty, rather than an ad-hoc flag added to a command
line. The hardened image has nothing to accept.

**`.gitleaksignore`** holds exactly one line — the fingerprint from section 7.4 — for the same reason.

---

## 14. Cleanup

Everything created on this machine has been removed. The branch, the runs and the published package
stay, because they are the deliverable.

```bash
kubectl delete namespace hw17
kubectl get ns hw17
```

```text
namespace "hw17" deleted
Error from server (NotFound): namespaces "hw17" not found
```

```bash
docker image rm session17-claim-check:base-bullseye session17-claim-check:base-trixie
docker image rm ghcr.io/amanyadav7015/devops-coursework/claim-check-api:1.0.5-d61a7fa
docker image rm python:3.9-slim python:3.9-slim-buster python:3.11-slim-bullseye python:3.13-slim-bookworm python:3.13-alpine
rm -rf /tmp/leak-demo
```

```text
Untagged: session17-claim-check:base-bullseye
Deleted: sha256:bc73d2c322fe6007d166036c53921938aacbf4d153092cc8382c14ce868795de
Untagged: session17-claim-check:base-trixie
Deleted: sha256:c69d8517421b337ded8c2baa73a958fef0df9d601b8b2f3771527fbb1f829fed
Untagged: ghcr.io/amanyadav7015/devops-coursework/claim-check-api:1.0.5-d61a7fa
Deleted: sha256:12b1027d1eaf70a631fe38a94e5542c8d3023f7128af4d700b440b827a9de38b

images matching session17*: 0
containers matching session17: 0
images matching claim-check*: 0
throwaway secret fixture removed: yes
```

The five base images pulled purely to produce the comparison in section 8.2
(`python:3.9-slim`, `python:3.9-slim-buster`, `python:3.11-slim-bullseye`,
`python:3.13-slim-bookworm`, `python:3.13-alpine`) were removed as well. The throwaway directory that
held the planted credentials in section 7.1 was deleted along with its git repository, so those
generated placeholder values exist nowhere on this machine or in any history.

Deliberately **not** cleaned up:

- the `session-17-devsecops-ci` branch and its eight runs — they are the evidence
- the GHCR package `ghcr.io/amanyadav7015/devops-coursework/claim-check-api` — the registry step
  would be unverifiable without it
- the run artifacts, which expire on their own (3 days for the 45 MB image tarball, 7 days for the
  reports)
- the code-scanning alerts in the repository's Security tab

No repository secret was created for this lab. The pipeline authenticates to GHCR with the
automatically-provided `GITHUB_TOKEN` and needs nothing else. The `main` branch was never touched,
and no `git push --force` was ever run.

---

## 15. Interview questions

**What is DevSecOps, in one sentence that is not a slogan?**
Moving security checks into the delivery pipeline so that they produce decisions rather than reports,
early enough that fixing a finding is cheap. The operative word is *decisions*: a scan that cannot
stop a release is a dashboard, not a control.

**What is the difference between SAST, SCA, secret scanning and image scanning?**
They read four different things. SAST reads source you wrote and looks for dangerous constructs. SCA
reads your dependency manifest and compares pinned versions against advisory databases. Secret
scanning reads files and git history for credential-shaped strings. Image scanning inventories the
built container — OS packages, language packages, anything installed — and compares that against
advisories. In this lab each one found something the other three could not: `eval()` on a request
body, ten HIGH advisories in pinned packages, a hardcoded salt still reachable in history, and 35
fixable HIGH/CRITICAL findings in a base image's TLS stack.

**What makes a gate a gate?**
A non-zero exit code that the pipeline is not allowed to ignore. `trivy image --exit-code 1
--severity HIGH,CRITICAL` returns 1, the step fails, the job fails, and every job with `needs:` on it
is skipped. Without `--exit-code`, trivy prints the same findings and returns 0, the pipeline goes
green, and the image ships. The two pipelines are indistinguishable until the day it matters.

**Why does this pipeline gate on `--ignore-unfixed`?**
Because the alternative never passes. The hardened image has 44 HIGH findings with no fix available
from Debian — not neglect, just advisories the distro has not patched. A gate that blocks on those
blocks every image forever, and a gate that can never pass is switched off within a week, which is
worse than no gate because the switching-off is silent. `--ignore-unfixed` asks an answerable
question: is there an upgrade you have not taken? The unfixed findings still go to the Security tab
for triage.

**Your scanner reports clean. What could still be wrong?**
Quite a lot. It could be clean because it is broken — wrong config path, failed install, a scan
pointed at an empty directory. That is why this pipeline runs a positive control that plants a
generated credential and fails the job if gitleaks does *not* find it. It could be clean because the
finding is not in its database yet; every advisory has a window between exploitation and publication.
It could be clean because the defect is a kind the tool has no rule for — bandit has no rule for
broken authorization logic, and never will. And it could be clean because an allowlist is hiding
something, which is why allowlist entries here are fingerprint-scoped and justified in writing.

**What do you do when a secret is committed?**
Revoke first. Everything else is tidying — the moment it was pushed, you must assume it is captured.
Rotate the replacement into a secret manager, check the provider's audit log for use, and only then
decide about history. Rewriting history on a pushed branch invalidates every clone and does not
retrieve the value from anyone who already fetched it. In this lab the finding was a default salt
that was never a credential for anything, so it was accepted by fingerprint in `.gitleaksignore` with
the reasoning written down in section 7.4 — and the running deployment now reads its salt from a
Kubernetes Secret generated at deploy time.

**Why not just run the scanners as a nightly job instead of in the pipeline?**
Nightly scanning tells you what is already in production. Pipeline scanning tells you what is about to
be. You want both, but only one of them can prevent the deploy. Run 37631386888 in this lab is the
case in point: seven stages green, and the release stopped before the registry.

**Why build the image once and carry it forward rather than rebuilding in each job?**
Because the gate must approve the exact bytes that get published. Commits `d61a7fa` and `1ecb2ab`
have byte-identical Dockerfiles and application code and produced different image digests, because
`docker build` writes layer timestamps. If `8 Security Gate` scanned one build and `9 Push` published
another, the gate's verdict would apply to an image that no longer exists. `6 Docker Build` exports
with `docker save | gzip`; every later job loads that tarball.

**Why does your pipeline use two SAST tools?**
Because they fail differently. bandit flagged `subprocess.check_output(..., shell=True)` because
`shell=True` is on a list; it would say the same about a hardcoded, harmless command. CodeQL called
the same line `py/command-line-injection` at critical severity, because it tracked `request.args` into
the sink and proved the data was attacker-controlled. CodeQL also found four stack-trace-exposure
alerts that bandit has no rule for. bandit gates because it is fast and deterministic; CodeQL reports
because it is deep and slow and its findings need a human.

**Everything was green and the gate still blocked the build. Is that a false positive?**
No, and the distinction matters. A false positive is a finding that is not real. Those 35 findings
were real CVEs in packages genuinely present in that image — six OpenSSL advisories, five GnuTLS, a
libpam local privilege escalation in an image running as root. What was true is that none of them were
in code anyone on the project wrote, which is precisely why nobody would have found them without
scanning the image. The fix was not a code change; it was changing the base image.

**How would you deploy to a real cluster from this pipeline?**
The deploy job here is honest about not being able to: a GitHub-hosted runner has no route to a laptop
on a private network, and the job proves that with a curl that times out after 15 seconds. For a real
target there are three options. A cloud cluster with a reachable API endpoint and a short-lived OIDC
credential, which is the right answer and avoids storing a kubeconfig at all. A self-hosted runner
inside the network, which trades credential risk for runner-maintenance risk. Or GitOps — the
pipeline commits the new digest to a manifest repository and an in-cluster agent pulls it, which means
no inbound access and no cluster credential in CI at all.

**What is still missing from this pipeline?**
Image signing and provenance. Nothing here proves the image in GHCR was produced by this workflow —
cosign with keyless signing plus a SLSA provenance attestation would close that. There is no SBOM
published alongside the image, so answering "are we affected by tomorrow's CVE?" means rescanning
rather than querying. DAST is absent: everything here is static, and nothing exercises the running
service for authorization flaws. And there is no policy admission control on the cluster side — the
pod security context is set in the manifest, but nothing stops someone applying a manifest without it.
