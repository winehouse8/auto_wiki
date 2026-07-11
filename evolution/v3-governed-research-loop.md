# v3 — Governed autonomous research loop

## 현재 구조

```text
human/agent interests and leads
  → bounded campaign
  → discovery ladder + counter-search
  → immutable snapshot / quarantine
  → source assessment + independence clustering
  → atomic claim/evidence admission
  → independent/adversarial review
  → scoped synthesis patch
  → deterministic validation + factual regression eval
  → low-risk merge OR governance RFC
  → next gap
```

## v3에 구현한 것

- `config/interests.json`: 관심 분야와 관찰 주기
- campaign queue: 예산·독립 출처·종료 조건
- `AGENTS.md`와 `prompts/research-cycle.md`: provider-neutral 운영 프로토콜
- deterministic CLI: actor/source/claim/evidence/review/campaign/proposal
- source와 claim 신뢰 레벨의 gate-based 계산
- raw SHA-256 검사와 event hash chain 검사
- 사람이 읽는 index·epistemic dashboard 자동 생성
- lint, unit tests, release checklist, content-addressed snapshot
- 하네스 변경 자동 적용 금지와 RFC 템플릿

## 아직 증명하지 못한 것

- 장기 운영에서 C0–C4가 실제 정확도와 잘 보정되는지
- 주기적 연구가 인간의 정보 이득을 늘리고 중복을 줄이는지
- writer/reviewer 모델 다양성이 오류 상관을 실제로 낮추는지
- 1만 개 이상의 claim에서 파일형 상태가 충분한지
- prompt injection 및 multimodal poisoning 방어가 실제 공격에서 견디는지
- 동시 인간/Agent 편집의 semantic conflict 해결

## v4 승격 금지 조건

운영 사례와 benchmark 없이 vector DB, multi-agent jury, 자동 source scoring, 완전 무인 self-modification을 추가하지 않는다. v4는 `governance/proposals/` RFC와 회귀평가가 모두 있어야 한다.

