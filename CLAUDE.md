# repoCity — 프로젝트 규칙

## 라이선스 · 공개
MIT 라이선스 공개 오픈소스다. 커밋 히스토리, 코드, 문서가 모두 외부에 노출된다는 전제로 작업한다.
사내 시스템 주소·계정·내부 전용 정보를 커밋에 넣지 않는다.

## 커밋
- 커밋 메시지에 `Co-Authored-By` 트레일러를 넣지 않는다.
- Conventional Commits 를 따른다: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- 한 커밋은 한 가지 일만 한다.
- 푸시와 브랜치 생성은 사람이 판단한다. 에이전트는 커밋까지만 하고 멈춘다.

## 문서
기능을 추가하면 관련 문서를 같은 변경에 포함한다.

| 문서 | 역할 |
|---|---|
| `README.md` | 무엇인지, 어떻게 돌리는지 |
| `docs/OVERVIEW.md` | 왜 이렇게 만들었는지, 전체 그림 |
| `docs/DESIGN.md` | 데이터 스키마, API, 매핑 룰 |
| `docs/ROADMAP.md` | Phase 별 계획과 수용 기준 |
| `CONTRIBUTING.md` | 개발 환경 세팅, PR 규약 |

## 코드
- 주석은 **왜**를 설명할 때만 쓴다. 코드가 이미 말하는 것을 반복하지 않는다.
- 자명한 함수에 docstring 을 채우려고 문장을 지어내지 않는다.
- 공개 API(`repocity/api/`, `schema.py`)와 비자명한 알고리즘(`layout.py`, `imports/`)에는
  의도와 제약을 남긴다.
- Python: 타입 힌트 필수, `ruff` + `ruff format`.
- TypeScript: `strict: true`, `any` 금지.
- CityMap 스키마의 단일 진실 공급원은 `services/analyzer/repocity/schema.py` 다.
  TS 타입은 생성물이므로 손으로 고치지 않는다.
