# Session 16 — CI/CD & GitHub Actions

**Official task:** Build a complete CI/CD demo project using GitHub Actions (refer to
`10-final-cicd-pipeline`). Must cover CI vs CD, the CI/CD pipeline, GitHub Actions, workflows, jobs,
steps, runners, secrets, artifacts, build, test, and pipeline execution. Deliverables: application
source code, Dockerfile, GitHub Actions workflow, CI pipeline, CD pipeline, evidence of a successful
pipeline execution, README.

Everything below was executed for real. The pipeline runs in a public repository on GitHub's hosted
runners, and every log excerpt in this document was pulled back out of those runs with `gh`.

| | |
| --- | --- |
| Repository | <https://github.com/AmanYadav7015/devops-coursework> |
| Branch | `session-16-ci` |
| Application | `labs/16-github-actions/` |
| Workflow | `.github/workflows/session16-cicd.yml` |
| Runner | `ubuntu-latest` (GitHub-hosted, image `ubuntu-24.04`, runner `2.337.0`) |

### Files in this folder

```text
README.md                        this walkthrough
app/fare.py                      pricing rules
app/server.py                    Flask HTTP surface
app/__init__.py                  service name
tests/test_fare.py               15 tests over the pricing rules
tests/test_server.py             5 tests over the HTTP endpoints
Dockerfile                       multi-stage build, non-root runtime
.dockerignore                    build-context exclusions
build.sh                         packaging script that produces dist/
requirements.txt                 runtime dependencies
requirements-dev.txt             test and lint dependencies
setup.cfg                        flake8 and pytest configuration
workflows/session16-cicd.yml     the pipeline (deployed at .github/workflows/ in the repository)
run-output/                      captured evidence from the real runs
  run1-37625624255.json          failed run, job conclusions
  run1-failure-excerpt.txt       the import error that failed the test matrix
  run2-37625820072.json          failed run, job conclusions
  run2-failure-excerpt.txt       the invalid Docker tag error
  run3-green-37626141643.json    the green push run
  run3-green-full.log            full 3036-line log of the green run
  run3-artifacts-api.txt         artifacts listed from the REST API
  artifact-download-proof.txt    artifacts downloaded back to this machine
  run4-dispatch-37626587346.json manual run with inputs
  run4-dispatch-full.log         full log of the manual run
  run5-dispatch-skipdeploy-37626942944.json  manual run with CD skipped
```

The official deliverable list asks for screenshots of a successful pipeline execution. Screenshots of
a terminal are not evidence — they cannot be grepped, diffed or verified. What is here instead is the
machine-readable equivalent: the complete run logs and the JSON job graphs, pulled from GitHub's API
with `gh` after the runs finished. Every block of output quoted below comes out of those files, and
the run URLs are live.

---

## 1. What this lab builds

The session material's `10-final-cicd-pipeline` demo is a three-job workflow (test, security-check,
build) around a calculator module. It stops at "artifact uploaded", and its README says the next step
is to connect the pipeline to a deployment target. This lab is that next step.

The application is `yatri-fare-api`: a small Flask service that prices a ride. It is deliberately
small but not a toy — it has pure business logic, an HTTP surface, 20 real unit tests, and a
multi-stage Dockerfile that produces an image small enough for a pipeline to build on every push.

```text
app/fare.py     pricing rules: base fare, per-km, per-minute, surge, night surcharge,
                coupons, minimum fare, splitting a fare between riders
app/server.py   Flask routes: GET /health, GET /version, POST /fare
tests/          20 tests: 15 over the pricing rules, 5 over the HTTP endpoints
Dockerfile      stage 1 builds wheels, stage 2 installs them and runs gunicorn as uid 10001
build.sh        packages app + requirements + Dockerfile + build-info.txt into dist/
```

---

## 2. CI vs CD, grounded in this pipeline

The textbook definitions are easy to recite and easy to forget. Here they are mapped onto jobs that
actually ran.

**CI — Continuous Integration — answers "is this commit safe to merge?"**

In this pipeline CI is the jobs `CI / Lint`, `CI / Test` (three times, once per Python version) and
`CI / Package`. They take the commit, check it, and produce one trustworthy build output. They never
touch anything outside the runner. If they fail, the only consequence is a red tick on the commit.

**CD — Continuous Delivery/Deployment — answers "can this build reach users?"**

In this pipeline CD is `CD / Build image` and `CD / Deploy to staging`. They take the output CI
already produced — not the source again — turn it into a container image, start it, and prove over
real HTTP that the running service answers correctly. This is the half that changes the world
outside the repository.

The distinction that matters in the YAML is this one line:

```yaml
  package:
    needs:
      - lint
      - test
```

CD jobs cannot start until CI jobs have concluded `success`. That is the gate. Run
`37625624255` below proves it: the test matrix failed, and `CI / Package`, `CD / Build image` and
`CD / Deploy to staging` were all reported `skipped` without consuming a runner.

The second distinction is *what flows between them*. `CD / Build image` has no `actions/checkout`
step at all. It cannot see the source tree. It builds from the artifact that `CI / Package` uploaded.
That is Continuous Delivery done properly: you deploy the thing you tested, not a fresh rebuild of
the branch that might have moved underneath you.

Continuous Delivery vs Continuous Deployment: this pipeline is *Delivery*. It produces a release
candidate, verifies it in a staging container, and stops. Making it *Deployment* would mean the last
step pushed to production without a human in the loop.

---

## 3. Vocabulary, mapped to this workflow file

| Term | In this pipeline |
| --- | --- |
| Workflow | `.github/workflows/session16-cicd.yml`, named `Session 16 CI/CD Pipeline` |
| Trigger / event | `push` to `session-16-ci` filtered by path, and `workflow_dispatch` with inputs |
| Job | `lint`, `test`, `package`, `docker-build`, `deploy`, `pipeline-summary` |
| Matrix | `test` fans out to three jobs, one per Python version |
| Step | e.g. `Run the unit test suite` inside the `test` job |
| Runner | `ubuntu-latest`, a fresh GitHub-hosted VM per job |
| Artifact | `test-report-py3.11/3.12/3.13`, `yatri-fare-api-package`, `yatri-fare-api-image` |
| Secret | `SESSION16_REGISTRY_USERNAME`, `SESSION16_REGISTRY_TOKEN`, `SESSION16_DEPLOY_WEBHOOK` |
| Dependency | `needs:` on `package`, `docker-build`, `deploy`, `pipeline-summary` |
| Condition | `if:` on the `deploy` job and on five individual steps |

A thing worth internalising: **each job is a different machine.** `CI / Test (py3.12)` and
`CD / Build image` share no disk. Anything one job needs from another has to be uploaded as an
artifact and downloaded again, or passed as a job `outputs` value. That constraint is the reason
artifacts exist, and this pipeline uses both mechanisms.

---

## 4. The workflow, walked through

Full file: [`workflows/session16-cicd.yml`](workflows/session16-cicd.yml) (deployed in the repository
at `.github/workflows/session16-cicd.yml` — a workflow only runs from that path).

### 4.1 Triggers — two of them, both exercised for real

```yaml
on:
  push:
    branches:
      - session-16-ci
    paths:
      - 'labs/16-github-actions/**'
      - '.github/workflows/session16-cicd.yml'
  workflow_dispatch:
    inputs:
      deploy_environment:
        description: 'Target environment for the CD stage'
        type: choice
        options:
          - staging
          - production
        default: staging
      skip_deploy:
        description: 'Stop after CI and skip the CD stage'
        type: boolean
        default: false
```

`push` with a `paths` filter means a change to an unrelated lab does not burn runner minutes here.
`workflow_dispatch` adds a **Run workflow** button in the Actions tab, with typed inputs that arrive
in the `inputs` context. Both trigger types were genuinely used — see sections 6 and 8.

A `schedule:` trigger is deliberately absent. Scheduled workflows only run from the repository's
default branch, so a `cron` entry on `session-16-ci` would sit in the file looking useful and never
fire once. Showing a trigger that cannot run is worse than not showing it.

### 4.2 Workflow-level settings

```yaml
permissions:
  contents: read

concurrency:
  group: session16-${{ github.ref }}
  cancel-in-progress: true

env:
  APP_DIR: labs/16-github-actions
  IMAGE_NAME: yatri-fare-api

defaults:
  run:
    shell: bash
```

`permissions: contents: read` narrows the automatic `GITHUB_TOKEN` to the minimum this pipeline
needs. The run log confirms it took effect:

```text
##[group]GITHUB_TOKEN Permissions
Contents: read
Metadata: read
##[endgroup]
```

`concurrency` cancels a previous in-flight run on the same ref when a new push arrives, so two pushes
in quick succession do not race each other to the same staging environment.

### 4.3 Job 1 and 2 — `lint` and `test` run in parallel

They declare no `needs:`, so GitHub schedules them simultaneously. The timestamps in section 6 show
all four jobs (`lint` plus three matrix legs) starting in the same second.

`test` uses a matrix:

```yaml
    strategy:
      fail-fast: false
      matrix:
        os:
          - ubuntu-latest
        python-version:
          - '3.11'
          - '3.12'
          - '3.13'
```

`fail-fast: false` matters. The default is `true`, which cancels the whole matrix the moment one leg
fails — convenient for saving minutes, useless when you want to know whether a failure is
version-specific. With it off, a 3.13-only break is immediately visible as "3.11 green, 3.12 green,
3.13 red".

Caching is explicit rather than delegated to `setup-python`, because the cache key is worth seeing:

```yaml
      - name: Restore pip cache
        id: pip-cache
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ matrix.python-version }}-${{ hashFiles('labs/16-github-actions/requirements*.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-${{ matrix.python-version }}-
```

The key contains a hash of the requirements files, so the cache invalidates itself exactly when the
dependency set changes and not before. The Python version is in the key because a wheel built for
3.11 is not usable by 3.13. `restore-keys` provides a prefix fallback: on a dependency bump you still
get yesterday's cache as a warm starting point instead of nothing.

### 4.4 Job 3 — `package` joins the matrix back together

```yaml
  package:
    needs:
      - lint
      - test
    outputs:
      app-version: ${{ steps.version.outputs.app_version }}
```

`needs: [lint, test]` waits for *all three* matrix legs plus the lint job. The job computes a version
string once and publishes it as a job output, which `docker-build` and `deploy` then read with
`needs.package.outputs.app-version`. That is the lightweight way to pass a *value* between jobs;
artifacts are for passing *files*.

It downloads every test report the matrix produced:

```yaml
      - name: Download every test report produced by the matrix
        uses: actions/download-artifact@v4
        with:
          pattern: test-report-py*
          path: labs/16-github-actions/incoming-reports
          merge-multiple: true
```

and then parses the JUnit XML to prove the files are real rather than just present.

### 4.5 Job 4 — `docker-build`, which never sees the source

```yaml
  docker-build:
    name: CD / Build image
    needs: package
    runs-on: ubuntu-latest
    steps:
      - name: Download the application package
        uses: actions/download-artifact@v4
        with:
          name: yatri-fare-api-package
          path: package
```

There is no `actions/checkout` in this job. The build context is the downloaded artifact. The image
is exported with `docker save | gzip` and uploaded, so the next job deploys the exact bytes that were
built here.

`compression-level: 0` on that upload is intentional: the tar is already gzipped, so asking the
upload action to zip it again costs CPU and saves nothing.

### 4.6 Job 5 — `deploy`, the CD half

```yaml
  deploy:
    name: CD / Deploy to staging
    needs:
      - package
      - docker-build
    if: github.ref == 'refs/heads/session-16-ci' && inputs.skip_deploy != true
```

A job-level `if:`. On a `push` event the `inputs` context is empty, so `inputs.skip_deploy` evaluates
to null, `null != true` is true, and the job runs. On a `workflow_dispatch` where the operator ticks
**Stop after CI**, it evaluates to false and the job is skipped — CI still runs, CD does not.

Secrets are read into `env:` and checked without ever being printed:

```yaml
        env:
          REGISTRY_USERNAME: ${{ secrets.SESSION16_REGISTRY_USERNAME }}
          REGISTRY_TOKEN: ${{ secrets.SESSION16_REGISTRY_TOKEN }}
          DEPLOY_WEBHOOK: ${{ secrets.SESSION16_DEPLOY_WEBHOOK }}
        run: |
          for name in REGISTRY_USERNAME REGISTRY_TOKEN DEPLOY_WEBHOOK; do
            value="${!name}"
            if [ -z "$value" ]; then
              echo "::error::secret $name is not configured on this repository"
              exit 1
            fi
            fingerprint=$(printf '%s' "$value" | sha256sum | cut -c1-12)
            echo "$name present, length ${#value}, sha256 prefix ${fingerprint}"
          done
```

The log gets a truncated SHA-256 of each value: enough to prove the secret arrived and to tell two
different values apart, never enough to reconstruct one. Passing secrets through `env:` rather than
interpolating `${{ secrets.X }}` straight into a shell string also avoids a shell-injection hole,
because the value never becomes part of the command text.

The deploy then loads the image, starts a container, polls `/health` until it answers, and runs three
real HTTP requests against it. Teardown is `if: always()` so a failed smoke test still leaves a clean
runner and still prints container logs.

### 4.7 Job 6 — `pipeline-summary`

```yaml
  pipeline-summary:
    needs:
      - lint
      - test
      - package
      - docker-build
      - deploy
    if: always()
```

`if: always()` makes this job run even when an upstream job failed or was skipped — without it,
`needs:` would skip it too and the pipeline would end silently. It prints every job's `result` and
then fails itself if any of them is `failure` or `cancelled`, which turns six independent job
statuses into one honest overall verdict.

---

## 5. Getting to green: the two failures on the way

The pipeline did not pass first time. Both failures are the kind that only show up on a runner, which
is exactly why they are worth recording.

### 5.1 Run 1 — the test matrix could not import the application

```bash
git push -u origin session-16-ci
gh run list -R AmanYadav7015/devops-coursework --branch session-16-ci --limit 5
```

```text
queued		Session 16: CI/CD pipeline for the yatri-fare-api service	Session 16 CI/CD Pipeline	session-16-ci	push	37625624255	9s	2026-10-07T13:04:05Z
```

```bash
gh run view 37625624255 -R AmanYadav7015/devops-coursework --log-failed
```

```text
CI / Test (py3.11) | 2026-10-07T13:04:19Z collecting ... collected 0 items / 2 errors
CI / Test (py3.11) | 2026-10-07T13:04:19Z ImportError while importing test module '/home/runner/work/devops-coursework/devops-coursework/labs/16-github-actions/tests/test_fare.py'.
CI / Test (py3.11) | 2026-10-07T13:04:19Z E   ModuleNotFoundError: No module named 'app'
CI / Test (py3.11) | 2026-10-07T13:04:19Z ImportError while importing test module '/home/runner/work/devops-coursework/devops-coursework/labs/16-github-actions/tests/test_server.py'.
CI / Test (py3.11) | 2026-10-07T13:04:19Z E   ModuleNotFoundError: No module named 'app'
CI / Test (py3.11) | 2026-10-07T13:04:19Z !!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
CI / Test (py3.11) | 2026-10-07T13:04:19Z ============================== 2 errors in 0.22s ===============================
CI / Test (py3.11) | 2026-10-07T13:04:19Z ##[error]Process completed with exit code 2.
```

The same error on all three Python versions. The cause is the purest "works on my machine" there is:
locally the tests had been run as `python -m pytest`, and the `-m` form puts the current directory on
`sys.path`. The workflow runs the bare `pytest` console script, which does not. The test modules could
not import `app`.

The fix is one line of configuration rather than `sys.path` surgery in the test files:

```ini
[tool:pytest]
testpaths = tests
pythonpath = .
addopts = -v
```

Verified locally by reproducing the *runner's* invocation exactly — bare `pytest`, not `python -m`:

```bash
cd labs/16-github-actions && pytest
```

```text
tests/test_server.py::test_fare_endpoint_rejects_an_invalid_trip PASSED  [100%]

============================== 20 passed in 0.09s ==============================
```

What this run also proved, for free, is that the gate works. Job conclusions for run `37625624255`:

```bash
gh run view 37625624255 -R AmanYadav7015/devops-coursework \
  --json conclusion,jobs --jq '.jobs[] | "\(.name): \(.conclusion)"'
```

```text
CI / Test (py3.11): failure
CI / Lint: success
CI / Test (py3.12): failure
CI / Test (py3.13): failure
CI / Package: skipped
Pipeline summary: failure
CD / Build image: skipped
CD / Deploy to staging: skipped
```

Three CI jobs red, and every downstream job `skipped` — not failed, *skipped*. `needs:` stopped them
before a runner was ever allocated. No broken build was packaged and nothing was deployed. That is CI
acting as a gate, observed rather than described.

### 5.2 Run 2 — CI green, the image build rejected the tag

With the import fixed, all five CI jobs passed and the pipeline got further than before, then died in
`CD / Build image`:

```bash
gh run view 37625820072 -R AmanYadav7015/devops-coursework --log-failed
```

```text
CD / Build image | 2026-10-07T13:06:30Z ERROR: failed to build: invalid tag "yatri-fare-api:1.0.2+95fd058": invalid reference format
CD / Build image | 2026-10-07T13:06:30Z ##[error]buildx failed with: ERROR: failed to build: invalid tag "yatri-fare-api:1.0.2+95fd058": invalid reference format
```

The version string was `1.0.${GITHUB_RUN_NUMBER}+${GITHUB_SHA::7}`. That is a perfectly legal SemVer
string — `+` introduces build metadata. It is not a legal Docker tag: tags allow word characters, `.`
and `-`, and nothing else. Two standards, one separator, one broken pipeline.

The fix keeps both and stops conflating them. The `package` job now publishes two outputs:

```yaml
    outputs:
      app-version: ${{ steps.version.outputs.app_version }}
      image-tag: ${{ steps.version.outputs.image_tag }}
```

```bash
VERSION="1.0.${GITHUB_RUN_NUMBER}+${GITHUB_SHA::7}"
IMAGE_TAG="1.0.${GITHUB_RUN_NUMBER}-${GITHUB_SHA::7}"
```

`app-version` stays SemVer and goes into `build-info.txt` and the `/version` endpoint; `image-tag`
is the registry-safe variant and is the only thing that ever touches `docker build -t`.

---

## 6. Run 3 — the green pipeline, end to end

```bash
git push origin session-16-ci
gh run view 37626141643 -R AmanYadav7015/devops-coursework
```

```text
✓ session-16-ci Session 16 CI/CD Pipeline · 37626141643
Triggered via push about 10 minutes ago

JOBS
✓ CI / Lint in 11s (ID 112808267448)
✓ CI / Test (py3.13) in 19s (ID 112808267633)
✓ CI / Test (py3.12) in 16s (ID 112808267666)
✓ CI / Test (py3.11) in 14s (ID 112808267793)
✓ CI / Package in 11s (ID 112808429772)
✓ CD / Build image in 31s (ID 112808532904)
✓ CD / Deploy to staging in 17s (ID 112808779290)
✓ Pipeline summary in 5s (ID 112808935942)
```

Run URL: <https://github.com/AmanYadav7015/devops-coursework/actions/runs/37626141643>
Commit: `ff4c890fc6cd98e07b5123736952414018cc66df`
Overall conclusion: **success**

### 6.1 The job graph in wall-clock time

```bash
gh run view 37626141643 -R AmanYadav7015/devops-coursework \
  --json jobs --jq '.jobs[] | "\(.name)\t\(.conclusion)\t\(.startedAt)\t\(.completedAt)"'
```

```text
CI / Lint               success  2026-10-07T13:08:12Z  2026-10-07T13:08:23Z
CI / Test (py3.13)      success  2026-10-07T13:08:12Z  2026-10-07T13:08:31Z
CI / Test (py3.12)      success  2026-10-07T13:08:12Z  2026-10-07T13:08:28Z
CI / Test (py3.11)      success  2026-10-07T13:08:12Z  2026-10-07T13:08:26Z
CI / Package            success  2026-10-07T13:08:34Z  2026-10-07T13:08:45Z
CD / Build image        success  2026-10-07T13:08:48Z  2026-10-07T13:09:19Z
CD / Deploy to staging  success  2026-10-07T13:09:22Z  2026-10-07T13:09:39Z
Pipeline summary        success  2026-10-07T13:09:43Z  2026-10-07T13:09:48Z
```

Read the timestamps, not the diagram. The first four jobs all start at `13:08:12` — that is four
separate virtual machines running at once, because none of them declares `needs:`. `CI / Package`
cannot start until `13:08:34`, three seconds after the slowest matrix leg finished at `13:08:31`.
From there everything is strictly serial, each job waiting on the one before. Total wall clock:
**1 minute 36 seconds** for lint, 60 test executions, packaging, an image build and a live
deployment.

### 6.2 Runner — a fresh, disposable machine

```text
runner os     : Linux (X64)
runner image  : ubuntu-latest
python        : Python 3.12.15
cpu cores     : 4
workspace     : /home/runner/work/devops-coursework/devops-coursework
```

From the job setup block:

```text
Current runner version: '2.337.0'
Operating System: Ubuntu 24.04.5 LTS
Runner Image: ubuntu-24.04 / Version: 20261004.327.1
Cloud: Azure / Region: westus
```

`ubuntu-latest` currently resolves to `ubuntu-24.04` on a 4-core Azure VM. Every job in the run got
its own one, and every one of them was destroyed afterwards.

### 6.3 Cache — a real hit, from the previous run

Run 1 found nothing (`Cache not found for input keys: Linux-pip-3.11-a3a5c8adb...`) because the cache
was empty. Run 2's test jobs populated it on the way out:

```text
CI / Test (py3.11) | 2026-10-07T13:05:54Z Cache saved with key: Linux-pip-3.11-a3a5c8adb68fa7ecbb63a699b6d8e740c42d189567bf6ae26489173e52d15171
CI / Test (py3.13) | 2026-10-07T13:05:55Z Cache saved with key: Linux-pip-3.13-a3a5c8adb68fa7ecbb63a699b6d8e740c42d189567bf6ae26489173e52d15171
CI / Test (py3.12) | 2026-10-07T13:05:56Z Cache saved with key: Linux-pip-3.12-a3a5c8adb68fa7ecbb63a699b6d8e740c42d189567bf6ae26489173e52d15171
```

Run 3 read it straight back:

```text
Cache hit for: Linux-pip-3.12-a3a5c8adb68fa7ecbb63a699b6d8e740c42d189567bf6ae26489173e52d15171
Received 4303485 of 4303485 (100.0%), 9.8 MBs/sec
Cache Size: ~4 MB (4303485 B)
Cache restored successfully
Cache restored from key: Linux-pip-3.12-a3a5c8adb68fa7ecbb63a699b6d8e740c42d189567bf6ae26489173e52d15171
pip cache restored, dependency install should be fast
```

That last line comes from a step guarded by `if: steps.pip-cache.outputs.cache-hit == 'true'`. On
run 1 it did not appear at all, because the log said `Cache not found for input keys: ...`. Same
workflow, different behaviour, driven by a step condition reading another step's output.

### 6.4 Test — 20 tests, three interpreters

```text
collecting ... collected 20 items

tests/test_fare.py::test_validate_trip_accepts_a_normal_trip PASSED      [  5%]
tests/test_fare.py::test_validate_trip_rejects_bad_input[0-10-1.0] PASSED [ 10%]
tests/test_fare.py::test_validate_trip_rejects_bad_input[-3-10-1.0] PASSED [ 15%]
tests/test_fare.py::test_validate_trip_rejects_bad_input[5-0-1.0] PASSED [ 20%]
tests/test_fare.py::test_validate_trip_rejects_bad_input[5--1-1.0] PASSED [ 25%]
tests/test_fare.py::test_validate_trip_rejects_bad_input[5-10-0.5] PASSED [ 30%]
tests/test_fare.py::test_compute_fare_matches_the_published_formula PASSED [ 35%]
tests/test_fare.py::test_compute_fare_applies_surge_multiplier PASSED    [ 40%]
tests/test_fare.py::test_compute_fare_adds_night_surcharge PASSED        [ 45%]
tests/test_fare.py::test_compute_fare_never_drops_below_minimum PASSED   [ 50%]
tests/test_fare.py::test_apply_coupon_is_case_insensitive PASSED         [ 55%]
tests/test_fare.py::test_apply_coupon_rejects_unknown_code PASSED        [ 60%]
tests/test_fare.py::test_apply_coupon_rejects_negative_amount PASSED     [ 65%]
tests/test_fare.py::test_split_fare_shares_sum_back_to_the_total PASSED  [ 70%]
tests/test_fare.py::test_split_fare_rejects_zero_riders PASSED           [ 75%]
tests/test_server.py::test_health_endpoint PASSED                        [ 80%]
tests/test_server.py::test_version_endpoint_reports_build_metadata PASSED [ 85%]
tests/test_server.py::test_fare_endpoint_prices_a_trip PASSED            [ 90%]
tests/test_server.py::test_fare_endpoint_applies_a_coupon_and_splits PASSED [ 95%]
tests/test_server.py::test_fare_endpoint_rejects_an_invalid_trip PASSED  [100%]

- generated xml file: /home/runner/work/devops-coursework/devops-coursework/labs/16-github-actions/reports/junit-py3.12.xml -
================================ tests coverage ================================
_______________ coverage: platform linux, python 3.12.15-final-0 _______________

Name              Stmts   Miss  Cover
-------------------------------------
app/__init__.py       1      0   100%
app/fare.py          36      0   100%
app/server.py        28      3    89%
-------------------------------------
TOTAL                65      3    95%
Coverage XML written to file reports/coverage-py3.12.xml
============================== 20 passed in 0.29s ==============================
```

That is the 3.12 leg. 3.11 and 3.13 ran the same 20 tests simultaneously on their own runners, giving
60 test executions in under 20 seconds of wall clock.

The coverage summary step only ran on the 3.12 leg, because of
`if: matrix.python-version == '3.12'` — publishing the same coverage number three times would be
noise.

### 6.5 Package — the matrix artifacts come back together

```text
Found 3 artifact(s)
Filtering artifacts by pattern 'test-report-py*'
Preparing to download the following artifacts:
Starting download of artifact to: .../labs/16-github-actions/incoming-reports
SHA256 digest of downloaded artifact is 8927500808ee0781c583551f669f8b9da5976a0625711b942aa058fa42d08eb7
Artifact download completed successfully.
SHA256 digest of downloaded artifact is 773894482ebbcf100cb7eb7440b263d12dd63e7854359fa763ffa2f5efcf5dab
Artifact download completed successfully.
SHA256 digest of downloaded artifact is b7b84f1b55abeb5f58d52ef1203c30a0d804c85d7a56a25c92790c9df14cc4f7
Artifact download completed successfully.
Total of 3 artifact(s) downloaded
```

```text
files received from the test matrix:
total 32
drwxr-xr-x 2 runner runner 4096 Oct  7 13:08 .
drwxr-xr-x 5 runner runner 4096 Oct  7 13:08 ..
-rw-r--r-- 1 runner runner 3375 Oct  7 13:08 coverage-py3.11.xml
-rw-r--r-- 1 runner runner 3375 Oct  7 13:08 coverage-py3.12.xml
-rw-r--r-- 1 runner runner 3375 Oct  7 13:08 coverage-py3.13.xml
-rw-r--r-- 1 runner runner 2299 Oct  7 13:08 junit-py3.11.xml
-rw-r--r-- 1 runner runner 2299 Oct  7 13:08 junit-py3.12.xml
-rw-r--r-- 1 runner runner 2299 Oct  7 13:08 junit-py3.13.xml
incoming-reports/junit-py3.11.xml: tests=20 failures=0 errors=0 time=0.222s
incoming-reports/junit-py3.12.xml: tests=20 failures=0 errors=0 time=0.295s
incoming-reports/junit-py3.13.xml: tests=20 failures=0 errors=0 time=0.406s
```

Six files that were written on three different machines, parsed on a fourth. The last three lines are
the job reading the XML itself rather than trusting the filenames.

Then the build:

```text
resolved version 1.0.3+ff4c890
resolved image tag 1.0.3-ff4c890
[build] packaging yatri-fare-api version=1.0.3+ff4c890 commit=ff4c890fc6cd98e07b5123736952414018cc66df
[build] contents of dist
total 28
-rw-r--r-- 1 runner runner  955 Oct  7 13:08 Dockerfile
drwxr-xr-x 2 runner runner 4096 Oct  7 13:08 app
-rw-r--r-- 1 runner runner  158 Oct  7 13:08 build-info.txt
-rw-r--r-- 1 runner runner   45 Oct  7 13:08 requirements.txt
-rw-r--r-- 1 runner runner 2051 Oct  7 13:08 yatri-fare-api-1.0.3+ff4c890.tar.gz
```

### 6.6 Build image — from the artifact, not from the branch

The job's first step downloads the package and prints what it got. Note that this is a machine with
no checkout and no git history:

```text
total 28
-rw-r--r-- 1 runner runner  955 Oct  7 13:08 Dockerfile
drwxr-xr-x 2 runner runner 4096 Oct  7 13:08 app
-rw-r--r-- 1 runner runner  158 Oct  7 13:08 build-info.txt
-rw-r--r-- 1 runner runner   45 Oct  7 13:08 requirements.txt
-rw-r--r-- 1 runner runner 2051 Oct  7 13:08 yatri-fare-api-1.0.3+ff4c890.tar.gz
service=yatri-fare-api
version=1.0.3+ff4c890
commit=ff4c890fc6cd98e07b5123736952414018cc66df
built_at=2026-10-07T13:08:40Z
builder=github-actions-37626141643
```

Buildx then builds the two-stage image:

```text
#1 [internal] booting buildkit
#1 pulling image moby/buildkit:buildx-stable-1 5.3s done
#1 DONE 5.7s
#5 [internal] load build context
#5 transferring context: 3.20kB done
#6 [builder 1/4] FROM docker.io/library/python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f
#7 [builder 2/4] WORKDIR /wheels
#8 [runtime 2/6] WORKDIR /srv
```

Result:

```text
REPOSITORY       TAG             IMAGE ID       CREATED         SIZE
yatri-fare-api   1.0.3-ff4c890   e420db78baeb   3 seconds ago   127MB
id=sha256:e420db78baebc42e2313c6c5ba7e66d5a55a1ab71509a6a82e7f2f243847fc67 size=126703766 user=10001
```

`user=10001` is worth pointing at: the image runs as a non-root uid, which is one line in the
Dockerfile and removes an entire class of container escape from the deployment.

Exported and uploaded:

```text
-rw-r--r-- 1 runner runner 49M Oct  7 13:09 image.tar.gz
Artifact yatri-fare-api-image.zip successfully finalized. Artifact ID 11484411957
Artifact yatri-fare-api-image has been successfully uploaded! Final size is 51135677 bytes. Artifact ID is 11484411957
```

### 6.7 Deploy — the CD half, with real HTTP

```text
event        : push
ref          : refs/heads/session-16-ci
version      : 1.0.3+ff4c890
image tag    : 1.0.3-ff4c890
```

Secrets arrive and are verified without being printed:

```text
REGISTRY_USERNAME present, length 12, sha256 prefix 85fa1d784efe
REGISTRY_TOKEN present, length 39, sha256 prefix 7b2ccdbe2890
DEPLOY_WEBHOOK present, length 42, sha256 prefix c14bf91863aa
```

The image artifact is downloaded and loaded into this runner's Docker daemon — the same bytes the
previous job produced, as the identical image ID confirms:

```text
Total of 1 artifact(s) downloaded
Loaded image: yatri-fare-api:1.0.3-ff4c890
REPOSITORY       TAG             IMAGE ID       CREATED          SIZE
yatri-fare-api   1.0.3-ff4c890   e420db78baeb   25 seconds ago   127MB
```

`e420db78baeb` in `CD / Build image` and `e420db78baeb` here. Not a rebuild — the artifact.

The container starts and is polled until it answers:

```text
service answered after 2 attempt(s)
```

Then three real HTTP requests against the running release candidate:

```text
GET /health
{"service":"yatri-fare-api","status":"ok"}

GET /version
{"commit":"ff4c890fc6cd98e07b5123736952414018cc66df","service":"yatri-fare-api","version":"1.0.3+ff4c890"}

POST /fare
{"currency":"INR","per_rider":[137.82,137.82],"total":275.64}
```

The `/version` response is the proof that the whole chain stayed consistent: the commit SHA and the
version string that the `package` job computed are being served back by a container that was built in
a different job and started in a third.

The release announcement derives the webhook host from the secret without printing the secret:

```text
would POST the release notification to host staging.yatri.invalid
release 1.0.3+ff4c890 published by the CI service account
```

Container logs confirm the requests hit a real gunicorn:

```text
[2026-10-07 13:09:33 +0000] [1] [INFO] Starting gunicorn 23.0.0
[2026-10-07 13:09:33 +0000] [7] [INFO] Booting worker with pid: 7
[2026-10-07 13:09:33 +0000] [8] [INFO] Booting worker with pid: 8
172.17.0.1 - - [07/Oct/2026:13:09:34 +0000] "GET /health HTTP/1.1" 200 43 "-" "curl/8.5.0"
172.17.0.1 - - [07/Oct/2026:13:09:34 +0000] "GET /health HTTP/1.1" 200 43 "-" "curl/8.5.0"
172.17.0.1 - - [07/Oct/2026:13:09:34 +0000] "GET /version HTTP/1.1" 200 107 "-" "curl/8.5.0"
172.17.0.1 - - [07/Oct/2026:13:09:35 +0000] "POST /fare HTTP/1.1" 200 62 "-" "curl/8.5.0"
```

Teardown, guarded by `if: always()`:

```text
session16-yatri-staging
Untagged: yatri-fare-api:1.0.3-ff4c890
Deleted: sha256:e420db78baebc42e2313c6c5ba7e66d5a55a1ab71509a6a82e7f2f243847fc67
```

### 6.8 Pipeline summary

```bash
gh run view 37626141643 -R AmanYadav7015/devops-coursework \
  --json jobs --jq '.jobs[] | select(.name=="Pipeline summary") | {conclusion, steps: [.steps[] | {name, conclusion}]}'
```

```text
{
  "conclusion": "success",
  "steps": [
    {"conclusion": "success", "name": "Set up job"},
    {"conclusion": "success", "name": "Print every job result"},
    {"conclusion": "skipped", "name": "Fail the pipeline when any stage failed"},
    {"conclusion": "success", "name": "Report an all-green pipeline"},
    {"conclusion": "success", "name": "Complete job"}
  ]
}
```

The failure step was skipped and the success step ran — the two `if:` expressions are mutually
exclusive and both evaluated correctly.

---

## 7. The artifacts genuinely exist

A pipeline that *claims* to produce artifacts is easy to write. Here they are, queried from the API
after the run finished:

```bash
gh api repos/AmanYadav7015/devops-coursework/actions/runs/37626141643/artifacts \
  --jq '.artifacts[] | "\(.name)\t\(.size_in_bytes)\t\(.expired)\t\(.created_at)"'
```

```text
test-report-py3.12                                  1395      false  2026-10-07T13:08:25Z
test-report-py3.11                                  1395      false  2026-10-07T13:08:23Z
yatri-fare-api-image                                51135677  false  2026-10-07T13:09:14Z
AmanYadav7015~devops-coursework~KUAU06.dockerbuild  32013     false  2026-10-07T13:09:16Z
yatri-fare-api-package                              4941      false  2026-10-07T13:08:41Z
test-report-py3.13                                  1399      false  2026-10-07T13:08:28Z
```

Five of those are declared in the workflow. The sixth, `*.dockerbuild`, is uploaded automatically by
`docker/build-push-action@v6` — it is the build record that `docker buildx history` can replay.

Pulled back down to this laptop:

```bash
gh run download 37626141643 -R AmanYadav7015/devops-coursework -n yatri-fare-api-package -D package
gh run download 37626141643 -R AmanYadav7015/devops-coursework -n test-report-py3.12 -D report-3.12
find . -type f | sort
```

```text
./package/Dockerfile
./package/app/__init__.py
./package/app/fare.py
./package/app/server.py
./package/build-info.txt
./package/requirements.txt
./package/yatri-fare-api-1.0.3+ff4c890.tar.gz
./report-3.12/coverage-py3.12.xml
./report-3.12/junit-py3.12.xml
```

```bash
cat package/build-info.txt
```

```text
service=yatri-fare-api
version=1.0.3+ff4c890
commit=ff4c890fc6cd98e07b5123736952414018cc66df
built_at=2026-10-07T13:08:40Z
builder=github-actions-37626141643
```

```bash
head -c 300 report-3.12/junit-py3.12.xml
```

```text
<?xml version="1.0" encoding="utf-8"?><testsuites name="pytest tests"><testsuite name="pytest" errors="0" failures="0" skipped="0" tests="20" time="0.295" timestamp="2026-10-07T13:08:24.132079+00:00" hostname="runnervmmprz5">
```

Real files, real JUnit XML, naming the runner VM that produced them. `build-info.txt` carries the run
id, so any artifact can be traced back to the exact pipeline execution that created it — which is the
entire point of an artifact in a release process.

Both downloads are saved under [`run-output/`](run-output/) alongside the full 3036-line run log.

---

## 8. Trigger two — `workflow_dispatch`, run twice for real

The push trigger is proven by every run above. The second trigger type was exercised directly.

### 8.1 Manual run with inputs

```bash
gh workflow run session16-cicd.yml -R AmanYadav7015/devops-coursework \
  --ref session-16-ci -f deploy_environment=production -f skip_deploy=false
```

```text
https://github.com/AmanYadav7015/devops-coursework/actions/runs/37626587346
```

```bash
gh run view 37626587346 -R AmanYadav7015/devops-coursework --json event,conclusion,url
```

```text
{"event":"workflow_dispatch","conclusion":"success","url":"https://github.com/AmanYadav7015/devops-coursework/actions/runs/37626587346"}
```

```bash
gh run view 37626587346 -R AmanYadav7015/devops-coursework --json jobs --jq '.jobs[]|"\(.name): \(.conclusion)"'
```

```text
CI / Lint: success
CI / Test (py3.11): success
CI / Test (py3.12): success
CI / Test (py3.13): success
CI / Package: success
CD / Build image: success
CD / Deploy to staging: success
Pipeline summary: success
```

Same workflow, no commit, started by a human instead of a push. The deploy job's log shows the
`inputs` context arriving:

```text
event        : workflow_dispatch
ref          : refs/heads/session-16-ci
version      : 1.0.4+ff4c890
image tag    : 1.0.4-ff4c890
manual dispatch requested environment production
```

That last line comes from a step carrying `if: github.event_name == 'workflow_dispatch'`. In the push
run `37626141643` the same step is reported as `skipped`:

```text
{"conclusion": "skipped", "name": "Report the manual dispatch inputs"}
```

One workflow file, two behaviours, decided by the event that started it.

The version number also moved from `1.0.3` to `1.0.4` on the same commit `ff4c890`, because it is
derived from `GITHUB_RUN_NUMBER`. Two runs of the same source produce two distinguishable builds,
which is what you want for traceability and what you must avoid for reproducibility — a real pipeline
usually resolves this by tagging immutably on the commit SHA and treating the run number as metadata
only.

### 8.2 Manual run that stops before CD

The dispatch form has a second input, `skip_deploy`. Ticking it should run all of CI and none of CD.

```bash
gh workflow run session16-cicd.yml -R AmanYadav7015/devops-coursework \
  --ref session-16-ci -f deploy_environment=staging -f skip_deploy=true
```

```text
https://github.com/AmanYadav7015/devops-coursework/actions/runs/37626942944
```

```bash
gh run view 37626942944 -R AmanYadav7015/devops-coursework
```

```text
✓ session-16-ci Session 16 CI/CD Pipeline · 37626942944
Triggered via workflow_dispatch about 1 minute ago

JOBS
✓ CI / Test (py3.13) in 15s (ID 112811038575)
✓ CI / Lint in 11s (ID 112811039196)
✓ CI / Test (py3.11) in 17s (ID 112811039351)
✓ CI / Test (py3.12) in 16s (ID 112811039352)
✓ CI / Package in 11s (ID 112811195240)
✓ CD / Build image in 29s (ID 112811299295)
✓ Pipeline summary in 3s (ID 112811541468)
- CD / Deploy to staging in 0s (ID 112811543636)
```

`CD / Deploy to staging` is `skipped`, in `0s`, from the job-level condition:

```yaml
    if: github.ref == 'refs/heads/session-16-ci' && inputs.skip_deploy != true
```

The summary job, which runs under `if: always()`, saw the skip and still reported the pipeline green:

```text
lint         : success
test         : success
package      : success
docker-build : success
deploy       : skipped
every stage succeeded, the artifact is ready for promotion
```

That distinction matters. `skipped` is not `failure`: the summary's failure condition is
`contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled')`, so a deliberately
skipped CD stage does not turn the build red, while a genuinely broken one does — as run
`37625624255` showed.

### 8.3 Five runs on this branch

```bash
gh run list -R AmanYadav7015/devops-coursework --branch session-16-ci --limit 10
```

```text
completed	success	Session 16 CI/CD Pipeline	Session 16 CI/CD Pipeline	session-16-ci	workflow_dispatch	37626942944	1m16s	2026-10-07T13:14:28Z
completed	success	Session 16 CI/CD Pipeline	Session 16 CI/CD Pipeline	session-16-ci	workflow_dispatch	37626587346	1m52s	2026-10-07T13:11:40Z
completed	success	Use a registry-safe image tag for the container build	Session 16 CI/CD Pipeline	session-16-ci	push	37626141643	1m40s	2026-10-07T13:08:08Z
completed	failure	Fix test collection on the runner by setting pytest pythonpath	Session 16 CI/CD Pipeline	session-16-ci	push	37625820072	1m5s	2026-10-07T13:05:35Z
completed	failure	Session 16: CI/CD pipeline for the yatri-fare-api service	Session 16 CI/CD Pipeline	session-16-ci	push	37625624255	26s	2026-10-07T13:04:05Z
```

| Run | Event | Conclusion | What it proves |
| --- | --- | --- | --- |
| [37625624255](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37625624255) | `push` | failure | the `needs:` gate stops CD when CI fails |
| [37625820072](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37625820072) | `push` | failure | CI green, image build rejected an invalid tag |
| [37626141643](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37626141643) | `push` | **success** | the full CI/CD pipeline, end to end |
| [37626587346](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37626587346) | `workflow_dispatch` | **success** | manual trigger with inputs, full pipeline |
| [37626942944](https://github.com/AmanYadav7015/devops-coursework/actions/runs/37626942944) | `workflow_dispatch` | **success** | manual trigger, CD skipped by `if:` |

---

## 9. Secrets

Three repository secrets were created for this lab. All three hold placeholder values — there is no
real registry, no real webhook, and nothing in this repository can be used to authenticate against
anything.

```bash
gh secret set SESSION16_REGISTRY_USERNAME -R AmanYadav7015/devops-coursework --body "..."
gh secret set SESSION16_REGISTRY_TOKEN    -R AmanYadav7015/devops-coursework --body "..."
gh secret set SESSION16_DEPLOY_WEBHOOK    -R AmanYadav7015/devops-coursework --body "..."
gh secret list -R AmanYadav7015/devops-coursework
```

```text
SESSION16_DEPLOY_WEBHOOK	2026-10-07T13:03:44Z
SESSION16_REGISTRY_TOKEN	2026-10-07T13:03:43Z
SESSION16_REGISTRY_USERNAME	2026-10-07T13:03:42Z
```

`gh secret list` shows names and timestamps and no values, because GitHub cannot show you the values
either. Once written, a secret is write-only: you may overwrite or delete it, never read it back.

How they are consumed, and the three habits that matter:

```yaml
      - name: Verify the deployment credentials
        env:
          REGISTRY_USERNAME: ${{ secrets.SESSION16_REGISTRY_USERNAME }}
          REGISTRY_TOKEN: ${{ secrets.SESSION16_REGISTRY_TOKEN }}
          DEPLOY_WEBHOOK: ${{ secrets.SESSION16_DEPLOY_WEBHOOK }}
        run: |
          for name in REGISTRY_USERNAME REGISTRY_TOKEN DEPLOY_WEBHOOK; do
            value="${!name}"
            if [ -z "$value" ]; then
              echo "::error::secret $name is not configured on this repository"
              exit 1
            fi
            fingerprint=$(printf '%s' "$value" | sha256sum | cut -c1-12)
            echo "$name present, length ${#value}, sha256 prefix ${fingerprint}"
          done
```

1. **Into `env:`, never inline into the command.** `${{ secrets.X }}` written directly inside a `run:`
   string is textually substituted into the script before bash sees it, so a value containing a quote
   or a `$(...)` becomes executable code. Through `env:` it is just a variable.
2. **Never echo the value.** The log gets a length and a 12-character SHA-256 prefix: enough to prove
   the secret arrived and to distinguish it from a different value, useless for reconstructing it.
3. **Fail loudly when it is missing.** `::error::` plus `exit 1` turns an unset secret into a red job
   instead of a deploy that quietly authenticates as nobody.

Real output from the green run:

```text
REGISTRY_USERNAME present, length 12, sha256 prefix 85fa1d784efe
REGISTRY_TOKEN present, length 39, sha256 prefix 7b2ccdbe2890
DEPLOY_WEBHOOK present, length 42, sha256 prefix c14bf91863aa
```

And in the release step, the webhook host is derived from the secret rather than printed:

```text
would POST the release notification to host staging.yatri.invalid
```

GitHub also masks secret values automatically — the checkout step's log shows `token: ***` where the
`GITHUB_TOKEN` would be. Masking is a safety net, not a strategy: it only catches the exact string.
A base64-encoded secret, or one printed one character per line, walks straight past it.

---

## 10. Cleanup

Everything this lab created locally has been removed. The branch and its pipeline runs stay, because
they are the deliverable.

Local preflight container and image, created before the first push to check the Dockerfile:

```bash
docker rm -f session16-preflight && docker image rm session16-yatri-preflight:local
```

```text
session16-preflight
Untagged: session16-yatri-preflight:local
Deleted: sha256:b9bcfb73083abebcd14ac3ffe2204eedc3a2d4d153ee59653c7377b96871dfb1
```

Nothing is left behind on this machine:

```bash
docker ps -a --filter name=session16 --format '{{.Names}}' | wc -l
docker image ls 'session16*' --format '{{.Repository}}:{{.Tag}}' | wc -l
docker image ls 'yatri-fare-api*' --format '{{.Repository}}:{{.Tag}}' | wc -l
```

```text
containers named session16: 0
images session16*: 0
images yatri-fare-api*: 0
```

The runners clean themselves up: the `deploy` job's teardown step is `if: always()`, and the whole VM
is destroyed after the job regardless.

```text
session16-yatri-staging
Untagged: yatri-fare-api:1.0.3-ff4c890
Deleted: sha256:e420db78baebc42e2313c6c5ba7e66d5a55a1ab71509a6a82e7f2f243847fc67
```

Deliberately **not** cleaned up:

- the `session-16-ci` branch and its four pipeline runs — they are the evidence for this homework
- the three `SESSION16_*` repository secrets — the pipeline fails without them, and they contain
  placeholder values of no use to anyone
- the run artifacts, which expire on their own (7 days for the reports and the package, 3 days for
  the 49 MB image tarball)

The `main` branch was never touched.

---

## 11. Interview questions

**What is the difference between CI and CD?**
CI validates a commit: build it, lint it, test it, and produce one trusted artifact. Its blast radius
is the runner. CD takes that already-validated artifact and moves it towards users: image build,
release, deploy, smoke test. In this pipeline the split is literal — `lint`, `test` and `package` are
CI, `docker-build` and `deploy` are CD, and the `needs:` edge between `package` and `docker-build` is
the gate.

**Continuous Delivery versus Continuous Deployment?**
Delivery means every commit that passes CI is *releasable* and a human decides when to release.
Deployment means it goes to production automatically with no human step. This pipeline is Delivery:
it builds a release candidate and verifies it in staging, and stops there.

**What is a workflow, a job, a step and an action?**
A workflow is one YAML file under `.github/workflows/` triggered by events. A job is a set of steps
that run on one runner; jobs run in parallel unless `needs:` orders them. A step is one command or
one action inside a job. An action is a reusable unit someone packaged — `actions/checkout@v4`,
`docker/build-push-action@v6` — invoked with `uses:`.

**Why does the pipeline need artifacts? Can't job B just read job A's files?**
No. Every job gets a fresh runner with its own filesystem. Nothing survives the end of a job except
what you upload. `actions/upload-artifact` stores files on GitHub, `actions/download-artifact` pulls
them into another job. For small values — a version string — job `outputs` are lighter than an
artifact.

**What does `needs:` actually do?**
It creates a dependency edge and, by default, requires the upstream job to conclude `success`. If it
fails, the dependent job is `skipped`, not failed, and never occupies a runner. It also makes the
upstream job's `outputs` available as `needs.<job>.outputs.<name>`.

**A job must run even when an earlier job failed. How?**
Give it `if: always()`. Without it a `needs:` job inherits the skip. Related expressions:
`if: success()` (the default), `if: failure()`, `if: cancelled()`. The reporting job here uses
`if: always()` plus `contains(needs.*.result, 'failure')` to decide the pipeline's final verdict.

**What is a matrix build and when would you turn off `fail-fast`?**
A matrix expands one job definition into N parallel jobs over a set of variables — here three Python
versions. `fail-fast: true` (the default) cancels the whole matrix on the first failure, which saves
minutes but hides whether the break is version-specific. Turn it off when the per-combination result
is the information you wanted.

**What is a runner? GitHub-hosted versus self-hosted?**
The machine that executes a job. GitHub-hosted runners are clean, ephemeral VMs provisioned per job
and thrown away afterwards — free for public repositories, with a large preinstalled toolchain.
Self-hosted runners are machines you own: use them for private network access, specialist hardware,
large caches, or when hosted minutes get expensive. The trade-off is that you now own patching,
isolation, and the risk that one job leaves state behind for the next.

**How do secrets work and how do you avoid leaking them?**
Repository or environment secrets are encrypted at rest, injected into the runner at step level, and
their values are masked as `***` anywhere they appear in logs. The practical rules: pass them through
`env:` rather than interpolating `${{ secrets.X }}` into a shell string (that is a shell-injection
hole and it bakes the value into the command line); never `echo` them; never pass them to forks; keep
`permissions:` minimal. Masking is a safety net, not a strategy — a base64-encoded or
character-by-character leak slips straight past it.

**Can you read a secret back out of GitHub?**
No. You can overwrite or delete it. The value is write-only once saved.

**Why does `CD / Build image` have no checkout step?**
Because it must build the artifact CI produced, not a fresh copy of the branch. Re-cloning would
reintroduce the risk of building something nobody tested — the branch may have moved since the test
job ran. Building from the downloaded package makes "you deploy what you tested" structural rather
than aspirational.

**How do you make a pipeline fast?**
Parallelise independent work (lint and test have no `needs:`, so they start together); cache
dependencies with a key derived from the lock or requirements file; filter triggers by path so
unrelated changes do not run the pipeline; use `concurrency` with `cancel-in-progress` so superseded
runs are cancelled; keep images small with multi-stage builds.

**What makes a good cache key?**
It should change exactly when the cached content should change. `${{ runner.os }}-pip-${{ matrix.python-version }}-${{ hashFiles('**/requirements*.txt') }}`
changes on OS, interpreter, or dependency change and on nothing else. `restore-keys` gives a prefix
fallback so a dependency bump still warms from the previous cache.

**What triggers can start a workflow?**
`push`, `pull_request`, `workflow_dispatch` (manual, with typed inputs), `schedule` (cron),
`release`, `issue_comment`, `workflow_call` (reusable workflows), `repository_dispatch` (external),
and more. Note that `schedule` only runs from the default branch — a cron entry on a feature branch
silently never fires.

**How would you turn this pipeline into a real deployment?**
Replace the local `docker run` smoke test with: log in to a registry with the credentials already
wired in as secrets, `docker push` the image, then apply it to the target — `kubectl set image` or a
Helm upgrade for Kubernetes, an ECS/App Runner update on AWS. Add a GitHub `environment` with a
required reviewer so production needs an approval, and add a rollback path keyed on the previous
image tag, which the pipeline already produces deterministically.
