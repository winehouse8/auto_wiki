"""SPEC-GH-DELIVERY-001의 단일 단계 정책 전환 Red 계약."""

from __future__ import annotations

import copy
import hashlib
import json
import unittest

from tools import github_delivery


FROM_POLICY = "SPEC-GH-DELIVERY-001/v1.1.0"
TO_POLICY = "SPEC-GH-DELIVERY-001/v1.2.0"
TRANSITION_RFC = "RFC-7A0959853525"
TRANSITION_APPROVAL = "COL-B80046FC1C56"
BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
TREE_SHA = "3" * 40
RUN_ID = "RUN-20260715T032023Z-818E55"


def _api(name):
    value = getattr(github_delivery, name, None)
    if value is None:
        raise AssertionError(f"Red: tools.github_delivery.{name} API가 아직 없음")
    return value


def _transition(*, state="armed", from_policy=FROM_POLICY, to_policy=TO_POLICY):
    return {
        "schema_version": "github-delivery-policy-transition/v1",
        "from_policy_version": from_policy,
        "to_policy_version": to_policy,
        "state": state,
        "mode": "human-review-only",
        "approval_refs": ["COL-27B9ADD786ED", TRANSITION_APPROVAL],
        "rfc_ids": ["RFC-03F4FE85BB44", TRANSITION_RFC],
    }


def _config(*, active=FROM_POLICY, transition=None, extra=None):
    value = {
        "policy_version": active,
        "repository": "winehouse8/auto_wiki",
        "base_branch": "main",
        "branch_prefix": "wiki-auto/",
        "merge_method": "squash",
        "approval_refs": [
            "COL-27B9ADD786ED",
            "RFC-03F4FE85BB44",
            TRANSITION_APPROVAL,
            TRANSITION_RFC,
        ],
        "policy_transition": transition or _transition(),
    }
    if extra:
        value.update(extra)
    return value


def _document(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


class PolicyTransitionPureContractTests(unittest.TestCase):
    def test_exact_reviewed_edge_builds_base_bound_transition_proof(self):
        document = _document(_config())

        proof = _api("build_policy_transition_proof")(
            document,
            active_policy_version=FROM_POLICY,
            target_policy_version=TO_POLICY,
            base_sha=BASE_SHA,
        )

        self.assertEqual(
            proof["schema_version"],
            "github-delivery-policy-transition-proof/v1",
        )
        self.assertEqual(proof["from_policy_version"], FROM_POLICY)
        self.assertEqual(proof["to_policy_version"], TO_POLICY)
        self.assertEqual(proof["base_sha"], BASE_SHA)
        self.assertEqual(
            proof["base_policy_config_sha256"],
            hashlib.sha256(document).hexdigest(),
        )
        self.assertEqual(proof["mode"], "human-review-only")
        self.assertIn(TRANSITION_APPROVAL, proof["approval_refs"])
        self.assertIn(TRANSITION_RFC, proof["rfc_ids"])

    def test_build_proof_rejects_duplicate_authority_keys(self):
        valid_document = _document(_config()).decode("utf-8")
        duplicate_documents = (
            (
                "policy_version",
                valid_document.replace(
                    f'  "policy_version": "{FROM_POLICY}",',
                    f'  "policy_version": "{FROM_POLICY}",\n'
                    f'  "policy_version": "{FROM_POLICY}",',
                    1,
                ).encode("utf-8"),
            ),
            (
                "policy_transition",
                valid_document.replace(
                    '  "policy_transition": {',
                    '  "policy_transition": {},\n'
                    '  "policy_transition": {',
                    1,
                ).encode("utf-8"),
            ),
        )

        for duplicate_key, document in duplicate_documents:
            with self.subTest(duplicate_key=duplicate_key):
                with self.assertRaises(github_delivery.DeliveryBlocked):
                    _api("build_policy_transition_proof")(
                        document,
                        active_policy_version=FROM_POLICY,
                        target_policy_version=TO_POLICY,
                        base_sha=BASE_SHA,
                    )

    def test_begin_rejects_same_unsupported_consumed_or_unapproved_edge(self):
        fixtures = []
        same = _config(transition=_transition(to_policy=FROM_POLICY))
        fixtures.append((same, FROM_POLICY, FROM_POLICY))
        unsupported = _config(transition=_transition(to_policy="SPEC-GH-DELIVERY-001/v1.3.0"))
        fixtures.append((unsupported, FROM_POLICY, "SPEC-GH-DELIVERY-001/v1.3.0"))
        consumed = _config(transition=_transition(state="consumed"))
        fixtures.append((consumed, FROM_POLICY, TO_POLICY))
        missing_approval = _config()
        missing_approval["policy_transition"]["approval_refs"] = [
            "COL-27B9ADD786ED"
        ]
        fixtures.append((missing_approval, FROM_POLICY, TO_POLICY))
        missing_rfc = _config()
        missing_rfc["policy_transition"]["rfc_ids"] = ["RFC-03F4FE85BB44"]
        fixtures.append((missing_rfc, FROM_POLICY, TO_POLICY))
        active_mismatch = _config(active=TO_POLICY)
        fixtures.append((active_mismatch, FROM_POLICY, TO_POLICY))

        for config, active, target in fixtures:
            with self.subTest(config=config, active=active, target=target):
                with self.assertRaises(github_delivery.DeliveryBlocked):
                    _api("build_policy_transition_proof")(
                        _document(config),
                        active_policy_version=active,
                        target_policy_version=target,
                        base_sha=BASE_SHA,
                    )

    def test_activation_accepts_only_exact_config_consumption_and_unchanged_verifier(self):
        base_document = _document(_config())
        proof = {
            "schema_version": "github-delivery-policy-transition-proof/v1",
            "from_policy_version": FROM_POLICY,
            "to_policy_version": TO_POLICY,
            "base_sha": BASE_SHA,
            "base_policy_config_sha256": hashlib.sha256(base_document).hexdigest(),
            "mode": "human-review-only",
            "approval_refs": ["COL-27B9ADD786ED", TRANSITION_APPROVAL],
            "rfc_ids": ["RFC-03F4FE85BB44", TRANSITION_RFC],
        }
        head = _config(active=TO_POLICY, transition=_transition(state="consumed"))

        result = _api("validate_policy_transition_activation")(
            proof,
            base_config_document=base_document,
            head_config_document=_document(head),
            changed_paths=["config/github-delivery.json"],
            active_policy_version=TO_POLICY,
        )

        self.assertEqual(result["from_policy_version"], FROM_POLICY)
        self.assertEqual(result["to_policy_version"], TO_POLICY)
        self.assertEqual(result["route"], "review")

    def test_activation_rejects_head_only_edge_even_when_base_digest_matches(self):
        base = _config()
        base.pop("policy_transition")
        base_document = _document(base)
        proof = {
            "schema_version": "github-delivery-policy-transition-proof/v1",
            "from_policy_version": FROM_POLICY,
            "to_policy_version": TO_POLICY,
            "base_sha": BASE_SHA,
            "base_policy_config_sha256": hashlib.sha256(base_document).hexdigest(),
            "mode": "human-review-only",
            "approval_refs": ["COL-27B9ADD786ED", TRANSITION_APPROVAL],
            "rfc_ids": ["RFC-03F4FE85BB44", TRANSITION_RFC],
        }
        head = _config(
            active=TO_POLICY,
            transition=_transition(state="consumed"),
        )

        with self.assertRaises(github_delivery.DeliveryBlocked):
            _api("validate_policy_transition_activation")(
                proof,
                base_config_document=base_document,
                head_config_document=_document(head),
                changed_paths=["config/github-delivery.json"],
                active_policy_version=TO_POLICY,
            )

    def test_activation_rejects_digest_head_only_edge_extra_mutation_and_verifier_change(self):
        base = _config()
        base_document = _document(base)
        proof = {
            "schema_version": "github-delivery-policy-transition-proof/v1",
            "from_policy_version": FROM_POLICY,
            "to_policy_version": TO_POLICY,
            "base_sha": BASE_SHA,
            "base_policy_config_sha256": hashlib.sha256(base_document).hexdigest(),
            "mode": "human-review-only",
            "approval_refs": ["COL-27B9ADD786ED", TRANSITION_APPROVAL],
            "rfc_ids": ["RFC-03F4FE85BB44", TRANSITION_RFC],
        }
        valid_head = _config(
            active=TO_POLICY,
            transition=_transition(state="consumed"),
        )
        fixtures = []
        tampered_proof = copy.deepcopy(proof)
        tampered_proof["base_policy_config_sha256"] = "0" * 64
        fixtures.append((tampered_proof, base_document, valid_head, ["config/github-delivery.json"], TO_POLICY))
        head_only_base = _config()
        head_only_base.pop("policy_transition")
        fixtures.append((proof, _document(head_only_base), valid_head, ["config/github-delivery.json"], TO_POLICY))
        extra_head = copy.deepcopy(valid_head)
        extra_head["repository"] = "winehouse8/other"
        fixtures.append((proof, base_document, extra_head, ["config/github-delivery.json"], TO_POLICY))
        fixtures.append((proof, base_document, valid_head, ["config/github-delivery.json", "tools/github_delivery.py"], TO_POLICY))
        fixtures.append((proof, base_document, valid_head, ["config/github-delivery.json"], FROM_POLICY))

        for candidate_proof, candidate_base, candidate_head, paths, active in fixtures:
            with self.subTest(paths=paths, active=active, head=candidate_head):
                with self.assertRaises(github_delivery.DeliveryBlocked):
                    _api("validate_policy_transition_activation")(
                        candidate_proof,
                        base_config_document=candidate_base,
                        head_config_document=_document(candidate_head),
                        changed_paths=paths,
                        active_policy_version=active,
                    )

    def test_activation_rejects_json_type_change_even_when_python_values_compare_equal(self):
        base = _config(extra={"repository_settings": {"allow_auto_merge": True}})
        base_document = _document(base)
        proof = _api("build_policy_transition_proof")(
            base_document,
            active_policy_version=FROM_POLICY,
            target_policy_version=TO_POLICY,
            base_sha=BASE_SHA,
        )
        head = _config(
            active=TO_POLICY,
            transition=_transition(state="consumed"),
            extra={"repository_settings": {"allow_auto_merge": 1}},
        )

        with self.assertRaises(github_delivery.DeliveryBlocked):
            _api("validate_policy_transition_activation")(
                proof,
                base_config_document=base_document,
                head_config_document=_document(head),
                changed_paths=["config/github-delivery.json"],
                active_policy_version=TO_POLICY,
            )

    def test_transition_key_binds_from_to_and_base_config_digest_without_changing_legacy_key(self):
        legacy = _api("idempotency_key")(
            policy_version=FROM_POLICY,
            run_id=RUN_ID,
            base_sha=BASE_SHA,
            tree_sha=TREE_SHA,
        )
        expected_legacy = hashlib.sha256(
            json.dumps(
                [FROM_POLICY, RUN_ID, BASE_SHA, TREE_SHA],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(legacy, expected_legacy)

        digest = "a" * 64
        first = _api("idempotency_key")(
            policy_version=FROM_POLICY,
            target_policy_version=TO_POLICY,
            base_policy_config_sha256=digest,
            run_id=RUN_ID,
            base_sha=BASE_SHA,
            tree_sha=TREE_SHA,
        )
        second = _api("idempotency_key")(
            policy_version=FROM_POLICY,
            target_policy_version=TO_POLICY,
            base_policy_config_sha256=digest,
            run_id=RUN_ID,
            base_sha=BASE_SHA,
            tree_sha=TREE_SHA,
        )
        changed_target = _api("idempotency_key")(
            policy_version=FROM_POLICY,
            target_policy_version="SPEC-GH-DELIVERY-001/v1.3.0",
            base_policy_config_sha256=digest,
            run_id=RUN_ID,
            base_sha=BASE_SHA,
            tree_sha=TREE_SHA,
        )
        changed_digest = _api("idempotency_key")(
            policy_version=FROM_POLICY,
            target_policy_version=TO_POLICY,
            base_policy_config_sha256="b" * 64,
            run_id=RUN_ID,
            base_sha=BASE_SHA,
            tree_sha=TREE_SHA,
        )
        self.assertEqual(first, second)
        self.assertNotEqual(first, legacy)
        self.assertNotEqual(first, changed_target)
        self.assertNotEqual(first, changed_digest)

    def test_v12_runtime_policy_requires_the_consumed_reviewed_edge(self):
        consumed = _document(
            _config(active=TO_POLICY, transition=_transition(state="consumed"))
        )
        self.assertEqual(
            _api("_policy_version_from_document")(consumed),
            TO_POLICY,
        )

        armed = _document(_config(active=TO_POLICY, transition=_transition()))
        missing = _config(active=TO_POLICY)
        missing.pop("policy_transition")
        for document in (armed, _document(missing)):
            with self.subTest(document=document):
                with self.assertRaises(github_delivery.DeliveryBlocked):
                    _api("_policy_version_from_document")(document)


class PolicyTransitionIntegrationBoundaryTests(unittest.TestCase):
    def test_begin_cli_accepts_explicit_target_policy_version(self):
        args = _api("_parser")().parse_args(
            ["begin", "--target-policy-version", TO_POLICY]
        )
        self.assertEqual(args.target_policy_version, TO_POLICY)

    def test_core_deliver_rejects_unverified_transition_before_token_or_transport(self):
        class TrapTransport:
            def __init__(self):
                self.calls = []

            def set_token(self, token):
                self.calls.append("set_token")

            def clear_token(self):
                self.calls.append("clear_token")

            def find_delivery(self, **kwargs):
                self.calls.append("find_delivery")
                raise AssertionError("전환 증명 전에 transport를 호출하면 안 됨")

        token_calls = []
        transport = TrapTransport()
        request = {
            "repository": "winehouse8/auto_wiki",
            "base_branch": "main",
            "approval_id": "COL-27B9ADD786ED",
            "policy_version": FROM_POLICY,
            "target_policy_version": TO_POLICY,
            "policy_transition": {
                "schema_version": "github-delivery-policy-transition-proof/v1",
                "from_policy_version": FROM_POLICY,
                "to_policy_version": TO_POLICY,
                "base_sha": BASE_SHA,
                "base_policy_config_sha256": "a" * 64,
                "mode": "human-review-only",
                "approval_refs": ["COL-27B9ADD786ED", TRANSITION_APPROVAL],
                "rfc_ids": ["RFC-03F4FE85BB44", TRANSITION_RFC],
            },
            "run_id": RUN_ID,
            "actor": "agent:codex",
            "base_sha": BASE_SHA,
            "head_sha": HEAD_SHA,
            "tree_sha": TREE_SHA,
            "changes": [{"path": "config/github-delivery.json", "status": "modified"}],
            "rfc_ids": ["RFC-03F4FE85BB44", TRANSITION_RFC],
            "approval_refs": ["COL-27B9ADD786ED", TRANSITION_APPROVAL],
            "local_gates": {"전체 릴리스 게이트": "success"},
        }

        with self.assertRaises(github_delivery.GitHubDeliveryError):
            github_delivery.deliver(
                request,
                transport=transport,
                token_loader=lambda: token_calls.append("token") or "fake-token",
            )

        self.assertEqual(token_calls, [])
        self.assertEqual(transport.calls, ["clear_token"])


if __name__ == "__main__":
    unittest.main()
