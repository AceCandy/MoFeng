# OpenAPI Toolchain Research

## Local Baseline

- Backend dependencies: FastAPI `0.110.0`, Pydantic `2.12.2`.
- Current direct `app.openapi()` result: OpenAPI `3.1.0`, 86 paths, 110 operations, 92 schemas.
- Current operation IDs: zero missing and zero duplicate, but generated entirely by FastAPI defaults. SHA256 of the newline-joined sorted 110 IDs is `18f9fcb2944270ab91d2fdbf3e4e552b891e4e56d7925cb9079484ef12c60aa2`.
- Components currently contain `BackgroundTaskResponse` and `BackgroundTaskSnapshotResponse`; event/reset payload models are absent.
- `frontend/package-lock.json` resolves `openapi-typescript 7.13.0`, but its root dependency range is still `^7.13.0` while `package.json` has no matching declaration or script; implementation must make both manifests exact `7.13.0`.
- Only `.github/workflows/frontend-ci.yml` exists; it listens to `frontend/**` and does not run backend contract checks.

## FastAPI 0.110.0

Version-specific source confirms:

- `FastAPI(generate_unique_id_function=...)` accepts `Callable[[APIRoute], str]`.
- the callback runs when an `APIRoute` is built unless `operation_id` is explicit;
- the default generator combines route function name, `path_format` and `list(route.methods)[0]`;
- duplicate operation IDs only emit a warning during OpenAPI generation;
- `app.openapi()` synchronously builds/caches a schema and does not enter ASGI lifespan.

Decision: use an app-level generator that preserves the current single-method IDs while choosing the method deterministically, prohibit multi-method `APIRoute` contracts, preserve explicit compatibility IDs, and assert global uniqueness ourselves.

Sources:

- `https://raw.githubusercontent.com/fastapi/fastapi/0.110.0/fastapi/applications.py`
- `https://raw.githubusercontent.com/fastapi/fastapi/0.110.0/fastapi/routing.py`
- `https://raw.githubusercontent.com/fastapi/fastapi/0.110.0/fastapi/utils.py`
- `https://raw.githubusercontent.com/fastapi/fastapi/0.110.0/fastapi/openapi/utils.py`

## openapi-typescript 7.13.0

The installed CLI and upstream source confirm:

- `--output/-o` writes the artifact;
- `--alphabetize` sorts generated object keys/types;
- `--check` compares generated text to the existing output byte-for-byte and exits 1 on drift;
- the CLI already writes a fixed “auto-generated / do not edit” header.

Decision: pin exact `7.13.0`, use identical generate/check flags, and do not post-process the output.

Sources:

- `frontend/node_modules/openapi-typescript/bin/cli.js`
- `frontend/node_modules/openapi-typescript/dist/index.mjs`
- `https://github.com/openapi-ts/openapi-typescript/tree/openapi-typescript@7.13.0`

## oasdiff 1.26.1

The `v1.26.1` release was published on 2026-07-27 and provides checksum files and local binaries. Its documentation states OpenAPI 3.1 support is generally available from `v1.15.0`, including JSON Schema 2020-12 changes and breaking rules.

Selected policy:

- download the exact release binary in CI and verify `checksums.txt`;
- compare committed PR base/current `backend/openapi.json`;
- run `oasdiff breaking --fail-on ERR --format githubactions`;
- do not use `--open` or hosted review, so artifacts are not uploaded;
- keep byte drift and semantic breaking checks as separate gates.

Pinned Linux archive:

- URL: `https://github.com/oasdiff/oasdiff/releases/download/v1.26.1/oasdiff_1.26.1_linux_amd64.tar.gz`
- SHA256 from the release checksum list: `ea0007fe536c7915785f754885d2afdb11352d6a14531950edf9d601a2baa674`

Known limitations from the pinned documentation:

- `$dynamicRef`/`$dynamicAnchor` are parsed but not resolved;
- `components.pathItems` is not represented by the parser.

Decision: contract tests reject those constructs until a later pinned-tool evaluation removes the limitation.

Sources:

- `https://github.com/oasdiff/oasdiff/releases/tag/v1.26.1`
- `https://raw.githubusercontent.com/oasdiff/oasdiff/v1.26.1/docs/OPENAPI-31.md`
- `https://raw.githubusercontent.com/oasdiff/oasdiff/v1.26.1/docs/BREAKING-CHANGES.md`
- `https://raw.githubusercontent.com/oasdiff/oasdiff/v1.26.1/LICENSE`

## Rejected Alternatives

- Plain `git diff`: useful for artifact drift, but cannot classify required/nullable/enum/request/response changes.
- Custom structural summary: would need to reimplement OpenAPI 3.1 refs and compatibility direction, creating a high false-negative surface.
- Hosted schema review: unnecessary external data flow and availability dependency.
- A second generated runtime-validation toolchain: disproportionate for three SSE payload kinds; a small boundary decoder is easier to audit.
