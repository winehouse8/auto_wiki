"""SPEC-GH-DELIVERY-001의 로컬 Git/gh CLI 전달 Red 계약.

이 테스트는 실제 네트워크, 실제 GitHub 자격증명, 현재 작업 사본의 Git 상태를
사용하지 않는다. 기대하는 공개 API는 다음과 같다.

* ``main(argv, **dependencies)``: ``begin``/``publish`` argparse dispatch
* ``begin_run(context, repo_root=..., runner=..., now=...)``
* ``publish_run(context, repo_root=..., runner=..., gate_runner=...,
  transport=..., token_loader=..., now=...)``
* ``quality_gate_commands(now)``: 고정된 전체 품질 게이트
* ``GitHubCliTransport(runner=..., repo_root=..., token=...)``

runner와 gate_runner는 ``run(argv, cwd=..., env=..., input_text=...)``를
제공하고 subprocess.CompletedProcess와 같은 결과를 반환한다.
"""

from __future__ import annotations

import io
import json
import fcntl
import hashlib
import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

from tools import github_delivery


REPOSITORY = "winehouse8/auto_wiki"
BASE_BRANCH = "main"
APPROVAL = "COL-27B9ADD786ED"
POLICY = "SPEC-GH-DELIVERY-001/v1.1.0"
RUN_ID = "RUN-20260712T140000Z-ABC123"
NOW = "2026-07-12T23:30:00+09:00"
BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
TREE_SHA = "3" * 40
MERGE_SHA = "4" * 40
BRANCH = "wiki-auto/run-20260712t140000z-abc123"
SECRET = "fake-classic-token-ABC123"
REQUIRED_CHECK = "전체 저장소 품질 게이트"


def _api(name):
    value = getattr(github_delivery, name, None)
    if value is None:
        raise AssertionError(f"Red: tools.github_delivery.{name} API가 아직 없음")
    return value


@dataclass
class _Result:
    args: tuple[str, ...]
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class _FakeRunner:
    """로컬 git과 gh 프로세스의 비밀 없는 결정론적 대역."""

    def __init__(
        self,
        root,
        *,
        origin_url="https://github.com/winehouse8/auto_wiki.git",
        status="",
        local_head=BASE_SHA,
        remote_head=BASE_SHA,
        current_branch=BASE_BRANCH,
        checks_payload=None,
        auto_merge_request=None,
        git_common_dir=None,
        unresolved_threads=None,
    ):
        self.root = Path(root)
        self.origin_url = origin_url
        self.status = status
        self.local_head = local_head
        self.remote_head = remote_head
        self.current_branch = current_branch
        self.checks_payload = list(
            checks_payload
            if checks_payload is not None
            else [
                {
                    "state": "SUCCESS",
                    "bucket": "pass",
                    "name": REQUIRED_CHECK,
                    "workflow": "Wiki PR 품질 검증",
                }
            ]
        )
        self.auto_merge_request = auto_merge_request
        self.git_common_dir = Path(git_common_dir) if git_common_dir else self.root / ".git"
        self.unresolved_threads = list(unresolved_threads or [])
        self.after_commit = False
        self.committed_status = ""
        self.commit_message = ""
        self.calls = []

    def run(self, argv, *, cwd=None, env=None, input_text=None):
        args = tuple(str(value) for value in argv)
        call = {
            "argv": args,
            "cwd": str(cwd) if cwd is not None else None,
            "env": dict(env or {}),
            "input_text": input_text,
        }
        self.calls.append(call)

        if args[:4] == ("git", "remote", "get-url", "origin"):
            return _Result(args, stdout=self.origin_url + "\n")
        if args[:2] == ("git", "status"):
            return _Result(args, stdout=self.status)
        if args[:2] == ("git", "diff") and "--name-status" in args:
            source_status = self.committed_status if self.after_commit else self.status
            fields = []
            for line in source_status.splitlines():
                if not line or line.startswith("?? "):
                    continue
                code = line[:2]
                path = line[3:]
                status_code = (
                    "A" if "A" in code else "D" if "D" in code else "M"
                )
                fields.extend((status_code, path))
            payload = "\0".join(fields) + ("\0" if fields else "")
            return _Result(args, stdout=payload)
        if args[:3] == ("git", "ls-files", "--others"):
            paths = [
                line[3:]
                for line in self.status.splitlines()
                if line.startswith("?? ")
            ]
            payload = "\0".join(paths) + ("\0" if paths else "")
            return _Result(args, stdout=payload)
        if args[:3] == ("git", "rev-parse", "--show-toplevel"):
            return _Result(args, stdout=str(self.root) + "\n")
        if args[:3] == ("git", "rev-parse", "--git-common-dir"):
            return _Result(args, stdout=str(self.git_common_dir) + "\n")
        if args[:3] == ("git", "branch", "--show-current"):
            return _Result(args, stdout=self.current_branch + "\n")
        if args[:3] == ("git", "rev-parse", "HEAD"):
            sha = HEAD_SHA if self.after_commit else self.local_head
            return _Result(args, stdout=sha + "\n")
        if len(args) >= 3 and args[:2] == ("git", "rev-parse"):
            revision = args[-1]
            if revision in {
                "origin/main",
                "refs/remotes/origin/main",
                "refs/remotes/origin/main^{commit}",
            }:
                return _Result(args, stdout=self.remote_head + "\n")
            if revision in {"HEAD^{tree}", "HEAD^{tree}^{commit}"}:
                return _Result(args, stdout=TREE_SHA + "\n")
            if revision in {"HEAD^", "HEAD^1"}:
                return _Result(args, stdout=BASE_SHA + "\n")
        if args[:3] in {
            ("git", "switch", "-c"),
            ("git", "checkout", "-b"),
        }:
            self.current_branch = args[3]
            return _Result(args)
        if args[:2] == ("git", "commit"):
            self.committed_status = self.status
            self.after_commit = True
            self.status = ""
            return _Result(args)
        if args[:3] == ("git", "show", "-s"):
            return _Result(args, stdout=self.commit_message)
        if args[:3] == ("git", "diff", "--cached") and "--quiet" in args:
            return _Result(args, returncode=1)

        if args[:3] == ("gh", "pr", "list"):
            return _Result(args, stdout="[]\n")
        if args[:3] == ("gh", "pr", "create"):
            return _Result(args, stdout=f"https://github.com/{REPOSITORY}/pull/17\n")
        if args[:3] == ("gh", "pr", "view"):
            payload = {
                "number": 17,
                "url": f"https://github.com/{REPOSITORY}/pull/17",
                "isDraft": False,
                "state": "OPEN",
                "mergedAt": None,
                "mergeCommit": None,
                "headRefOid": HEAD_SHA,
                "baseRefOid": BASE_SHA,
                "autoMergeRequest": self.auto_merge_request,
            }
            return _Result(args, stdout=json.dumps(payload) + "\n")
        if args[:3] == ("gh", "pr", "checks"):
            return _Result(args, stdout=json.dumps(self.checks_payload) + "\n")
        if args[:2] == ("gh", "api") and "git/ref/heads/main" in " ".join(args):
            return _Result(args, stdout=json.dumps({"object": {"sha": BASE_SHA}}))
        if args[:2] == ("gh", "api") and "/git/commits/" in " ".join(args):
            return _Result(args, stdout=json.dumps({"tree": {"sha": TREE_SHA}}))
        if args[:3] == ("gh", "api", "graphql"):
            payload = [
                {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {
                                    "nodes": [
                                        {"isResolved": value}
                                        for value in self.unresolved_threads
                                    ],
                                    "pageInfo": {
                                        "hasNextPage": False,
                                        "endCursor": None,
                                    },
                                }
                            }
                        }
                    }
                }
            ]
            return _Result(args, stdout=json.dumps(payload))
        return _Result(args)


class _FakeGateRunner:
    def __init__(self, *, fail_at=None):
        self.fail_at = fail_at
        self.calls = []

    def run(self, argv, *, cwd=None, env=None, input_text=None):
        args = tuple(str(value) for value in argv)
        self.calls.append(args)
        return _Result(
            args,
            returncode=1 if args == self.fail_at else 0,
            stderr="고정 fixture 실패" if args == self.fail_at else "",
        )


class _FakeTransport:
    """publish와 순수 deliver의 연결만 확인하는 GitHub 대역."""

    def __init__(self):
        self.calls = []
        self.pr = None
        self.merge_requested = False

    def _record(self, name, **values):
        self.calls.append((name, values))

    def count(self, name):
        return sum(call_name == name for call_name, _ in self.calls)

    def find_delivery(self, *, repository, idempotency_key):
        self._record("find_delivery", repository=repository, key=idempotency_key)
        return dict(self.pr) if self.pr else None

    def get_base_sha(self, *, repository, base_branch):
        self._record("get_base_sha", repository=repository, base=base_branch)
        return BASE_SHA

    def create_branch(self, **kwargs):
        self._record("create_branch", **kwargs)
        return {"name": kwargs["branch"]}

    def create_pull_request(self, **kwargs):
        self._record("create_pull_request", **kwargs)
        self.pr = {
            "number": 17,
            "url": f"https://github.com/{REPOSITORY}/pull/17",
            "draft": kwargs["draft"],
            "state": "open",
            "merged": False,
            "merge_sha": None,
            "base_sha": BASE_SHA,
            "head_sha": kwargs["head_sha"],
            "tree_sha": kwargs["tree_sha"],
            "labels": [],
            "auto_merge_enabled": False,
        }
        return dict(self.pr)

    def add_labels(self, *, repository, pr_number, labels):
        self._record("add_labels", labels=list(labels))
        self.pr["labels"] = list(labels)

    def get_pull_request(self, *, repository, pr_number):
        self._record("get_pull_request", number=pr_number)
        result = dict(self.pr)
        result.update(
            {
                "base_sha": BASE_SHA,
                "head_sha": HEAD_SHA,
                "tree_sha": TREE_SHA,
                "unresolved_reviews": 0,
                "conflict": False,
            }
        )
        return result

    def get_checks(self, *, repository, pr_number, head_sha):
        self._record("get_checks", number=pr_number, head_sha=head_sha)
        return {
            "state": "success",
            "head_sha": HEAD_SHA,
            "checks": [{"name": REQUIRED_CHECK, "state": "success"}],
            "successful_names": [REQUIRED_CHECK],
        }

    def request_auto_merge(self, **kwargs):
        self._record("request_auto_merge", **kwargs)
        self.merge_requested = True
        self.pr.update(
            {
                "state": "closed",
                "merged": True,
                "merge_sha": MERGE_SHA,
                "auto_merge_enabled": False,
            }
        )
        return {"accepted": True}


def _context(*, changes):
    return {
        "repository": REPOSITORY,
        "base_branch": BASE_BRANCH,
        "approval_id": APPROVAL,
        "policy_version": POLICY,
        "run_id": RUN_ID,
        "actor": "agent:codex",
        "invocation": "예약",
        "work_type": "위생",
        "wiki_mode": "wiki-first",
        "changes": changes,
        "rfc_ids": ["RFC-03F4FE85BB44"],
        "approval_refs": [APPROVAL],
        "epistemic_impact": "C/S-level 및 생명주기 영향 없음",
        "unresolved": [],
        "rollback": "새 revert PR로 되돌린다.",
    }


def _begin_receipt(root, *, branch=BRANCH):
    path = Path(root) / ".git" / "wiki-delivery" / f"{RUN_ID}.begin.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "github-delivery-begin/v1",
                "repository": REPOSITORY,
                "base_branch": BASE_BRANCH,
                "approval_id": APPROVAL,
                "policy_version": POLICY,
                "run_id": RUN_ID,
                "actor": "agent:codex",
                "branch": branch,
                "base_sha": BASE_SHA,
                "started_at": NOW,
            }
        ),
        encoding="utf-8",
    )
    return path


def _real_git(root, *args):
    return subprocess.run(
        ("git", *args),
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _init_real_repository(root):
    root = Path(root)
    _real_git(root, "init", "-q", "-b", "main")
    _real_git(root, "config", "user.name", "Wiki 시험")
    _real_git(root, "config", "user.email", "wiki-test@example.invalid")
    (root / "README.md").write_text("# 시험 저장소\n", encoding="utf-8")
    (root / "state").mkdir()
    (root / "state" / "events.jsonl").write_text(
        '{"id":"EVT-1","event_hash":"시험"}\n', encoding="utf-8"
    )
    _real_git(root, "add", "README.md", "state/events.jsonl")
    _real_git(root, "commit", "-q", "-m", "시험 기준")
    return _real_git(root, "rev-parse", "HEAD")


def _publish(
    root,
    *,
    context,
    runner,
    gate_runner=None,
    transport=None,
    token_loader=None,
):
    for change in context.get("changes", []):
        if change.get("status") == "deleted":
            continue
        path = Path(root) / change["path"]
        if path.exists() or path.is_symlink():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if change["path"] == "wiki/index.md":
            content = "<!-- tools/wiki.py가 자동 생성함. 직접 수정하지 마세요. -->\n# 시험 색인\n"
        else:
            content = "시험 변경 내용\n"
        path.write_text(content, encoding="utf-8")
    return _api("publish_run")(
        context,
        repo_root=Path(root),
        runner=runner,
        gate_runner=gate_runner or _FakeGateRunner(),
        transport=transport or _FakeTransport(),
        token_loader=token_loader or (lambda: SECRET),
        now=NOW,
    )


class GitHubDeliveryCliDispatchRedTests(unittest.TestCase):
    def test_argparse_dispatches_begin_and_publish_without_network_defaults(self):
        main = _api("main")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(_context(changes=[]), ensure_ascii=False),
                encoding="utf-8",
            )
            output = io.StringIO()
            with mock.patch.object(github_delivery, "begin_run") as begin:
                begin.return_value = {"status": "begun"}
                code = main(
                    [
                        "begin",
                        "--repo-root",
                        str(root),
                        "--run-id",
                        RUN_ID,
                        "--actor",
                        "agent:codex",
                        "--invocation",
                        "예약",
                        "--work-type",
                        "위생",
                        "--wiki-mode",
                        "wiki-first",
                    ],
                    runner=_FakeRunner(root),
                    stdout=output,
                    now=NOW,
                )
                self.assertEqual(code, 0)
                begin.assert_called_once()

            with mock.patch.object(github_delivery, "publish_run") as publish:
                publish.return_value = {"status": "no-op"}
                code = main(
                    [
                        "publish",
                        "--repo-root",
                        str(root),
                        "--manifest",
                        str(manifest),
                    ],
                    runner=_FakeRunner(root),
                    gate_runner=_FakeGateRunner(),
                    transport=_FakeTransport(),
                    token_loader=lambda: SECRET,
                    stdout=output,
                    now=NOW,
                )
                self.assertEqual(code, 0)
                publish.assert_called_once()

    def test_publish_blocked_receipt_exits_two_instead_of_reporting_success(self):
        main = _api("main")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(_context(changes=[]), ensure_ascii=False),
                encoding="utf-8",
            )
            output = io.StringIO()
            with mock.patch.object(
                github_delivery,
                "publish_run",
                return_value={
                    "status": "blocked",
                    "route": "safe",
                    "reasons": ["원격 필수 check가 누락됨"],
                    "merge_requested": False,
                },
            ) as publish:
                code = main(
                    [
                        "publish",
                        "--repo-root",
                        str(root),
                        "--manifest",
                        str(manifest),
                    ],
                    runner=_FakeRunner(root),
                    gate_runner=_FakeGateRunner(),
                    transport=_FakeTransport(),
                    token_loader=lambda: SECRET,
                    stdout=output,
                    now=NOW,
                )

            publish.assert_called_once()
            self.assertEqual(code, 2)
            payload = json.loads(output.getvalue().strip())
            self.assertEqual(payload["status"], "blocked")


class GitHubDeliveryBeginRedTests(unittest.TestCase):
    def test_begin_supports_linked_worktree_gitfile_and_common_receipt_dir(self):
        begin_run = _api("begin_run")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "linked"
            common = Path(directory) / "main.git"
            root.mkdir()
            common.mkdir()
            (root / ".git").write_text(
                f"gitdir: {common / 'worktrees' / 'linked'}\n",
                encoding="utf-8",
            )
            runner = _FakeRunner(root, git_common_dir=common)

            receipt = begin_run(
                _context(changes=[]),
                repo_root=root,
                runner=runner,
                now=NOW,
            )

            self.assertEqual(receipt["status"], "begun")
            expected = common / "wiki-delivery" / f"{RUN_ID}.begin.json"
            self.assertTrue(expected.is_file())
            self.assertFalse((root / ".git" / "wiki-delivery").exists())

    def test_begin_validates_clean_exact_fresh_base_without_token_and_writes_receipt(self):
        begin_run = _api("begin_run")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            runner = _FakeRunner(root)

            receipt = begin_run(
                _context(changes=[]),
                repo_root=root,
                runner=runner,
                now=NOW,
            )

            self.assertEqual(receipt["status"], "begun")
            self.assertEqual(receipt["base_sha"], BASE_SHA)
            self.assertEqual(receipt["branch"], BRANCH)
            receipt_path = root / ".git" / "wiki-delivery" / f"{RUN_ID}.begin.json"
            self.assertTrue(receipt_path.is_file())
            stored = json.loads(receipt_path.read_text(encoding="utf-8"))
            for key in (
                "repository",
                "base_branch",
                "approval_id",
                "policy_version",
                "run_id",
                "actor",
                "branch",
                "base_sha",
                "started_at",
            ):
                self.assertEqual(stored[key], receipt[key])
            self.assertTrue(
                any(
                    call["argv"][:3] in {
                        ("git", "switch", "-c"),
                        ("git", "checkout", "-b"),
                    }
                    for call in runner.calls
                )
            )
            self.assertFalse(any(call["argv"][0] == "gh" for call in runner.calls))
            self.assertFalse(
                any("GH_TOKEN" in call["env"] for call in runner.calls)
            )

    def test_begin_blocks_dirty_worktree_before_branch_or_receipt(self):
        begin_run = _api("begin_run")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            runner = _FakeRunner(root, status=" M README.md\n")
            with self.assertRaises(github_delivery.DeliveryBlocked):
                begin_run(
                    _context(changes=[]), repo_root=root, runner=runner, now=NOW
                )
            self.assertFalse(
                any(
                    call["argv"][:3] in {
                        ("git", "switch", "-c"),
                        ("git", "checkout", "-b"),
                    }
                    for call in runner.calls
                )
            )
            self.assertFalse((root / ".git" / "wiki-delivery").exists())

    def test_begin_blocks_base_drift_and_exact_origin_mismatch(self):
        begin_run = _api("begin_run")
        fixtures = (
            {"remote_head": "a" * 40},
            {"origin_url": "https://github.com/winehouse8/auto_wiki-fork.git"},
            {"current_branch": "feature/not-main"},
        )
        for overrides in fixtures:
            with self.subTest(overrides=overrides):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    (root / ".git").mkdir()
                    runner = _FakeRunner(root, **overrides)
                    with self.assertRaises(github_delivery.DeliveryBlocked):
                        begin_run(
                            _context(changes=[]),
                            repo_root=root,
                            runner=runner,
                            now=NOW,
                        )
                    self.assertFalse(
                        (root / ".git" / "wiki-delivery").exists()
                    )


class GitHubDeliveryPublishRedTests(unittest.TestCase):
    def test_post_gate_manifest_accepts_only_digest_valid_release_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_dir = root / "evaluations" / "reports"
            archive_dir.mkdir(parents=True)
            fingerprint = "a" * 64
            report = {
                "passed": True,
                "production_certified": False,
                "component_fingerprint": fingerprint,
                "gates": [
                    {"name": f"gate-{index}", "passed": True}
                    for index in range(8)
                ],
            }
            material = json.dumps(
                report,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            report["report_digest"] = hashlib.sha256(material).hexdigest()
            path = f"evaluations/reports/v4-release-{fingerprint[:16]}.json"
            (root / path).write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            declared = {"wiki/index.md": "modified"}
            actual = {
                "wiki/index.md": {"status": "modified", "git_status": "M"},
                path: {"status": "added", "git_status": "?"},
            }

            reconciled = _api("_reconcile_post_gate_manifest")(
                declared,
                actual,
                root=root,
            )
            self.assertEqual(set(reconciled), set(actual))

            with self.assertRaises(github_delivery.DeliveryBlocked):
                _api("_reconcile_post_gate_manifest")(
                    declared,
                    {
                        **actual,
                        "unexpected/output.json": {
                            "status": "added",
                            "git_status": "?",
                        },
                    },
                    root=root,
                )
            report["report_digest"] = "b" * 64
            (root / path).write_text(
                json.dumps(report, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(github_delivery.DeliveryBlocked):
                _api("_reconcile_post_gate_manifest")(
                    declared,
                    actual,
                    root=root,
                )

    def test_owned_post_commit_retry_resumes_without_duplicate_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            _begin_receipt(root)
            path = "tools/github_delivery.py"
            runner = _FakeRunner(root, current_branch=BRANCH, status="")
            runner.after_commit = True
            runner.committed_status = f" M {path}\n"
            runner.commit_message = (
                f"[위키 자동화] 위생 — {RUN_ID}\n\n"
                f"Wiki-Run-ID: {RUN_ID}\nWiki-Actor: agent:codex\n"
                f"Wiki-Gate-Digest: {'a' * 64}\n"
            )
            transport = _FakeTransport()

            receipt = _publish(
                root,
                context=_context(changes=[{"path": path, "status": "modified"}]),
                runner=runner,
                transport=transport,
            )

            self.assertEqual(receipt["status"], "review")
            self.assertEqual(
                sum(call["argv"][:2] == ("git", "commit") for call in runner.calls),
                0,
            )
            self.assertEqual(transport.count("create_pull_request"), 1)

    def test_owned_post_commit_retry_requires_recorded_gate_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            _begin_receipt(root)
            path = "tools/github_delivery.py"
            runner = _FakeRunner(root, current_branch=BRANCH, status="")
            runner.after_commit = True
            runner.committed_status = f" M {path}\n"
            runner.commit_message = (
                f"Wiki-Run-ID: {RUN_ID}\nWiki-Actor: agent:codex\n"
            )
            transport = _FakeTransport()

            with self.assertRaises(github_delivery.DeliveryBlocked):
                _publish(
                    root,
                    context=_context(
                        changes=[{"path": path, "status": "modified"}]
                    ),
                    runner=runner,
                    transport=transport,
                )

            self.assertEqual(transport.calls, [])

    def test_real_git_exact_token_is_blocked_before_stage_commit_or_remote(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_sha = _init_real_repository(root)
            _real_git(root, "switch", "-q", "-c", BRANCH)
            candidate = root / "wiki" / "manual.md"
            candidate.parent.mkdir()
            candidate.write_text(
                f"---\ntype: Concept\n---\n# 시험\n{SECRET}\n",
                encoding="utf-8",
            )
            receipt_path = (
                root / ".git" / "wiki-delivery" / f"{RUN_ID}.begin.json"
            )
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(
                json.dumps(
                    {
                        "schema_version": "github-delivery-begin/v1",
                        "repository": REPOSITORY,
                        "base_branch": BASE_BRANCH,
                        "approval_id": APPROVAL,
                        "policy_version": POLICY,
                        "run_id": RUN_ID,
                        "actor": "agent:codex",
                        "branch": BRANCH,
                        "base_sha": base_sha,
                        "started_at": NOW,
                    }
                ),
                encoding="utf-8",
            )
            transport = _FakeTransport()
            token_calls = []

            with self.assertRaises(github_delivery.DeliveryBlocked):
                _api("publish_run")(
                    _context(
                        changes=[
                            {
                                "path": "wiki/manual.md",
                                "status": "added",
                                "generated": True,
                                "semantic_change": False,
                            }
                        ]
                    ),
                    repo_root=root,
                    runner=github_delivery.SubprocessRunner(),
                    gate_runner=_FakeGateRunner(),
                    transport=transport,
                    token_loader=lambda: token_calls.append("token") or SECRET,
                    now=NOW,
                )

            self.assertEqual(token_calls, ["token"])
            self.assertEqual(transport.calls, [])
            self.assertEqual(_real_git(root, "rev-parse", "HEAD"), base_sha)
            self.assertEqual(_real_git(root, "diff", "--cached", "--name-only"), "")
            self.assertIn(
                "?? wiki/manual.md",
                _real_git(
                    root,
                    "status",
                    "--porcelain",
                    "--untracked-files=all",
                ),
            )

    def test_real_git_quarantine_payload_is_blocked_before_token_commit_or_remote(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_sha = _init_real_repository(root)
            _real_git(root, "switch", "-q", "-c", BRANCH)
            relative = (
                "raw/quarantine/" + "a" * 64 + "/artifact.txt"
            )
            payload = root / relative
            payload.parent.mkdir(parents=True)
            payload.write_text("격리된 신뢰하지 않는 payload\n", encoding="utf-8")
            receipt_path = (
                root / ".git" / "wiki-delivery" / f"{RUN_ID}.begin.json"
            )
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(
                json.dumps(
                    {
                        "schema_version": "github-delivery-begin/v1",
                        "repository": REPOSITORY,
                        "base_branch": BASE_BRANCH,
                        "approval_id": APPROVAL,
                        "policy_version": POLICY,
                        "run_id": RUN_ID,
                        "actor": "agent:codex",
                        "branch": BRANCH,
                        "base_sha": base_sha,
                        "started_at": NOW,
                    }
                ),
                encoding="utf-8",
            )
            transport = _FakeTransport()
            token_calls = []

            with self.assertRaises(github_delivery.DeliveryBlocked):
                _api("publish_run")(
                    _context(
                        changes=[{"path": relative, "status": "added"}]
                    ),
                    repo_root=root,
                    runner=github_delivery.SubprocessRunner(),
                    gate_runner=_FakeGateRunner(),
                    transport=transport,
                    token_loader=lambda: token_calls.append("token") or SECRET,
                    now=NOW,
                )

            self.assertEqual(token_calls, [])
            self.assertEqual(transport.calls, [])
            self.assertEqual(_real_git(root, "rev-parse", "HEAD"), base_sha)
            self.assertEqual(_real_git(root, "diff", "--cached", "--name-only"), "")

    def test_real_git_event_rewrite_is_not_mislabeled_append_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_sha = _init_real_repository(root)
            (root / "state" / "events.jsonl").write_text(
                '{"id":"EVT-X","event_hash":"변조"}\n', encoding="utf-8"
            )

            measured = _api("inspect_actual_changes")(
                repo_root=root,
                runner=github_delivery.SubprocessRunner(),
                base_sha=base_sha,
                expected_paths=["state/events.jsonl"],
            )

            self.assertEqual(len(measured), 1)
            self.assertFalse(measured[0]["append_only_verified"])
            self.assertEqual(
                github_delivery.classify_changes(measured)["route"], "block"
            )

    def test_real_git_korean_rename_scope_uses_nul_diff_not_porcelain_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _init_real_repository(root)
            folder = root / "governance" / "proposals"
            folder.mkdir(parents=True)
            old = folder / "old-proposal.md"
            old.write_text("# 이전 제안\n", encoding="utf-8")
            _real_git(root, "add", old.relative_to(root).as_posix())
            _real_git(root, "commit", "-q", "-m", "이전 제안 추가")
            base_sha = _real_git(root, "rev-parse", "HEAD")
            new = folder / "새-제안.md"
            old.rename(new)
            declared = [
                {"path": old.relative_to(root).as_posix(), "status": "deleted"},
                {"path": new.relative_to(root).as_posix(), "status": "added"},
            ]

            scope = github_delivery._assert_worktree_scope(
                declared,
                root=root,
                runner=github_delivery.SubprocessRunner(),
                base_sha=base_sha,
            )

            self.assertEqual(set(scope), {item["path"] for item in declared})

    def test_concurrent_publish_lock_blocks_before_gate_token_or_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            _begin_receipt(root)
            runner = _FakeRunner(root, current_branch=BRANCH, status="")
            gate_runner = _FakeGateRunner()
            transport = _FakeTransport()
            token_calls = []
            lock_path = root / ".git" / "wiki-delivery" / "publish.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            with lock_path.open("w+", encoding="utf-8") as held:
                fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(github_delivery.DeliveryBlocked):
                    _publish(
                        root,
                        context=_context(changes=[]),
                        runner=runner,
                        gate_runner=gate_runner,
                        transport=transport,
                        token_loader=lambda: token_calls.append("token") or SECRET,
                    )

            self.assertEqual(gate_runner.calls, [])
            self.assertEqual(token_calls, [])
            self.assertEqual(transport.calls, [])

    def test_publish_requires_matching_begin_receipt_branch_and_manifest(self):
        fixtures = (
            {
                "receipt": False,
                "branch": BRANCH,
                "status": " M wiki/index.md\n",
                "changes": [
                    {
                        "path": "wiki/index.md",
                        "status": "modified",
                        "generated": True,
                        "semantic_change": False,
                    }
                ],
            },
            {
                "receipt": True,
                "branch": "wiki-auto/other-run",
                "status": " M wiki/index.md\n",
                "changes": [
                    {
                        "path": "wiki/index.md",
                        "status": "modified",
                        "generated": True,
                        "semantic_change": False,
                    }
                ],
            },
            {
                "receipt": True,
                "branch": BRANCH,
                "status": " M wiki/index.md\n M README.md\n",
                "changes": [
                    {
                        "path": "wiki/index.md",
                        "status": "modified",
                        "generated": True,
                        "semantic_change": False,
                    }
                ],
            },
        )
        for fixture in fixtures:
            with self.subTest(fixture=fixture):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    (root / ".git").mkdir()
                    if fixture["receipt"]:
                        _begin_receipt(root)
                    runner = _FakeRunner(
                        root,
                        current_branch=fixture["branch"],
                        status=fixture["status"],
                    )
                    token_calls = []
                    with self.assertRaises(github_delivery.DeliveryBlocked):
                        _publish(
                            root,
                            context=_context(changes=fixture["changes"]),
                            runner=runner,
                            token_loader=lambda: token_calls.append("token") or SECRET,
                        )
                    self.assertEqual(token_calls, [])
                    self.assertFalse(
                        any(call["argv"][:2] == ("git", "add") for call in runner.calls)
                    )

    def test_measured_diff_hazards_override_caller_booleans_and_block(self):
        fixtures = (
            (
                "secret",
                "wiki/index.md",
                "modified",
                {"secret_detected": True},
            ),
            (
                "binary",
                "wiki/index.md",
                "modified",
                {"binary": True},
            ),
            (
                "symlink",
                "wiki/index.md",
                "modified",
                {"symlink": True},
            ),
            (
                "oversized",
                "wiki/index.md",
                "modified",
                {"oversized": True},
            ),
            (
                "raw-overwrite",
                "raw/source/original.pdf",
                "added",
                {"status": "modified"},
            ),
            (
                "event-rewrite",
                "state/events.jsonl",
                "modified",
                {"append_only_verified": False},
            ),
        )
        for name, path, declared_status, measured_override in fixtures:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    (root / ".git").mkdir()
                    _begin_receipt(root)
                    declared = {
                        "path": path,
                        "status": declared_status,
                        "generated": True,
                        "semantic_change": False,
                        "secret_detected": False,
                        "binary": False,
                        "symlink": False,
                        "oversized": False,
                        "append_only_verified": True,
                    }
                    measured = dict(declared)
                    measured.update(measured_override)
                    actual_status = measured.get("status", declared_status)
                    porcelain = (
                        f"?? {path}\n"
                        if actual_status == "added"
                        else f" M {path}\n"
                    )
                    runner = _FakeRunner(
                        root,
                        current_branch=BRANCH,
                        status=porcelain,
                    )
                    transport = _FakeTransport()
                    token_calls = []
                    with mock.patch.object(
                        github_delivery,
                        "inspect_actual_changes",
                        create=True,
                        return_value=[measured],
                    ) as inspector:
                        try:
                            receipt = _publish(
                                root,
                                context=_context(changes=[declared]),
                                runner=runner,
                                transport=transport,
                                token_loader=lambda: token_calls.append("token")
                                or SECRET,
                            )
                        except github_delivery.DeliveryBlocked:
                            status = "blocked"
                        else:
                            status = receipt["status"]

                    self.assertEqual(status, "blocked")
                    inspector.assert_called_once()
                    self.assertEqual(token_calls, [])
                    self.assertEqual(transport.calls, [])
                    self.assertFalse(
                        any(
                            call["argv"][:2]
                            in {("git", "commit"), ("git", "push")}
                            for call in runner.calls
                        )
                    )

    def test_measured_generated_and_semantic_facts_force_draft_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            _begin_receipt(root)
            declared = {
                "path": "wiki/index.md",
                "status": "modified",
                "generated": True,
                "semantic_change": False,
            }
            measured = {
                "path": "wiki/index.md",
                "status": "modified",
                "generated": False,
                "semantic_change": True,
            }
            runner = _FakeRunner(
                root,
                current_branch=BRANCH,
                status=" M wiki/index.md\n",
            )
            transport = _FakeTransport()
            with mock.patch.object(
                github_delivery,
                "inspect_actual_changes",
                create=True,
                return_value=[measured],
            ) as inspector:
                receipt = _publish(
                    root,
                    context=_context(changes=[declared]),
                    runner=runner,
                    transport=transport,
                )

            self.assertEqual(receipt["status"], "review")
            inspector.assert_called_once()
            pr_call = next(
                details
                for name, details in transport.calls
                if name == "create_pull_request"
            )
            self.assertTrue(pr_call["draft"])
            self.assertEqual(transport.count("request_auto_merge"), 0)

    def test_no_op_uses_no_token_gate_commit_push_or_pr(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            _begin_receipt(root)
            runner = _FakeRunner(root, current_branch=BRANCH, status="")
            gate_runner = _FakeGateRunner()
            transport = _FakeTransport()
            token_calls = []

            receipt = _publish(
                root,
                context=_context(changes=[]),
                runner=runner,
                gate_runner=gate_runner,
                transport=transport,
                token_loader=lambda: token_calls.append("token") or SECRET,
            )

            self.assertEqual(receipt["status"], "no-op")
            self.assertEqual(token_calls, [])
            self.assertEqual(gate_runner.calls, [])
            self.assertEqual(transport.calls, [])
            forbidden = {("git", "add"), ("git", "commit"), ("git", "push")}
            self.assertFalse(
                any(call["argv"][:2] in forbidden for call in runner.calls)
            )

    def test_quality_gates_have_exact_order_and_failure_blocks_before_token_or_stage(self):
        expected = (
            ("python3", "tools/wiki.py", "evaluate"),
            ("python3", "tools/wiki.py", "render", "--no-log"),
            ("python3", "tools/wiki.py", "memory-hygiene", "--now", NOW),
            ("python3", "tools/wiki.py", "hygiene-plan", "--now", NOW),
            (
                "python3",
                "tools/wiki.py",
                "lint",
                "--quarantine-profile",
                "public-clean-clone",
                "--no-log",
            ),
            ("python3", "tools/wiki.py", "language-validate"),
            (
                "python3",
                "tools/wiki.py",
                "validate",
                "--quarantine-profile",
                "public-clean-clone",
            ),
            ("python3", "tools/wiki.py", "okf-validate"),
            ("python3", "-m", "unittest", "discover", "-s", "tests", "-v"),
            (
                "python3",
                "tools/wiki.py",
                "release-check",
                "--quarantine-profile",
                "public-clean-clone",
                "--no-log",
            ),
        )
        self.assertEqual(tuple(_api("quality_gate_commands")(NOW)), expected)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            _begin_receipt(root)
            change = {
                "path": "wiki/index.md",
                "status": "modified",
                "generated": True,
                "semantic_change": False,
            }
            runner = _FakeRunner(
                root, current_branch=BRANCH, status=" M wiki/index.md\n"
            )
            failed = expected[6]
            gate_runner = _FakeGateRunner(fail_at=failed)
            token_calls = []

            try:
                receipt = _publish(
                    root,
                    context=_context(changes=[change]),
                    runner=runner,
                    gate_runner=gate_runner,
                    token_loader=lambda: token_calls.append("token") or SECRET,
                )
            except github_delivery.DeliveryBlocked:
                status = "blocked"
            else:
                status = receipt["status"]

            self.assertEqual(status, "blocked")
            self.assertEqual(gate_runner.calls, list(expected[:7]))
            self.assertEqual(token_calls, [])
            self.assertFalse(
                any(call["argv"][:2] == ("git", "add") for call in runner.calls)
            )

    def test_publish_stages_only_manifest_paths_and_review_pr_never_merges(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            _begin_receipt(root)
            path = "tools/github_delivery.py"
            runner = _FakeRunner(
                root, current_branch=BRANCH, status=f" M {path}\n"
            )
            transport = _FakeTransport()

            receipt = _publish(
                root,
                context=_context(changes=[{"path": path, "status": "modified"}]),
                runner=runner,
                transport=transport,
            )

            self.assertEqual(receipt["status"], "review")
            stage_calls = [
                call["argv"]
                for call in runner.calls
                if call["argv"][:2] == ("git", "add")
            ]
            self.assertEqual(stage_calls, [("git", "add", "--", path)])
            flat_commands = [token for call in runner.calls for token in call["argv"]]
            self.assertNotIn("-A", flat_commands)
            self.assertFalse(
                any(call["argv"] == ("git", "add", ".") for call in runner.calls)
            )
            push_calls = [
                call["argv"]
                for call in runner.calls
                if call["argv"][:2] == ("git", "push")
            ]
            self.assertEqual(len(push_calls), 1)
            push = push_calls[0]
            self.assertEqual(
                push,
                (
                    "git",
                    "push",
                    "--set-upstream",
                    "origin",
                    f"{BRANCH}:{BRANCH}",
                ),
            )
            self.assertEqual(push.count("push"), 1)
            self.assertIn(BRANCH, " ".join(push))
            self.assertNotIn("--force", push)
            self.assertNotIn("main:main", " ".join(push))
            commit_text = " ".join(
                token
                for call in runner.calls
                if call["argv"][:2] == ("git", "commit")
                for token in call["argv"]
            )
            self.assertIn(f"Wiki-Run-ID: {RUN_ID}", commit_text)
            self.assertIn("Wiki-Actor: agent:codex", commit_text)
            self.assertIn("Wiki-Gate-Digest:", commit_text)
            pr_call = next(
                values
                for name, values in transport.calls
                if name == "create_pull_request"
            )
            self.assertTrue(pr_call["draft"])
            self.assertEqual(pr_call["branch"], BRANCH)
            self.assertEqual(transport.count("request_auto_merge"), 0)

    def test_safe_publish_pushes_branch_then_core_deliver_merges_and_records_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            _begin_receipt(root)
            change = {
                "path": "wiki/index.md",
                "status": "modified",
                "generated": True,
                "semantic_change": False,
            }
            runner = _FakeRunner(
                root, current_branch=BRANCH, status=" M wiki/index.md\n"
            )
            transport = _FakeTransport()

            receipt = _publish(
                root,
                context=_context(changes=[change]),
                runner=runner,
                transport=transport,
            )

            self.assertEqual(receipt["status"], "merged")
            self.assertEqual(receipt["merge_sha"], MERGE_SHA)
            push_position = next(
                index
                for index, call in enumerate(runner.calls)
                if call["argv"][:2] == ("git", "push")
            )
            self.assertGreaterEqual(push_position, 0)
            self.assertEqual(transport.count("create_pull_request"), 1)
            self.assertEqual(transport.count("request_auto_merge"), 1)
            delivery_path = (
                root / ".git" / "wiki-delivery" / f"{RUN_ID}.delivery.json"
            )
            self.assertTrue(delivery_path.is_file())
            stored = json.loads(delivery_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["pr_number"], 17)
            self.assertEqual(stored["merge_sha"], MERGE_SHA)
            self.assertNotIn(SECRET, delivery_path.read_text(encoding="utf-8"))


class GitHubCliTransportRemoteStateRedTests(unittest.TestCase):
    def test_read_queries_retry_transient_5xx_but_not_403(self):
        class RetryRunner(_FakeRunner):
            def __init__(self, *args, failures, **kwargs):
                super().__init__(*args, **kwargs)
                self.failures = list(failures)
                self.ref_attempts = 0

            def run(self, argv, *, cwd=None, env=None, input_text=None):
                args = tuple(str(value) for value in argv)
                if args[:2] == ("gh", "api") and "git/ref/heads/main" in " ".join(args):
                    self.ref_attempts += 1
                    if self.failures:
                        status = self.failures.pop(0)
                        return _Result(
                            args,
                            returncode=1,
                            stderr=f"HTTP {status} 비밀 없는 시험 실패",
                        )
                return super().run(
                    argv, cwd=cwd, env=env, input_text=input_text
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transient = RetryRunner(root, failures=[502])
            transport = _api("GitHubCliTransport")(
                runner=transient,
                repo_root=root,
                token=SECRET,
            )
            with mock.patch("time.sleep") as sleeper:
                self.assertEqual(
                    transport.get_base_sha(
                        repository=REPOSITORY,
                        base_branch=BASE_BRANCH,
                    ),
                    BASE_SHA,
                )
            self.assertEqual(transient.ref_attempts, 2)
            sleeper.assert_called_once()

            forbidden = RetryRunner(root, failures=[403, 403])
            blocked = _api("GitHubCliTransport")(
                runner=forbidden,
                repo_root=root,
                token=SECRET,
            )
            with self.assertRaises(github_delivery.DeliveryBlocked):
                blocked.get_base_sha(
                    repository=REPOSITORY,
                    base_branch=BASE_BRANCH,
                )
            self.assertEqual(forbidden.ref_attempts, 1)

    def test_cli_counts_unresolved_review_threads_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = _FakeRunner(root, unresolved_threads=[False, True, False])
            transport = _api("GitHubCliTransport")(
                runner=runner,
                repo_root=root,
                token=SECRET,
            )

            pull_request = transport.get_pull_request(
                repository=REPOSITORY,
                pr_number=17,
            )

            self.assertEqual(pull_request["unresolved_reviews"], 2)
            graphql = next(
                call
                for call in runner.calls
                if call["argv"][:3] == ("gh", "api", "graphql")
            )
            self.assertIn("--paginate", graphql["argv"])
            self.assertIn("--slurp", graphql["argv"])

    def test_cli_checks_require_exact_configured_name_not_any_success(self):
        fixtures = (
            (
                [
                    {
                        "state": "SUCCESS",
                        "bucket": "pass",
                        "name": REQUIRED_CHECK,
                        "workflow": "Wiki PR 품질 검증",
                    }
                ],
                "success",
            ),
            (
                [
                    {
                        "state": "SUCCESS",
                        "bucket": "pass",
                        "name": REQUIRED_CHECK + "-가짜",
                        "workflow": "Wiki PR 품질 검증",
                    }
                ],
                "missing",
            ),
            (
                [
                    {
                        "state": "SUCCESS",
                        "bucket": "pass",
                        "name": "다른 성공 check",
                        "workflow": "다른 workflow",
                    }
                ],
                "missing",
            ),
        )
        for checks_payload, expected_state in fixtures:
            with self.subTest(expected_state=expected_state, checks=checks_payload):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    runner = _FakeRunner(root, checks_payload=checks_payload)
                    transport = _api("GitHubCliTransport")(
                        runner=runner,
                        repo_root=root,
                        token=SECRET,
                    )

                    result = transport.get_checks(
                        repository=REPOSITORY,
                        pr_number=17,
                        head_sha=HEAD_SHA,
                    )

                    self.assertEqual(result["state"], expected_state)

    def test_cli_pr_state_exposes_armed_auto_merge_for_retry_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = _FakeRunner(
                root,
                auto_merge_request={
                    "enabledAt": "2026-07-12T14:00:00Z",
                    "mergeMethod": "SQUASH",
                },
            )
            transport = _api("GitHubCliTransport")(
                runner=runner,
                repo_root=root,
                token=SECRET,
            )

            pull_request = transport.get_pull_request(
                repository=REPOSITORY,
                pr_number=17,
            )

            self.assertTrue(pull_request.get("auto_merge_enabled"))
            view_call = next(
                call
                for call in runner.calls
                if call["argv"][:3] == ("gh", "pr", "view")
            )
            json_fields = view_call["argv"][view_call["argv"].index("--json") + 1]
            self.assertIn("autoMergeRequest", json_fields.split(","))


class GitHubCliTransportSecretBoundaryRedTests(unittest.TestCase):
    def test_gh_and_push_receive_token_only_via_gh_token_environment(self):
        transport_type = _api("GitHubCliTransport")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = _FakeRunner(root, current_branch=BRANCH)
            transport = transport_type(
                runner=runner,
                repo_root=root,
                token=SECRET,
            )

            self.assertEqual(
                transport.get_base_sha(
                    repository=REPOSITORY, base_branch=BASE_BRANCH
                ),
                BASE_SHA,
            )
            transport.create_branch(
                repository=REPOSITORY,
                branch=BRANCH,
                base_sha=BASE_SHA,
                idempotency_key="a" * 64,
            )
            transport.create_pull_request(
                repository=REPOSITORY,
                base_branch=BASE_BRANCH,
                branch=BRANCH,
                title="[위키 자동화] 사람 검토 필요",
                body="비밀 없는 사람 검토 본문",
                draft=True,
                idempotency_key="a" * 64,
                head_sha=HEAD_SHA,
                tree_sha=TREE_SHA,
            )
            transport.get_checks(
                repository=REPOSITORY,
                pr_number=17,
                head_sha=HEAD_SHA,
            )

            external_calls = [
                call
                for call in runner.calls
                if call["argv"][0] in {"gh", "git"}
                and (
                    call["argv"][0] == "gh"
                    or call["argv"][:2] == ("git", "push")
                )
            ]
            self.assertTrue(external_calls)
            for call in external_calls:
                with self.subTest(argv=call["argv"]):
                    self.assertEqual(call["env"].get("GH_TOKEN"), SECRET)
                    observable = json.dumps(
                        {
                            "argv": call["argv"],
                            "cwd": call["cwd"],
                            "input": call["input_text"],
                        },
                        ensure_ascii=False,
                    )
                    self.assertNotIn(SECRET, observable)

            all_argv = [token for call in runner.calls for token in call["argv"]]
            self.assertNotIn(SECRET, all_argv)
            joined = " ".join(all_argv).casefold()
            self.assertNotIn("remote set-url", joined)
            self.assertNotIn("gh auth login", joined)
            self.assertNotIn("--admin", joined)

            push_call = next(
                call
                for call in runner.calls
                if call["argv"][:2] == ("git", "push")
            )
            self.assertEqual(push_call["env"].get("GIT_CONFIG_COUNT"), "2")
            self.assertEqual(
                push_call["env"].get("GIT_CONFIG_KEY_0"),
                "credential.https://github.com.helper",
            )
            self.assertEqual(push_call["env"].get("GIT_CONFIG_VALUE_0"), "")
            self.assertEqual(
                push_call["env"].get("GIT_CONFIG_KEY_1"),
                "credential.https://github.com.helper",
            )
            self.assertEqual(
                push_call["env"].get("GIT_CONFIG_VALUE_1"),
                "!gh auth git-credential",
            )
            self.assertEqual(push_call["env"].get("GIT_TERMINAL_PROMPT"), "0")
            self.assertEqual(push_call["env"].get("GCM_INTERACTIVE"), "Never")
            self.assertEqual(push_call["env"].get("GH_PROMPT_DISABLED"), "1")

            pr_create = next(
                call
                for call in runner.calls
                if call["argv"][:3] == ("gh", "pr", "create")
            )
            self.assertIn("--assignee", pr_create["argv"])
            self.assertIn("winehouse8", pr_create["argv"])

            checks = next(
                call
                for call in runner.calls
                if call["argv"][:3] == ("gh", "pr", "checks")
            )
            self.assertIn("--watch", checks["argv"])
            self.assertIn("--fail-fast", checks["argv"])


if __name__ == "__main__":
    unittest.main()
