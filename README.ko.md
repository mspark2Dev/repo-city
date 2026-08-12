# repoCity

[![CI](https://github.com/mspark2Dev/repo-city/actions/workflows/ci.yml/badge.svg)](https://github.com/mspark2Dev/repo-city/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

코드베이스를 날아다닐 수 있는 도시로 바꾸고, 망가진 구역에 에이전트를 보내 정리시키는 도구.

repoCity 는 리포지토리를 정적 분석해 3D 도시로 렌더링한다. 건물 하나가 파일 하나이고, 코드 라인 수만큼
높아지며, 순환 복잡도가 높을수록 녹슬고 붉게 빛난다. 손봐야 할 코드가 가장 먼저 눈에 들어오게 만드는 것이
목적이다. 거기에 로컬 LLM 을 붙여 리팩토링을 제안받는다.

![파이썬 의존성 트리를 도시로 렌더링한 모습](docs/images/city.png)

> **상태: pre-alpha 이지만 전 과정이 동작한다.** 리포지토리를 분석해 도시를 날아다니고, 파일을
> 에이전트에 넘기고, diff 를 검토해 적용하면 그 건물이 무너지고 다시 솟아오른다.
> 각 Phase 의 결과는 [docs/ROADMAP.md](docs/ROADMAP.md) 참고.

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

건물을 클릭하면 메트릭과 원본 코드가 열린다.

![복잡도가 높은 파일을 들여다보는 화면](docs/images/inspect.png)

하단 커맨드바에 *"이 파일에서 가장 복잡한 함수를 쪼개줘"* 같은 명령을 넣으면, 에이전트가 해당 파일과
직접 의존 코드를 읽고 diff 를 제안한다.

![에이전트가 제안한 리팩토링 diff](docs/images/agent.png)

적용을 누르면 그 건물이 무너지고 리팩토링 결과대로 다시 솟아오르며, 전후 수치를 나란히 보여준다.

![변경 후 도시와 전후 비교표](docs/images/after.png)

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

## 시작하기

```bash
pnpm install

# 터미널 1 — 분석기
cd services/analyzer && uv sync && uv run uvicorn repocity.app:app --port 8787

# 터미널 2 — 웹
pnpm dev            # http://localhost:5173
```

좌측 상단 입력창은 **로컬 경로와 git URL 을 모두** 받는다:

```
/path/to/your/project
https://github.com/owner/repo.git
git@gitlab.example.com:group/repo.git
```

브랜치를 지정하지 않으면 원격의 기본 브랜치를 가져온다(main 이든 master 든). 다른 것을 보려면
`#브랜치` 를 붙이거나 브랜치 페이지 주소를 그대로 붙여넣는다:

```
https://github.com/owner/repo.git#develop
https://github.com/owner/repo/tree/release-2.0
https://github.com/owner/repo/tree/main/packages/core   # 그 하위 디렉터리만
https://gitlab.example.com/group/repo/-/tree/staging
```

태그도 브랜치와 동일하게 쓸 수 있다. ref 마다 별도 체크아웃이라 브랜치를 오가도 서로 영향이 없다.

원격 리포지토리는 `~/.local/share/repocity/clones/` 에 shallow clone 된다. 이미 클론된 것이
있으면 다시 받지 않고 재사용하므로, 거기에 적용한 변경이 날아가지 않는다. 비공개 리포는 git 이
이미 가진 자격증명을 쓰며, repoCity 가 별도로 묻지 않는다.

UI 없이 쓰려면:

```bash
cd services/analyzer
uv run repocity analyze ../../fixtures/sample-project --stats -o citymap.json
```

`fixtures/sample-project` 는 순환 의존 한 쌍과 복잡도가 아주 높은 함수 하나를 일부러 심어둔
작은 파이썬 프로젝트다. 자기 코드에 들이대기 전에 그런 것들이 도시에서 어떻게 보이는지
확인할 수 있다.

## 언어

인터페이스는 영어와 한국어를 지원한다. 첫 방문 시 브라우저 언어 설정을 보고 고르고, 우측 상단
토글로 바꾸면 그 선택을 기억한다. 메시지 카탈로그의 기준은 영어이고 `Messages` 타입이 거기서
파생되므로, 한국어에 키가 빠지면 조용히 영어로 새는 대신 **컴파일 에러**가 난다.

## 다른 머신에서 접근

개발 서버는 localhost 에 바인딩된다. Tailscale 같은 VPN 을 통해 다른 머신에서 쓰려면 해당
인터페이스에 바인딩하고 사용할 호스트 이름을 명시한다:

```bash
REPOCITY_WEB_HOST=100.x.y.z \
REPOCITY_ALLOWED_HOSTS=myhost,myhost.example.ts.net \
pnpm dev
```

**웹 서버만 열면 된다.** `/api` 와 `/ws` 를 서버 사이드에서 프록시하므로 분석기는 루프백에
그대로 둔다. 분석기 자체를 노출하지 말 것.

`0.0.0.0` 대신 특정 인터페이스에 바인딩한다. 이 서버에 닿을 수 있는 사람은 이 머신이 읽을 수
있는 모든 경로를 분석할 수 있고, 에이전트가 설정돼 있으면 쓸 수도 있다. 사설 VPN 인터페이스는
납득할 만한 위치지만 LAN 이나 인터넷은 아니다.

## 에이전트 사용

`.env` 의 `LLM_BASE_URL` 을 OpenAI 호환 엔드포인트로 지정한다:

```env
LLM_BASE_URL=http://<host>:<port>/v1
LLM_MODEL=<해당 서버가 서빙하는 모델>
LLM_CONTEXT_BUDGET=60000
```

건물을 고르고 하단 커맨드바에 명령을 넣은 뒤 diff 를 읽고 결정한다. Apply 를 누르기 전까지
아무것도 쓰이지 않고, 원본은 리포지토리 바깥에 스냅샷으로 남으며, Revert 는 바이트 단위로 되돌린다.

## 지원 언어

| | |
|---|---|
| 크기·복잡도·함수 **+ 의존 그래프** | Python, TypeScript, JavaScript, Java, Kotlin, C, C++ |
| 크기·복잡도·함수 | Go, Rust, C#, Ruby, PHP, Swift, Scala, Objective-C, Lua, Perl, R, Erlang, Fortran, Solidity, Zig, Vue, GDScript, PL/SQL, Smalltalk, TTCN |
| 라인 수만 | 읽을 수 있는 나머지 |

복잡도는 [lizard](https://github.com/terryyin/lizard) 가 측정하며 위 언어를 모두 읽는다.
의존 그래프는 언어별 모듈 규칙을 따로 구현해야 해서 첫 목록이 더 짧다. 패널이 import 해석률을
표시하므로 그 차이는 숨겨지지 않고 드러난다.

## 요구사항

- Node.js 22.13+ (pnpm 11 의 요구사항), pnpm 11+
- Python 3.12+ ([uv](https://docs.astral.sh/uv/) 로 관리)
- 리팩토링 기능용 OpenAI 호환 LLM 엔드포인트 (선택 — 분석과 시각화는 없어도 동작)

## 문서

| | |
|---|---|
| [docs/OVERVIEW.md](docs/OVERVIEW.md) | 왜 만들었고 각 조각이 어떻게 맞물리는지 (영문) |
| [docs/DESIGN.md](docs/DESIGN.md) | 스키마, API, 시각 매핑 룰 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phase 별 계획과 수용 기준 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 개발 환경 세팅과 규약 (영문) |

## 보안

repoCity 는 지정한 디렉토리를 읽고, 에이전트를 쓰면 대상 파일을 설정된 모델 엔드포인트로 보낸다.
그 의미와 취약점 신고 방법은 [SECURITY.md](SECURITY.md) 참고. (영문)

## 라이선스

MIT — [LICENSE](LICENSE) 참고.
