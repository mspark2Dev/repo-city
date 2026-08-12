# epoCity

코드베이스를 날아다닐 수 있는 도시로 바꾸고, 망가진 구역에 에이전트를 보내 정리시키는 도구.

epoCity 는 리포지토리를 정적 분석해 3D 도시로 렌더링한다. 건물 하나가 파일 하나이고, 코드 라인 수만큼
높아지며, 순환 복잡도가 높을수록 녹슬고 붉게 빛난다. 손봐야 할 코드가 가장 먼저 눈에 들어오게 만드는 것이
목적이다. 거기에 로컬 LLM 을 붙여 리팩토링을 제안받는다.

> **상태: pre-alpha.** 설계는 확정됐고 Phase 1 을 구현 중이다. 아직 실행할 수 있는 것은 없다.
> 진행 상황은 [docs/ROADMAP.md](docs/ROADMAP.md) 참고.

## 아이디어

| 보이는 것 | 의미 |
|---|---|
| 구역 | 디렉토리 |
| 건물 | 파일 |
| 건물 높이 | 코드 라인 수 |
| 녹슨 콘크리트, 붉은 발광, 연기 | 높은 순환 복잡도 |
| 깨끗한 유리, 푸른 네온 | 낮은 복잡도 |
| 건물 사이를 잇는 빛나는 곡선 | import |
| 굵고 붉게 얽힌 선 | 순환 의존 |

건물을 클릭하면 메트릭과 원본 코드가 열린다. 하단 커맨드바에 *"이 파일에서 가장 복잡한 함수를 쪼개줘"*
같은 명령을 넣으면, 에이전트가 해당 파일과 직접 의존 코드를 읽고 diff 를 제안한다. 적용을 누르면 그 건물이
무너지고 리팩토링 결과대로 다시 솟아오른다.

## 구조

```
apps/web            React Three Fiber 캔버스 + Monaco 인스펙터 + 커맨드바
services/analyzer   Python: tree-sitter 파싱, 메트릭, import 그래프, treemap 레이아웃
                    FastAPI REST + WebSocket, 에이전트 런타임
LLM                 OpenAI 호환 엔드포인트 (vLLM, Ollama, LM Studio)
```

분석기는 `CityMap.json` 을 만든다. 결정론적이고 ID 가 안정적인 도시 기술서다. ID 안정성이 리팩토링
애니메이션을 의미 있게 만든다 — 파일이 바뀌면 그 건물만 바뀌고 나머지 도시는 그대로 있는다.

설계 결정과 그 근거는 [docs/DESIGN.md](docs/DESIGN.md) 에 있다.

## 안전장치

에이전트는 파일을 직접 쓰지 않는다. unified diff 를 만들고, 결과가 문법적으로 파싱되는지 검증한 뒤
사용자에게 보여준다. 명시적으로 적용해야만 파일이 쓰이고, 원본은 스냅샷으로 남아 되돌릴 수 있다.

## 요구사항

- Node.js 20+, pnpm
- Python 3.12+ ([uv](https://docs.astral.sh/uv/) 로 관리)
- 리팩토링 기능용 OpenAI 호환 LLM 엔드포인트 (선택 — 분석과 시각화는 없어도 동작)

## 문서

| | |
|---|---|
| [docs/OVERVIEW.md](docs/OVERVIEW.md) | 왜 만들었고 각 조각이 어떻게 맞물리는지 (영문) |
| [docs/DESIGN.md](docs/DESIGN.md) | 스키마, API, 시각 매핑 룰 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phase 별 계획과 수용 기준 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 개발 환경 세팅과 규약 (영문) |

## 라이선스

MIT — [LICENSE](LICENSE) 참고.
