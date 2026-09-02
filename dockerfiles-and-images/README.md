# Dockerfiles & Images — Docker Multi-Stage Builds

**Assignment requirements** (verbatim from `DevOps Homework.docx`):

> ## Task 1: Run Multi-Stage Dockerfile
> - Clone the repository containing the multi-stage Dockerfile.
> - Build the Docker image using the multi-stage Dockerfile.
> - Run a container from the image.
> - Access the application running inside the container.
> - Verify that the application displays: `Hello World from Docker multi-stage build`
> - Verify the running container using `docker ps`.
> - Confirm that the application is running on port 8080.
>
> ## Task 2: Documentation
> Create an .md file containing: your name, enrollment number, a screenshot/output showing
> the application running, and a screenshot/output of `docker ps` on port 8080.
>
> ## Task 3: Docker Application Deployment
> Deploy at least 3 different types of applications using Docker, such as: Node.js, Python, Java

## Honest note on the missing repository URL

The assignment says to "clone the repository containing the multi-stage Dockerfile" but the
source document does not actually contain a repository URL anywhere. Rather than invent one
or clone an arbitrary unrelated public repo (which would prove nothing about understanding
multi-stage builds), **Task 1's Dockerfile and application were written from scratch** to
meet the real requirement being tested: build a genuine multi-stage image, run it, and serve
exactly `Hello World from Docker multi-stage build` on port 8080. See
[`01-multi-stage-build/README.md`](01-multi-stage-build/README.md) for the full writeup.

## Tasks

| Task | Folder | What it covers |
|---|---|---|
| 1 | [`01-multi-stage-build/`](01-multi-stage-build/README.md) | A genuine multi-stage Dockerfile (Go builder → `scratch` runtime), built, run, and verified; plus a single-stage comparison build for real size numbers |
| 2 | [`02-documentation/`](02-documentation/README.md) | The Task 2 deliverable: name/enrollment placeholders + real captured output |
| 3 | [`03-application-deployment/`](03-application-deployment/README.md) | Three different app types (Node.js/Express, Python/Flask, Java/Maven) each with a JSON API, deployed via their own multi-stage Dockerfiles |

---

## How multi-stage builds work

A multi-stage Dockerfile has more than one `FROM` line, each starting a new **stage**:

```dockerfile
FROM golang:1.23-alpine AS builder     # stage 1: has the full build toolchain
WORKDIR /src
COPY . .
RUN go build -o /out/app .

FROM scratch AS final                  # stage 2: starts from nothing
COPY --from=builder /out/app /app      # pull ONLY the built artifact across
ENTRYPOINT ["/app"]
```

- **`FROM ... AS <name>`** names a stage so later stages (or `docker build --target`) can
  refer back to it. Each stage is its own independent build, sharing nothing implicitly.
- **`COPY --from=builder <path> <path>`** is the only bridge between stages — it reaches back
  into an *already-built* stage's filesystem and copies out specific files. Nothing else
  about that stage (its layers, its installed packages, its shell) crosses over.
- **Why the toolchain gets discarded**: a stage that is never the final `FROM` and is never
  referenced by a later `--from` (or `--target`) is built (so its `RUN` steps still execute
  and can be cached) but is not part of the final image manifest — `docker build` doesn't
  export or ship it. That's what lets a builder stage contain gigabytes of compiler, package
  manager, and cache while the shipped image contains only the artifact.
- **Build targets (`--target`)**: `docker build --target builder .` builds and tags *just*
  that intermediate stage — useful for a debug/dev image that does need the toolchain, built
  from the exact same Dockerfile as the production image, without maintaining two files.
- **Caching**: each stage caches independently, layer by layer, the normal Docker way (a
  layer is reused if the instruction and everything that could affect it — like a
  previously-`COPY`'d file — is unchanged). Ordering `COPY go.mod` + `RUN go mod download`
  *before* `COPY . .` means dependency-resolution layers stay cached across source-code-only
  changes; the same principle applies to `package.json`+`npm install` and
  `requirements.txt`+`pip install` in Task 3's Node.js and Python builds.

## Real size comparison — single-stage vs multi-stage

Same Go application, same `golang:1.23-alpine` base for the build step in both cases —
the only difference is whether the second stage exists to discard the toolchain:

| Build | Dockerfile | Size | What ships |
|---|---|---|---|
| Single-stage | `Dockerfile.singlestage` | **468MB** | Full Go compiler + stdlib + module cache + shell + coreutils, *plus* the binary |
| Multi-stage | `Dockerfile` | **7.3MB** | `scratch` (0B) + only the ~5MB compiled binary |

**Reduction: 460.7MB → the multi-stage image is ~98.4% smaller**, for identical runtime
behaviour (both serve `Hello World from Docker multi-stage build` on port 8080). Verified
with `docker images` and cross-checked with `docker history` (the multi-stage image is
literally one 5.08MB `COPY` layer plus zero-byte metadata layers — see
[`01-multi-stage-build/README.md`](01-multi-stage-build/README.md) for the full command
output).

## Task 3 — three deployed application types

| App | Language / runtime | Framework | Host port → container port | Image size |
|---|---|---|---|---|
| Node.js | Node.js v22.23.2 | Express 4.22.2 | 18091 → 3000 | 234MB |
| Python | CPython 3.12.14 | Flask 3.0.3 | 18092 → 5000 | 112MB |
| Java | JRE 21.0.12 (built with Maven) | org.json 20240303 | 18093 → 8080 | 286MB |

Each app exposes a JSON API (`GET /api/info`, reporting its own language/runtime/framework
version) plus an HTML page, and is itself built with a multi-stage Dockerfile (dependency
install/compile stage → slim runtime stage). Full detail in
[`03-application-deployment/README.md`](03-application-deployment/README.md).

## Best practices demonstrated / worth calling out

- **Layer ordering for cache hits**: copy dependency manifests (`go.mod`, `package.json`,
  `requirements.txt`, `pom.xml`) and install/resolve *before* copying application source, so
  a source-only change doesn't invalidate the (often slow) dependency-resolution layer.
- **`.dockerignore`**: keeps build context small and prevents accidentally `COPY`-ing local
  build artifacts, `.git`, or `node_modules` into the image. Not strictly needed for these
  small single-file apps (context here is under 2KB each) but essential on any real project.
- **Non-root `USER`**: every runtime image in this section drops root — `USER 65534`
  (numeric, since `scratch` has no `/etc/passwd`) for the Go app, `USER node` for the Node.js
  image, a created `appuser`/`app` user for Python/Java. Running as root inside a container is
  unnecessary risk with no benefit for a stateless HTTP server.
- **Pinning base image tags**: every `FROM` in this section pins a specific tag
  (`golang:1.23-alpine`, `node:22-alpine`, `python:3.12-alpine`,
  `eclipse-temurin:21-jre-alpine`, `maven:3.9-eclipse-temurin-21-alpine`) rather than
  `:latest`, so a rebuild next month doesn't silently pull a different major version and
  change behaviour or size.
- **`EXPOSE` as documentation**: `EXPOSE 8080` (etc.) does not publish a port by itself — only
  `docker run -p` does that — it's metadata that documents which port the *application*
  listens on, which is exactly the port number the assignment asks to confirm.
- **Minimising layers**: each `RUN` here does one logical thing (build, install deps, create a
  user) rather than combining unrelated steps, favouring cache granularity over the last few
  bytes of layer-count savings, which matters much less than the stage-discarding shown above.

## Cleanup

All containers from this section (`ms-app`, `ms-deploy-node`, `ms-deploy-python`,
`ms-deploy-java`) were stopped and removed after verification. The images
(`ms-app:multistage`, `ms-app:singlestage`, `ms-deploy-node`, `ms-deploy-python`,
`ms-deploy-java`) were kept — see the `docker images` output in each task's README.

<!-- AUTO-ATTACHED: screenshots & transcripts -->

## Tasks in this topic

- [`01-multi-stage-build`](01-multi-stage-build/README.md)
- [`02-documentation`](02-documentation/README.md)
- [`03-application-deployment`](03-application-deployment/README.md)
