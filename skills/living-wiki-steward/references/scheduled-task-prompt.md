# 예약 작업 프롬프트

이 프롬프트를 Living Wiki 프로젝트의 독립 실행 일일 Codex 예약 작업으로 설정한다. 기본 일정은 `Asia/Seoul` 매일 20:00이며 고급 반복 규칙은 `RRULE:FREQ=DAILY;BYHOUR=20;BYMINUTE=0`이다. Codex 화면의 다음 실행 시각이 실제 KST 20:00인지 확인한다. 지속 변경을 반영할 때는 사람이 편집하지 않는 전용 로컬 자동화 checkout을 사용한다.

```text
현재 Living Wiki 프로젝트에서 $living-wiki-steward를 독립 실행하라. 호출 방식은 예약이고 Wiki 의존도 정책은 `wiki-first`다.

이 프로젝트는 예약 전용 로컬 checkout이어야 한다. 실질 작업 전에 현재 branch와 Git 상태를 확인하라. dirty, detached HEAD 또는 안전하게 설명할 수 없는 diverged 상태면 reset, stash, clean, force checkout으로 덮지 말고 차단 요소를 보고하라. 깨끗한 이전 `wiki-auto/` 실행 branch라면 `main`으로 전환하고, `origin/main`을 fetch한 뒤 fast-forward-only로 최신화하라. 그 다음에만 아래 GitHub `begin`을 호출하라.

현재 색인, SPEC-LWS-001과 SPEC-GH-DELIVERY-001을 읽어라. 시간대가 포함된 같은 <NOW>를 실행 전체에 사용하고, 작업 전에 GitHub 실행 시작을 다음 명령으로 수행하라.

python3 tools/github_delivery.py begin --now <NOW> --invocation 예약 --work-type <작업 종류> --wiki-mode wiki-first

먼저 위생 작업을 실행하라. 다음으로 도래한 관심사를 캠페인으로 만들고, 대기 중인 캠페인이 있으면 도래한 캠페인 하나, 즉 최대 하나만 진행하라. 시점이 된 연구가 없으면 연구를 만들지 마라. 출처 입수 심사, 보안 검사, 반증 검색, 정확한 증거 위치, 캠페인 예산, RFC로 통제되는 하네스 개선과 모든 자동 신뢰 승격 금지 규칙을 보존하라.

지역 날짜와 하루 캠페인 상한은 `config/wiki.json`과 `config/interests.json`을 따른다. `Wiki 하네스 연구`와 `Agent/Training 논문 연구` 두 프로젝트를 합쳐 하루 캠페인 최대 하나만 만들고 공정하게 순환하라. 선택된 캠페인의 `project_id`와 `research_brief`를 먼저 읽고 목표·제약·단계별 산출물·성공 기준을 지켜라. 프로젝트별 Wiki 뷰를 유지하되 출처와 주장은 전역 원장을 공유하고 복제하거나 중복 증거로 세지 마라. Agent/Training 논문화 트랙에서는 Apple M4·16GB에서 재현 가능한 실험만 실행하고, ChatGPT·Codex 구독을 API credit으로 간주하지 마라. 유료 API·새 자격증명·비용 증가는 별도 사람 승인이 없으면 계획에서 멈춰라.

권한을 확장하지 말고, SPEC-GH-DELIVERY-001의 정확한 저장소·승인·토큰 안전 계약을 통과한 PR 전달 외에는 자격증명을 사용하거나 외부에 공개하지 마라. 원문 증거를 삭제하거나 승인되지 않은 하네스·정책·Skill 변경을 구현하지 마라. 권한, 모호함, 동시 편집 또는 검증 때문에 단계가 차단되면 대화형 확인을 기다리지 말고 안전한 로컬 근거와 차단 요소를 보존하라.

모든 변경을 전체 품질 게이트로 검증한 뒤 실제 변경이 있을 때만 다음 명령을 수행하라.

GitHub 전달 명령: python3 tools/github_delivery.py publish --now <NOW>

`검증 → GitHub 전달 → 차이 보고` 순서를 지켜라. 위험이 낮은 변경만 필수 check와 SHA 일치 뒤 squash auto-merge 후보로 전달하라. `사람 검토 필요` 변경은 검토 이유, 영향, 검증법, 미해결 항목과 롤백을 한국어로 적은 draft PR만 만들고 자동화가 approve·ready·merge하지 마라.

예약 작업 받은 편지함에는 중요한 변경, 검증 상태, 미해결 모순·불확실성, 사용 예산, PR URL과 병합 영수증 또는 전달 차단 원인, 다음 정보 이득이 가장 큰 질문만 반환하라. 실질적으로 바뀐 것이 없으면 token을 읽거나 branch, commit이나 PR을 만들지 말고 "중요한 변경 없음"이라고 보고하라.
```

예약을 활성화하기 전에 의도한 샌드박스, 네트워크, 모델과 추론 설정으로 위키 프로젝트에서 이 프롬프트를 한 번 수동 실행한다. 예약 작업 받은 편지함에서 최초 몇 차례의 예약 실행을 검토한다.
