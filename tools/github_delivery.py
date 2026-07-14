"""Living Wiki 변경의 GitHub PR 전달을 위한 보수적 코어.

이 모듈은 GitHub API 구현과 정책 판단을 분리한다. ``deliver``에 전달되는
transport는 아래 메서드를 제공해야 하며, 자격증명은 transport의 영속 상태나
호출 인자에 기록하지 않는다. 실제 adapter는 토큰을 프로세스 환경에만 넣어야
한다.

정책 계약: SPEC-GH-DELIVERY-001의 v1.1→v1.2 단일 단계 전환 브리지
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import os
import re
import secrets as secrets_module
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


EXPECTED_REPOSITORY = "winehouse8/auto_wiki"
EXPECTED_REMOTE_URL = "https://github.com/winehouse8/auto_wiki.git"
EXPECTED_BASE_BRANCH = "main"
EXPECTED_BASE_REFSPEC = "refs/heads/main:refs/remotes/origin/main"
EXPECTED_APPROVAL_ID = "COL-27B9ADD786ED"
REQUIRED_DELIVERY_RFC = "RFC-03F4FE85BB44"
BRANCH_PREFIX = "wiki-auto/"
MERGE_METHOD = "squash"
POLICY_VERSION = "SPEC-GH-DELIVERY-001/v1.1.0"
TARGET_POLICY_VERSION = "SPEC-GH-DELIVERY-001/v1.2.0"
POLICY_CONFIG_PATH = "config/github-delivery.json"
POLICY_TRANSITION_SCHEMA = "github-delivery-policy-transition/v1"
POLICY_TRANSITION_PROOF_SCHEMA = "github-delivery-policy-transition-proof/v1"
POLICY_TRANSITION_MODE = "human-review-only"
POLICY_TRANSITION_APPROVAL = "COL-B80046FC1C56"
POLICY_TRANSITION_RFC = "RFC-7A0959853525"
REQUIRED_CHECK_NAMES = ("전체 저장소 품질 게이트",)
MAX_TRACKED_FILE_BYTES = 5 * 1024 * 1024


class GitHubDeliveryError(RuntimeError):
    """GitHub 전달 계약의 기본 오류."""


class DeliveryBlocked(GitHubDeliveryError):
    """안전 계약 때문에 외부 전달을 시작할 수 없음."""


class TokenSafetyError(DeliveryBlocked):
    """자격증명 파일이 비밀 경계 계약을 충족하지 않음."""


class TransportError(GitHubDeliveryError):
    """비밀을 포함하지 않는 transport 실패."""


class GitProbe:
    """토큰 파일의 Git ignore/추적 상태를 읽기 전용으로 확인한다."""

    def __init__(self, repo_root: Path | str):
        self.repo_root = Path(repo_root).resolve()

    def _relative(self, path: Path | str) -> str:
        try:
            return Path(path).resolve().relative_to(self.repo_root).as_posix()
        except ValueError as exc:
            raise TokenSafetyError("토큰 경로가 저장소 밖에 있음") from exc

    def is_ignored(self, path: Path | str) -> bool:
        relative = self._relative(path)
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--", relative],
            cwd=self.repo_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0

    def is_tracked(self, path: Path | str) -> bool:
        relative = self._relative(path)
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative],
            cwd=self.repo_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0


class SubprocessRunner:
    """실제 CLI에서 사용하는 최소 subprocess adapter."""

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | str | None = None,
        env: Mapping[str, str] | None = None,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        child_env = os.environ.copy()
        if env:
            child_env.update(env)
        return subprocess.run(
            list(argv),
            cwd=cwd,
            env=child_env,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_bytes(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        """Git blob처럼 줄바꿈 정규화가 금지된 결과를 bytes로 읽는다."""

        child_env = os.environ.copy()
        if env:
            child_env.update(env)
        return subprocess.run(
            list(argv),
            cwd=cwd,
            env=child_env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
        )


def _git_auth_env(token: str) -> dict[str, str]:
    """GitHub token과 비영속 gh credential helper를 child 환경에만 둔다."""

    return {
        "GH_TOKEN": token,
        # 빈 helper가 상속된 global/system helper 목록을 먼저 초기화한다.
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "credential.https://github.com.helper",
        "GIT_CONFIG_VALUE_0": "",
        "GIT_CONFIG_KEY_1": "credential.https://github.com.helper",
        "GIT_CONFIG_VALUE_1": "!gh auth git-credential",
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "Never",
        "GH_PROMPT_DISABLED": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }


def _credential_free_git_env() -> dict[str, str]:
    """공개 기준선 조회가 상속 credential이나 prompt를 사용하지 않게 한다."""

    return {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "credential.helper",
        "GIT_CONFIG_VALUE_0": "",
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "Never",
    }


def _command(
    runner: Any,
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    input_text: str | None = None,
    allowed: Sequence[int] = (0,),
    purpose: str,
) -> Any:
    """명령 실패 세부를 노출하지 않고 결과만 반환한다."""

    command_env = dict(env or {})
    if argv and str(argv[0]) == "git":
        # refs/replace는 SHA 문자열을 바꾸지 않은 채 commit/tree 해석만 바꾼다.
        # 모든 Git 판단에서 이를 무시해 base Git 객체 권위를 보존한다.
        command_env["GIT_NO_REPLACE_OBJECTS"] = "1"
    try:
        result = runner.run(
            tuple(argv),
            cwd=cwd,
            env=command_env or None,
            input_text=input_text,
        )
    except Exception:
        raise DeliveryBlocked(f"{purpose} 명령을 안전하게 실행하지 못함") from None
    if getattr(result, "returncode", None) not in set(allowed):
        raise DeliveryBlocked(f"{purpose} 검증에 실패함")
    return result


def _output(result: Any) -> str:
    value = getattr(result, "stdout", "")
    return value if isinstance(value, str) else ""


def _command_bytes(
    runner: Any,
    argv: Sequence[str],
    *,
    cwd: Path,
    allowed: Sequence[int] = (0,),
    purpose: str,
) -> Any:
    """text mode의 CRLF 변환 없이 Git 객체 bytes를 읽는다."""

    run_bytes = getattr(runner, "run_bytes", None)
    if not callable(run_bytes):
        raise DeliveryBlocked(f"{purpose} 명령이 bytes 보존 runner를 제공하지 않음")
    command_env: dict[str, str] = {}
    if argv and str(argv[0]) == "git":
        command_env["GIT_NO_REPLACE_OBJECTS"] = "1"
    try:
        result = run_bytes(
            tuple(argv),
            cwd=cwd,
            env=command_env or None,
        )
    except Exception:
        raise DeliveryBlocked(f"{purpose} 명령을 안전하게 실행하지 못함") from None
    if getattr(result, "returncode", None) not in set(allowed):
        raise DeliveryBlocked(f"{purpose} 검증에 실패함")
    return result


def _output_bytes(result: Any) -> bytes:
    value = getattr(result, "stdout", b"")
    return value if isinstance(value, bytes) else b""


class GitHubCliTransport:
    """``gh``와 local ``git push``를 사용하는 delivery transport.

    토큰은 argv, body, URL, remote나 receipt에 넣지 않고 각 child process의
    ``GH_TOKEN`` 환경에만 전달한다.
    """

    def __init__(
        self,
        *,
        runner: Any,
        repo_root: Path | str,
        token: str | None = None,
    ):
        self.runner = runner
        self.repo_root = Path(repo_root).resolve()
        self._token = token if isinstance(token, str) and token else None

    def set_token(self, token: str) -> None:
        if not isinstance(token, str) or not token:
            raise TokenSafetyError("GitHub 자격증명이 비어 있거나 잘못됨")
        self._token = token

    def clear_token(self) -> None:
        self._token = None

    def _env(self) -> dict[str, str]:
        if not self._token:
            raise TokenSafetyError("GitHub transport에 자격증명이 주입되지 않음")
        return _git_auth_env(self._token)

    def _run(
        self,
        argv: Sequence[str],
        *,
        input_text: str | None = None,
        purpose: str,
        retry_safe: bool = False,
    ) -> Any:
        attempts = 3 if retry_safe else 1
        for attempt in range(attempts):
            try:
                result = self.runner.run(
                    tuple(argv),
                    cwd=self.repo_root,
                    env=self._env(),
                    input_text=input_text,
                )
            except Exception:
                raise DeliveryBlocked(f"{purpose} 명령을 안전하게 실행하지 못함") from None
            if getattr(result, "returncode", None) == 0:
                return result
            stderr = str(getattr(result, "stderr", ""))
            lowered = stderr.casefold()
            if re.search(r"(?:http\s*)?(?:401|403)\b", lowered) or any(
                marker in lowered
                for marker in ("bad credentials", "authentication failed", "forbidden")
            ):
                raise DeliveryBlocked(f"{purpose} 인증·권한 검증에 실패함")
            retryable = bool(
                re.search(r"(?:http\s*)?(?:429|5\d\d)\b", lowered)
                or "rate limit" in lowered
                or "temporarily unavailable" in lowered
            )
            if not retry_safe or not retryable or attempt + 1 >= attempts:
                raise DeliveryBlocked(f"{purpose} 검증에 실패함")
            time.sleep(2**attempt)
        raise DeliveryBlocked(f"{purpose} 제한 재시도 후 실패함")

    def find_delivery(self, *, repository: str, idempotency_key: str):
        result = self._run(
            (
                "gh",
                "pr",
                "list",
                "--repo",
                repository,
                "--state",
                "all",
                "--search",
                f'\"Wiki-Delivery-Key: {idempotency_key}\" in:body',
                "--json",
                "number,url,isDraft,state,mergedAt,mergeCommit,headRefOid,baseRefOid,labels,autoMergeRequest",
                "--limit",
                "2",
            ),
            purpose="기존 PR 조회",
            retry_safe=True,
        )
        try:
            payload = json.loads(_output(result) or "[]")
        except json.JSONDecodeError:
            raise TransportError("기존 PR 조회 결과 형식이 잘못됨") from None
        if not isinstance(payload, list) or len(payload) > 1:
            raise TransportError("멱등성 표식에 대응하는 PR을 단일하게 확인하지 못함")
        return self._normalize_pr(payload[0]) if payload else None

    def get_base_sha(self, *, repository: str, base_branch: str):
        result = self._run(
            (
                "gh",
                "api",
                f"repos/{repository}/git/ref/heads/{base_branch}",
            ),
            purpose="원격 기준 SHA 조회",
            retry_safe=True,
        )
        try:
            payload = json.loads(_output(result))
            sha = payload["object"]["sha"]
        except (json.JSONDecodeError, KeyError, TypeError):
            raise TransportError("원격 기준 SHA 응답 형식이 잘못됨") from None
        if not isinstance(sha, str) or not sha:
            raise TransportError("원격 기준 SHA가 비어 있음")
        return sha

    def create_branch(
        self,
        *,
        repository: str,
        branch: str,
        base_sha: str,
        idempotency_key: str,
    ):
        del repository, idempotency_key
        _validate_origin_identity(self.repo_root, self.runner)
        self._run(
            (
                "git",
                "push",
                EXPECTED_REMOTE_URL,
                f"{branch}:{branch}",
            ),
            purpose="자동 작업 브랜치 push",
        )
        return {"name": branch, "base_sha": base_sha}

    def create_pull_request(
        self,
        *,
        repository: str,
        base_branch: str,
        branch: str,
        title: str,
        body: str,
        draft: bool,
        idempotency_key: str,
        head_sha: str,
        tree_sha: str,
    ):
        marked_body = (
            body.rstrip()
            + f"\n\n<!-- Wiki-Delivery-Key: {idempotency_key} -->\n"
        )
        argv = [
            "gh",
            "pr",
            "create",
            "--repo",
            repository,
            "--base",
            base_branch,
            "--head",
            branch,
            "--title",
            title,
            "--body",
            marked_body,
        ]
        if draft:
            argv.extend(("--draft", "--assignee", "winehouse8"))
        result = self._run(argv, purpose="Pull Request 생성")
        url = _output(result).strip().splitlines()[-1] if _output(result).strip() else ""
        match = re.search(r"/pull/(\d+)(?:\D|$)", url)
        if not match:
            raise TransportError("생성된 Pull Request 번호를 확인하지 못함")
        return {
            "number": int(match.group(1)),
            "url": url,
            "draft": draft,
            "state": "open",
            "merged": False,
            "merge_sha": None,
            "base_sha": None,
            "head_sha": head_sha,
            "tree_sha": tree_sha,
            "labels": [],
            "idempotency_key": idempotency_key,
        }

    def add_labels(self, *, repository: str, pr_number: int, labels: Sequence[str]):
        self._run(
            (
                "gh",
                "pr",
                "edit",
                str(pr_number),
                "--repo",
                repository,
                "--add-label",
                ",".join(labels),
            ),
            purpose="Pull Request 라벨 추가",
        )

    def _normalize_pr(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        merge_commit = payload.get("mergeCommit")
        merge_sha = (
            merge_commit.get("oid")
            if isinstance(merge_commit, Mapping)
            else None
        )
        labels = payload.get("labels") or []
        normalized_labels = [
            item.get("name") if isinstance(item, Mapping) else item for item in labels
        ]
        return {
            "number": payload.get("number"),
            "url": payload.get("url"),
            "draft": bool(payload.get("isDraft", payload.get("draft", False))),
            "state": str(payload.get("state", "open")).lower(),
            "merged": bool(payload.get("mergedAt") or merge_sha),
            "merge_sha": merge_sha,
            "base_sha": payload.get("baseRefOid", payload.get("base_sha")),
            "head_sha": payload.get("headRefOid", payload.get("head_sha")),
            "tree_sha": payload.get("tree_sha"),
            "labels": [label for label in normalized_labels if label],
            "unresolved_reviews": (
                1 if payload.get("reviewDecision") == "CHANGES_REQUESTED" else 0
            ),
            "conflict": payload.get("mergeStateStatus") in {"DIRTY", "CONFLICTING"},
            "auto_merge_enabled": bool(payload.get("autoMergeRequest")),
        }

    def get_pull_request(self, *, repository: str, pr_number: int):
        result = self._run(
            (
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--repo",
                repository,
                "--json",
                "number,url,isDraft,state,mergedAt,mergeCommit,headRefOid,baseRefOid,labels,reviewDecision,mergeStateStatus,autoMergeRequest",
            ),
            purpose="Pull Request 상태 조회",
            retry_safe=True,
        )
        try:
            payload = json.loads(_output(result))
        except json.JSONDecodeError:
            raise TransportError("Pull Request 상태 응답 형식이 잘못됨") from None
        if not isinstance(payload, Mapping):
            raise TransportError("Pull Request 상태 응답 구조가 잘못됨")
        normalized = self._normalize_pr(payload)
        head_sha = normalized.get("head_sha")
        if head_sha:
            tree_result = self._run(
                (
                    "gh",
                    "api",
                    f"repos/{repository}/git/commits/{head_sha}",
                ),
                purpose="Pull Request tree SHA 조회",
                retry_safe=True,
            )
            try:
                tree_payload = json.loads(_output(tree_result))
                normalized["tree_sha"] = tree_payload["tree"]["sha"]
            except (json.JSONDecodeError, KeyError, TypeError):
                # tree SHA를 증명하지 못하면 core가 자동 병합을 차단한다.
                normalized["tree_sha"] = None
        try:
            owner, name = repository.split("/", 1)
        except ValueError:
            raise TransportError("검토 대화 조회용 저장소 이름이 잘못됨") from None
        query = """
query($owner:String!,$name:String!,$number:Int!,$endCursor:String){
  repository(owner:$owner,name:$name){
    pullRequest(number:$number){
      reviewThreads(first:100,after:$endCursor){
        nodes{isResolved}
        pageInfo{hasNextPage endCursor}
      }
    }
  }
}
""".strip()
        thread_result = self._run(
            (
                "gh",
                "api",
                "graphql",
                "--paginate",
                "--slurp",
                "-f",
                f"query={query}",
                "-F",
                f"owner={owner}",
                "-F",
                f"name={name}",
                "-F",
                f"number={pr_number}",
            ),
            purpose="미해결 Pull Request 검토 대화 조회",
            retry_safe=True,
        )
        try:
            pages = json.loads(_output(thread_result) or "[]")
            if isinstance(pages, Mapping):
                pages = [pages]
            if not isinstance(pages, list) or not pages:
                raise TypeError
            unresolved = 0
            last_page_info: Mapping[str, Any] | None = None
            for page in pages:
                threads = page["data"]["repository"]["pullRequest"][
                    "reviewThreads"
                ]
                nodes = threads["nodes"]
                if not isinstance(nodes, list):
                    raise TypeError
                unresolved += sum(
                    1
                    for node in nodes
                    if isinstance(node, Mapping) and node.get("isResolved") is False
                )
                last_page_info = threads["pageInfo"]
            if not isinstance(last_page_info, Mapping) or last_page_info.get(
                "hasNextPage"
            ):
                raise TypeError
        except (json.JSONDecodeError, KeyError, TypeError):
            raise TransportError("검토 대화 조회 응답 형식이 잘못됨") from None
        normalized["unresolved_reviews"] = max(
            int(normalized.get("unresolved_reviews", 0)), unresolved
        )
        return normalized

    def get_checks(self, *, repository: str, pr_number: int, head_sha: str):
        result = self._run(
            (
                "gh",
                "pr",
                "checks",
                str(pr_number),
                "--repo",
                repository,
                "--json",
                "state,bucket,name,workflow",
                "--watch",
                "--fail-fast",
                "--interval",
                "10",
            ),
            purpose="Pull Request 필수 check 조회",
            retry_safe=True,
        )
        try:
            checks = json.loads(_output(result) or "[]")
        except json.JSONDecodeError:
            raise TransportError("Pull Request check 응답 형식이 잘못됨") from None
        normalized: list[dict[str, str]] = []
        if isinstance(checks, list):
            for item in checks:
                if not isinstance(item, Mapping):
                    continue
                normalized.append(
                    {
                        "name": str(item.get("name", "")),
                        "state": str(
                            item.get("state", item.get("bucket", ""))
                        ).lower(),
                        "workflow": str(item.get("workflow", "")),
                    }
                )
        success_states = {"success", "pass", "passed"}
        successful_names = sorted(
            {
                item["name"]
                for item in normalized
                if item["name"] and item["state"] in success_states
            }
        )
        required_present = all(
            required in successful_names for required in REQUIRED_CHECK_NAMES
        )
        all_visible_success = bool(normalized) and all(
            item["state"] in success_states for item in normalized
        )
        return {
            "state": (
                "success"
                if required_present and all_visible_success
                else "missing"
            ),
            "head_sha": head_sha,
            "checks": normalized,
            "successful_names": successful_names,
            "required_names": list(REQUIRED_CHECK_NAMES),
        }

    def request_auto_merge(
        self,
        *,
        repository: str,
        pr_number: int,
        method: str,
        expected_base_sha: str,
        expected_head_sha: str,
        expected_tree_sha: str,
    ):
        del expected_base_sha, expected_tree_sha
        if method != "squash":
            raise TransportError("승인되지 않은 병합 방식")
        self._run(
            (
                "gh",
                "pr",
                "merge",
                str(pr_number),
                "--repo",
                repository,
                "--auto",
                "--squash",
                "--match-head-commit",
                expected_head_sha,
            ),
            purpose="squash auto-merge 요청",
        )
        return {"accepted": True}

def validate_target(*, repository: str, base_branch: str, approval_id: str) -> None:
    """외부 권한을 열기 전에 정확한 단일 대상 allowlist를 검증한다."""

    supplied = (repository, base_branch, approval_id)
    expected = (EXPECTED_REPOSITORY, EXPECTED_BASE_BRANCH, EXPECTED_APPROVAL_ID)
    if supplied != expected:
        raise DeliveryBlocked(
            "승인된 GitHub 저장소·기준 브랜치·승인 근거와 정확히 일치하지 않음"
        )


_PLAIN_TOKEN = re.compile(r"\A[A-Za-z0-9_-]+\Z")
_PATTERNS = (
    re.compile(r"(?i)\bgh[pousr]_[A-Za-z0-9_]{8,}\b"),
    re.compile(r"(?i)\bgithub_pat_[A-Za-z0-9_]{8,}\b"),
        )


def _is_non_string_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def _validate_policy_context(
    context: Mapping[str, Any],
    *,
    active_policy_version: str = POLICY_VERSION,
    validated_transition: Mapping[str, Any] | None = None,
) -> None:
    transition_requested = (
        context.get("target_policy_version") is not None
        or context.get("policy_transition") is not None
    )
    if transition_requested:
        if validated_transition is None:
            raise DeliveryBlocked(
                "정책 전환은 base Git 객체로 검증된 publish 경로에서만 허용됨"
            )
        if context.get("policy_transition") != validated_transition:
            raise DeliveryBlocked("검증된 정책 전환 proof와 전달 context가 다름")
        if (
            context.get("policy_version")
            != validated_transition.get("from_policy_version")
            or context.get("target_policy_version")
            != validated_transition.get("to_policy_version")
            or active_policy_version
            != validated_transition.get("to_policy_version")
        ):
            raise DeliveryBlocked("정책 전환의 시작·목표·활성 버전이 일치하지 않음")
    elif context.get("policy_version") != active_policy_version:
        raise DeliveryBlocked("승인된 GitHub 전달 정책 버전과 정확히 일치하지 않음")
    approval_refs = context.get("approval_refs")
    if (
        not _is_non_string_sequence(approval_refs)
        or EXPECTED_APPROVAL_ID not in approval_refs
    ):
        raise DeliveryBlocked("필수 사용자 승인 근거가 전달 context에 없음")
    rfc_ids = context.get("rfc_ids")
    if (
        not _is_non_string_sequence(rfc_ids)
        or REQUIRED_DELIVERY_RFC not in rfc_ids
    ):
        raise DeliveryBlocked("필수 GitHub 전달 RFC가 context에 없음")
    if validated_transition is not None and (
        POLICY_TRANSITION_APPROVAL not in approval_refs
        or POLICY_TRANSITION_RFC not in rfc_ids
    ):
        raise DeliveryBlocked("정책 전환의 사용자 승인 또는 RFC 근거가 context에 없음")


def _strict_json_object(document: bytes, *, purpose: str) -> dict[str, Any]:
    """중복 key를 거부하며 UTF-8 JSON 객체를 해석한다."""

    if not isinstance(document, bytes) or len(document) > 1024 * 1024:
        raise DeliveryBlocked(f"{purpose} bytes 형식이나 크기가 잘못됨")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    try:
        parsed = json.loads(
            document.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ValueError("non-standard JSON constant")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, ValueError):
        raise DeliveryBlocked(f"{purpose}을 엄격한 JSON 객체로 해석하지 못함") from None
    if not isinstance(parsed, dict):
        raise DeliveryBlocked(f"{purpose} 최상위 형식이 객체가 아님")
    return parsed


def _exact_string_list(value: Any, *, purpose: str) -> list[str]:
    if not _is_non_string_sequence(value):
        raise DeliveryBlocked(f"{purpose} 목록 형식이 잘못됨")
    items = list(value)
    if not items or any(not isinstance(item, str) or not item for item in items):
        raise DeliveryBlocked(f"{purpose} 목록 값이 잘못됨")
    if len(items) != len(set(items)):
        raise DeliveryBlocked(f"{purpose} 목록에 중복 값이 있음")
    return items


def _transition_requested(context: Mapping[str, Any]) -> bool:
    return (
        context.get("target_policy_version") is not None
        or context.get("policy_transition") is not None
    )


def _validate_transition_entry_context(
    context: Mapping[str, Any], *, phase: str
) -> None:
    """base proof를 쓰기 전 허용할 exact 전환 intent의 구조만 검사한다."""

    if phase not in {"begin", "publish"}:
        raise DeliveryBlocked("정책 전환 entry 검증 단계가 잘못됨")
    if (
        context.get("policy_version") != POLICY_VERSION
        or context.get("target_policy_version") != TARGET_POLICY_VERSION
    ):
        raise DeliveryBlocked("승인된 exact v1.1→v1.2 정책 전환 intent가 아님")
    approval_refs = _exact_string_list(
        context.get("approval_refs"), purpose="정책 전환 context 승인 근거"
    )
    rfc_ids = _exact_string_list(
        context.get("rfc_ids"), purpose="정책 전환 context RFC 근거"
    )
    if set(approval_refs) != {EXPECTED_APPROVAL_ID, POLICY_TRANSITION_APPROVAL}:
        raise DeliveryBlocked("정책 전환 context의 승인 근거가 exact 계약과 다름")
    if set(rfc_ids) != {REQUIRED_DELIVERY_RFC, POLICY_TRANSITION_RFC}:
        raise DeliveryBlocked("정책 전환 context의 RFC 근거가 exact 계약과 다름")
    supplied_proof = context.get("policy_transition")
    if phase == "begin":
        if supplied_proof is not None:
            raise DeliveryBlocked("begin caller가 정책 전환 proof를 직접 공급할 수 없음")
        return
    if not isinstance(supplied_proof, Mapping):
        raise DeliveryBlocked("publish context에 정책 전환 proof가 없음")
    if (
        supplied_proof.get("schema_version") != POLICY_TRANSITION_PROOF_SCHEMA
        or supplied_proof.get("from_policy_version") != POLICY_VERSION
        or supplied_proof.get("to_policy_version") != TARGET_POLICY_VERSION
        or supplied_proof.get("mode") != POLICY_TRANSITION_MODE
        or not re.fullmatch(
            r"[0-9a-f]{40,64}", str(supplied_proof.get("base_sha", ""))
        )
        or not re.fullmatch(
            r"[0-9a-f]{64}",
            str(supplied_proof.get("base_policy_config_sha256", "")),
        )
    ):
        raise DeliveryBlocked("publish 정책 전환 proof의 구조가 잘못됨")


def build_policy_transition_proof(
    config_document: bytes,
    *,
    active_policy_version: str,
    target_policy_version: str,
    base_sha: str,
) -> dict[str, Any]:
    """base 정책 설정에 이미 승인된 exact one-hop edge를 proof로 고정한다."""

    config = _strict_json_object(config_document, purpose="base 정책 설정")
    normalized_base_sha = str(base_sha).lower()
    if not re.fullmatch(r"[0-9a-f]{40,64}", normalized_base_sha):
        raise DeliveryBlocked("정책 전환 base SHA가 잘못됨")
    if (
        active_policy_version != POLICY_VERSION
        or target_policy_version != TARGET_POLICY_VERSION
        or active_policy_version == target_policy_version
    ):
        raise DeliveryBlocked("승인된 exact v1.1→v1.2 정책 전환이 아님")
    if config.get("policy_version") != active_policy_version:
        raise DeliveryBlocked("base 정책 설정의 활성 버전이 전환 시작점과 다름")
    if (
        config.get("repository") != EXPECTED_REPOSITORY
        or config.get("base_branch") != EXPECTED_BASE_BRANCH
        or config.get("branch_prefix") != BRANCH_PREFIX
        or config.get("merge_method") != MERGE_METHOD
    ):
        raise DeliveryBlocked("base 정책 설정의 GitHub 대상 계약이 다름")
    transition = config.get("policy_transition")
    if not isinstance(transition, Mapping):
        raise DeliveryBlocked("base 정책 설정에 검토된 전환 edge가 없음")
    expected_keys = {
        "schema_version",
        "from_policy_version",
        "to_policy_version",
        "state",
        "mode",
        "approval_refs",
        "rfc_ids",
    }
    if set(transition) != expected_keys:
        raise DeliveryBlocked("정책 전환 edge 필드가 exact 계약과 다름")
    if (
        transition.get("schema_version") != POLICY_TRANSITION_SCHEMA
        or transition.get("from_policy_version") != active_policy_version
        or transition.get("to_policy_version") != target_policy_version
        or transition.get("state") != "armed"
        or transition.get("mode") != POLICY_TRANSITION_MODE
    ):
        raise DeliveryBlocked("정책 전환 edge가 승인된 armed one-hop과 다름")
    approval_refs = _exact_string_list(
        transition.get("approval_refs"), purpose="정책 전환 승인 근거"
    )
    rfc_ids = _exact_string_list(
        transition.get("rfc_ids"), purpose="정책 전환 RFC 근거"
    )
    if set(approval_refs) != {EXPECTED_APPROVAL_ID, POLICY_TRANSITION_APPROVAL}:
        raise DeliveryBlocked("정책 전환 승인 근거가 exact 계약과 다름")
    if set(rfc_ids) != {REQUIRED_DELIVERY_RFC, POLICY_TRANSITION_RFC}:
        raise DeliveryBlocked("정책 전환 RFC 근거가 exact 계약과 다름")
    return {
        "schema_version": POLICY_TRANSITION_PROOF_SCHEMA,
        "from_policy_version": active_policy_version,
        "to_policy_version": target_policy_version,
        "base_sha": normalized_base_sha,
        "base_policy_config_sha256": hashlib.sha256(config_document).hexdigest(),
        "mode": POLICY_TRANSITION_MODE,
        "approval_refs": approval_refs,
        "rfc_ids": rfc_ids,
    }


def validate_policy_transition_activation(
    proof: Mapping[str, Any],
    *,
    base_config_document: bytes,
    head_config_document: bytes,
    changed_paths: Sequence[str],
    active_policy_version: str,
) -> dict[str, Any]:
    """활성화 diff가 설정 두 값만 소비하는지 base bytes에 묶어 검증한다."""

    if not isinstance(proof, Mapping):
        raise DeliveryBlocked("정책 전환 proof 형식이 객체가 아님")
    expected_proof_keys = {
        "schema_version",
        "from_policy_version",
        "to_policy_version",
        "base_sha",
        "base_policy_config_sha256",
        "mode",
        "approval_refs",
        "rfc_ids",
    }
    if set(proof) != expected_proof_keys:
        raise DeliveryBlocked("정책 전환 proof 필드가 exact 계약과 다름")
    expected_proof = build_policy_transition_proof(
        base_config_document,
        active_policy_version=str(proof.get("from_policy_version", "")),
        target_policy_version=str(proof.get("to_policy_version", "")),
        base_sha=str(proof.get("base_sha", "")),
    )
    if dict(proof) != expected_proof:
        raise DeliveryBlocked("정책 전환 proof가 base 설정 bytes와 다름")
    if active_policy_version != expected_proof["to_policy_version"]:
        raise DeliveryBlocked("head 활성 정책 버전이 전환 목표와 다름")
    if (
        not _is_non_string_sequence(changed_paths)
        or list(changed_paths) != [POLICY_CONFIG_PATH]
    ):
        raise DeliveryBlocked("정책 활성화는 설정 파일 하나만 바꿀 수 있음")

    base_config = _strict_json_object(
        base_config_document, purpose="base 정책 설정"
    )
    head_config = _strict_json_object(
        head_config_document, purpose="head 정책 설정"
    )
    expected_head = copy.deepcopy(base_config)
    expected_head["policy_version"] = expected_proof["to_policy_version"]
    expected_transition = expected_head.get("policy_transition")
    if not isinstance(expected_transition, dict):
        raise DeliveryBlocked("base 정책 설정에 소비할 전환 edge가 없음")
    expected_transition["state"] = "consumed"
    canonical_head = json.dumps(
        head_config,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    canonical_expected = json.dumps(
        expected_head,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if canonical_head != canonical_expected:
        raise DeliveryBlocked("정책 활성화 diff가 허용된 두 설정 값만 바꾸지 않음")
    return {
        "route": "review",
        "from_policy_version": expected_proof["from_policy_version"],
        "to_policy_version": expected_proof["to_policy_version"],
        "base_sha": expected_proof["base_sha"],
        "base_policy_config_sha256": expected_proof[
            "base_policy_config_sha256"
        ],
    }


def _parse_token_document(document: str) -> str:
    """YAML의 의도된 한 줄 부분집합만 해석한다.

    YAML 일반 기능(별칭, 태그, collection, block scalar, 중복 key)을 허용하지
    않음으로써 parser 차이와 예기치 않은 구조를 제거한다.
    """

    match = re.fullmatch(r"key:[ \t]+([^\r\n]+)(?:\r?\n)?", document)
    if not match:
        raise TokenSafetyError("토큰 파일은 top-level key 하나만 가져야 함")
    token = match.group(1)
    if token != token.strip() or not _PLAIN_TOKEN.fullmatch(token):
        raise TokenSafetyError("토큰 key 값은 비어 있지 않은 단순 문자열이어야 함")
    return token


def load_token(
    path: Path | str,
    *,
    repo_root: Path | str,
    git_probe: Any | None = None,
) -> str:
    """안전한 ``auth/github_token.yaml``에서 토큰을 읽는다.

    경로·파일 종류·권한·소유자·Git 상태를 본문 read보다 먼저 검사하고,
    ``O_NOFOLLOW``와 ``fstat``으로 검사와 read 사이의 symlink 교체도 막는다.
    """

    root = Path(repo_root).resolve()
    token_path = Path(path)
    expected_path = root / "auth" / "github_token.yaml"
    try:
        # macOS의 /var -> /private/var처럼 상위 경로 alias는 정규화하되,
        # 최종 component 자체는 resolve하지 않아 symlink 검사를 우회하지 않는다.
        lexical_path = token_path.parent.resolve() / token_path.name
    except OSError as exc:
        raise TokenSafetyError("토큰 경로를 확인할 수 없음") from exc
    if lexical_path != expected_path:
        raise TokenSafetyError("승인된 토큰 경로가 아님")

    try:
        metadata = token_path.lstat()
    except OSError as exc:
        raise TokenSafetyError("토큰 파일 상태를 안전하게 확인할 수 없음") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise TokenSafetyError("토큰 파일은 symbolic link가 아닌 regular file이어야 함")
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise TokenSafetyError("토큰 파일 권한은 정확히 0600이어야 함")
    if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
        raise TokenSafetyError("토큰 파일 소유자가 현재 실행 사용자와 다름")

    probe = git_probe if git_probe is not None else GitProbe(root)
    # 호출 순서 자체가 계약이다. ignore 확인 후 tracked 여부를 별도로 확인한다.
    if not bool(probe.is_ignored(token_path)):
        raise TokenSafetyError("토큰 파일이 Git ignore 대상이 아님")
    if bool(probe.is_tracked(token_path)):
        raise TokenSafetyError("토큰 파일이 Git에 추적되고 있음")

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(token_path, flags)
    except OSError as exc:
        raise TokenSafetyError("토큰 파일을 안전하게 열 수 없음") from exc
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise TokenSafetyError("열린 토큰 객체가 regular file이 아님")
        if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise TokenSafetyError("검증 중 토큰 파일이 바뀜")
        if stat.S_IMODE(opened.st_mode) != 0o600:
            raise TokenSafetyError("열린 토큰 파일 권한이 0600이 아님")
        with os.fdopen(descriptor, "r", encoding="utf-8", newline="") as handle:
            descriptor = -1
            document = handle.read(16 * 1024 + 1)
    except (OSError, UnicodeError) as exc:
        raise TokenSafetyError("토큰 파일 내용을 안전하게 읽을 수 없음") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if len(document.encode("utf-8")) > 16 * 1024:
        raise TokenSafetyError("토큰 파일 크기가 허용 범위를 넘음")
    return _parse_token_document(document)


def redact(value: Any, *, secrets: Iterable[str] = ()) -> str:
    """명시적 비밀과 대표 GitHub token 형태를 모두 마스킹한다."""

    result = str(value)
    # 긴 값부터 지워 prefix 관계의 비밀도 완전히 제거한다.
    normalized = sorted(
        {secret for secret in secrets if isinstance(secret, str) and secret},
        key=len,
        reverse=True,
    )
    for secret in normalized:
        result = result.replace(secret, "[REDACTED]")
    for pattern in _PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


_PROTECTED_PREFIXES = (
    ".github/",
    "governance/",
    "config/",
    "tools/",
    "scripts/",
    "prompts/",
    "skills/",
    "tests/",
    "wiki/specs/",
)
_PROTECTED_EXACT = {"AGENTS.md", "AGENTS.override.md"}
_SAFE_EXACT = {"wiki/index.md", "wiki/log.md"}
_SAFE_PREFIXES = (
    "wiki/actors/",
    "wiki/admissions/",
    "wiki/campaigns/",
    "wiki/collaborations/",
    "wiki/feedback/",
    "wiki/governance/",
    "wiki/runs/",
    "wiki/trust/",
    "evaluations/reports/",
)


def _normalized_change_path(value: Any) -> str | None:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or "`" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        return None
    return path.as_posix()


def _classify_one(change: Any) -> tuple[str, str]:
    if not isinstance(change, Mapping):
        return "block", "변경 manifest 항목의 구조가 올바르지 않음"
    path = _normalized_change_path(change.get("path"))
    if path is None:
        return "block", "변경 경로를 안전하게 해석할 수 없음"
    status = change.get("status")
    if status not in {"added", "modified", "deleted", "renamed", "copied"}:
        return "review", f"{path}: 알 수 없는 변경 상태"
    lowered = path.lower()

    if lowered == "auth" or lowered.startswith("auth/"):
        return "block", f"{path}: 자격증명 경로 변경은 금지됨"
    if change.get("scope_status_mismatch") is True:
        return "block", f"{path}: 선언 상태와 실제 Git 상태가 다름"
    if any(
        change.get(flag) is True
        for flag in ("missing", "irregular", "type_changed")
    ):
        return "block", f"{path}: 파일 실체·종류를 안전하게 증명하지 못함"
    if path == "state/events.jsonl" and (
        status != "modified" or change.get("append_only_verified") is not True
    ):
        return "block", f"{path}: 사건 원장 재작성 또는 append-only 미검증"
    if lowered == "raw/quarantine" or lowered.startswith("raw/quarantine/"):
        return "block", f"{path}: 로컬 격리 payload는 public Git에 게시할 수 없음"
    if path.startswith("raw/"):
        if status != "added":
            return "block", f"{path}: 기존 raw 수정·이동·삭제는 금지됨"
        return "review", f"{path}: 새 raw의 입수·보안 근거를 사람이 확인해야 함"
    if change.get("secret_detected") is True or change.get("binary") is True:
        return "block", f"{path}: 비밀 또는 실행 바이너리 위험이 감지됨"
    if change.get("oversized") is True or change.get("symlink") is True:
        return "block", f"{path}: 과대 파일 또는 symbolic link는 금지됨"

    if path in _PROTECTED_EXACT or path.startswith(_PROTECTED_PREFIXES):
        return "review", f"{path}: 제어면 변경은 사람 검토가 필요함"
    if path == "state/events.jsonl":
        return "safe", f"{path}: append-only 검증된 사건 추가"
    if path.startswith("state/"):
        return "review", f"{path}: 원장 상태 변경은 사람 검토가 필요함"

    if path in _SAFE_EXACT or path.startswith(_SAFE_PREFIXES):
        if change.get("generated") is True and change.get("semantic_change") is False:
            return "safe", f"{path}: 의미 영향 없는 파생 산출물"
        return "review", f"{path}: 파생·비의미 변경임을 증명하지 못함"
    if path.startswith("wiki/"):
        if change.get("generated") is True and change.get("semantic_change") is False:
            return "safe", f"{path}: 의미 영향 없는 파생 Wiki 산출물"
        return "review", f"{path}: Wiki 의미·근거 영향 가능성을 배제하지 못함"
    return "review", f"{path}: 사전 승인된 안전 경로로 분류할 수 없음"


def classify_changes(changes: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    """변경 전체를 ``no-op|safe|review|block`` 중 하나로 fail-closed 분류한다."""

    if changes is None:
        return {"route": "block", "reasons": ["변경 manifest가 없음"]}
    if isinstance(changes, (str, bytes, Mapping)):
        return {"route": "block", "reasons": ["변경 manifest 형식이 잘못됨"]}
    materialized = list(changes)
    if not materialized:
        return {"route": "no-op", "reasons": ["추적할 파일 변경이 없음"]}

    decisions = [_classify_one(change) for change in materialized]
    routes = {route for route, _ in decisions}
    if "block" in routes:
        route = "block"
    elif "review" in routes:
        route = "review"
    else:
        route = "safe"
    return {"route": route, "reasons": [reason for _, reason in decisions]}


def idempotency_key(
    *,
    policy_version: str,
    run_id: str,
    base_sha: str,
    tree_sha: str,
    target_policy_version: str | None = None,
    base_policy_config_sha256: str | None = None,
) -> str:
    """일반 전달 또는 base-bound 정책 전환의 안정적인 SHA-256 key를 만든다."""

    if target_policy_version is None and base_policy_config_sha256 is None:
        components = [policy_version, run_id, base_sha, tree_sha]
    else:
        if (
            not isinstance(target_policy_version, str)
            or not target_policy_version
            or not isinstance(base_policy_config_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", base_policy_config_sha256)
        ):
            raise DeliveryBlocked("정책 전환 멱등성 구성요소가 잘못됨")
        components = [
            policy_version,
            target_policy_version,
            base_policy_config_sha256,
            run_id,
            base_sha,
            tree_sha,
        ]
    payload = json.dumps(
        components,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _format_collection(value: Any, *, empty: str = "없음") -> str:
    if isinstance(value, Mapping):
        if not value:
            return empty
        return "\n".join(f"- {key}: {item}" for key, item in value.items())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if not value:
            return empty
        return "\n".join(f"- {item}" for item in value)
    return str(value) if value not in (None, "") else empty


def _format_bounded_collection(value: Any, *, limit: int = 40) -> str:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return _format_collection(value)
    items = list(value)
    visible = items[:limit]
    lines = [f"- {item}" for item in visible]
    if len(items) > limit:
        lines.append(f"- 나머지 {len(items) - limit}개 이유는 delivery receipt에 보존됨")
    return "\n".join(lines) if lines else "없음"


def _format_changes(changes: Any) -> str:
    if not changes:
        return "없음"
    lines = []
    for change in changes:
        if isinstance(change, Mapping):
            lines.append(f"- `{change.get('path', '알 수 없음')}` ({change.get('status', '알 수 없음')})")
        else:
            lines.append("- 해석할 수 없는 manifest 항목")
    details = "\n".join(lines)
    return (
        f"<details>\n<summary>전체 manifest {len(lines)}개 보기</summary>\n\n"
        f"{details}\n\n</details>"
    )


def _format_change_groups(changes: Any) -> str:
    groups = {
        "GitHub·하네스 제어면": 0,
        "정규 원장·거버넌스": 0,
        "Wiki 명세·지식 문서": 0,
        "테스트·평가·운영 문서": 0,
        "원문·기타": 0,
    }
    if not isinstance(changes, Sequence) or isinstance(changes, (str, bytes)):
        return "- 판정 불가"
    for change in changes:
        path = str(change.get("path", "")) if isinstance(change, Mapping) else ""
        if path.startswith(
            (".github/", "tools/", "config/", "skills/", "prompts/", "scripts/")
        ) or path in {"AGENTS.md", "AGENTS.override.md"}:
            group = "GitHub·하네스 제어면"
        elif path.startswith(("state/", "governance/", "wiki/governance/")):
            group = "정규 원장·거버넌스"
        elif path.startswith("wiki/"):
            group = "Wiki 명세·지식 문서"
        elif path.startswith(
            ("tests/", "evaluations/", "reports/", "docs/", "evolution/")
        ) or path in {"README.md", "pyproject.toml"}:
            group = "테스트·평가·운영 문서"
        else:
            group = "원문·기타"
        groups[group] += 1
    return "\n".join(
        f"- {name}: {count}개" for name, count in groups.items() if count
    )


def _gate_digest(value: Any) -> str:
    try:
        material = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        return "판정 불가"
    return hashlib.sha256(material).hexdigest()


def build_pr_body(context: Mapping[str, Any]) -> str:
    """사람과 자동화가 함께 감사할 수 있는 한국어 PR 본문을 만든다."""

    risk = context.get("risk") if isinstance(context.get("risk"), Mapping) else {}
    route = risk.get("route", "block")
    route_label = {
        "safe": "자동 병합 후보",
        "review": "사람 검토 필요",
        "block": "차단",
        "no-op": "중요한 변경 없음",
    }.get(route, "판정 불가")
    reasons = _format_bounded_collection(risk.get("reasons", []))
    review_request = ""
    if route == "review":
        review_request = """

## 사람 검토 요청

@winehouse8 실제 diff와 필수 check를 확인해 주세요. 자동화는 이 draft PR을 approve·ready·merge하지 않습니다. 검토 후 안전하다고 판단되면 사람이 직접 ready 전환과 병합을 수행하고, 아니라면 변경 요청 또는 close로 남겨 주세요.

- [ ] `.github/**`, `tools/**`, `config/**`, `skills/**` 제어면 변경을 확인함
- [ ] 로컬 전체 게이트 결과와 게이트 지문을 확인함
- [ ] 비밀·raw 덮어쓰기·C/S 단계·생명주기 영향이 없음을 확인함
- [ ] 병합 뒤 필수 원격 check와 무해한 auto-merge canary를 설정하기로 함
"""
    transition_section = ""
    transition = context.get("policy_transition")
    if isinstance(transition, Mapping):
        transition_section = f"""

## 정책 전환

- 시작 정책: `{transition.get('from_policy_version', '없음')}`
- 목표 정책: `{transition.get('to_policy_version', '없음')}`
- base 설정 SHA-256: `{transition.get('base_policy_config_sha256', '없음')}`
- 적용 방식: **사람 검토 전용**
"""
    body = f"""## 실행 정보

- 실행 ID: `{context.get('run_id', '없음')}`
- 행위자: `{context.get('actor', '없음')}`
- 호출 방식: `{context.get('invocation', '없음')}`
- 작업 종류: `{context.get('work_type', '없음')}`
- Wiki 의존도: `{context.get('wiki_mode', '없음')}`

## 고정된 Git 상태

- 기준 SHA: `{context.get('base_sha', '없음')}`
- 헤드 SHA: `{context.get('head_sha', '없음')}`
- 트리 SHA: `{context.get('tree_sha', '없음')}`

## 변경 파일

{_format_change_groups(context.get('changes'))}

{_format_changes(context.get('changes'))}

## 거버넌스 근거

- RFC: {_format_collection(context.get('rfc_ids', []))}
- 승인 근거: {_format_collection(context.get('approval_refs', []))}
- 부트스트랩 영수증: {context.get('bootstrap_receipt', '해당 없음')}
{transition_section}

## 검증

{_format_collection(context.get('local_gates', {}))}

- 게이트 지문: `{context.get('gate_digest') or _gate_digest(context.get('local_gates', {}))}`

## 위험 판정

- 경로: **{route_label}**
- 이유:
{reasons}

## 인식론적 영향

- C/S-level 및 생명주기 영향: {context.get('epistemic_impact', '판정되지 않음')}

## 미해결

{_format_collection(context.get('unresolved', []))}

## 롤백

{context.get('rollback', '새 revert PR로 되돌린다.')}
{review_request}
"""
    return redact(body)


def _branch_name(run_id: Any, key: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", str(run_id).lower()).strip("-")
    if not slug:
        slug = "run"
    return f"{BRANCH_PREFIX}{slug[:70]}-{key[:12]}"


def _blocked_receipt(
    *,
    key: str,
    risk: Mapping[str, Any],
    reason: str,
    pr: Mapping[str, Any] | None = None,
    merge_requested: bool = False,
    merge_state_uncertain: bool = False,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "status": "blocked",
        "route": risk.get("route", "block"),
        "reasons": list(risk.get("reasons", [])) + [reason],
        "idempotency_key": key,
        "merge_requested": merge_requested,
        "merge_state_uncertain": merge_state_uncertain,
        "merge_method": MERGE_METHOD if merge_requested else None,
        "merge_sha": None,
    }
    if pr:
        receipt.update(
            {
                "pr_number": pr.get("number"),
                "pr_url": pr.get("url"),
                "draft": pr.get("draft"),
            }
        )
    return receipt


def _pr_receipt(
    *, status: str, key: str, risk: Mapping[str, Any], pr: Mapping[str, Any],
    branch: str, labels: Sequence[str], merge_requested: bool = False,
) -> dict[str, Any]:
    return {
        "status": status,
        "route": risk["route"],
        "reasons": list(risk["reasons"]),
        "idempotency_key": key,
        "branch": branch,
        "pr_number": pr.get("number"),
        "pr_url": pr.get("url"),
        "draft": bool(pr.get("draft")),
        "labels": list(labels),
        "merge_requested": merge_requested,
        "merge_method": MERGE_METHOD if status == "merged" or merge_requested else None,
        "merge_sha": pr.get("merge_sha"),
    }


def _prior_auto_merge_requested(
    prior_receipt: Mapping[str, Any] | None,
    *,
    key: str,
    risk: Mapping[str, Any],
    existing: Mapping[str, Any],
) -> bool:
    """같은 safe PR의 이전 영수증만 auto-merge 요청 근거로 재사용한다."""

    return bool(
        isinstance(prior_receipt, Mapping)
        and risk.get("route") == "safe"
        and prior_receipt.get("route") == "safe"
        and prior_receipt.get("status") in {"auto-merge-pending", "merged"}
        and prior_receipt.get("idempotency_key") == key
        and prior_receipt.get("pr_number") == existing.get("number")
        and prior_receipt.get("merge_requested") is True
        and prior_receipt.get("merge_method") == MERGE_METHOD
    )


def _required_text(request: Mapping[str, Any], name: str) -> str:
    value = request.get(name)
    if not isinstance(value, str) or not value:
        raise DeliveryBlocked(f"필수 전달 필드가 없거나 잘못됨: {name}")
    return value


def _all_local_gates_passed(value: Any) -> bool:
    return isinstance(value, Mapping) and bool(value) and all(
        str(result).lower() in {"success", "passed", "pass", "ok"}
        for result in value.values()
    )


def _required_checks_passed(value: Any, *, head_sha: str) -> bool:
    """정확한 이름의 필수 check가 같은 head에서 성공했는지 확인한다."""

    if not isinstance(value, Mapping):
        return False
    if value.get("state") != "success" or value.get("head_sha") != head_sha:
        return False
    checks = value.get("checks")
    if not isinstance(checks, Sequence) or isinstance(checks, (str, bytes)):
        return False
    success_states = {"success", "pass", "passed"}
    states_by_name: dict[str, set[str]] = {}
    for item in checks:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name", ""))
        state_value = str(item.get("state", "")).lower()
        if name:
            states_by_name.setdefault(name, set()).add(state_value)
    return all(
        states_by_name.get(required, set()) & success_states
        for required in REQUIRED_CHECK_NAMES
    )


def _deliver_impl(
    request: Mapping[str, Any],
    *,
    transport: Any,
    token_loader: Any,
    prior_receipt: Mapping[str, Any] | None = None,
    active_policy_version: str = POLICY_VERSION,
    validated_transition: Mapping[str, Any] | None = None,
    reconciliation_only: bool = False,
) -> dict[str, Any]:
    """분류→PR→검증→조건부 병합 상태기계를 실행한다.

    대상 allowlist는 모든 분류·자격증명·transport 접근보다 먼저 검사한다.
    정책상 즉시 금지된 diff와 무변경 실행은 자격증명을 읽지 않는다.
    """

    if not isinstance(request, Mapping):
        raise DeliveryBlocked("전달 요청 형식이 올바르지 않음")
    # 이 세 필드 외의 request 검증보다도 exact allowlist가 먼저다.
    validate_target(
        repository=request.get("repository"),
        base_branch=request.get("base_branch"),
        approval_id=request.get("approval_id"),
    )
    _validate_policy_context(
        request,
        active_policy_version=active_policy_version,
        validated_transition=validated_transition,
    )
    repository = EXPECTED_REPOSITORY
    base_branch = EXPECTED_BASE_BRANCH
    risk = classify_changes(request.get("changes"))

    if risk["route"] == "no-op":
        return {
            "status": "no-op",
            "route": "no-op",
            "reasons": list(risk["reasons"]),
            "merge_requested": False,
        }

    policy_version = _required_text(request, "policy_version")
    run_id = _required_text(request, "run_id")
    base_sha = _required_text(request, "base_sha")
    head_sha = _required_text(request, "head_sha")
    tree_sha = _required_text(request, "tree_sha")
    key_arguments: dict[str, Any] = {
        "policy_version": policy_version,
        "run_id": run_id,
        "base_sha": base_sha,
        "tree_sha": tree_sha,
    }
    if validated_transition is not None:
        key_arguments.update(
            {
                "target_policy_version": validated_transition.get(
                    "to_policy_version"
                ),
                "base_policy_config_sha256": validated_transition.get(
                    "base_policy_config_sha256"
                ),
            }
        )
    key = idempotency_key(**key_arguments)
    if risk["route"] == "block":
        return _blocked_receipt(
            key=key,
            risk=risk,
            reason="금지 변경이 있어 GitHub 권한을 열지 않음",
        )
    if risk["route"] == "safe" and not _all_local_gates_passed(
        request.get("local_gates")
    ):
        return _blocked_receipt(
            key=key,
            risk=risk,
            reason="필수 로컬 검증이 성공하지 않음",
        )

    try:
        token = token_loader()
    except Exception as exc:
        # loader 예외 문구는 알려지지 않은 비밀을 포함할 수 있어 전달하지 않는다.
        raise DeliveryBlocked("GitHub 자격증명을 안전하게 불러오지 못함") from None
    if not isinstance(token, str) or not token:
        raise DeliveryBlocked("GitHub 자격증명이 비어 있거나 잘못됨")
    try:
        public_context = json.dumps(
            request,
            ensure_ascii=False,
            sort_keys=True,
        )
        preview_context = dict(request)
        preview_context["risk"] = risk
        public_body = build_pr_body(preview_context)
    except Exception:
        token = None
        raise DeliveryBlocked("공개 전달 context의 비밀 포함 여부를 검사하지 못함") from None
    if token in public_context or token in public_body:
        token = None
        raise DeliveryBlocked("실제 GitHub token이 공개 전달 context에 포함됨")
    setter = getattr(transport, "set_token", None)
    if callable(setter):
        setter(token)
    # transport 경계 밖의 지역 참조는 즉시 제거한다.
    token = None

    requested_branch = request.get("branch")
    if requested_branch is None:
        branch = _branch_name(run_id, key)
    elif (
        isinstance(requested_branch, str)
        and requested_branch.startswith(BRANCH_PREFIX)
        and _normalized_change_path(requested_branch) == requested_branch
    ):
        branch = requested_branch
    else:
        raise DeliveryBlocked("자동 작업 브랜치 소유권 형식이 잘못됨")
    labels = (
        ["자동화", "사람-검토-필요"]
        if risk["route"] == "review"
        else ["자동화", "자동-병합-후보"]
    )
    try:
        existing = transport.find_delivery(
            repository=repository, idempotency_key=key
        )
    except Exception:
        raise TransportError("기존 GitHub 전달 상태를 안전하게 조회하지 못함") from None

    if existing and existing.get("merged") and existing.get("merge_sha"):
        merge_requested = bool(
            risk["route"] == "safe"
            and (
                existing.get("auto_merge_enabled")
                or existing.get("auto_merge_requested")
                or _prior_auto_merge_requested(
                    prior_receipt,
                    key=key,
                    risk=risk,
                    existing=existing,
                )
            )
        )
        return _pr_receipt(
            status="merged",
            key=key,
            risk=risk,
            pr=existing,
            branch=branch,
            labels=existing.get("labels") or labels,
            merge_requested=merge_requested,
        )
    if existing and existing.get("state") == "closed":
        return _blocked_receipt(
            key=key,
            risk=risk,
            reason="같은 멱등성 키의 PR이 병합 없이 닫혀 있음",
            pr=existing,
        )
    if reconciliation_only and (
        existing is None or risk["route"] != "review"
    ):
        return _blocked_receipt(
            key=key,
            risk=risk,
            reason="기준 SHA 이동 뒤에는 기존 사람 검토 PR의 읽기 전용 재조정만 허용됨",
            pr=existing,
        )

    if risk["route"] == "safe" and existing and existing.get(
        "auto_merge_enabled"
    ):
        try:
            armed = transport.get_pull_request(
                repository=repository, pr_number=existing.get("number")
            )
        except Exception:
            return _blocked_receipt(
                key=key,
                risk=risk,
                reason="활성화된 auto-merge PR을 재조정하지 못함",
                pr=existing,
            )
        if armed.get("merged") and armed.get("merge_sha"):
            return _pr_receipt(
                status="merged",
                key=key,
                risk=risk,
                pr=armed,
                branch=branch,
                labels=armed.get("labels") or labels,
                merge_requested=True,
            )
        if armed.get("auto_merge_enabled"):
            return _pr_receipt(
                status="auto-merge-pending",
                key=key,
                risk=risk,
                pr=armed,
                branch=branch,
                labels=armed.get("labels") or labels,
                merge_requested=True,
            )

    if existing is None:
        pull_request: Mapping[str, Any] | None = None
        try:
            remote_base = transport.get_base_sha(
                repository=repository, base_branch=base_branch
            )
        except Exception:
            return _blocked_receipt(
                key=key, risk=risk, reason="원격 기준 SHA를 조회하지 못함"
            )
        if remote_base != base_sha:
            return _blocked_receipt(
                key=key, risk=risk, reason="기준 브랜치 SHA가 실행 영수증과 달라짐"
            )
        try:
            transport.create_branch(
                repository=repository,
                branch=branch,
                base_sha=base_sha,
                idempotency_key=key,
            )
            context = dict(request)
            context["risk"] = risk
            body = build_pr_body(context)
            title_prefix = (
                "사람 검토 필요" if risk["route"] == "review" else "자동 병합 후보"
            )
            requested_title = request.get("pr_title")
            if requested_title is not None and (
                not isinstance(requested_title, str)
                or not requested_title.strip()
                or len(requested_title) > 120
                or any(ord(character) < 32 for character in requested_title)
            ):
                raise DeliveryBlocked("사용자 지정 PR 제목 형식이 안전하지 않음")
            pull_request = transport.create_pull_request(
                repository=repository,
                base_branch=base_branch,
                branch=branch,
                title=(
                    requested_title.strip()
                    if isinstance(requested_title, str)
                    else f"[위키 자동화] {title_prefix}: {run_id}"
                ),
                body=body,
                draft=risk["route"] == "review",
                idempotency_key=key,
                head_sha=head_sha,
                tree_sha=tree_sha,
            )
            transport.add_labels(
                repository=repository,
                pr_number=pull_request["number"],
                labels=labels,
            )
            pull_request = dict(pull_request)
            pull_request["labels"] = list(labels)
            existing = pull_request
        except Exception:
            return _blocked_receipt(
                key=key,
                risk=risk,
                reason="브랜치 또는 PR을 안전하게 생성하지 못함",
                pr=pull_request,
            )

    if risk["route"] == "review":
        try:
            reviewed = transport.get_pull_request(
                repository=repository, pr_number=existing.get("number")
            )
        except Exception:
            return _blocked_receipt(
                key=key,
                risk=risk,
                reason="사람 검토 PR의 최종 상태를 재조회하지 못함",
                pr=existing,
            )
        if reviewed.get("head_sha") != head_sha or reviewed.get("base_sha") != base_sha:
            return _blocked_receipt(
                key=key,
                risk=risk,
                reason="사람 검토 PR의 기준 또는 head SHA가 실행 영수증과 다름",
                pr=reviewed,
            )
        actual_labels = list(reviewed.get("labels") or [])
        if not set(labels).issubset(set(actual_labels)):
            return _blocked_receipt(
                key=key,
                risk=risk,
                reason="사람 검토 PR의 필수 라벨을 확인하지 못함",
                pr=reviewed,
            )
        return _pr_receipt(
            status="review",
            key=key,
            risk=risk,
            pr=reviewed,
            branch=branch,
            labels=actual_labels,
        )

    pr_number = existing.get("number")
    try:
        current = transport.get_pull_request(
            repository=repository, pr_number=pr_number
        )
    except Exception:
        return _blocked_receipt(
            key=key, risk=risk, reason="병합 전 PR 상태를 재조회하지 못함", pr=existing
        )
    if current.get("conflict"):
        return _blocked_receipt(
            key=key, risk=risk, reason="PR merge conflict가 있음", pr=current
        )
    if current.get("unresolved_reviews", 0):
        return _blocked_receipt(
            key=key, risk=risk, reason="미해결 GitHub 검토 대화가 있음", pr=current
        )
    if current.get("base_sha") != base_sha:
        return _blocked_receipt(
            key=key, risk=risk, reason="병합 전 기준 SHA drift가 감지됨", pr=current
        )
    if current.get("head_sha") != head_sha:
        return _blocked_receipt(
            key=key, risk=risk, reason="병합 전 head SHA drift가 감지됨", pr=current
        )
    if current.get("tree_sha") != tree_sha:
        return _blocked_receipt(
            key=key, risk=risk, reason="병합 전 tree SHA drift가 감지됨", pr=current
        )

    try:
        checks = transport.get_checks(
            repository=repository, pr_number=pr_number, head_sha=head_sha
        )
    except Exception:
        return _blocked_receipt(
            key=key, risk=risk, reason="원격 필수 check를 조회하지 못함", pr=current
        )
    if not _required_checks_passed(checks, head_sha=head_sha):
        return _blocked_receipt(
            key=key,
            risk=risk,
            reason="원격 필수 check가 성공하지 않았거나 다른 head의 결과임",
            pr=current,
        )

    # check와 merge 호출 사이의 drift도 막기 위해 기준과 PR을 한 번 더 확인한다.
    try:
        final_base = transport.get_base_sha(
            repository=repository, base_branch=base_branch
        )
        premerge = transport.get_pull_request(
            repository=repository, pr_number=pr_number
        )
    except Exception:
        return _blocked_receipt(
            key=key, risk=risk, reason="병합 직전 원격 상태를 재확인하지 못함", pr=current
        )
    if final_base != base_sha or any(
        premerge.get(field) != expected
        for field, expected in (
            ("base_sha", base_sha),
            ("head_sha", head_sha),
            ("tree_sha", tree_sha),
        )
    ):
        return _blocked_receipt(
            key=key, risk=risk, reason="병합 직전 Git SHA drift가 감지됨", pr=premerge
        )
    if premerge.get("conflict") or premerge.get("unresolved_reviews", 0):
        return _blocked_receipt(
            key=key, risk=risk, reason="병합 직전 충돌 또는 미해결 검토가 감지됨", pr=premerge
        )

    try:
        accepted = transport.request_auto_merge(
            repository=repository,
            pr_number=pr_number,
            method=MERGE_METHOD,
            expected_base_sha=base_sha,
            expected_head_sha=head_sha,
            expected_tree_sha=tree_sha,
        )
        if not isinstance(accepted, Mapping) or accepted.get("accepted") is not True:
            return _blocked_receipt(
                key=key, risk=risk, reason="GitHub auto-merge 요청이 수락되지 않음", pr=premerge
            )
        completed = transport.get_pull_request(
            repository=repository, pr_number=pr_number
        )
    except Exception:
        return _blocked_receipt(
            key=key,
            risk=risk,
            reason="auto-merge 요청 또는 최종 상태 재조회 실패",
            pr=premerge,
            merge_requested=True,
            merge_state_uncertain=True,
        )
    if completed.get("auto_merge_enabled") and not completed.get("merged"):
        return _pr_receipt(
            status="auto-merge-pending",
            key=key,
            risk=risk,
            pr=completed,
            branch=branch,
            labels=completed.get("labels") or labels,
            merge_requested=True,
        )
    if not completed.get("merged") or not completed.get("merge_sha"):
        return _blocked_receipt(
            key=key,
            risk=risk,
            reason="PR 재조회에서 병합 완료와 merge SHA를 확인하지 못함",
            pr=completed,
            merge_requested=True,
            merge_state_uncertain=True,
        )
    return _pr_receipt(
        status="merged",
        key=key,
        risk=risk,
        pr=completed,
        branch=branch,
        labels=labels,
        merge_requested=True,
    )


def deliver(
    request: Mapping[str, Any],
    *,
    transport: Any,
    token_loader: Any,
    prior_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """비밀 수명을 transport 호출 범위로 제한해 전달 상태기계를 실행한다."""

    return _deliver_guarded(
        request,
        transport=transport,
        token_loader=token_loader,
        prior_receipt=prior_receipt,
        active_policy_version=POLICY_VERSION,
        validated_transition=None,
        reconciliation_only=False,
    )


def _deliver_guarded(
    request: Mapping[str, Any],
    *,
    transport: Any,
    token_loader: Any,
    prior_receipt: Mapping[str, Any] | None,
    active_policy_version: str,
    validated_transition: Mapping[str, Any] | None,
    reconciliation_only: bool,
) -> dict[str, Any]:
    """public normal 경로와 private 검증 전환 경로의 비밀 정리를 공유한다."""

    try:
        return _deliver_impl(
            request,
            transport=transport,
            token_loader=token_loader,
            prior_receipt=prior_receipt,
            active_policy_version=active_policy_version,
            validated_transition=validated_transition,
            reconciliation_only=reconciliation_only,
        )
    finally:
        clearer = getattr(transport, "clear_token", None)
        if callable(clearer):
            try:
                clearer()
            except Exception:
                # clear 실패가 기존 전달 결과를 성공으로 바꾸지는 않는다. 구현
                # transport는 clear를 메모리 대입 하나로 유지해야 한다.
                pass


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_id_from_now(now: str) -> str:
    timestamp = re.sub(r"[^0-9]", "", str(now))[:14]
    if len(timestamp) < 14:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"RUN-{timestamp}Z-{secrets_module.token_hex(3).upper()}"


def _safe_run_id(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise DeliveryBlocked("실행 ID 형식이 안전하지 않음")
    return value


def _run_branch(run_id: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", run_id.lower()).strip("-")
    if not slug:
        raise DeliveryBlocked("실행 ID에서 브랜치 이름을 만들 수 없음")
    return f"{BRANCH_PREFIX}{slug[:100]}"


def _delivery_state_dir(root: Path, runner: Any | None = None) -> Path:
    if runner is None:
        return root / ".git" / "wiki-delivery"
    result = _command(
        runner,
        ("git", "rev-parse", "--git-common-dir"),
        cwd=root,
        purpose="Git 공통 메타데이터 경로 확인",
    )
    raw = _output(result).strip()
    if not raw or "\x00" in raw:
        raise DeliveryBlocked("Git 공통 메타데이터 경로가 비어 있거나 잘못됨")
    common = Path(raw)
    if not common.is_absolute():
        common = root / common
    try:
        common = common.resolve()
    except OSError:
        raise DeliveryBlocked("Git 공통 메타데이터 경로를 정규화하지 못함") from None
    return common / "wiki-delivery"


def _begin_receipt_path(
    root: Path, run_id: str, *, runner: Any | None = None
) -> Path:
    return _delivery_state_dir(root, runner) / f"{_safe_run_id(run_id)}.begin.json"


def _delivery_receipt_path(
    root: Path, run_id: str, *, runner: Any | None = None
) -> Path:
    return _delivery_state_dir(root, runner) / f"{_safe_run_id(run_id)}.delivery.json"


def _write_json_receipt(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _acquire_publish_lock(root: Path, runner: Any):
    directory = _delivery_state_dir(root, runner)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "publish.lock"
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    handle = os.fdopen(descriptor, "r+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()}\n")
        handle.flush()
        os.fsync(handle.fileno())
    except (BlockingIOError, OSError):
        handle.close()
        raise DeliveryBlocked("다른 GitHub publish 실행이 현재 저장소 잠금을 보유함") from None
    return handle


def _release_publish_lock(handle: Any) -> None:
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _read_json_object(path: Path, *, purpose: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise DeliveryBlocked(f"{purpose}을 안전하게 읽지 못함") from None
    if not isinstance(value, dict):
        raise DeliveryBlocked(f"{purpose} 형식이 객체가 아님")
    return value


def _worktree_policy_config_document(
    root: Path, *, required: bool
) -> bytes | None:
    path = root / POLICY_CONFIG_PATH
    try:
        metadata = path.lstat()
    except OSError:
        if required:
            raise DeliveryBlocked("작업 사본의 정책 설정을 읽지 못함") from None
        return None
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise DeliveryBlocked("정책 설정은 symbolic link가 아닌 regular file이어야 함")
    if metadata.st_size > 1024 * 1024:
        raise DeliveryBlocked("정책 설정 파일 크기가 허용 범위를 넘음")
    try:
        return path.read_bytes()
    except OSError:
        raise DeliveryBlocked("작업 사본의 정책 설정 bytes를 읽지 못함") from None


def _policy_version_from_document(document: bytes) -> str:
    config = _strict_json_object(document, purpose="GitHub 전달 정책 설정")
    version = config.get("policy_version")
    if version not in {POLICY_VERSION, TARGET_POLICY_VERSION}:
        raise DeliveryBlocked("지원되는 GitHub 전달 정책 버전이 아님")
    if (
        config.get("repository") != EXPECTED_REPOSITORY
        or config.get("base_branch") != EXPECTED_BASE_BRANCH
        or config.get("branch_prefix") != BRANCH_PREFIX
        or config.get("merge_method") != MERGE_METHOD
    ):
        raise DeliveryBlocked("GitHub 전달 정책 설정의 exact 대상 계약이 다름")
    transition = config.get("policy_transition")
    if transition is not None:
        if not isinstance(transition, Mapping) or set(transition) != {
            "schema_version",
            "from_policy_version",
            "to_policy_version",
            "state",
            "mode",
            "approval_refs",
            "rfc_ids",
        }:
            raise DeliveryBlocked("GitHub 전달 정책 전환 record가 잘못됨")
        expected_state = "consumed" if version == TARGET_POLICY_VERSION else "armed"
        if (
            transition.get("schema_version") != POLICY_TRANSITION_SCHEMA
            or transition.get("from_policy_version") != POLICY_VERSION
            or transition.get("to_policy_version") != TARGET_POLICY_VERSION
            or transition.get("state") != expected_state
            or transition.get("mode") != POLICY_TRANSITION_MODE
            or set(
                _exact_string_list(
                    transition.get("approval_refs"),
                    purpose="정책 설정 전환 승인 근거",
                )
            )
            != {EXPECTED_APPROVAL_ID, POLICY_TRANSITION_APPROVAL}
            or set(
                _exact_string_list(
                    transition.get("rfc_ids"),
                    purpose="정책 설정 전환 RFC 근거",
                )
            )
            != {REQUIRED_DELIVERY_RFC, POLICY_TRANSITION_RFC}
        ):
            raise DeliveryBlocked("GitHub 전달 정책 전환 상태가 active 버전과 다름")
    elif version == TARGET_POLICY_VERSION:
        raise DeliveryBlocked("v1.2 active 정책에 consumed 전환 record가 없음")
    return str(version)


def _base_policy_config_document(
    root: Path, runner: Any, *, base_sha: str, required: bool
) -> bytes | None:
    if not required and not (root / POLICY_CONFIG_PATH).is_file():
        # 구형 isolated fixture에는 정책 파일이 없다. 실제 저장소에서는 tracked
        # worktree 파일이 있을 때만 base Git 객체를 권위로 다시 읽는다.
        return None
    document = _git_base_blob(
        root,
        runner,
        base_sha=base_sha,
        path=POLICY_CONFIG_PATH,
    )
    if document is None and required:
        raise DeliveryBlocked("begin 기준 Git 객체에 정책 설정이 없음")
    return document


def _origin_repository(url: str) -> str | None:
    value = url.strip()
    patterns = (
        r"https://github\.com/([^/\s]+/[^/\s]+?)(?:\.git)?$",
        r"git@github\.com:([^/\s]+/[^/\s]+?)(?:\.git)?$",
        r"ssh://git@github\.com/([^/\s]+/[^/\s]+?)(?:\.git)?$",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, value)
        if match:
            return match.group(1)
    return None


def _single_remote_url(
    root: Path, runner: Any, *, push: bool
) -> str:
    arguments = ["git", "remote", "get-url"]
    if push:
        arguments.append("--push")
    arguments.extend(("--all", "origin"))
    result = _command(
        runner,
        arguments,
        cwd=root,
        purpose="origin push URL 확인" if push else "origin fetch URL 확인",
    )
    urls = [line.strip() for line in _output(result).splitlines() if line.strip()]
    if len(urls) != 1 or _origin_repository(urls[0]) != EXPECTED_REPOSITORY:
        kind = "push" if push else "fetch"
        raise DeliveryBlocked(f"origin {kind} URL이 승인된 exact 저장소 하나가 아님")
    return urls[0]


def _validate_origin_identity(root: Path, runner: Any) -> dict[str, str]:
    """fetch와 push URL 모두 정확한 단일 승인 저장소인지 확인한다."""

    return {
        "fetch_url": _single_remote_url(root, runner, push=False),
        "push_url": _single_remote_url(root, runner, push=True),
    }


def _refresh_and_validate_base(
    root: Path,
    runner: Any,
    *,
    expected_base_sha: str,
    allow_review_reconciliation: bool = False,
) -> bool:
    """자격증명 없이 origin/main을 갱신하고 새 게시의 base drift를 차단한다."""

    _validate_origin_identity(root, runner)
    _command(
        runner,
        (
            "git",
            "fetch",
            "--no-tags",
            "--prune",
            EXPECTED_REMOTE_URL,
            EXPECTED_BASE_REFSPEC,
        ),
        cwd=root,
        env=_credential_free_git_env(),
        purpose="GitHub 전달 기준 브랜치 최신성 확인",
    )
    drifted = (
        _rev_parse(root, runner, "refs/remotes/origin/main")
        != expected_base_sha
    )
    if drifted and not allow_review_reconciliation:
        raise DeliveryBlocked("begin 뒤 origin/main 기준 SHA가 이동함")
    return drifted


def _git_status(root: Path, runner: Any) -> str:
    result = _command(
        runner,
        ("git", "status", "--porcelain=v1", "--untracked-files=all"),
        cwd=root,
        purpose="Git 작업 사본 상태 확인",
    )
    return _output(result)


def _current_branch(root: Path, runner: Any) -> str:
    result = _command(
        runner,
        ("git", "branch", "--show-current"),
        cwd=root,
        purpose="현재 Git 브랜치 확인",
    )
    branch = _output(result).strip()
    if not branch:
        raise DeliveryBlocked("detached HEAD에서는 자동 전달을 시작할 수 없음")
    return branch


def _rev_parse(root: Path, runner: Any, revision: str) -> str:
    result = _command(
        runner,
        ("git", "rev-parse", revision),
        cwd=root,
        purpose=f"Git revision {revision} 확인",
    )
    value = _output(result).strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", value):
        raise DeliveryBlocked(f"Git revision {revision} 결과가 SHA가 아님")
    return value.lower()


def begin_run(
    context: Mapping[str, Any],
    *,
    repo_root: Path | str,
    runner: Any,
    now: str | None = None,
) -> dict[str, Any]:
    """깨끗하고 최신인 ``main``에서 전용 실행 브랜치와 영수증을 만든다."""

    if not isinstance(context, Mapping):
        raise DeliveryBlocked("begin context 형식이 올바르지 않음")
    validate_target(
        repository=context.get("repository"),
        base_branch=context.get("base_branch"),
        approval_id=context.get("approval_id"),
    )
    root = Path(repo_root).resolve()
    if not (root / ".git").exists():
        raise DeliveryBlocked("Git 저장소 루트를 확인할 수 없음")
    worktree_policy = _worktree_policy_config_document(root, required=False)
    worktree_active_policy = (
        _policy_version_from_document(worktree_policy)
        if worktree_policy is not None
        else POLICY_VERSION
    )
    target_policy_version = context.get("target_policy_version")
    if target_policy_version is not None:
        _validate_transition_entry_context(context, phase="begin")
        if worktree_active_policy != POLICY_VERSION:
            raise DeliveryBlocked("정책 전환 begin의 작업 사본이 v1.1 active가 아님")
    else:
        _validate_policy_context(
            context, active_policy_version=worktree_active_policy
        )
    run_id = _safe_run_id(context.get("run_id"))
    receipt_path = _begin_receipt_path(root, run_id, runner=runner)
    if receipt_path.exists():
        raise DeliveryBlocked("같은 실행 ID의 begin 영수증이 이미 있음")

    top = _command(
        runner,
        ("git", "rev-parse", "--show-toplevel"),
        cwd=root,
        purpose="Git 저장소 루트 확인",
    )
    try:
        reported_root = Path(_output(top).strip()).resolve()
    except OSError:
        raise DeliveryBlocked("Git 저장소 루트를 정규화하지 못함") from None
    if reported_root != root:
        raise DeliveryBlocked("지정한 경로와 Git 저장소 루트가 다름")

    origin_identity = _validate_origin_identity(root, runner)
    if _current_branch(root, runner) != EXPECTED_BASE_BRANCH:
        raise DeliveryBlocked("begin은 최신 main 브랜치에서만 실행할 수 있음")
    if _git_status(root, runner):
        raise DeliveryBlocked("begin 전 Git 작업 사본이 깨끗하지 않음")

    _command(
        runner,
        (
            "git",
            "fetch",
            "--no-tags",
            "--prune",
            EXPECTED_REMOTE_URL,
            EXPECTED_BASE_REFSPEC,
        ),
        cwd=root,
        env=_credential_free_git_env(),
        purpose="최신 origin/main fetch",
    )
    local_head = _rev_parse(root, runner, "HEAD")
    remote_head = _rev_parse(root, runner, "refs/remotes/origin/main")
    if local_head != remote_head:
        raise DeliveryBlocked("HEAD와 최신 origin/main이 일치하지 않음")

    transition_proof: dict[str, Any] | None = None
    if worktree_policy is not None or target_policy_version is not None:
        base_policy = _base_policy_config_document(
            root,
            runner,
            base_sha=local_head,
            required=True,
        )
        assert base_policy is not None
        base_active_policy = _policy_version_from_document(base_policy)
        if base_active_policy != worktree_active_policy:
            raise DeliveryBlocked("작업 사본과 begin 기준 Git 정책 버전이 다름")
        if target_policy_version is not None:
            transition_proof = build_policy_transition_proof(
                base_policy,
                active_policy_version=base_active_policy,
                target_policy_version=str(target_policy_version),
                base_sha=local_head,
            )
        else:
            _validate_policy_context(
                context, active_policy_version=base_active_policy
            )

    branch = _run_branch(run_id)
    _command(
        runner,
        ("git", "switch", "-c", branch, local_head),
        cwd=root,
        purpose="전용 자동 작업 브랜치 생성",
    )
    timestamp = now or _now_iso8601()
    receipt = {
        "schema_version": (
            "github-delivery-begin/v2"
            if transition_proof is not None
            else "github-delivery-begin/v1"
        ),
        "status": "begun",
        "repository": EXPECTED_REPOSITORY,
        "base_branch": EXPECTED_BASE_BRANCH,
        "approval_id": EXPECTED_APPROVAL_ID,
        "policy_version": context.get("policy_version", POLICY_VERSION),
        "run_id": run_id,
        "actor": context.get("actor", "agent:codex"),
        "invocation": context.get("invocation", "수동"),
        "work_type": context.get("work_type", "위생"),
        "wiki_mode": context.get("wiki_mode", "wiki-first"),
        "branch": branch,
        "base_sha": local_head,
        "started_at": timestamp,
        "rfc_ids": list(context.get("rfc_ids", ["RFC-03F4FE85BB44"])),
        "approval_refs": list(context.get("approval_refs", [EXPECTED_APPROVAL_ID])),
        "origin_fetch_url": origin_identity["fetch_url"],
        "origin_push_url": origin_identity["push_url"],
    }
    if transition_proof is not None:
        receipt["target_policy_version"] = TARGET_POLICY_VERSION
        receipt["policy_transition"] = transition_proof
    _write_json_receipt(receipt_path, receipt)
    return receipt


def _parse_status(status: str) -> dict[str, str]:
    changes: dict[str, str] = {}
    for line in status.splitlines():
        if not line:
            continue
        if len(line) < 4:
            raise DeliveryBlocked("Git status 항목을 안전하게 해석하지 못함")
        code = line[:2]
        raw_path = line[3:]
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1]
        path = _normalized_change_path(raw_path)
        if path is None or path in changes:
            raise DeliveryBlocked("Git status 변경 경로가 잘못되었거나 중복됨")
        if "?" in code or "A" in code:
            change_status = "added"
        elif "D" in code:
            change_status = "deleted"
        elif "R" in code:
            change_status = "renamed"
        else:
            change_status = "modified"
        changes[path] = change_status
    return changes


def _manifest_paths(changes: Any) -> dict[str, str]:
    if not isinstance(changes, Sequence) or isinstance(changes, (str, bytes)):
        raise DeliveryBlocked("명시적 change manifest 형식이 잘못됨")
    paths: dict[str, str] = {}
    for change in changes:
        if not isinstance(change, Mapping):
            raise DeliveryBlocked("change manifest 항목 형식이 잘못됨")
        path = _normalized_change_path(change.get("path"))
        status = change.get("status")
        if path is None or path in paths or not isinstance(status, str):
            raise DeliveryBlocked("change manifest 경로가 잘못되었거나 중복됨")
        paths[path] = status
    return paths


def _assert_manifest_matches(changes: Any, status: str) -> dict[str, str]:
    manifest = _manifest_paths(changes)
    actual = _parse_status(status)
    if set(manifest) != set(actual):
        raise DeliveryBlocked("명시적 manifest 밖 변경 또는 누락된 변경이 있음")
    return manifest


def _assert_worktree_scope(
    changes: Any,
    *,
    root: Path,
    runner: Any,
    base_sha: str,
) -> dict[str, str]:
    """줄 단위 porcelain 대신 NUL diff로 선언 경로와 실제 범위를 비교한다."""

    manifest = _manifest_paths(changes)
    actual = _git_worktree_changes(root, runner, base_sha=base_sha)
    if set(manifest) != set(actual):
        raise DeliveryBlocked("명시적 manifest 밖 변경 또는 누락된 변경이 있음")
    return manifest


_RELEASE_ARCHIVE_PATH = re.compile(
    r"evaluations/reports/v4-release-([0-9a-f]{16})\.json\Z"
)


def _valid_post_gate_release_archive(root: Path, path: str, observed: Mapping[str, Any]) -> bool:
    """게이트가 새로 만든 content-addressed 릴리스 JSON만 좁게 인정한다."""

    match = _RELEASE_ARCHIVE_PATH.fullmatch(path)
    if not match or observed.get("status") != "added":
        return False
    target = root / path
    try:
        metadata = target.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_TRACKED_FILE_BYTES:
            return False
        report = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(report, dict):
        return False
    fingerprint = report.get("component_fingerprint")
    digest = report.get("report_digest")
    gates = report.get("gates")
    if (
        not isinstance(fingerprint, str)
        or not re.fullmatch(r"[0-9a-f]{64}", fingerprint)
        or fingerprint[:16] != match.group(1)
        or not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
        or report.get("passed") is not True
        or report.get("production_certified") is not False
        or not isinstance(gates, list)
        or len(gates) < 8
        or any(not isinstance(gate, dict) or gate.get("passed") is not True for gate in gates)
    ):
        return False
    material = {key: value for key, value in report.items() if key != "report_digest"}
    expected_digest = hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return digest == expected_digest


def _reconcile_post_gate_manifest(
    declared: Mapping[str, str],
    actual: Mapping[str, Mapping[str, Any]],
    *,
    root: Path,
) -> dict[str, str]:
    """게이트가 경로·상태를 하나도 바꾸지 않았을 때만 manifest를 보존한다."""

    if not isinstance(declared, Mapping) or not isinstance(actual, Mapping):
        raise DeliveryBlocked("게이트 후 manifest 구조가 잘못됨")
    observed = {
        path: str(value.get("status"))
        for path, value in actual.items()
        if isinstance(value, Mapping)
    }
    if len(observed) != len(actual) or observed != dict(declared):
        raise DeliveryBlocked("게이트가 권위 manifest의 경로 또는 상태를 바꾸었음")
    return dict(declared)


_SECRET_BYTE_PATTERNS = (
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(rb"(?i)authorization\s*:\s*(?:bearer|token)\s+[A-Za-z0-9._~+/=-]{16,}"),
)


def _parse_name_status_z(value: str) -> dict[str, dict[str, str]]:
    """`git diff --name-status -z --no-renames` 출력을 손실 없이 해석한다."""

    if not value:
        return {}
    fields = value.split("\0")
    if fields[-1] != "" or (len(fields) - 1) % 2:
        raise DeliveryBlocked("Git NUL name-status 출력 구조가 잘못됨")
    changes: dict[str, dict[str, str]] = {}
    status_map = {"A": "added", "M": "modified", "D": "deleted"}
    for offset in range(0, len(fields) - 1, 2):
        git_status = fields[offset]
        path = _normalized_change_path(fields[offset + 1])
        if path is None or path in changes:
            raise DeliveryBlocked("Git diff 변경 경로가 잘못되었거나 중복됨")
        code = git_status[:1]
        if code in {"U", "X", "B"}:
            raise DeliveryBlocked(f"{path}: 병합되지 않은 Git 상태가 있음")
        changes[path] = {
            "status": status_map.get(code, "modified"),
            "git_status": git_status,
        }
    return changes


def _git_worktree_changes(
    root: Path, runner: Any, *, base_sha: str
) -> dict[str, dict[str, str]]:
    tracked = _command(
        runner,
        (
            "git",
            "diff",
            "--name-status",
            "-z",
            "--no-renames",
            base_sha,
            "--",
        ),
        cwd=root,
        purpose="기준 SHA 대비 실제 변경 경로 관찰",
    )
    changes = _parse_name_status_z(_output(tracked))
    untracked = _command(
        runner,
        (
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
        ),
        cwd=root,
        purpose="미추적 변경 경로 관찰",
    )
    values = _output(untracked)
    if values:
        paths = values.split("\0")
        if paths[-1] != "":
            raise DeliveryBlocked("Git NUL 미추적 경로 출력 구조가 잘못됨")
        for raw_path in paths[:-1]:
            path = _normalized_change_path(raw_path)
            if path is None or path in changes:
                raise DeliveryBlocked("미추적 변경 경로가 잘못되었거나 중복됨")
            changes[path] = {"status": "added", "git_status": "?"}
    return changes


def _git_worktree_snapshot(
    root: Path, runner: Any, *, base_sha: str
) -> dict[str, dict[str, Any]]:
    """경로·상태·현재 bytes를 함께 고정해 gate 자기 변경을 탐지한다."""

    changes = _git_worktree_changes(root, runner, base_sha=base_sha)
    snapshot: dict[str, dict[str, Any]] = {}
    for relative, observed in sorted(changes.items()):
        target = root / relative
        status_value = observed.get("status")
        if status_value == "deleted":
            if target.exists() or target.is_symlink():
                raise DeliveryBlocked(f"{relative}: 삭제 상태와 작업 사본이 일치하지 않음")
            snapshot[relative] = {
                "status": "deleted",
                "git_status": observed.get("git_status"),
                "sha256": None,
                "size": 0,
            }
            continue
        try:
            metadata = target.lstat()
        except OSError:
            raise DeliveryBlocked(f"{relative}: 변경 파일을 읽지 못함") from None
        if not stat.S_ISREG(metadata.st_mode):
            raise DeliveryBlocked(f"{relative}: gate snapshot은 regular file만 허용함")
        if metadata.st_size > MAX_TRACKED_FILE_BYTES:
            raise DeliveryBlocked(f"{relative}: gate snapshot 파일 크기 상한을 넘음")
        digest = hashlib.sha256()
        try:
            with target.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            raise DeliveryBlocked(f"{relative}: gate snapshot bytes를 읽지 못함") from None
        snapshot[relative] = {
            "status": status_value,
            "git_status": observed.get("git_status"),
            "sha256": digest.hexdigest(),
            "size": metadata.st_size,
        }
    return snapshot


def _git_base_blob(root: Path, runner: Any, *, base_sha: str, path: str) -> bytes | None:
    result = _command_bytes(
        runner,
        ("git", "show", f"{base_sha}:{path}"),
        cwd=root,
        allowed=(0, 128),
        purpose=f"기준 blob 확인: {path}",
    )
    if getattr(result, "returncode", None) != 0:
        return None
    return _output_bytes(result)


def _generator_owned(path: str, data: bytes) -> bool:
    if not path.startswith("wiki/"):
        return False
    prefix = data[:16384]
    if path in {"wiki/index.md", "wiki/log.md"}:
        return b"tools/wiki.py" in prefix and "자동 생성".encode() in prefix
    return (
        b"generated: true" in prefix
        and "자동 생성".encode() in prefix
        and b"tools/wiki.py" in prefix
    )


def _pattern_secret_detected(data: bytes) -> bool:
    return any(pattern.search(data) for pattern in _SECRET_BYTE_PATTERNS)


def inspect_actual_changes(
    *,
    repo_root: Path | str,
    runner: Any,
    base_sha: str,
    expected_paths: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """고정 base와 현재 worktree를 직접 관찰해 권위 있는 manifest를 만든다.

    caller가 제공한 위험 boolean은 읽지 않는다. Git status, lstat, 실제 bytes와
    기준 blob만 사용하며 증명할 수 없는 generated/semantic 속성은 보수적으로
    사람 검토로 보낸다.
    """

    root = Path(repo_root).resolve()
    discovered = _git_worktree_changes(root, runner, base_sha=base_sha)
    if expected_paths is not None and set(discovered) != set(expected_paths):
        raise DeliveryBlocked("선언한 범위와 base 대비 실제 변경 경로가 다름")

    patch = _command(
        runner,
        (
            "git",
            "diff",
            "--no-ext-diff",
            "--no-color",
            base_sha,
            "--",
        ),
        cwd=root,
        purpose="공개 diff 비밀 패턴 검사",
    )
    global_diff = _output(patch).encode("utf-8")
    global_secret = _pattern_secret_detected(global_diff)
    result: list[dict[str, Any]] = []
    for index, (path, observed) in enumerate(sorted(discovered.items())):
        status_value = observed["status"]
        item: dict[str, Any] = {
            "path": path,
            "status": status_value,
            "git_status": observed["git_status"],
            "observed": True,
            "generated": False,
            "semantic_change": None,
            "secret_detected": global_secret and index == 0,
            "binary": False,
            "oversized": False,
            "symlink": False,
            "irregular": False,
            "missing": False,
            "type_changed": observed["git_status"].startswith("T"),
            "append_only_verified": False,
        }
        if status_value == "deleted":
            base_data = _git_base_blob(
                root, runner, base_sha=base_sha, path=path
            ) or b""
            item["secret_detected"] = item["secret_detected"] or _pattern_secret_detected(
                base_data
            )
            item["content_sha256"] = None
            result.append(item)
            continue

        target = root / path
        try:
            metadata = target.lstat()
        except OSError:
            item["missing"] = True
            result.append(item)
            continue
        item["symlink"] = stat.S_ISLNK(metadata.st_mode)
        item["irregular"] = not (
            stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
        )
        item["size"] = metadata.st_size
        item["oversized"] = metadata.st_size > MAX_TRACKED_FILE_BYTES
        if item["symlink"] or item["irregular"] or item["oversized"]:
            result.append(item)
            continue
        try:
            data = target.read_bytes()
        except OSError:
            item["missing"] = True
            result.append(item)
            continue
        item["content_sha256"] = hashlib.sha256(data).hexdigest()
        item["binary"] = b"\0" in data[:8192]
        item["secret_detected"] = item["secret_detected"] or _pattern_secret_detected(
            data
        )
        item["generated"] = _generator_owned(path, data)
        if item["generated"]:
            item["semantic_change"] = False
        if path == "state/events.jsonl" and status_value == "modified":
            base_data = _git_base_blob(root, runner, base_sha=base_sha, path=path)
            item["append_only_verified"] = bool(
                base_data is not None
                and data.startswith(base_data)
                and len(data) > len(base_data)
                and (not base_data or base_data.endswith(b"\n"))
            )
        result.append(item)
    return result


def _merge_declared_risk_constraints(
    measured: Sequence[Mapping[str, Any]], declared: Any
) -> list[dict[str, Any]]:
    """caller 선언은 위험을 높일 수만 있고 실측 결과를 낮출 수 없다."""

    declared_by_path = {
        item.get("path"): item
        for item in declared
        if isinstance(item, Mapping) and isinstance(item.get("path"), str)
    } if isinstance(declared, Sequence) and not isinstance(declared, (str, bytes)) else {}
    merged: list[dict[str, Any]] = []
    for observed in measured:
        item = dict(observed)
        supplied = declared_by_path.get(item.get("path"), {})
        for flag in (
            "secret_detected",
            "binary",
            "oversized",
            "symlink",
            "irregular",
            "missing",
            "type_changed",
        ):
            if supplied.get(flag) is True:
                item[flag] = True
        if supplied.get("generated") is False:
            item["generated"] = False
        if supplied.get("semantic_change") is True:
            item["semantic_change"] = True
        if supplied and item.get("status") != supplied.get("status"):
            item["scope_status_mismatch"] = True
        merged.append(item)
    return merged


def _exact_secret_in_publish_material(
    token: str,
    *,
    root: Path,
    runner: Any,
    base_sha: str,
    context: Mapping[str, Any],
    changes: Sequence[Mapping[str, Any]],
) -> bool:
    secret = token.encode("utf-8")
    if not secret:
        return True
    public_context = json.dumps(
        {key: value for key, value in context.items() if not str(key).startswith("_")},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    if secret in public_context:
        return True
    diff = _command(
        runner,
        ("git", "diff", "--no-ext-diff", "--no-color", base_sha, "--"),
        cwd=root,
        purpose="실제 token의 공개 diff 포함 여부 검사",
    )
    if secret in _output(diff).encode("utf-8"):
        return True
    for change in changes:
        if change.get("status") == "deleted":
            continue
        path = _normalized_change_path(change.get("path"))
        if path is None:
            return True
        try:
            data = (root / path).read_bytes()
        except OSError:
            return True
        if secret in data:
            return True
    return False


def _expected_status_map(changes: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for change in changes:
        path = _normalized_change_path(change.get("path"))
        status_value = change.get("status")
        if (
            path is None
            or path in result
            or status_value not in {"added", "modified", "deleted"}
        ):
            raise DeliveryBlocked("권위 manifest의 경로 또는 상태가 잘못됨")
        result[path] = str(status_value)
    return result


def _verify_git_diff_scope(
    root: Path,
    runner: Any,
    *,
    expected: Mapping[str, str],
    revisions: Sequence[str],
    cached: bool = False,
    purpose: str,
) -> None:
    argv = ["git", "diff"]
    if cached:
        argv.append("--cached")
    argv.extend(("--name-status", "-z", "--no-renames", *revisions, "--"))
    observed = _parse_name_status_z(
        _output(_command(runner, argv, cwd=root, purpose=purpose))
    )
    status_map = {path: item["status"] for path, item in observed.items()}
    if status_map != dict(expected):
        raise DeliveryBlocked(f"{purpose}의 경로·상태가 권위 manifest와 다름")


def quality_gate_commands(now: str) -> tuple[tuple[str, ...], ...]:
    """SPEC-GH-DELIVERY-001의 전체 로컬 게이트 순서를 반환한다."""

    return (
        ("python3", "tools/wiki.py", "evaluate"),
        ("python3", "tools/wiki.py", "render", "--no-log"),
        ("python3", "tools/wiki.py", "memory-hygiene", "--now", now),
        ("python3", "tools/wiki.py", "hygiene-plan", "--now", now),
        (
            "python3",
            "tools/wiki.py",
            "lint",
            "--quarantine-profile",
            "public-clean-clone",
            "--check-only",
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
            "--check-only",
        ),
    )


class _LocalBranchTransport:
    """주입된 transport 앞에서 local branch push를 한 번 수행한다."""

    def __init__(self, transport: Any, *, runner: Any, repo_root: Path):
        self.transport = transport
        self.runner = runner
        self.repo_root = repo_root
        self._token: str | None = None

    def set_token(self, token: str) -> None:
        if not isinstance(token, str) or not token:
            raise TokenSafetyError("GitHub 자격증명이 비어 있거나 잘못됨")
        self._token = token

    def clear_token(self) -> None:
        self._token = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.transport, name)

    def create_branch(self, **kwargs: Any):
        if not self._token:
            raise TokenSafetyError("branch push용 자격증명이 주입되지 않음")
        _validate_origin_identity(self.repo_root, self.runner)
        branch = kwargs["branch"]
        _command(
            self.runner,
            (
                "git",
                "push",
                EXPECTED_REMOTE_URL,
                f"{branch}:{branch}",
            ),
            cwd=self.repo_root,
            env=_git_auth_env(self._token),
            purpose="자동 작업 브랜치 push",
        )
        return self.transport.create_branch(**kwargs)


def _read_begin_receipt(
    root: Path, context: Mapping[str, Any], *, runner: Any
) -> dict[str, Any]:
    run_id = _safe_run_id(context.get("run_id"))
    path = _begin_receipt_path(root, run_id, runner=runner)
    if not path.is_file():
        raise DeliveryBlocked("대응하는 begin 영수증이 없음")
    receipt = _read_json_object(path, purpose="begin 영수증")
    expected = {
        "repository": EXPECTED_REPOSITORY,
        "base_branch": EXPECTED_BASE_BRANCH,
        "approval_id": EXPECTED_APPROVAL_ID,
        "policy_version": context.get("policy_version", POLICY_VERSION),
        "run_id": run_id,
        "actor": context.get("actor"),
        "target_policy_version": context.get("target_policy_version"),
        "policy_transition": context.get("policy_transition"),
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise DeliveryBlocked(f"begin 영수증의 {key} 소유권이 context와 다름")
    current_origin = _validate_origin_identity(root, runner)
    if receipt.get("origin_fetch_url") is not None and receipt.get(
        "origin_fetch_url"
    ) != current_origin["fetch_url"]:
        raise DeliveryBlocked("begin 영수증 이후 origin fetch URL이 바뀜")
    if receipt.get("origin_push_url") is not None and receipt.get(
        "origin_push_url"
    ) != current_origin["push_url"]:
        raise DeliveryBlocked("begin 영수증 이후 origin push URL이 바뀜")
    for audit_key in ("approval_refs", "rfc_ids"):
        if audit_key in receipt and receipt.get(audit_key) != context.get(audit_key):
            raise DeliveryBlocked(f"begin 영수증의 {audit_key} 감사 근거가 context와 다름")
    if receipt.get("branch") != _run_branch(run_id):
        raise DeliveryBlocked("begin 영수증 브랜치 소유권이 잘못됨")
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", str(receipt.get("base_sha", ""))):
        raise DeliveryBlocked("begin 영수증 기준 SHA가 잘못됨")
    if _transition_requested(context):
        _validate_transition_entry_context(context, phase="publish")
        if receipt.get("schema_version") != "github-delivery-begin/v2":
            raise DeliveryBlocked("정책 전환 begin 영수증 schema가 잘못됨")
        proof = receipt.get("policy_transition")
        if not isinstance(proof, Mapping) or proof.get("base_sha") != receipt.get(
            "base_sha"
        ):
            raise DeliveryBlocked("정책 전환 proof와 begin 기준 SHA가 다름")
    return receipt


def _prior_review_receipt_allows_reconciliation(
    prior: Mapping[str, Any] | None,
    *,
    context: Mapping[str, Any],
    begin_receipt: Mapping[str, Any],
    current_head: str,
    current_tree: str,
) -> bool:
    """사람 검토 PR의 원격 상태만 다시 읽을 수 있는 local evidence를 검사한다."""

    if not isinstance(prior, Mapping) or current_head == begin_receipt.get("base_sha"):
        return False
    proof = context.get("policy_transition")
    key_arguments: dict[str, Any] = {
        "policy_version": context.get("policy_version"),
        "run_id": context.get("run_id"),
        "base_sha": begin_receipt.get("base_sha"),
        "tree_sha": current_tree,
    }
    if isinstance(proof, Mapping):
        key_arguments.update(
            {
                "target_policy_version": proof.get("to_policy_version"),
                "base_policy_config_sha256": proof.get(
                    "base_policy_config_sha256"
                ),
            }
        )
    try:
        expected_key = idempotency_key(**key_arguments)
    except GitHubDeliveryError:
        return False
    pr_url = prior.get("pr_url")
    return bool(
        prior.get("schema_version") == "github-delivery-receipt/v1"
        and prior.get("status") == "review"
        and prior.get("route") == "review"
        and prior.get("merge_requested") is False
        and isinstance(prior.get("pr_number"), int)
        and isinstance(pr_url, str)
        and re.fullmatch(
            r"https://github\.com/winehouse8/auto_wiki/pull/[1-9][0-9]*",
            pr_url,
        )
        and prior.get("run_id") == context.get("run_id")
        and prior.get("actor") == context.get("actor")
        and prior.get("branch") == begin_receipt.get("branch")
        and prior.get("base_sha") == begin_receipt.get("base_sha")
        and prior.get("head_sha") == current_head
        and prior.get("tree_sha") == current_tree
        and prior.get("idempotency_key") == expected_key
        and re.fullmatch(r"[0-9a-f]{64}", str(prior.get("gate_digest", "")))
        and (
            not isinstance(proof, Mapping)
            or (
                prior.get("policy_transition") == proof
                and prior.get("begin_policy_version")
                == proof.get("from_policy_version")
                and prior.get("target_policy_version")
                == proof.get("to_policy_version")
                and prior.get("base_policy_config_sha256")
                == proof.get("base_policy_config_sha256")
            )
        )
    )


def _publish_run_unlocked(
    context: Mapping[str, Any],
    *,
    repo_root: Path | str,
    runner: Any,
    gate_runner: Any,
    transport: Any,
    token_loader: Any,
    now: str | None = None,
) -> dict[str, Any]:
    """begin 이후 명시 manifest만 commit하고 PR 전달 상태기계에 연결한다."""

    if not isinstance(context, Mapping):
        raise DeliveryBlocked("publish context 형식이 올바르지 않음")
    validate_target(
        repository=context.get("repository"),
        base_branch=context.get("base_branch"),
        approval_id=context.get("approval_id"),
    )
    if _transition_requested(context):
        _validate_transition_entry_context(context, phase="publish")
    else:
        _validate_policy_context(
            context,
            active_policy_version=str(context.get("policy_version", "")),
        )
    root = Path(repo_root).resolve()
    receipt = _read_begin_receipt(root, context, runner=runner)
    branch = str(receipt["branch"])
    if _current_branch(root, runner) != branch:
        raise DeliveryBlocked("현재 브랜치가 begin 영수증 소유 브랜치와 다름")
    base_sha = str(receipt["base_sha"]).lower()
    current_head = _rev_parse(root, runner, "HEAD")
    current_tree = _rev_parse(root, runner, "HEAD^{tree}")
    run_id = str(context["run_id"])
    actor = str(context.get("actor", "agent:codex"))
    prior_delivery_receipt: Mapping[str, Any] | None = None
    prior_delivery_path = _delivery_receipt_path(root, run_id, runner=runner)
    if prior_delivery_path.exists():
        prior_delivery_receipt = _read_json_object(
            prior_delivery_path,
            purpose="이전 전달 영수증",
        )
    allow_review_reconciliation = _prior_review_receipt_allows_reconciliation(
        prior_delivery_receipt,
        context=context,
        begin_receipt=receipt,
        current_head=current_head,
        current_tree=current_tree,
    )
    base_drifted = _refresh_and_validate_base(
        root,
        runner,
        expected_base_sha=base_sha,
        allow_review_reconciliation=allow_review_reconciliation,
    )
    base_policy = _base_policy_config_document(
        root,
        runner,
        base_sha=base_sha,
        required=_transition_requested(context)
        or (root / POLICY_CONFIG_PATH).is_file(),
    )
    base_active_policy = (
        _policy_version_from_document(base_policy)
        if base_policy is not None
        else POLICY_VERSION
    )
    if _transition_requested(context):
        _validate_transition_entry_context(context, phase="publish")
    else:
        _validate_policy_context(
            context, active_policy_version=base_active_policy
        )
    resume_owned_commit = current_head != base_sha
    resume_gate_digest: str | None = None
    if resume_owned_commit:
        if _rev_parse(root, runner, "HEAD^") != base_sha:
            raise DeliveryBlocked("재개 대상 HEAD가 begin 기준의 단일 자식 commit이 아님")
        message = _output(
            _command(
                runner,
                ("git", "show", "-s", "--format=%B", "HEAD"),
                cwd=root,
                purpose="재개 commit 소유권 확인",
            )
        )
        required_trailers = (
            f"Wiki-Run-ID: {run_id}",
            f"Wiki-Actor: {actor}",
        )
        if not all(trailer in message.splitlines() for trailer in required_trailers):
            raise DeliveryBlocked("재개 commit trailer가 begin 실행 소유권과 다름")
        for line in message.splitlines():
            if line.startswith("Wiki-Gate-Digest: "):
                candidate = line.removeprefix("Wiki-Gate-Digest: ").strip()
                if re.fullmatch(r"[0-9a-f]{64}", candidate):
                    resume_gate_digest = candidate
        if resume_gate_digest is None:
            raise DeliveryBlocked("재개 commit에 검증된 gate 지문 trailer가 없음")
        if _git_status(root, runner):
            raise DeliveryBlocked("commit 재개 시 Git 작업 사본이 깨끗하지 않음")

    changes = context.get("changes")
    manifest = (
        _manifest_paths(changes)
        if resume_owned_commit
        else _assert_worktree_scope(
            changes,
            root=root,
            runner=runner,
            base_sha=base_sha,
        )
    )
    transition_proof: Mapping[str, Any] | None = None
    transition_validation: Mapping[str, Any] | None = None
    if _transition_requested(context):
        transition_proof = context.get("policy_transition")
        if not isinstance(transition_proof, Mapping):
            raise DeliveryBlocked("정책 전환 proof가 없음")
        if transition_proof.get("base_sha") != base_sha:
            raise DeliveryBlocked("정책 전환 proof base SHA가 begin 영수증과 다름")
        if manifest != {POLICY_CONFIG_PATH: "modified"}:
            raise DeliveryBlocked("정책 활성화 manifest는 설정 파일 한 건의 수정이어야 함")
        observed_transition_changes = _git_worktree_changes(
            root, runner, base_sha=base_sha
        )
        if {
            path: item.get("status")
            for path, item in observed_transition_changes.items()
        } != {POLICY_CONFIG_PATH: "modified"}:
            raise DeliveryBlocked(
                "정책 활성화의 실측 Git diff가 설정 파일 한 건의 수정이 아님"
            )
        if base_policy is None:
            raise DeliveryBlocked("정책 전환 base 설정을 읽지 못함")
        head_policy = _worktree_policy_config_document(root, required=True)
        assert head_policy is not None
        head_active_policy = _policy_version_from_document(head_policy)
        transition_validation = validate_policy_transition_activation(
            transition_proof,
            base_config_document=base_policy,
            head_config_document=head_policy,
            changed_paths=sorted(manifest),
            active_policy_version=head_active_policy,
        )
    if not manifest:
        if resume_owned_commit:
            raise DeliveryBlocked("변경 없는 실행에 재개 commit이 존재함")
        return _deliver_guarded(
            context,
            transport=transport,
            token_loader=token_loader,
            prior_receipt=prior_delivery_receipt,
            active_policy_version=base_active_policy,
            validated_transition=None,
            reconciliation_only=base_drifted,
        )

    gate_timestamp = now or _now_iso8601()
    gates: dict[str, str]
    if resume_owned_commit:
        gates = {"재개 commit에 고정된 로컬 gate": "success"}
        gate_digest = str(resume_gate_digest)
    else:
        gates = {}
        gate_snapshot = _git_worktree_snapshot(
            root,
            runner,
            base_sha=base_sha,
        )
        if set(gate_snapshot) != set(manifest):
            raise DeliveryBlocked("gate 시작 snapshot이 권위 manifest 범위와 다름")
        for command in quality_gate_commands(gate_timestamp):
            try:
                result = gate_runner.run(
                    command, cwd=root, env=None, input_text=None
                )
            except Exception:
                raise DeliveryBlocked("로컬 품질 gate를 실행하지 못함") from None
            if getattr(result, "returncode", None) != 0:
                raise DeliveryBlocked("로컬 품질 gate가 실패하여 publish를 차단함")
            if (
                _git_worktree_snapshot(
                    root,
                    runner,
                    base_sha=base_sha,
                )
                != gate_snapshot
            ):
                raise DeliveryBlocked(
                    "로컬 품질 gate가 작업 사본의 경로·상태 또는 bytes를 바꾸었음"
                )
            gates[" ".join(command)] = "success"
        gate_digest = _gate_digest(gates)

    if resume_owned_commit:
        if _git_status(root, runner):
            raise DeliveryBlocked("재개 검증 gate가 commit 밖 변경을 만들었음")
    else:
        post_gate_actual = _git_worktree_changes(root, runner, base_sha=base_sha)
    measured = inspect_actual_changes(
        repo_root=root,
        runner=runner,
        base_sha=base_sha,
        expected_paths=sorted(manifest),
    )
    authoritative_changes = _merge_declared_risk_constraints(measured, changes)
    local_risk = classify_changes(authoritative_changes)
    if local_risk["route"] == "block":
        raise DeliveryBlocked(
            "실제 Git diff의 금지 위험 때문에 stage·commit 전에 publish를 차단함"
        )
    if transition_validation is not None and local_risk["route"] != "review":
        raise DeliveryBlocked("정책 활성화 diff가 사람 검토 경로로 분류되지 않음")
    if not resume_owned_commit:
        manifest = _reconcile_post_gate_manifest(
            manifest,
            post_gate_actual,
            root=root,
        )

    # prefix가 없는 legacy classic PAT도 Git object 생성 전에 정확한 값으로 찾는다.
    try:
        preflight_token = token_loader()
    except Exception:
        raise DeliveryBlocked("GitHub 자격증명 사전 검사를 안전하게 수행하지 못함") from None
    if not isinstance(preflight_token, str) or not preflight_token:
        raise DeliveryBlocked("GitHub 자격증명 사전 검사 값이 비어 있거나 잘못됨")
    exact_secret_found = _exact_secret_in_publish_material(
        preflight_token,
        root=root,
        runner=runner,
        base_sha=base_sha,
        context=context,
        changes=authoritative_changes,
    )
    preflight_token = None
    if exact_secret_found:
        raise DeliveryBlocked("실제 GitHub token이 공개 후보에 포함되어 publish를 차단함")

    expected_statuses = _expected_status_map(authoritative_changes)
    if resume_owned_commit:
        head_sha = current_head
    else:
        for path in sorted(manifest):
            _command(
                runner,
                ("git", "add", "--", path),
                cwd=root,
                purpose=f"manifest 경로 stage: {path}",
            )
        staged = _command(
            runner,
            ("git", "diff", "--cached", "--quiet", "--exit-code"),
            cwd=root,
            allowed=(0, 1),
            purpose="staged diff 확인",
        )
        if getattr(staged, "returncode", None) != 1:
            raise DeliveryBlocked("명시 manifest를 stage한 뒤 변경이 없음")
        _verify_git_diff_scope(
            root,
            runner,
            expected=expected_statuses,
            revisions=(base_sha,),
            cached=True,
            purpose="staged diff 재검증",
        )
        unstaged = _command(
            runner,
            ("git", "diff", "--quiet", "--exit-code", "--"),
            cwd=root,
            allowed=(0, 1),
            purpose="stage 이후 미포함 수정 확인",
        )
        if getattr(unstaged, "returncode", None) != 0:
            raise DeliveryBlocked("stage 이후 manifest 파일에 미포함 수정이 남아 있음")
        _assert_worktree_scope(
            authoritative_changes,
            root=root,
            runner=runner,
            base_sha=base_sha,
        )

        commit_message = f"[위키 자동화] {context.get('work_type', '위생')} — {run_id}"
        trailers = (
            f"Wiki-Run-ID: {run_id}\n"
            f"Wiki-Actor: {actor}\n"
            f"Wiki-Gate-Digest: {gate_digest}"
        )
        _command(
            runner,
            ("git", "commit", "-m", commit_message, "-m", trailers),
            cwd=root,
            purpose="자동 Wiki 변경 commit",
        )
        head_sha = _rev_parse(root, runner, "HEAD")
    tree_sha = _rev_parse(root, runner, "HEAD^{tree}")
    _verify_git_diff_scope(
        root,
        runner,
        expected=expected_statuses,
        revisions=(base_sha, head_sha),
        purpose="commit diff 재검증",
    )
    if _git_status(root, runner):
        raise DeliveryBlocked("commit 뒤 Git 작업 사본이 깨끗하지 않음")

    request = dict(context)
    request.update(
        {
            "base_sha": base_sha,
            "head_sha": head_sha,
            "tree_sha": tree_sha,
            "branch": branch,
            "local_gates": gates,
            "gate_digest": gate_digest,
            "changes": authoritative_changes,
        }
    )
    delivery_transport = (
        transport
        if isinstance(transport, GitHubCliTransport)
        else _LocalBranchTransport(transport, runner=runner, repo_root=root)
    )
    if transition_proof is not None:
        delivery = _deliver_guarded(
            request,
            transport=delivery_transport,
            token_loader=token_loader,
            prior_receipt=prior_delivery_receipt,
            active_policy_version=str(
                transition_proof.get("to_policy_version", "")
            ),
            validated_transition=transition_proof,
            reconciliation_only=base_drifted,
        )
    else:
        delivery = _deliver_guarded(
            request,
            transport=delivery_transport,
            token_loader=token_loader,
            prior_receipt=prior_delivery_receipt,
            active_policy_version=base_active_policy,
            validated_transition=None,
            reconciliation_only=base_drifted,
        )
    public_receipt = dict(delivery)
    public_receipt.update(
        {
            "schema_version": "github-delivery-receipt/v1",
            "run_id": run_id,
            "actor": actor,
            "base_sha": request["base_sha"],
            "head_sha": head_sha,
            "tree_sha": tree_sha,
            "gate_digest": gate_digest,
            "completed_at": gate_timestamp,
        }
    )
    if transition_proof is not None:
        public_receipt.update(
            {
                "begin_policy_version": transition_proof.get(
                    "from_policy_version"
                ),
                "target_policy_version": transition_proof.get(
                    "to_policy_version"
                ),
                "base_policy_config_sha256": transition_proof.get(
                    "base_policy_config_sha256"
                ),
                "policy_transition": dict(transition_proof),
            }
        )
    _write_json_receipt(
        _delivery_receipt_path(root, run_id, runner=runner), public_receipt
    )
    return public_receipt


def publish_run(
    context: Mapping[str, Any],
    *,
    repo_root: Path | str,
    runner: Any,
    gate_runner: Any,
    transport: Any,
    token_loader: Any,
    now: str | None = None,
) -> dict[str, Any]:
    """저장소 공통 잠금 아래에서 한 publish 상태기계만 실행한다."""

    if not isinstance(context, Mapping):
        raise DeliveryBlocked("publish context 형식이 올바르지 않음")
    validate_target(
        repository=context.get("repository"),
        base_branch=context.get("base_branch"),
        approval_id=context.get("approval_id"),
    )
    if _transition_requested(context):
        _validate_transition_entry_context(context, phase="publish")
    else:
        _validate_policy_context(
            context,
            active_policy_version=str(context.get("policy_version", "")),
        )
    root = Path(repo_root).resolve()
    _validate_origin_identity(root, runner)
    lock_handle = _acquire_publish_lock(root, runner)
    try:
        return _publish_run_unlocked(
            context,
            repo_root=root,
            runner=runner,
            gate_runner=gate_runner,
            transport=transport,
            token_loader=token_loader,
            now=now,
        )
    finally:
        _release_publish_lock(lock_handle)


def _conservative_changes(status: str) -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "status": change_status,
            "generated": False,
            "semantic_change": None,
        }
        for path, change_status in sorted(_parse_status(status).items())
    ]


def _context_from_current_receipt(root: Path, runner: Any) -> dict[str, Any]:
    branch = _current_branch(root, runner)
    matches = []
    directory = _delivery_state_dir(root, runner)
    for path in sorted(directory.glob("*.begin.json")) if directory.is_dir() else []:
        try:
            receipt = _read_json_object(path, purpose="begin 영수증")
        except DeliveryBlocked:
            continue
        if receipt.get("branch") == branch:
            matches.append(receipt)
    if len(matches) != 1:
        raise DeliveryBlocked("현재 브랜치의 begin 영수증을 단일하게 찾지 못함")
    receipt = matches[0]
    context = {
        "repository": receipt.get("repository"),
        "base_branch": receipt.get("base_branch"),
        "approval_id": receipt.get("approval_id"),
        "policy_version": receipt.get("policy_version", POLICY_VERSION),
        "run_id": receipt.get("run_id"),
        "actor": receipt.get("actor", "agent:codex"),
        "invocation": receipt.get("invocation", "수동"),
        "work_type": receipt.get("work_type", "위생"),
        "wiki_mode": receipt.get("wiki_mode", "wiki-first"),
        "rfc_ids": receipt.get("rfc_ids", ["RFC-03F4FE85BB44"]),
        "approval_refs": receipt.get("approval_refs", [EXPECTED_APPROVAL_ID]),
        "epistemic_impact": "자동 추론 없음 — 사람이 최종 diff를 검토해야 함",
        "unresolved": ["자동 생성·비의미 변경임을 manifest 없이 증명하지 못함"],
        "rollback": "새 revert PR로 되돌린다.",
    }
    if receipt.get("target_policy_version") is not None:
        context["target_policy_version"] = receipt.get("target_policy_version")
        context["policy_transition"] = receipt.get("policy_transition")
    context["changes"] = inspect_actual_changes(
        repo_root=root,
        runner=runner,
        base_sha=str(receipt.get("base_sha", "")),
    )
    return context


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Living Wiki 변경을 GitHub PR로 감사 가능하게 전달한다."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    begin = subparsers.add_parser("begin", help="깨끗한 main에서 실행을 시작한다.")
    begin.add_argument("--repo-root", default=".")
    begin.add_argument("--run-id")
    begin.add_argument("--actor", default="agent:codex")
    begin.add_argument("--invocation", default="수동")
    begin.add_argument("--work-type", default="위생")
    begin.add_argument("--wiki-mode", default="wiki-first")
    begin.add_argument("--target-policy-version")
    begin.add_argument("--now")

    publish = subparsers.add_parser("publish", help="검증 후 PR로 전달한다.")
    publish.add_argument("--repo-root", default=".")
    publish.add_argument("--manifest")
    publish.add_argument("--run-id")
    publish.add_argument("--now")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Any | None = None,
    gate_runner: Any | None = None,
    transport: Any | None = None,
    token_loader: Any | None = None,
    stdout: Any | None = None,
    now: str | None = None,
) -> int:
    """``begin``과 ``publish`` CLI를 dependency-injection 가능하게 dispatch한다."""

    args = _parser().parse_args(list(argv) if argv is not None else None)
    command_runner = runner or SubprocessRunner()
    output = stdout or sys.stdout
    timestamp = now or getattr(args, "now", None) or _now_iso8601()
    root = Path(args.repo_root).resolve()
    try:
        if args.command == "begin":
            run_id = args.run_id or _run_id_from_now(timestamp)
            policy_document = _worktree_policy_config_document(
                root, required=False
            )
            active_policy_version = (
                _policy_version_from_document(policy_document)
                if policy_document is not None
                else POLICY_VERSION
            )
            transition_requested = args.target_policy_version is not None
            context = {
                "repository": EXPECTED_REPOSITORY,
                "base_branch": EXPECTED_BASE_BRANCH,
                "approval_id": EXPECTED_APPROVAL_ID,
                "policy_version": active_policy_version,
                "run_id": run_id,
                "actor": args.actor,
                "invocation": args.invocation,
                "work_type": args.work_type,
                "wiki_mode": args.wiki_mode,
                "rfc_ids": (
                    [REQUIRED_DELIVERY_RFC, POLICY_TRANSITION_RFC]
                    if transition_requested
                    else [REQUIRED_DELIVERY_RFC]
                ),
                "approval_refs": (
                    [EXPECTED_APPROVAL_ID, POLICY_TRANSITION_APPROVAL]
                    if transition_requested
                    else [EXPECTED_APPROVAL_ID]
                ),
            }
            if transition_requested:
                context["target_policy_version"] = args.target_policy_version
            receipt = begin_run(
                context,
                repo_root=root,
                runner=command_runner,
                now=timestamp,
            )
        else:
            if args.manifest:
                context = _read_json_object(
                    Path(args.manifest), purpose="publish manifest"
                )
            else:
                context = _context_from_current_receipt(root, command_runner)
                if args.run_id and context.get("run_id") != args.run_id:
                    raise DeliveryBlocked("지정한 실행 ID와 현재 브랜치 영수증이 다름")
            selected_transport = transport or GitHubCliTransport(
                runner=command_runner,
                repo_root=root,
            )
            selected_loader = token_loader or (
                lambda: load_token(
                    root / "auth" / "github_token.yaml",
                    repo_root=root,
                )
            )
            receipt = publish_run(
                context,
                repo_root=root,
                runner=command_runner,
                gate_runner=gate_runner or command_runner,
                transport=selected_transport,
                token_loader=selected_loader,
                now=timestamp,
            )
    except GitHubDeliveryError as exc:
        output.write(
            json.dumps(
                {"status": "blocked", "reason": redact(str(exc))},
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )
        return 2
    output.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
    return 2 if receipt.get("status") == "blocked" else 0


__all__ = [
    "DeliveryBlocked",
    "GitHubDeliveryError",
    "GitHubCliTransport",
    "GitProbe",
    "SubprocessRunner",
    "TokenSafetyError",
    "TransportError",
    "begin_run",
    "build_policy_transition_proof",
    "build_pr_body",
    "classify_changes",
    "deliver",
    "idempotency_key",
    "inspect_actual_changes",
    "load_token",
    "main",
    "publish_run",
    "quality_gate_commands",
    "redact",
    "validate_target",
    "validate_policy_transition_activation",
]


if __name__ == "__main__":
    raise SystemExit(main())
