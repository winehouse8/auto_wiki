import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock


try:
    from tools import github_delivery
except ImportError as exc:  # Red 단계에서는 아직 구현 모듈이 없다.
    github_delivery = None
    GITHUB_DELIVERY_IMPORT_ERROR = exc
else:
    GITHUB_DELIVERY_IMPORT_ERROR = None


EXPECTED_REPOSITORY = "winehouse8/auto_wiki"
EXPECTED_BASE = "main"
EXPECTED_APPROVAL = "COL-27B9ADD786ED"
POLICY_VERSION = "SPEC-GH-DELIVERY-001/v1.1.0"
BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
TREE_SHA = "3" * 40
MERGE_SHA = "4" * 40
REQUIRED_CHECK = "전체 저장소 품질 게이트"


def _safe_change():
    return {
        "path": "wiki/index.md",
        "status": "modified",
        "generated": True,
        "semantic_change": False,
    }


def _request(*, repository=EXPECTED_REPOSITORY, changes=None):
    return {
        "repository": repository,
        "base_branch": EXPECTED_BASE,
        "approval_id": EXPECTED_APPROVAL,
        "policy_version": POLICY_VERSION,
        "run_id": "RUN-20260712T140000Z-ABC123",
        "actor": "agent:codex",
        "invocation": "예약",
        "work_type": "위생",
        "wiki_mode": "wiki-first",
        "base_sha": BASE_SHA,
        "head_sha": HEAD_SHA,
        "tree_sha": TREE_SHA,
        "changes": [_safe_change()] if changes is None else changes,
        "rfc_ids": ["RFC-03F4FE85BB44"],
        "approval_refs": [EXPECTED_APPROVAL],
        "local_gates": {"전체 릴리스 게이트": "success"},
        "epistemic_impact": "C/S-level 및 생명주기 영향 없음",
        "unresolved": [],
        "rollback": "새 revert PR로 되돌린다.",
    }


class _FakeGitProbe:
    def __init__(self, *, ignored=True, tracked=False):
        self.ignored = ignored
        self.tracked = tracked
        self.calls = []

    def is_ignored(self, path):
        self.calls.append(("is_ignored", Path(path)))
        return self.ignored

    def is_tracked(self, path):
        self.calls.append(("is_tracked", Path(path)))
        return self.tracked


class _FakeTransport:
    """네트워크와 자격증명을 사용하지 않는 결정론적 GitHub 대역이다."""

    def __init__(
        self,
        *,
        check_state="success",
        remote_base_sha=BASE_SHA,
        remote_head_sha=HEAD_SHA,
        remote_tree_sha=TREE_SHA,
        unresolved_reviews=0,
        conflict=False,
        check_names=None,
        merge_immediately=True,
    ):
        self.check_state = check_state
        self.remote_base_sha = remote_base_sha
        self.remote_head_sha = remote_head_sha
        self.remote_tree_sha = remote_tree_sha
        self.unresolved_reviews = unresolved_reviews
        self.conflict = conflict
        self.check_names = list(
            [REQUIRED_CHECK] if check_names is None else check_names
        )
        self.merge_immediately = merge_immediately
        self.calls = []
        self.deliveries = {}
        self.pull_requests = {}
        self.next_number = 17

    def _record(self, name, **details):
        self.calls.append((name, details))

    def count(self, name):
        return sum(call_name == name for call_name, _ in self.calls)

    def find_delivery(self, *, repository, idempotency_key):
        self._record(
            "find_delivery",
            repository=repository,
            idempotency_key=idempotency_key,
        )
        number = self.deliveries.get(idempotency_key)
        return dict(self.pull_requests[number]) if number is not None else None

    def get_base_sha(self, *, repository, base_branch):
        self._record(
            "get_base_sha",
            repository=repository,
            base_branch=base_branch,
        )
        return self.remote_base_sha

    def create_branch(self, *, repository, branch, base_sha, idempotency_key):
        self._record(
            "create_branch",
            repository=repository,
            branch=branch,
            base_sha=base_sha,
            idempotency_key=idempotency_key,
        )
        return {"name": branch, "base_sha": base_sha}

    def create_pull_request(
        self,
        *,
        repository,
        base_branch,
        branch,
        title,
        body,
        draft,
        idempotency_key,
        head_sha,
        tree_sha,
    ):
        self._record(
            "create_pull_request",
            repository=repository,
            base_branch=base_branch,
            branch=branch,
            title=title,
            body=body,
            draft=draft,
            idempotency_key=idempotency_key,
        )
        number = self.next_number
        self.next_number += 1
        pull_request = {
            "number": number,
            "url": f"https://example.invalid/{repository}/pull/{number}",
            "draft": draft,
            "state": "open",
            "merged": False,
            "merge_sha": None,
            "base_sha": self.remote_base_sha,
            "head_sha": head_sha,
            "tree_sha": tree_sha,
            "labels": [],
            "idempotency_key": idempotency_key,
            "auto_merge_enabled": False,
        }
        self.deliveries[idempotency_key] = number
        self.pull_requests[number] = pull_request
        return dict(pull_request)

    def add_labels(self, *, repository, pr_number, labels):
        self._record(
            "add_labels",
            repository=repository,
            pr_number=pr_number,
            labels=list(labels),
        )
        self.pull_requests[pr_number]["labels"] = list(labels)

    def get_pull_request(self, *, repository, pr_number):
        self._record(
            "get_pull_request",
            repository=repository,
            pr_number=pr_number,
        )
        pull_request = dict(self.pull_requests[pr_number])
        pull_request.update(
            {
                "base_sha": self.remote_base_sha,
                "head_sha": self.remote_head_sha,
                "tree_sha": self.remote_tree_sha,
                "unresolved_reviews": self.unresolved_reviews,
                "conflict": self.conflict,
            }
        )
        return pull_request

    def get_checks(self, *, repository, pr_number, head_sha):
        self._record(
            "get_checks",
            repository=repository,
            pr_number=pr_number,
            head_sha=head_sha,
        )
        return {
            "state": self.check_state,
            "head_sha": self.remote_head_sha,
            "checks": [
                {"name": name, "state": self.check_state}
                for name in self.check_names
            ],
            "successful_names": (
                list(self.check_names) if self.check_state == "success" else []
            ),
        }

    def request_auto_merge(
        self,
        *,
        repository,
        pr_number,
        method,
        expected_base_sha,
        expected_head_sha,
        expected_tree_sha,
    ):
        self._record(
            "request_auto_merge",
            repository=repository,
            pr_number=pr_number,
            method=method,
            expected_base_sha=expected_base_sha,
            expected_head_sha=expected_head_sha,
            expected_tree_sha=expected_tree_sha,
        )
        self.pull_requests[pr_number]["auto_merge_enabled"] = True
        if self.merge_immediately:
            self.pull_requests[pr_number].update(
                {
                    "state": "closed",
                    "merged": True,
                    "merge_sha": MERGE_SHA,
                    "auto_merge_enabled": False,
                }
            )
        return {"accepted": True}


class GitHubDeliveryContractTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            github_delivery,
            "Red: tools.github_delivery가 아직 구현되지 않음: "
            f"{GITHUB_DELIVERY_IMPORT_ERROR}",
        )

    def test_exact_repository_mismatch_is_blocked_before_token_loader(self):
        order = []
        original_validate_target = github_delivery.validate_target

        def validate_spy(*args, **kwargs):
            order.append("validate_target")
            return original_validate_target(*args, **kwargs)

        def token_loader():
            order.append("token_loader")
            return "가짜-토큰"

        transport = _FakeTransport()
        request = _request(repository="winehouse8/not-auto-wiki")

        with mock.patch.object(
            github_delivery,
            "validate_target",
            side_effect=validate_spy,
        ):
            with self.assertRaises(github_delivery.DeliveryBlocked):
                github_delivery.deliver(
                    request,
                    transport=transport,
                    token_loader=token_loader,
                )

        self.assertEqual(order, ["validate_target"])
        self.assertEqual(transport.calls, [])

    def test_target_allowlist_requires_exact_repository_base_and_approval(self):
        github_delivery.validate_target(
            repository=EXPECTED_REPOSITORY,
            base_branch=EXPECTED_BASE,
            approval_id=EXPECTED_APPROVAL,
        )
        invalid = (
            {"repository": "winehouse8/auto_wiki-fork"},
            {"base_branch": "develop"},
            {"approval_id": "COL-UNKNOWN"},
        )
        for override in invalid:
            values = {
                "repository": EXPECTED_REPOSITORY,
                "base_branch": EXPECTED_BASE,
                "approval_id": EXPECTED_APPROVAL,
            }
            values.update(override)
            with self.subTest(override=override):
                with self.assertRaises(github_delivery.DeliveryBlocked):
                    github_delivery.validate_target(**values)

    def test_policy_and_governance_refs_are_pinned_before_token_or_transport(self):
        fixtures = (
            {"policy_version": "SPEC-GH-DELIVERY-001/v0.9.0"},
            {"rfc_ids": []},
            {"approval_refs": []},
        )
        for override in fixtures:
            with self.subTest(override=override):
                request = _request()
                request.update(override)
                token_calls = []
                transport = _FakeTransport()

                with self.assertRaises(github_delivery.DeliveryBlocked):
                    github_delivery.deliver(
                        request,
                        transport=transport,
                        token_loader=lambda: token_calls.append("token")
                        or "가짜-토큰",
                    )

                self.assertEqual(token_calls, [])
                self.assertEqual(transport.calls, [])

    def test_token_loader_accepts_only_safe_regular_ignored_untracked_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            token_path = root / "auth" / "github_token.yaml"
            token_path.parent.mkdir()
            token_path.write_text("key: fake-token-value\n", encoding="utf-8")
            token_path.chmod(0o600)
            probe = _FakeGitProbe(ignored=True, tracked=False)

            token = github_delivery.load_token(
                token_path,
                repo_root=root,
                git_probe=probe,
            )

            self.assertEqual(token, "fake-token-value")
            self.assertEqual(token_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(
                [name for name, _ in probe.calls],
                ["is_ignored", "is_tracked"],
            )

    def test_token_loader_rejects_symlink_and_group_or_world_readable_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            auth = root / "auth"
            auth.mkdir()
            target = auth / "target.yaml"
            target.write_text("key: fake-token-value\n", encoding="utf-8")
            target.chmod(0o600)
            link = auth / "github_token.yaml"
            link.symlink_to(target.name)

            with self.assertRaises(github_delivery.TokenSafetyError):
                github_delivery.load_token(
                    link,
                    repo_root=root,
                    git_probe=_FakeGitProbe(),
                )

            link.unlink()
            link.write_text("key: fake-token-value\n", encoding="utf-8")
            for mode in (0o640, 0o644):
                link.chmod(mode)
                with self.subTest(mode=oct(mode)):
                    with self.assertRaises(github_delivery.TokenSafetyError):
                        github_delivery.load_token(
                            link,
                            repo_root=root,
                            git_probe=_FakeGitProbe(),
                        )

    def test_token_loader_rejects_non_regular_malformed_tracked_or_unignored_input(self):
        malformed = (
            "token: fake-token-value\n",
            "key: fake-token-value\nextra: unexpected\n",
            "key:\n",
            "key: [fake-token-value]\n",
            "key: fake-token-value\nkey: duplicate\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            auth = root / "auth"
            auth.mkdir()
            token_path = auth / "github_token.yaml"

            with self.assertRaises(github_delivery.TokenSafetyError):
                github_delivery.load_token(
                    auth,
                    repo_root=root,
                    git_probe=_FakeGitProbe(),
                )

            for body in malformed:
                token_path.write_text(body, encoding="utf-8")
                token_path.chmod(0o600)
                with self.subTest(body=body):
                    with self.assertRaises(github_delivery.TokenSafetyError):
                        github_delivery.load_token(
                            token_path,
                            repo_root=root,
                            git_probe=_FakeGitProbe(),
                        )

            token_path.write_text("key: fake-token-value\n", encoding="utf-8")
            token_path.chmod(0o600)
            unsafe_probes = (
                _FakeGitProbe(ignored=False, tracked=False),
                _FakeGitProbe(ignored=True, tracked=True),
            )
            for probe in unsafe_probes:
                with self.subTest(ignored=probe.ignored, tracked=probe.tracked):
                    with self.assertRaises(github_delivery.TokenSafetyError):
                        github_delivery.load_token(
                            token_path,
                            repo_root=root,
                            git_probe=probe,
                        )

    def test_redaction_removes_every_literal_secret_occurrence(self):
        secret = "fake-token-value-ABC123"
        text = (
            f"GH_TOKEN={secret}\n"
            f"Authorization: token {secret}\n"
            f'{{"stderr":"request failed for {secret}"}}'
        )

        redacted = github_delivery.redact(text, secrets=[secret])

        self.assertNotIn(secret, redacted)
        self.assertGreaterEqual(redacted.count("[REDACTED]"), 3)

    def test_exact_legacy_token_in_public_context_blocks_before_transport(self):
        token = "legacy-classic-token-1234567890"
        request = _request(
            changes=[{"path": "tools/wiki.py", "status": "modified"}]
        )
        request["rollback"] = f"문제 발생 시 {token}을 사용한다."
        transport = _FakeTransport()

        with self.assertRaises(github_delivery.DeliveryBlocked):
            github_delivery.deliver(
                request,
                transport=transport,
                token_loader=lambda: token,
            )

        self.assertEqual(transport.calls, [])

    def test_risk_classifier_has_safe_review_block_and_no_op_routes(self):
        fixtures = (
            ([], "no-op"),
            ([_safe_change()], "safe"),
            ([{"path": "tools/wiki.py", "status": "modified"}], "review"),
            ([{"path": "auth/github_token.yaml", "status": "added"}], "block"),
        )
        for changes, expected_route in fixtures:
            with self.subTest(expected_route=expected_route):
                decision = github_delivery.classify_changes(changes)
                self.assertEqual(decision["route"], expected_route)
                self.assertTrue(decision["reasons"])

    def test_protected_and_unknown_paths_fail_closed_instead_of_becoming_safe(self):
        protected_paths = (
            ".github/workflows/wiki-quality.yml",
            "AGENTS.md",
            "governance/constitution.md",
            "config/wiki.json",
            "tools/wiki.py",
            "scripts/run.sh",
            "prompts/research.md",
            "skills/living-wiki-steward/SKILL.md",
            "tests/test_wiki.py",
            "wiki/specs/harness-ux.md",
        )
        for path in protected_paths:
            with self.subTest(path=path):
                decision = github_delivery.classify_changes(
                    [{"path": path, "status": "modified"}]
                )
                self.assertEqual(decision["route"], "review")

        unknown = github_delivery.classify_changes(
            [{"path": "unclassified/output.bin", "status": "added"}]
        )
        self.assertIn(unknown["route"], {"review", "block"})
        self.assertNotEqual(unknown["route"], "safe")

        for hostile_path in (
            "wiki/index.md\n- 위조된 PR 문구",
            "wiki/`마크다운-종료`.md",
            "wiki/tab\tname.md",
        ):
            with self.subTest(hostile_path=hostile_path):
                decision = github_delivery.classify_changes(
                    [{"path": hostile_path, "status": "modified"}]
                )
                self.assertEqual(decision["route"], "block")

    def test_raw_overwrite_event_rewrite_and_auth_change_are_immediately_blocked(self):
        forbidden = (
            {"path": "raw/source/original.pdf", "status": "modified"},
            {
                "path": "raw/quarantine/"
                + "a" * 64
                + "/artifact.txt",
                "status": "added",
            },
            {
                "path": "state/events.jsonl",
                "status": "modified",
                "append_only_verified": False,
            },
            {"path": "auth/github_token.yaml", "status": "added"},
        )
        for change in forbidden:
            with self.subTest(change=change):
                decision = github_delivery.classify_changes([change])
                self.assertEqual(decision["route"], "block")

    def test_korean_pr_body_contains_all_audit_and_review_fields(self):
        context = _request(changes=[{"path": "tools/wiki.py", "status": "modified"}])
        context.update(
            {
                "risk": {
                    "route": "review",
                    "reasons": ["도구 변경은 사람 검토가 필요함"],
                },
                "head_sha": HEAD_SHA,
                "tree_sha": TREE_SHA,
                "unresolved": ["최종 diff를 사람이 확인해야 함"],
            }
        )

        body = github_delivery.build_pr_body(context)

        required_phrases = (
            "실행 ID",
            "행위자",
            "호출 방식",
            "작업 종류",
            "Wiki 의존도",
            "기준 SHA",
            "헤드 SHA",
            "트리 SHA",
            "변경 파일",
            "RFC",
            "승인 근거",
            "검증",
            "게이트 지문",
            "위험 판정",
            "C/S-level 및 생명주기 영향",
            "미해결",
            "롤백",
        )
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)
        self.assertIn(context["run_id"], body)
        self.assertIn("tools/wiki.py", body)
        self.assertNotRegex(body, r"(?i)(ghp_|github_pat_)[A-Za-z0-9_]{8,}")

    def test_idempotency_key_is_stable_and_covers_all_contract_components(self):
        components = {
            "policy_version": POLICY_VERSION,
            "run_id": "RUN-20260712T140000Z-ABC123",
            "base_sha": BASE_SHA,
            "tree_sha": TREE_SHA,
        }
        first = github_delivery.idempotency_key(**components)
        second = github_delivery.idempotency_key(**components)
        self.assertEqual(first, second)
        self.assertRegex(first, re.compile(r"\A[0-9a-f]{64}\Z"))

        for field in components:
            changed = dict(components)
            changed[field] = changed[field] + "-different"
            with self.subTest(field=field):
                self.assertNotEqual(
                    first,
                    github_delivery.idempotency_key(**changed),
                )

    def test_no_op_avoids_token_branch_commit_pr_and_merge(self):
        token_calls = []

        def token_loader():
            token_calls.append("called")
            return "가짜-토큰"

        transport = _FakeTransport()
        receipt = github_delivery.deliver(
            _request(changes=[]),
            transport=transport,
            token_loader=token_loader,
        )

        self.assertEqual(receipt["status"], "no-op")
        self.assertEqual(token_calls, [])
        self.assertEqual(transport.calls, [])

    def test_failed_or_missing_checks_never_call_merge_transport(self):
        for check_state in ("failure", "missing"):
            transport = _FakeTransport(check_state=check_state)
            with self.subTest(check_state=check_state):
                receipt = github_delivery.deliver(
                    _request(),
                    transport=transport,
                    token_loader=lambda: "가짜-토큰",
                )
                self.assertEqual(receipt["status"], "blocked")
                self.assertEqual(transport.count("request_auto_merge"), 0)

    def test_wrong_or_missing_required_check_name_never_requests_auto_merge(self):
        fixtures = ([], [REQUIRED_CHECK + "-가짜"], ["다른 성공 check"])
        for check_names in fixtures:
            transport = _FakeTransport(check_names=check_names)
            with self.subTest(check_names=check_names):
                receipt = github_delivery.deliver(
                    _request(),
                    transport=transport,
                    token_loader=lambda: "가짜-토큰",
                )

                self.assertEqual(receipt["status"], "blocked")
                self.assertEqual(transport.count("get_checks"), 1)
                self.assertEqual(transport.count("request_auto_merge"), 0)

    def test_base_or_head_drift_never_calls_merge_transport(self):
        transports = (
            _FakeTransport(remote_base_sha="a" * 40),
            _FakeTransport(remote_head_sha="b" * 40),
        )
        for transport in transports:
            with self.subTest(
                remote_base_sha=transport.remote_base_sha,
                remote_head_sha=transport.remote_head_sha,
            ):
                receipt = github_delivery.deliver(
                    _request(),
                    transport=transport,
                    token_loader=lambda: "가짜-토큰",
                )
                self.assertEqual(receipt["status"], "blocked")
                self.assertEqual(transport.count("request_auto_merge"), 0)

    def test_human_review_route_creates_draft_message_but_never_calls_merge(self):
        transport = _FakeTransport()
        receipt = github_delivery.deliver(
            _request(changes=[{"path": "tools/wiki.py", "status": "modified"}]),
            transport=transport,
            token_loader=lambda: "가짜-토큰",
        )

        self.assertEqual(receipt["status"], "review")
        self.assertTrue(receipt["draft"])
        self.assertEqual(transport.count("create_pull_request"), 1)
        self.assertEqual(transport.count("request_auto_merge"), 0)
        pull_request_call = next(
            details
            for name, details in transport.calls
            if name == "create_pull_request"
        )
        self.assertTrue(pull_request_call["draft"])
        self.assertIn("사람 검토", pull_request_call["body"])
        self.assertIn("@winehouse8", pull_request_call["body"])
        label_call = next(
            details for name, details in transport.calls if name == "add_labels"
        )
        self.assertEqual(
            set(label_call["labels"]),
            {"자동화", "사람-검토-필요"},
        )

    def test_same_idempotency_key_does_not_duplicate_branch_pr_or_merge(self):
        transport = _FakeTransport()
        request = _request()

        first = github_delivery.deliver(
            request,
            transport=transport,
            token_loader=lambda: "가짜-토큰",
        )
        second = github_delivery.deliver(
            request,
            transport=transport,
            token_loader=lambda: "가짜-토큰",
        )

        self.assertEqual(first["idempotency_key"], second["idempotency_key"])
        self.assertEqual(first["pr_number"], second["pr_number"])
        self.assertEqual(transport.count("create_branch"), 1)
        self.assertEqual(transport.count("create_pull_request"), 1)
        self.assertEqual(transport.count("request_auto_merge"), 1)

        pr_number = first["pr_number"]
        transport.pull_requests[pr_number].update(
            {
                "state": "closed",
                "merged": True,
                "merge_sha": MERGE_SHA,
                "auto_merge_enabled": False,
            }
        )
        completed = github_delivery.deliver(
            request,
            transport=transport,
            token_loader=lambda: "가짜-토큰",
        )

        self.assertEqual(completed["status"], "merged")
        self.assertEqual(completed["merge_sha"], MERGE_SHA)
        self.assertEqual(transport.count("request_auto_merge"), 1)

    def test_merge_is_complete_only_after_pr_requery_returns_merge_receipt(self):
        transport = _FakeTransport()

        receipt = github_delivery.deliver(
            _request(),
            transport=transport,
            token_loader=lambda: "가짜-토큰",
        )

        self.assertEqual(receipt["status"], "merged")
        self.assertEqual(receipt["merge_sha"], MERGE_SHA)
        self.assertEqual(receipt["merge_method"], "squash")
        merge_position = next(
            index
            for index, (name, _) in enumerate(transport.calls)
            if name == "request_auto_merge"
        )
        requery_positions = [
            index
            for index, (name, _) in enumerate(transport.calls)
            if name == "get_pull_request"
        ]
        self.assertTrue(requery_positions)
        self.assertGreater(requery_positions[-1], merge_position)

    def test_open_auto_merge_is_pending_and_retry_reconciles_without_duplicate(self):
        transport = _FakeTransport(merge_immediately=False)
        request = _request()

        first = github_delivery.deliver(
            request,
            transport=transport,
            token_loader=lambda: "가짜-토큰",
        )
        second = github_delivery.deliver(
            request,
            transport=transport,
            token_loader=lambda: "가짜-토큰",
        )

        for receipt in (first, second):
            self.assertEqual(receipt["status"], "auto-merge-pending")
            self.assertEqual(receipt["route"], "safe")
            self.assertTrue(receipt["merge_requested"])
            self.assertIsNone(receipt["merge_sha"])
        self.assertEqual(transport.count("create_branch"), 1)
        self.assertEqual(transport.count("create_pull_request"), 1)
        self.assertEqual(transport.count("request_auto_merge"), 1)

    def test_post_request_requery_failure_never_claims_merge_was_not_requested(self):
        class RequeryFailureTransport(_FakeTransport):
            def __init__(self):
                super().__init__(merge_immediately=False)
                self.fail_after_request = False

            def request_auto_merge(self, **kwargs):
                result = super().request_auto_merge(**kwargs)
                self.fail_after_request = True
                return result

            def get_pull_request(self, *, repository, pr_number):
                if self.fail_after_request:
                    raise RuntimeError("비밀 없는 최종 조회 실패")
                return super().get_pull_request(
                    repository=repository,
                    pr_number=pr_number,
                )

        transport = RequeryFailureTransport()
        receipt = github_delivery.deliver(
            _request(),
            transport=transport,
            token_loader=lambda: "가짜-토큰",
        )

        self.assertEqual(receipt["status"], "blocked")
        self.assertTrue(receipt["merge_requested"])
        self.assertTrue(receipt["merge_state_uncertain"])


if __name__ == "__main__":
    unittest.main()
