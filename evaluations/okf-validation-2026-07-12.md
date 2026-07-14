# OKF 검증 — 2026-07-12

## 범위

- 번들 경계: `wiki/`
- 고정 형식: Open Knowledge Format v0.1 Draft
- 생산자 프로필: Living Wiki v4
- 번들 밖 제어면: JSON 원장, 원문·격리 자료, 영수증, 평가 자료, 도구, 비밀

## 결과

- OKF 개념 문서: 92
- 핵심 오류·경고: 0 / 0
- Living Wiki 프로필 오류·경고: 0 / 0
- 상태 투영 일치성: 출처 35, 주장 26, 행위자 2, 검토 0, 캠페인 5, RFC 1, 협업 1, 입수 1, 실행 1

명령:

```bash
/opt/homebrew/bin/python3.13 tools/wiki.py render --actor agent:codex
/opt/homebrew/bin/python3.13 tools/wiki.py okf-validate
/opt/homebrew/bin/python3.13 tools/wiki.py validate
```

이는 형식, 링크, 필수 메타데이터, 사건·상태 불변식, 투영 일치성을 검증한다. 주장의 진실성이나 외부 콘텐츠의 안전성을 인증하지는 않는다.
