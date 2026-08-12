# AIMETA P=Docker发布状态机契约|R=结构化校验DAG_权限_dry-run_不可逆顺序|NR=不执行GitHub或registry操作|E=test_*|X=internal|A=contract_test|D=pytest,pyyaml|S=test|RD=../../.trellis/tasks/08-11-release-governance/design.md
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_FILE = ROOT / ".github" / "workflows" / "docker-publish.yml"


def _load_workflow():
    return yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))


def _needs(job):
    value = job.get("needs", [])
    return {value} if isinstance(value, str) else set(value)


def test_release_jobs_form_the_required_acyclic_state_machine():
    jobs = _load_workflow()["jobs"]
    required = {
        "plan",
        "backend-gate",
        "frontend-gate",
        "release-gate",
        "validate-credentials",
        "capture-baseline",
        "build-candidate",
        "scan-platform",
        "smoke-candidate",
        "candidate-verified",
        "release-state-gate",
        "promote-version",
        "push-git-tag",
        "promote-latest",
        "update-metadata",
    }
    assert required <= jobs.keys()

    assert _needs(jobs["release-gate"]) == {"plan", "backend-gate", "frontend-gate"}
    assert _needs(jobs["capture-baseline"]) == {"plan", "validate-credentials"}
    assert _needs(jobs["build-candidate"]) == {"plan", "capture-baseline"}
    assert _needs(jobs["scan-platform"]) == {"plan", "build-candidate"}
    assert _needs(jobs["smoke-candidate"]) == {"plan", "build-candidate"}
    assert _needs(jobs["candidate-verified"]) == {
        "plan",
        "build-candidate",
        "scan-platform",
        "smoke-candidate",
    }
    assert _needs(jobs["release-state-gate"]) == {
        "plan",
        "capture-baseline",
        "build-candidate",
        "candidate-verified",
    }
    assert _needs(jobs["promote-version"]) == {
        "plan",
        "build-candidate",
        "release-state-gate",
    }
    assert _needs(jobs["push-git-tag"]) == {"plan", "promote-version"}
    assert _needs(jobs["promote-latest"]) == {
        "plan",
        "capture-baseline",
        "build-candidate",
        "push-git-tag",
    }
    assert _needs(jobs["update-metadata"]) == {
        "plan",
        "capture-baseline",
        "build-candidate",
        "promote-latest",
    }

    visiting = set()
    visited = set()

    def visit(job_name):
        assert job_name not in visiting, f"job dependency cycle at {job_name}"
        if job_name in visited:
            return
        visiting.add(job_name)
        for dependency in _needs(jobs[job_name]):
            assert dependency in jobs
            visit(dependency)
        visiting.remove(job_name)
        visited.add(job_name)

    for job_name in jobs:
        visit(job_name)


def test_release_permissions_pins_and_dry_run_boundary_are_fail_closed():
    workflow = _load_workflow()
    jobs = workflow["jobs"]
    trigger = workflow.get("on", workflow.get(True))

    assert workflow["concurrency"]["cancel-in-progress"] is False
    assert workflow["permissions"] == {"contents": "read"}
    assert trigger["workflow_dispatch"]["inputs"]["dry_run"]["default"] is True

    write_jobs = {
        name for name, job in jobs.items() if job.get("permissions", {}).get("contents") == "write"
    }
    assert write_jobs == {"push-git-tag", "update-metadata"}

    source = WORKFLOW_FILE.read_text(encoding="utf-8")
    uses_lines = [line.strip() for line in source.splitlines() if line.strip().startswith("uses:")]
    assert uses_lines
    assert all(re.fullmatch(r"uses: [^@\s]+@[0-9a-f]{40} +# v[^\s]+", line) for line in uses_lines)
    assert "continue-on-error" not in source
    assert "--force" not in source
    assert "RELEASE_TAG_WRITER_EXCLUSIVE" in source

    for job_name in (
        "release-state-gate",
        "promote-version",
        "push-git-tag",
        "promote-latest",
        "update-metadata",
    ):
        assert "dry_run != 'true'" in str(jobs[job_name]["if"])


def test_quality_gates_keep_openapi_export_with_backend_dependencies():
    jobs = _load_workflow()["jobs"]
    backend_gate = jobs["backend-gate"]
    frontend_gate = jobs["frontend-gate"]

    postgres = backend_gate["services"]["postgres"]
    assert postgres["image"] == "pgvector/pgvector:pg16"
    assert postgres["env"]["POSTGRES_USER"] == "mofeng"
    assert postgres["env"]["POSTGRES_PASSWORD"] == "ci-postgres-password"
    assert postgres["env"]["POSTGRES_DB"] == "mofeng"
    assert postgres["ports"] == ["5432:5432"]
    assert "pg_isready -U mofeng -d mofeng" in postgres["options"]

    test_secret = backend_gate["env"]["SECRET_KEY"]
    assert test_secret.startswith("ci-test-")
    assert len(test_secret) >= 32
    assert "${{" not in test_secret
    expected_database_url = "postgresql+asyncpg://mofeng:ci-postgres-password@127.0.0.1:5432/mofeng"
    assert backend_gate["env"]["TEST_POSTGRES_URL"] == expected_database_url
    assert backend_gate["env"]["DATABASE_URL"] == expected_database_url

    backend_commands = {
        line.strip() for step in backend_gate["steps"] for line in step.get("run", "").splitlines()
    }
    assert "python -m app.openapi_export --check --output openapi.json" in backend_commands

    frontend_commands = {
        line.strip() for step in frontend_gate["steps"] for line in step.get("run", "").splitlines()
    }
    assert "npm run api:check:types" in frontend_commands
    assert "npm run api:check:ownership" in frontend_commands
    assert "npm run api:check" not in frontend_commands
    assert "npm run api:check:openapi" not in frontend_commands
    assert not any("app.openapi_export" in command for command in frontend_commands)


def test_candidate_is_digest_verified_scanned_and_smoked_before_promotion():
    jobs = _load_workflow()["jobs"]
    build = jobs["build-candidate"]
    build_step = next(
        step for step in build["steps"] if "docker/build-push-action" in step.get("uses", "")
    )
    build_inputs = build_step["with"]

    assert build_inputs["platforms"] == "linux/amd64,linux/arm64"
    assert build_inputs["push"] is True
    assert build_inputs["provenance"] == "mode=max"
    assert ":build-${{ needs.plan.outputs.source_sha }}" in build_inputs["tags"]
    assert ":latest" not in build_inputs["tags"]
    assert "needs.plan.outputs.version" not in build_inputs["tags"]

    scan = jobs["scan-platform"]
    assert "fromJSON(needs.build-candidate.outputs.platform_matrix)" in str(
        scan["strategy"]["matrix"]
    )
    trivy = next(
        step for step in scan["steps"] if "aquasecurity/trivy-action" in step.get("uses", "")
    )
    assert trivy["with"]["exit-code"] == "1"
    assert trivy["with"]["severity"] == "HIGH,CRITICAL"
    assert "@${{ matrix.digest }}" in trivy["with"]["image-ref"]

    smoke_source = "\n".join(step.get("run", "") for step in jobs["smoke-candidate"]["steps"])
    assert "bash deploy/scripts/smoke_release_image.sh" in smoke_source
    assert "@${{ needs.build-candidate.outputs.manifest_digest }}" in smoke_source


def test_provenance_uses_buildkit_root_request_vcs_contract():
    source = WORKFLOW_FILE.read_text(encoding="utf-8")

    assert (
        source.count('.buildDefinition.externalParameters.request.root.request.args["vcs:source"]')
        == 2
    )
    assert (
        source.count(
            '.buildDefinition.externalParameters.request.root.request.args["vcs:revision"]'
        )
        == 2
    )
    assert ".buildDefinition.externalParameters.request.root.configSource" not in source
    assert ".runDetails.metadata.vcs" not in source


def test_formal_state_is_idempotent_and_metadata_uses_blob_optimistic_lock():
    source = WORKFLOW_FILE.read_text(encoding="utf-8")

    assert 'baseline_mode="legacy"' in source
    assert 'baseline_mode="normal"' in source
    assert "metadata_blob" in source
    assert "previous_latest_digest" in source
    assert "image_digest" in source
    assert "commit_sha" in source
    assert "version image conflict" in source
    assert "Git tag conflict" in source
    assert "latest changed after baseline capture" in source
    assert "metadata blob changed" in source


def test_metadata_digest_shell_parsing_preserves_json_input():
    source = WORKFLOW_FILE.read_text(encoding="utf-8")
    capture_step = next(
        step
        for step in _load_workflow()["jobs"]["capture-baseline"]["steps"]
        if step.get("id") == "capture"
    )
    capture_line = next(
        line.strip()
        for line in capture_step["run"].splitlines()
        if line.strip().startswith('metadata_digest="$(jq -r')
    )
    command = "\n".join(
        (
            "set -euo pipefail",
            'metadata_json="$1"',
            capture_line,
            'printf "%s" "${metadata_digest}"',
        )
    )

    def parse(metadata_json):
        return subprocess.run(
            ["bash", "-c", command, "metadata-test", metadata_json],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    digest = "sha256:" + "a" * 64
    assert parse(f'{{"image_digest":"{digest}"}}') == digest
    assert parse('{"version":"0.1.34"}') == ""
    assert parse("") == ""
    assert "metadata_json:-{}" not in source
