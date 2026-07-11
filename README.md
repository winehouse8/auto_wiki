# Living Wiki v3.1

사람과 Agent가 같은 종류의 **기여 행위자(actor)** 로 참여하고, Agent가 일상적인 조사·정리·검증·합성을 수행하는 로컬 우선 연구 위키입니다. 현재 하네스는 두 차례의 자체 비판을 거친 v3에 OKF 상호운용성을 추가한 v3.1이며, `evolution/`에 변경 근거가 남아 있습니다.

이 위키의 핵심은 문서 수가 아니라 다음 네 가지입니다.

1. 원문은 불변으로 보존합니다.
2. 사실 후보는 원자적 주장으로 분해하고 출처의 정확한 위치와 연결합니다.
3. 출처의 평판과 메시지의 증거력을 따로 평가합니다.
4. 합성 문서는 언제든 재생성 가능한 파생물로 취급합니다.

## 5분 시작

```bash
python3 tools/wiki.py status
python3 tools/wiki.py next-task
python3 tools/wiki.py okf-validate
python3 tools/wiki.py validate
python3 -m unittest discover -s tests -v
```

새 관심 분야는 `config/interests.json`에 추가합니다. 사람이 링크나 아이디어를 던질 때는 `python3 tools/wiki.py campaign-add ...`로 연구 큐에 넣거나 `research/inbox.md`에 기록합니다. Agent는 `AGENTS.md`와 `prompts/research-cycle.md`를 읽고 한 사이클씩 실행합니다.

## 중요한 구분

- **행위자 동등성**: 사람/Agent 모두 같은 스키마로 제안·기여·검토하고 기여 이력이 남습니다.
- **권한 동일성은 아님**: 권한은 종(species)이 아니라 역할·위험·책임 범위에 따라 부여됩니다. 삭제, 정책 변경, 외부 공개, 비용 증가 같은 고위험 작업은 승인이 필요합니다.
- **신뢰도는 진실 확률이 아님**: C0–C4는 현재 확보한 증거의 성숙도입니다. 반증이 생기면 언제든 내려갑니다.
- **출처 등급은 면죄부가 아님**: S4 출처도 범위를 벗어난 주장에는 약한 증거일 수 있고, S1 출처도 새로운 탐색 단서가 될 수 있습니다.

## 구조

```text
raw/                 불변 원문 또는 원문 스냅샷
state/               행위자·출처·주장·검토·캠페인의 기계 가독 원장
wiki/                OKF v0.1 호환 지식 bundle (교환·읽기용)
research/            관심 분야, 큐, 캠페인, 조사 메모
governance/          헌장, 결정, 하네스 변경 제안
evaluations/         품질 게이트와 회귀평가
evolution/           v1→v2→v3.1 진화 기록
reports/             lint·상태·연구 보고서
tools/wiki.py         의존성 없는 결정론적 CLI
```

자세한 설계와 비판적 자료 분석은 [docs/SELF_EVOLVING_WIKI_REPORT.md](docs/SELF_EVOLVING_WIKI_REPORT.md)를 참고하세요.

## 지속 실행

현재 하네스는 특정 모델이나 스케줄러에 종속되지 않습니다. `wiki/`만 떼어내도 [Open Knowledge Format v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) bundle로 소비할 수 있고, 그 밖의 JSON 원장과 도구는 더 강한 provenance·governance를 제공하는 control plane입니다. `scripts/research-cycle.sh`가 다음 연구 과제와 실행 프롬프트를 출력하고, cron·CI·로컬 Agent runner가 그 프롬프트를 Agent에게 전달합니다. 무인 실행에서도 수집과 초안은 허용하지만, 헌장·신뢰 정책·삭제·외부 공개 변경은 제안 파일만 만들도록 제한합니다.
