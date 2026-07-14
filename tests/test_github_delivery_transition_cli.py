"""정책 전환 CLI의 base-bound·review-only 통합 계약."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import github_delivery


FROM_POLICY = "SPEC-GH-DELIVERY-001/v1.1.0"
TO_POLICY = "SPEC-GH-DELIVERY-001/v1.2.0"
DELIVERY_APPROVAL = "COL-27B9ADD786ED"
TRANSITION_APPROVAL = "COL-B80046FC1C56"
DELIVERY_RFC = "RFC-03F4FE85BB44"
TRANSITION_RFC = "RFC-7A0959853525"
NOW = "2026-07-15T03:20:23+00:00"
TOKEN = "integration-fixture-token"


def _transition(*, state: str = "armed") -> dict[str, object]:
    return {
        "schema_version": "github-delivery-policy-transition/v1",
        "from_policy_version": FROM_POLICY,
        "to_policy_version": TO_POLICY,
        "state": state,
        "mode": "human-review-only",
        "approval_refs": [DELIVERY_APPROVAL, TRANSITION_APPROVAL],
        "rfc_ids": [DELIVERY_RFC, TRANSITION_RFC],
    }


def _config(
    *, active: str = FROM_POLICY, transition_state: str = "armed"
) -> dict[str, object]:
    return {
        "policy_version": active,
        "repository": "winehouse8/auto_wiki",
        "base_branch": "main",
        "branch_prefix": "wiki-auto/",
        "merge_method": "squash",
        "approval_refs": [
            DELIVERY_APPROVAL,
            DELIVERY_RFC,
            TRANSITION_APPROVAL,
            TRANSITION_RFC,
        ],
        "policy_transition": _transition(state=transition_state),
    }


def _document(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _git(root: Path, *arguments: str, allowed: tuple[int, ...] = (0,)) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode not in allowed:
        raise AssertionError(
            f"git {' '.join(arguments)} failed ({result.returncode}): {result.stderr}"
        )
    return result.stdout


class _RealGitRunner:
    """로컬 Git은 그대로 실행하고 승인된 원격 경계만 대체한다."""

    def __init__(self):
        self.calls: list[tuple[str, ...]] = []
        self.origin_url = "https://github.com/winehouse8/auto_wiki.git"
        self.push_url = self.origin_url

    def run(self, argv, *, cwd=None, env=None, input_text=None):
        arguments = tuple(str(value) for value in argv)
        self.calls.append(arguments)
        if arguments == ("git", "remote", "get-url", "origin"):
            return subprocess.CompletedProcess(
                arguments,
                0,
                stdout=self.origin_url + "\n",
                stderr="",
            )
        if arguments == ("git", "remote", "get-url", "--all", "origin"):
            return subprocess.CompletedProcess(
                arguments, 0, stdout=self.origin_url + "\n", stderr=""
            )
        if arguments == (
            "git",
            "remote",
            "get-url",
            "--push",
            "--all",
            "origin",
        ):
            return subprocess.CompletedProcess(
                arguments, 0, stdout=self.push_url + "\n", stderr=""
            )
        if arguments[:2] == ("git", "fetch"):
            return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")
        if arguments[:2] == ("git", "push"):
            return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")

        child_environment = os.environ.copy()
        if env:
            child_environment.update({str(key): str(value) for key, value in env.items()})
        return subprocess.run(
            list(arguments),
            cwd=cwd,
            env=child_environment,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_bytes(self, argv, *, cwd=None, env=None):
        arguments = tuple(str(value) for value in argv)
        self.calls.append(arguments)
        child_environment = os.environ.copy()
        if env:
            child_environment.update({str(key): str(value) for key, value in env.items()})
        return subprocess.run(
            list(arguments),
            cwd=cwd,
            env=child_environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
        )


class _GateRunner:
    def __init__(self):
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv, *, cwd=None, env=None, input_text=None):
        arguments = tuple(str(value) for value in argv)
        self.calls.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")


class _ReviewTransport:
    """원격 PR 상태만 재현하고 merge 시도는 눈에 보이게 기록한다."""

    def __init__(self, *, base_sha: str):
        self.base_sha = base_sha
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.pull_request: dict[str, object] | None = None

    def _record(self, name: str, **values: object) -> None:
        self.calls.append((name, values))

    def count(self, name: str) -> int:
        return sum(call_name == name for call_name, _ in self.calls)

    def find_delivery(self, *, repository, idempotency_key):
        self._record(
            "find_delivery",
            repository=repository,
            idempotency_key=idempotency_key,
        )
        return dict(self.pull_request) if self.pull_request else None

    def get_base_sha(self, *, repository, base_branch):
        self._record(
            "get_base_sha", repository=repository, base_branch=base_branch
        )
        return self.base_sha

    def create_branch(self, **kwargs):
        self._record("create_branch", **kwargs)
        return {"name": kwargs["branch"]}

    def create_pull_request(self, **kwargs):
        self._record("create_pull_request", **kwargs)
        self.pull_request = {
            "number": 41,
            "url": "https://github.com/winehouse8/auto_wiki/pull/41",
            "draft": kwargs["draft"],
            "state": "open",
            "merged": False,
            "merge_sha": None,
            "base_sha": self.base_sha,
            "head_sha": kwargs["head_sha"],
            "tree_sha": kwargs["tree_sha"],
            "labels": [],
            "auto_merge_enabled": False,
            "unresolved_reviews": 0,
            "conflict": False,
        }
        return dict(self.pull_request)

    def add_labels(self, *, repository, pr_number, labels):
        self._record(
            "add_labels",
            repository=repository,
            pr_number=pr_number,
            labels=list(labels),
        )
        assert self.pull_request is not None
        self.pull_request["labels"] = list(labels)

    def get_pull_request(self, *, repository, pr_number):
        self._record(
            "get_pull_request", repository=repository, pr_number=pr_number
        )
        assert self.pull_request is not None
        return dict(self.pull_request)

    def get_checks(self, **kwargs):
        self._record("get_checks", **kwargs)
        raise AssertionError("review-only 전환에서 원격 check를 조회하면 안 됨")

    def request_auto_merge(self, **kwargs):
        self._record("request_auto_merge", **kwargs)
        raise AssertionError("review-only 전환에서 auto-merge를 요청하면 안 됨")


class _TrapGateRunner:
    def __init__(self):
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv, *, cwd=None, env=None, input_text=None):
        arguments = tuple(str(value) for value in argv)
        self.calls.append(arguments)
        raise AssertionError("차단 fixture가 품질 gate에 도달함")


class _TrapTokenLoader:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        raise AssertionError("차단 fixture가 token loader에 도달함")


class _TrapTransport:
    def __init__(self):
        self.calls: list[str] = []

    def __getattr__(self, name):
        def trapped(*args, **kwargs):
            self.calls.append(name)
            raise AssertionError(f"차단 fixture가 transport.{name}에 도달함")

        return trapped


def _make_repository(
    directory: str,
    *,
    active: str = FROM_POLICY,
    transition_state: str = "armed",
    crlf: bool = False,
):
    root = Path(directory).resolve()
    _git(root, "init", "--quiet")
    _git(root, "checkout", "--quiet", "-b", "main")
    _git(root, "config", "user.name", "Policy Transition Fixture")
    _git(root, "config", "user.email", "fixture@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    hooks = root / ".git" / "empty-hooks"
    hooks.mkdir()
    _git(root, "config", "core.hooksPath", str(hooks))

    config_path = root / "config" / "github-delivery.json"
    config_path.parent.mkdir(parents=True)
    base_document = _document(
        _config(active=active, transition_state=transition_state)
    )
    if crlf:
        base_document = base_document.replace(b"\n", b"\r\n")
    config_path.write_bytes(base_document)
    _git(root, "add", "--", "config/github-delivery.json")
    _git(root, "commit", "--quiet", "-m", "정책 전환 base fixture")
    base_sha = _git(root, "rev-parse", "HEAD").strip()
    _git(root, "update-ref", "refs/remotes/origin/main", base_sha)
    return root, base_document, base_sha, _RealGitRunner()


def _activate_transition(root: Path) -> None:
    config = copy.deepcopy(_config())
    config["policy_version"] = TO_POLICY
    transition = config["policy_transition"]
    assert isinstance(transition, dict)
    transition["state"] = "consumed"
    (root / "config" / "github-delivery.json").write_bytes(_document(config))


def _begin(root: Path, runner: _RealGitRunner, *, run_id: str):
    output = io.StringIO()
    code = github_delivery.main(
        [
            "begin",
            "--repo-root",
            str(root),
            "--run-id",
            run_id,
            "--target-policy-version",
            TO_POLICY,
        ],
        runner=runner,
        stdout=output,
        now=NOW,
    )
    return code, json.loads(output.getvalue())


def _delivery_receipt_path(root: Path, run_id: str) -> Path:
    return root / ".git" / "wiki-delivery" / f"{run_id}.delivery.json"


class PolicyTransitionCliIntegrationTests(unittest.TestCase):
    def test_human_merged_transition_is_reconciled_without_claiming_auto_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, base_sha, runner = _make_repository(directory)
            run_id = "RUN-HUMAN-MERGE-RECONCILE"
            begin_code, _ = _begin(root, runner, run_id=run_id)
            self.assertEqual(begin_code, 0)
            _activate_transition(root)
            transport = _ReviewTransport(base_sha=base_sha)
            first_output = io.StringIO()
            first_code = github_delivery.main(
                ["publish", "--repo-root", str(root), "--run-id", run_id],
                runner=runner,
                gate_runner=_GateRunner(),
                transport=transport,
                token_loader=lambda: TOKEN,
                stdout=first_output,
                now=NOW,
            )
            self.assertEqual(first_code, 0)
            self.assertEqual(json.loads(first_output.getvalue())["status"], "review")
            self.assertIsNotNone(transport.pull_request)

            head_sha = _git(root, "rev-parse", "HEAD").strip()
            merge_sha = _git(
                root,
                "commit-tree",
                f"{head_sha}^{{tree}}",
                "-p",
                base_sha,
                "-m",
                "사람 squash 병합 fixture",
            ).strip()
            _git(root, "update-ref", "refs/remotes/origin/main", merge_sha)
            assert transport.pull_request is not None
            transport.pull_request.update(
                {
                    "state": "closed",
                    "merged": True,
                    "merge_sha": merge_sha,
                    "draft": False,
                }
            )
            transport.calls.clear()
            runner.calls.clear()
            second_output = io.StringIO()

            second_code = github_delivery.main(
                ["publish", "--repo-root", str(root), "--run-id", run_id],
                runner=runner,
                gate_runner=_GateRunner(),
                transport=transport,
                token_loader=lambda: TOKEN,
                stdout=second_output,
                now=NOW,
            )
            reconciled = json.loads(second_output.getvalue())

            self.assertEqual(second_code, 0)
            self.assertEqual(reconciled["status"], "merged")
            self.assertEqual(reconciled["merge_sha"], merge_sha)
            self.assertIs(reconciled["merge_requested"], False)
            self.assertEqual(transport.count("create_branch"), 0)
            self.assertEqual(transport.count("create_pull_request"), 0)
            self.assertEqual(transport.count("request_auto_merge"), 0)

    def test_publish_rejects_changed_origin_or_pushurl_before_gate_token_and_transport(self):
        for changed_field in ("origin_url", "push_url"):
            with self.subTest(changed_field=changed_field), tempfile.TemporaryDirectory() as directory:
                root, _, base_sha, runner = _make_repository(directory)
                run_id = f"RUN-ORIGIN-{changed_field.upper()}"
                begin_code, _ = _begin(root, runner, run_id=run_id)
                self.assertEqual(begin_code, 0)
                _activate_transition(root)
                setattr(
                    runner,
                    changed_field,
                    "https://github.com/winehouse8/not-approved.git",
                )
                runner.calls.clear()
                gate = _GateRunner()
                token_calls: list[bool] = []
                transport = _ReviewTransport(base_sha=base_sha)
                output = io.StringIO()

                code = github_delivery.main(
                    ["publish", "--repo-root", str(root), "--run-id", run_id],
                    runner=runner,
                    gate_runner=gate,
                    transport=transport,
                    token_loader=lambda: token_calls.append(True) or TOKEN,
                    stdout=output,
                    now=NOW,
                )

                self.assertEqual(code, 2)
                self.assertEqual(json.loads(output.getvalue())["status"], "blocked")
                self.assertEqual(gate.calls, [])
                self.assertEqual(token_calls, [])
                self.assertEqual(transport.calls, [])
                self.assertFalse(
                    any(
                        call[:2] in {("git", "commit"), ("git", "push")}
                        for call in runner.calls
                    )
                )

    def test_old_normal_receipt_is_rejected_on_base_drift_before_gate_or_token(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, base_sha, runner = _make_repository(directory)
            run_id = "RUN-OLD-NORMAL-RECEIPT"
            output = io.StringIO()
            begin_code = github_delivery.main(
                ["begin", "--repo-root", str(root), "--run-id", run_id],
                runner=runner,
                stdout=output,
                now=NOW,
            )
            self.assertEqual(begin_code, 0)
            advanced_base = _git(
                root,
                "commit-tree",
                f"{base_sha}^{{tree}}",
                "-p",
                base_sha,
                "-m",
                "새 기준선 fixture",
            ).strip()
            _git(
                root,
                "update-ref",
                "refs/remotes/origin/main",
                advanced_base,
            )
            candidate = root / "wiki" / "index.md"
            candidate.parent.mkdir()
            candidate.write_text(
                "<!-- tools/wiki.py가 자동 생성함. 직접 수정하지 마세요. -->\n# 시험\n",
                encoding="utf-8",
            )
            runner.calls.clear()
            gate = _GateRunner()
            token_calls: list[bool] = []
            transport = _ReviewTransport(base_sha=base_sha)
            output = io.StringIO()

            code = github_delivery.main(
                ["publish", "--repo-root", str(root), "--run-id", run_id],
                runner=runner,
                gate_runner=gate,
                transport=transport,
                token_loader=lambda: token_calls.append(True) or TOKEN,
                stdout=output,
                now=NOW,
            )

            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output.getvalue())["status"], "blocked")
            self.assertEqual(gate.calls, [])
            self.assertEqual(token_calls, [])
            self.assertEqual(transport.calls, [])

    def test_local_git_replace_cannot_redefine_the_base_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, base_sha, runner = _make_repository(directory)
            forged = _config()
            forged["reviewer"] = "forged-local-authority"
            forged_document = _document(forged)
            (root / "config" / "github-delivery.json").write_bytes(
                forged_document
            )
            _git(root, "add", "--", "config/github-delivery.json")
            _git(root, "commit", "--quiet", "-m", "로컬 대체 객체 fixture")
            forged_commit = _git(root, "rev-parse", "HEAD").strip()
            _git(root, "update-ref", "refs/heads/main", base_sha)
            _git(root, "replace", base_sha, forged_commit)
            self.assertEqual(_git(root, "status", "--porcelain"), "")
            self.assertEqual(
                _git(root, "show", f"{base_sha}:config/github-delivery.json").encode(
                    "utf-8"
                ),
                forged_document,
            )

            output = io.StringIO()
            code = github_delivery.main(
                [
                    "begin",
                    "--repo-root",
                    str(root),
                    "--run-id",
                    "RUN-REPLACE-REF-BLOCKED",
                    "--target-policy-version",
                    TO_POLICY,
                ],
                runner=runner,
                stdout=output,
                now=NOW,
            )

            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output.getvalue())["status"], "blocked")
            self.assertEqual(
                _git(root, "branch", "--show-current").strip(), "main"
            )
            self.assertFalse(
                (
                    root
                    / ".git"
                    / "wiki-delivery"
                    / "RUN-REPLACE-REF-BLOCKED.begin.json"
                ).exists()
            )

    def test_consumed_v12_base_allows_normal_begin_but_rejects_reused_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, base_sha, runner = _make_repository(
                directory,
                active=TO_POLICY,
                transition_state="consumed",
            )
            output = io.StringIO()
            normal_run_id = "RUN-V12-NORMAL-000"

            code = github_delivery.main(
                [
                    "begin",
                    "--repo-root",
                    str(root),
                    "--run-id",
                    normal_run_id,
                ],
                runner=runner,
                stdout=output,
                now=NOW,
            )
            receipt = json.loads(output.getvalue())

            self.assertEqual(code, 0)
            self.assertEqual(receipt["schema_version"], "github-delivery-begin/v1")
            self.assertEqual(receipt["policy_version"], TO_POLICY)
            self.assertEqual(receipt["base_sha"], base_sha)
            self.assertNotIn("target_policy_version", receipt)
            self.assertNotIn("policy_transition", receipt)

        with tempfile.TemporaryDirectory() as directory:
            root, _, _, runner = _make_repository(
                directory,
                active=TO_POLICY,
                transition_state="consumed",
            )
            output = io.StringIO()
            code = github_delivery.main(
                [
                    "begin",
                    "--repo-root",
                    str(root),
                    "--run-id",
                    "RUN-V12-REUSE-BLOCKED",
                    "--target-policy-version",
                    TO_POLICY,
                ],
                runner=runner,
                stdout=output,
                now=NOW,
            )

            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output.getvalue())["status"], "blocked")
            self.assertEqual(_git(root, "branch", "--show-current").strip(), "main")
            self.assertFalse(
                (
                    root
                    / ".git"
                    / "wiki-delivery"
                    / "RUN-V12-REUSE-BLOCKED.begin.json"
                ).exists()
            )

    def test_main_begin_pins_base_blob_proof_before_branch_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root, base_document, base_sha, runner = _make_repository(directory)
            run_id = "RUN-BASE-PROOF-001"

            code, receipt = _begin(root, runner, run_id=run_id)

            self.assertEqual(code, 0)
            self.assertEqual(receipt["schema_version"], "github-delivery-begin/v2")
            self.assertEqual(receipt["base_sha"], base_sha)
            self.assertEqual(receipt["policy_version"], FROM_POLICY)
            self.assertEqual(receipt["target_policy_version"], TO_POLICY)
            proof = receipt["policy_transition"]
            self.assertEqual(proof["from_policy_version"], FROM_POLICY)
            self.assertEqual(proof["to_policy_version"], TO_POLICY)
            self.assertEqual(proof["base_sha"], base_sha)
            self.assertEqual(
                proof["base_policy_config_sha256"],
                hashlib.sha256(base_document).hexdigest(),
            )
            self.assertEqual(
                _git(
                    root,
                    "show",
                    f"{base_sha}:config/github-delivery.json",
                ).encode("utf-8"),
                base_document,
            )

            proof_read = (
                "git",
                "show",
                f"{base_sha}:config/github-delivery.json",
            )
            proof_read_index = runner.calls.index(proof_read)
            exact_fetch = (
                "git",
                "fetch",
                "--no-tags",
                "--prune",
                "https://github.com/winehouse8/auto_wiki.git",
                "refs/heads/main:refs/remotes/origin/main",
            )
            self.assertIn(exact_fetch, runner.calls)
            branch_index = next(
                index
                for index, call in enumerate(runner.calls)
                if call[:3] == ("git", "switch", "-c")
            )
            self.assertLess(proof_read_index, branch_index)
            self.assertEqual(
                _git(root, "branch", "--show-current").strip(), receipt["branch"]
            )

            persisted = json.loads(
                (
                    root
                    / ".git"
                    / "wiki-delivery"
                    / f"{run_id}.begin.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(persisted["policy_transition"], proof)

    def test_base_policy_digest_uses_exact_git_blob_bytes_without_newline_normalization(self):
        with tempfile.TemporaryDirectory() as directory:
            root, base_document, base_sha, runner = _make_repository(
                directory,
                crlf=True,
            )
            blob = subprocess.run(
                [
                    "git",
                    "--no-replace-objects",
                    "show",
                    f"{base_sha}:config/github-delivery.json",
                ],
                cwd=root,
                capture_output=True,
                check=True,
            ).stdout
            self.assertEqual(blob, base_document)

            code, receipt = _begin(
                root,
                runner,
                run_id="RUN-EXACT-BLOB-BYTES-001",
            )

            self.assertEqual(code, 0)
            self.assertEqual(
                receipt["policy_transition"]["base_policy_config_sha256"],
                hashlib.sha256(blob).hexdigest(),
            )

    def test_exact_config_only_activation_creates_draft_review_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root, base_document, base_sha, runner = _make_repository(directory)
            run_id = "RUN-REVIEW-ONLY-002"
            begin_code, _ = _begin(root, runner, run_id=run_id)
            self.assertEqual(begin_code, 0)
            _activate_transition(root)

            gate = _GateRunner()
            transport = _ReviewTransport(base_sha=base_sha)
            token_calls: list[bool] = []

            def load_token():
                token_calls.append(True)
                return TOKEN

            output = io.StringIO()
            code = github_delivery.main(
                ["publish", "--repo-root", str(root), "--run-id", run_id],
                runner=runner,
                gate_runner=gate,
                transport=transport,
                token_loader=load_token,
                stdout=output,
                now=NOW,
            )
            receipt = json.loads(output.getvalue())

            self.assertEqual(code, 0)
            self.assertEqual(receipt["status"], "review")
            self.assertEqual(receipt["route"], "review")
            self.assertIs(receipt["draft"], True)
            self.assertIs(receipt["merge_requested"], False)
            self.assertIsNone(receipt["merge_method"])
            self.assertEqual(receipt["begin_policy_version"], FROM_POLICY)
            self.assertEqual(receipt["target_policy_version"], TO_POLICY)
            self.assertEqual(
                receipt["base_policy_config_sha256"],
                hashlib.sha256(base_document).hexdigest(),
            )
            proof = receipt["policy_transition"]
            self.assertEqual(proof["from_policy_version"], FROM_POLICY)
            self.assertEqual(proof["to_policy_version"], TO_POLICY)
            self.assertEqual(
                proof["base_policy_config_sha256"],
                hashlib.sha256(base_document).hexdigest(),
            )

            self.assertTrue(gate.calls)
            self.assertTrue(token_calls)
            self.assertEqual(transport.count("create_pull_request"), 1)
            create_pr = next(
                values
                for name, values in transport.calls
                if name == "create_pull_request"
            )
            self.assertIs(create_pr["draft"], True)
            self.assertEqual(transport.count("request_auto_merge"), 0)
            self.assertEqual(transport.count("get_checks"), 0)
            self.assertEqual(
                sum(call[:2] == ("git", "commit") for call in runner.calls), 1
            )
            self.assertEqual(
                sum(call[:2] == ("git", "push") for call in runner.calls), 1
            )
            self.assertIn(
                f"Wiki-Run-ID: {run_id}",
                _git(root, "show", "-s", "--format=%B", "HEAD"),
            )

            persisted = json.loads(
                _delivery_receipt_path(root, run_id).read_text(encoding="utf-8")
            )
            self.assertEqual(persisted, receipt)
            public_material = json.dumps(
                {
                    "receipt": receipt,
                    "runner_calls": runner.calls,
                    "transport_calls": transport.calls,
                },
                ensure_ascii=False,
                default=str,
            )
            self.assertNotIn(TOKEN, public_material)

    def test_extra_path_or_tampered_proof_blocks_before_any_side_effect(self):
        fixtures = (
            "extra-path",
            "tampered-proof",
            "tampered-approval",
            "tampered-rfc",
        )
        for fixture in fixtures:
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as directory:
                root, _, base_sha, runner = _make_repository(directory)
                run_id = f"RUN-BLOCK-{fixture.upper()}"
                begin_code, _ = _begin(root, runner, run_id=run_id)
                self.assertEqual(begin_code, 0)
                _activate_transition(root)

                if fixture == "extra-path":
                    (root / "unexpected.md").write_text(
                        "전환 manifest 밖 변경\n", encoding="utf-8"
                    )
                if fixture != "extra-path":
                    receipt_path = (
                        root
                        / ".git"
                        / "wiki-delivery"
                        / f"{run_id}.begin.json"
                    )
                    begin_receipt = json.loads(
                        receipt_path.read_text(encoding="utf-8")
                    )
                    if fixture == "tampered-proof":
                        begin_receipt["policy_transition"][
                            "base_policy_config_sha256"
                        ] = "0" * 64
                    elif fixture == "tampered-approval":
                        begin_receipt["approval_refs"] = [DELIVERY_APPROVAL]
                    else:
                        begin_receipt["rfc_ids"] = [DELIVERY_RFC]
                    receipt_path.write_text(
                        json.dumps(
                            begin_receipt,
                            ensure_ascii=False,
                            sort_keys=True,
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                    )

                runner.calls.clear()
                gate = _TrapGateRunner()
                token_loader = _TrapTokenLoader()
                transport = _TrapTransport()
                output = io.StringIO()

                code = github_delivery.main(
                    ["publish", "--repo-root", str(root), "--run-id", run_id],
                    runner=runner,
                    gate_runner=gate,
                    transport=transport,
                    token_loader=token_loader,
                    stdout=output,
                    now=NOW,
                )
                result = json.loads(output.getvalue())

                self.assertEqual(code, 2)
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(gate.calls, [])
                self.assertEqual(token_loader.calls, 0)
                self.assertEqual(transport.calls, [])
                for command in runner.calls:
                    self.assertNotIn(
                        command[:2],
                        {
                            ("git", "add"),
                            ("git", "commit"),
                            ("git", "push"),
                        },
                    )
                self.assertEqual(_git(root, "rev-parse", "HEAD").strip(), base_sha)
                self.assertEqual(
                    _git(root, "diff", "--cached", "--name-only"),
                    "",
                )
                self.assertFalse(_delivery_receipt_path(root, run_id).exists())


if __name__ == "__main__":
    unittest.main()
