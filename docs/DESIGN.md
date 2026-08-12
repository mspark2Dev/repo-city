# repoCity — 설계 문서 (v0.1)

> 최초 아이디어 스케치를 구현 가능한 규격으로 확정한 문서다.
> 스케치와 달라진 결정은 각 절의 **[결정]** 항목에 근거와 함께 적는다.

---

## 0. 한 줄 정의

로컬 코드베이스를 정적 분석해 **도시(city)** 로 렌더링하고, 문제 있는 건물(파일)을 골라
**LLM 에이전트에게 리팩토링을 시켜 diff 를 받아보고**, 적용하면 도시가 그 자리에서 변형되는 도구.

## 1. 아키텍처 개요

```
┌──────────────────────────── apps/web (Vite + React 19 + R3F) ────────────────────────────┐
│  CityCanvas(70%)          │ Inspector/Editor(30%)      │ CommandBar(하단 플로팅)          │
│   InstancedMesh 도시       │  metrics + Monaco diff     │  자연어 명령                     │
└───────────▲──────────────────────────▲───────────────────────────▲──────────────────────┘
            │ CityMap.json / delta      │ REST                      │ WS(token stream)
┌───────────┴───────────────────────────┴───────────────────────────┴──────────────────────┐
│ services/analyzer (Python 3.12 + FastAPI)                                                │
│  ┌─ scan ─┐ ┌─ parse(tree-sitter) ─┐ ┌─ metrics ─┐ ┌─ resolve imports ─┐ ┌─ layout ─┐    │
│  │ ignore │→│  AST per file        │→│ LOC/CC/sym│→│ 파일→파일 그래프   │→│ treemap  │    │
│  └────────┘ └──────────────────────┘ └───────────┘ └───────────────────┘ └────┬─────┘    │
│                                                                        CityMap.json      │
│  ┌─ agent runtime ────────────────────────────────────────────────────────────────────┐  │
│  │ context builder(대상 파일 + 1-hop import) → LLMAdapter → unified diff → 검증 → 적용 │  │
│  └────────────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────▲───────────────────────────────────────────────────┘
                                       │ OpenAI 호환 /v1/chat/completions
                        ┌──────────────┴───────────────────────┐
                        │ vLLM 0.23.0 (OpenAI 호환)             │
                        │ Qwen3.6-27B (FP8), ctx 120k          │
                        │ APC on · tool_calls · json_schema    │
                        └──────────────────────────────────────┘
```

### [결정 1] 추론은 OpenAI 호환 엔드포인트로 추상화한다 (기준 배포 실측 완료)

최초 스케치는 "로컬 Qwen 30B / vLLM"이었으나, vLLM 은 macOS(Apple Silicon) 서빙을 지원하지
않으므로 개발 머신에 따라 성립하지 않는다. repoCity 는 특정 런타임에 묶이지 않고
**OpenAI 호환 `/v1/chat/completions` 를 말하는 아무 엔드포인트**(vLLM, Ollama, LM Studio)를
받는다. 주소는 `.env` 로만 주입하고 커밋하지 않는다.

아래는 이 프로젝트가 성능 목표의 기준으로 삼는 배포(reference deployment)의 실측값이다.

| 항목 | 실측값 |
|---|---|
| 서버 | vLLM 0.23.0, OpenAI 호환 |
| 모델 | `Qwen3.6-27B` (FP8, `/ThinkingCap-Qwen3.6-27B-FP8`) |
| 컨텍스트 | **120,000 토큰** |
| 디코딩 속도 | 25~64 tok/s (부하에 따라 변동) |
| TTFT (8k 프리필, 콜드) | **4.5s** |
| TTFT (프리필 캐시 히트) | **0.58s** — 7.8배 |
| tool calling | 지원 (네이티브 `tool_calls` 파싱) |
| `response_format: json_schema` | 지원 (guided decoding) |
| `reasoning` 필드 | 응답 스키마에 존재하나 기본 비활성 (`null`) — 파싱 불필요 |

`LLMAdapter` 가 이 추상화의 경계다. 원격 서버는 다운/혼잡할 수 있으므로 어댑터 뒤에서
로컬 런타임(Ollama 등)으로 폴백할 수 있어야 하고, LLM 이 없어도 분석·시각화는 동작해야 한다.

```env
LLM_BASE_URL=http://<vllm-host>:<port>/v1
LLM_MODEL=Qwen3.6-27B
LLM_API_KEY=dummy          # vLLM 은 키를 검사하지 않지만 OpenAI 클라이언트가 요구
LLM_MAX_CONTEXT=120000
LLM_CONTEXT_BUDGET=60000   # 프롬프트에 실제로 채울 상한
```

### [결정 1-a] 프롬프트는 "정적 → 동적" 순서로 조립한다 (프리필 캐시 활용)

서버에 **automatic prefix caching 이 켜져 있다.** 같은 접두사를 공유하면 프리필이 사실상 공짜다
(4.51s → 0.58s, 접두사가 같고 뒷부분만 달라도 동일하게 히트).

사용자는 한 파일을 붙잡고 명령을 여러 번 던진다("쪼개줘" → "이름 바꿔줘" → "타입 붙여줘").
따라서 프롬프트를 이 순서로 고정한다:

```
[1] 시스템 프롬프트 (불변)
[2] 대상 파일 원본 + 1-hop 의존 코드 (파일이 안 바뀌면 불변)
[3] 파일 메트릭 요약 (불변)
────────── 여기까지가 캐시되는 접두사 ──────────
[4] 사용자 명령 (매번 다름)
```

명령을 앞에 두는 순진한 조립은 매 요청마다 프리필을 다시 태워 **4초를 그냥 버린다.**
이 순서 규약은 `agent/context.py` 의 계약으로 못박고 테스트로 고정한다.

### [결정 2] 에이전트는 파일을 직접 쓰지 않는다 — diff 를 제안한다
사용자 소스코드를 LLM 이 무단으로 덮어쓰는 것은 되돌리기 어려운 파괴적 동작이다.
`POST /agent/refactor` 는 **unified diff 를 만들어 반환만** 하고, 실제 파일 쓰기는
사용자가 Monaco diff 뷰에서 확인한 뒤 `POST /agent/apply` 를 호출해야 일어난다.
적용 전 원본은 `.repocity/snapshots/<taskId>/` 에 보관되어 1-클릭 롤백이 가능하다.

---

## 2. 데이터 모델 — `CityMap.json`

단일 진실 공급원은 **Pydantic 모델**(`services/analyzer/repocity/schema.py`)이다.
거기서 JSON Schema 를 export 하고 `json-schema-to-typescript` 로 프론트 타입을 생성한다.
스키마가 갈라지는 사고를 구조적으로 막기 위함이다. (`pnpm gen:types`)

```jsonc
{
  "schemaVersion": "1.0",
  "projectId": "sha1(abs_root)[:12]",
  "root": "/abs/path/to/repo",
  "generatedAt": "2026-08-12T10:29:00Z",
  "stats": { "files": 812, "loc": 94211, "links": 1903, "unresolved": 47, "durationMs": 4120 },

  "districts": [{
    "id": "d:src/core",              // 안정 ID = 레포 상대경로
    "parentId": "d:src",
    "path": "src/core",
    "depth": 2,
    "rect": { "x": -40, "z": 12, "w": 30, "d": 22 },   // XZ 평면, 중심 기준 아님(좌상단 기준)
    "y": 0.8,                        // depth * 0.4 — 타일 위에 타일
    "fileCount": 31, "loc": 5120
  }],

  "buildings": [{
    "id": "f:src/core/parser.py",    // 안정 ID
    "districtId": "d:src/core",
    "path": "src/core/parser.py",
    "name": "parser.py",
    "lang": "python",
    "position": { "x": -38.5, "z": 14.0 },
    "footprint": { "w": 2.4, "d": 2.4 },
    "height": 11.3,
    "metrics": {
      "loc": 412, "sloc": 337, "comments": 41,
      "symbols": 18, "functions": 14, "classes": 2,
      "maxCC": 23, "avgCC": 4.1, "ccDensity": 0.17,
      "fanIn": 9, "fanOut": 4
    },
    "grade": "critical"              // clean | watch | hot | critical
  }],

  "links": [{
    "id": "l:src/a.py>src/b.py",
    "source": "f:src/a.py", "target": "f:src/b.py",
    "kind": "import", "weight": 3, "bidirectional": false
  }],

  "unresolved": [{ "from": "f:src/a.py", "spec": "numpy", "reason": "external" }]
}
```

### ID 안정성 계약 (중요)
ID 는 **배열 인덱스가 아니라 레포 상대경로**다. 리팩토링 후 재분석해도 같은 파일은 같은 ID 를
유지하므로 프론트에서 **delta 를 정확히 계산해 애니메이션**(기존 건물 폭파 → 신규 건물 상승)
할 수 있다. Phase 4 가 이 계약 위에 서 있다.

---

## 3. 시각화 매핑 룰 (확정값)

| 시각 요소 | 소스 메트릭 | 매핑 식 |
|---|---|---|
| 건물 높이 | LOC | `h = 0.5 + 11.5 * log1p(loc) / log1p(max(p95_loc, 400))`, 상한 12 |
| 건물 바닥 | symbols(함수+클래스 수) | `w = d = clamp(1.2 + 0.25*sqrt(symbols), 1.2, 6)` |
| 건물 색/재질 | `maxCC` (파일 내 최대 순환 복잡도) | 아래 등급표 |
| 구역 타일 | 디렉토리 | squarified treemap, `y = depth * 0.4` |
| 연결선 | import | 3차 베지어, 굵기 `1 + log2(weight)` |

**[결정 3] 높이는 LOC 에 선형이 아니라 로그다.** 선형이면 5000줄짜리 파일 하나가 화면을
독점해 나머지 도시가 보이지 않는다. 로그 정규화로 "거대한 마천루" 느낌은 유지하되 스케일이
붕괴하지 않게 한다.

정규화 기준은 p95 만이 아니라 `max(p95, 400)` 이다 (Phase 1 실측 후 수정). p95 만 쓰면 작고
균일한 프로젝트에서 모든 파일이 최대 높이에 붙어 스카이라인이 정보를 잃는다. 절대 기준을
섞으면 서로 다른 리포 사이에서도 높이를 비교할 수 있다는 이점이 따라온다.

**[결정 4] 복잡도는 평균이 아니라 파일 내 최대 CC 를 쓴다.** 400줄 중 1개 함수만 CC 40 인
파일이 진짜 위험한 파일이고, 평균을 쓰면 이게 희석돼 사라진다.

### 등급표 (grade)

| grade | 조건(maxCC) | 재질 | 색 | 이펙트 |
|---|---|---|---|---|
| `clean` | ≤ 5 | 유리(투과 + 약한 fresnel) | `#4EA8FF` 네온 | 없음 |
| `watch` | 6–10 | 매트 | `#FFC24E` | 없음 |
| `hot` | 11–20 | 거친 콘크리트 | `#FF7A3D` | 미세 그레인 |
| `critical` | > 20 | 녹슨 콘크리트 + 경고 셰이더(맥동) | `#FF3B30` | 먼지/연기 파티클 |

재질은 grade 별 InstancedMesh 에 하나씩 붙는다. `clean` 은 `MeshPhysicalMaterial` 의 transmission
으로 유리, 나머지는 roughness 를 올려 콘크리트로 간다. `critical` 은 `emissiveIntensity` 를
매 프레임 맥동시킨다.

**[결정 5] 파티클은 화면 내 `critical` 상위 N=12 개에만 붙인다.** 전 건물 파티클은
드로우콜을 폭발시킨다. 카메라 프러스텀 + 거리순 정렬로 매 프레임이 아니라 200ms 스로틀로 갱신.

### 연결선 렌더링 정책
전체 링크를 다 그리면 1900개 곡선이 헤어볼이 되어 아무 정보도 주지 못한다.
- 기본: **weight 상위 5% 만** 은은하게 표시
- 노드 hover/select: 해당 노드의 **1-hop 링크 전부** 를 강조 표시, 나머지는 dim
- 양방향(순환) 의존은 항상 표시 — 이건 찾아내야 할 결함이므로 붉고 두껍게.
  **튜브 지오메트리로 그린다**: WebGL 은 주요 플랫폼에서 `lineWidth` 를 무시하므로, 선으로 그리면
  "두껍게" 가 성립하지 않고 1px 로 나온다

---

## 4. 레이아웃 알고리즘

1. 파일 스캔 → 디렉토리 트리 구축 (`.gitignore` + 기본 제외 목록 적용)
2. 리프에서 위로 올라가며 각 디렉토리 **요구 면적** = Σ(자식 면적) × 1.25(여유분) + padding
3. 루트부터 **squarified treemap** 으로 XZ 사각형 분할 → district `rect`
4. district 내부는 **자기 파일 밴드**와 **하위 디렉토리 밴드**로 먼저 쪼갠 뒤 각각 squarify
5. 두 밴드 모두 **파일명 사전순 고정 배치**

**[결정 6-a] 파일과 하위 디렉토리를 같은 treemap 에서 경쟁시키지 않는다.** (Phase 1 실측 후 추가)
루트에 거대한 서브트리 하나와 `README.md` 가 같이 있으면, 면적 비례 분할은 README 에게 폭 0.13
짜리 조각을 준다. 파일을 별도 밴드로 분리하고, 그 밴드 두께가 최소한 가장 넓은 건물보다
`BAND_CLEARANCE` 배 두껍도록 구역을 키운다. 늘어난 면적은 하위 디렉토리의 slack 이 흡수한다.

구역 면적은 `(sqrt(자식 면적 합 × 1.25) + 2 × padding)²` 이다. padding 을 면적에 `padding²` 만
더하면 실제 inset 이 깎는 양(`2p(w+d) - 4p²`)에 못 미쳐, 중첩될수록 건물이 조각으로 눌린다.

**[결정 6] 건물 배치 순서는 크기순이 아니라 이름순이다.** 크기순 정렬이 패킹은 예쁘지만,
LOC 가 10줄 바뀌는 순간 도시 전체가 재배열된다. 그러면 "리팩토링 전후 비교"라는 이 도구의
핵심 가치가 사라진다. 이름순 + 25% 여유 면적을 두면, 파일이 추가/삭제되지 않는 한
리팩토링 후에도 건물은 **제자리에서 높이와 색만 바뀐다.**

---

## 5. 정적 분석 파이프라인

- **파서:** `tree-sitter` + `tree-sitter-language-pack` (언어별 빌드 불필요)
- **MVP 언어:** Python, TypeScript/TSX, JavaScript/JSX. 그 외 확장자는 LOC 만 집계하고
  `lang: "other"` 로 회색 건물 처리 (도시에서 사라지지 않게)
- **LOC:** 전체 라인 / `sloc`(주석·공백 제외) / 주석 라인 분리 집계.
  Python docstring 은 AST 로 찾아 주석으로 집계한다. `#` 만 세면 잘 문서화된 파이썬 파일이
  주석 0 으로 나온다
- **순환 복잡도:** AST 질의로 분기 노드 카운트 → `CC = 1 + Σ(분기)`
  분기 노드: `if/elif`, `for`, `while`, `case`, `catch/except`, `&&`, `||`, `??`, 삼항, `assert`
  언어별 노드 타입 매핑은 `metrics/cc_rules.json` 으로 외부화 (언어 추가가 코드 수정 없이 가능).
  `"binary_expression:&&"` 처럼 연산자까지 지정 가능
- **import 해석:**
  - Python: 상대 import 는 패키지 경로 기준, 절대 import 는 프로젝트 루트/`src` 루트 후보로 탐색
  - TS/JS: 상대경로 + `tsconfig.json`/`jsconfig.json` 의 `paths`/`baseUrl` 별칭 해석,
    확장자·index 후보 순회. tsconfig 는 주석과 trailing comma 를 허용하는 JSONC 라 전용 파서를 쓴다.
    별칭이 구체적 파일을 가리키는 경우(`"~lib": ["lib/index.ts"]`)를 위해 경로 원본도 후보에 넣는다
  - 해석 실패 = 외부 패키지로 간주 → `unresolved` 에 기록하고 **링크는 만들지 않는다**
  - `unresolved` 비율은 stats 에 노출한다. 이 수치가 곧 그래프 신뢰도이므로 숨기지 않는다.
- **성능:** 파일 단위 `ProcessPoolExecutor` 병렬 파싱. 목표 — 1000 파일 / 10초 이내
- **캐시:** 사용자 캐시 디렉토리(`~/.cache/repocity/<projectId>.json`, `REPOCITY_CACHE_DIR` 로 재정의)
  에 `mtime+size` 키로 파일별 분석 결과를 저장. 재분석 시 변경 파일만 다시 판다.
  **분석 대상 리포지토리 안에는 아무것도 쓰지 않는다** — 남의 체크아웃을 들여다보는 도구가
  거기에 파일을 남기면 상대의 `git status` 에 나타난다.
  캐시 키에는 **분석기 자신의 소스 해시**가 포함된다. mtime+size 만으로는 분석 *대상*의 변경만
  감지하고 분석 *로직*의 변경은 놓쳐서, 메트릭 계산을 고쳐도 옛 숫자를 계속 돌려주게 된다.

---

## 6. API 규격 (확정)

노트 초안을 기준으로, 안전장치 2개(`apply`, `revert`)와 진행률 폴링을 추가했다.

### REST
| 메서드 | 경로 | 요청 | 응답 |
|---|---|---|---|
| POST | `/api/v1/analyze` | `{path, include?, exclude?, force?}` | `202 {jobId, projectId}` |
| GET | `/api/v1/analyze/{jobId}` | – | `{status, progress, filesDone, filesTotal, error?}` |
| GET | `/api/v1/projects/{projectId}/citymap` | – | `CityMap.json` |
| GET | `/api/v1/projects/{projectId}/metrics/{node_id}` | – | `{metrics, source, imports[], importedBy[]}` |

node id 는 `f:src/core/parser.py` 처럼 슬래시를 포함한다. FastAPI `:path` 컨버터를 써서 인코딩
없이 그대로 받는다. 메트릭 조회는 어느 프로젝트의 노드인지 알아야 하므로 프로젝트 하위 경로다.
| POST | `/api/v1/agent/refactor` | `{nodeId, instruction, mode?}` | `202 {taskId}` |
| GET | `/api/v1/agent/tasks/{taskId}` | – | `{status, diff?, explanation?, error?}` |
| POST | `/api/v1/agent/apply` | `{taskId}` | `{applied:[paths], snapshotId, delta}` |
| POST | `/api/v1/agent/revert` | `{snapshotId}` | `{reverted:[paths], delta}` |

### WebSocket `/ws/stream?projectId=...`
서버 → 클라이언트 이벤트 (모두 `{type, ts, ...payload}`):

| type | 언제 | payload |
|---|---|---|
| `analysis.progress` | 분석 중 | `{jobId, done, total}` |
| `analysis.done` | 분석 완료 | `{jobId, projectId}` |
| `agent.plan` | 태스크 분해 완료 | `{taskId, steps[]}` |
| `agent.token` | 토큰 스트리밍 | `{taskId, delta}` |
| `agent.diff` | diff 생성 완료 | `{taskId, diff, files[]}` |
| `agent.error` | 실패 | `{taskId, message, stage}` |
| `citymap.delta` | 파일 변경 반영 | `{ops:[{op:"add"\|"update"\|"remove", ...}]}` |

**[결정 7] 소켓은 태스크당이 아니라 프로젝트당 하나다.** 노트의 `/ws/agent/stream` 은
리팩토링 전용이었지만, 분석 진행률과 도시 델타도 같은 채널로 흘려보내는 편이
프론트 상태 관리가 단순하다. 이벤트는 `taskId` 로 구분한다.

---

## 7. 프론트엔드 구조

```
apps/web/src/
  scene/
    CityCanvas.tsx        // <Canvas> + 조명/환경/포스트프로세싱
    Buildings.tsx         // grade별 InstancedMesh 4개 (드로우콜 4)
    Districts.tsx         // 바닥 타일 InstancedMesh
    Links.tsx             // 베지어 라인, 선택 기반 필터링
    Effects.tsx           // bloom + 먼지 파티클 풀
    useCityStore.ts       // zustand: citymap, selection, hover, filters
  panels/
    Inspector.tsx         // 메트릭 + 의존성 목록
    CodeView.tsx          // Monaco (읽기) / DiffEditor (제안 검토)
    CommandBar.tsx        // 프롬프트 + 스트리밍 로그
  api/  rest.ts, ws.ts, types.gen.ts
```

- **렌더링:** 건물은 grade 별 `InstancedMesh` 4개. 5000 파일 → 드로우콜 한 자릿수.
  피킹은 `instanceId` → building id 역매핑 테이블로 처리.
- **카메라:** `OrbitControls`, 각도 5°~85° 클램프(지하 진입 방지), 더블클릭 시 대상 건물로
  스무스 포커스, `F` 키로 선택 건물 프레이밍.
- **상태:** zustand 단일 스토어. citymap 은 immutable 스냅샷 + delta 적용 리듀서.

---

## 8. 에이전트 파이프라인

```
1) 컨텍스트 빌드   대상 파일 전문 + 1-hop import 대상 **본문 포함**(예산 60k 토큰).
                   초과 시에만 시그니처로 축약, 그래도 넘치면 CC 높은 함수 우선.
                   조립 순서는 결정 1-a 를 따른다.
2) 계획           `response_format: json_schema` 로 단계 목록을 강제 → agent.plan 이벤트
                  (프롬프트로 "JSON 으로 답해" 라고 부탁하지 않는다. 서버가 보장해준다)
3) 생성           수정된 파일 전문을 스트리밍 → agent.token 이벤트
4) 자체 검증      (a) 문법: tree-sitter 재파싱 성공 여부  ← 하드 게이트, 실패 시 1회 재시도
                  (b) 심볼: 공개 심볼 이름이 사라졌는지 비교 → 경고로 표시
                  (c) 메트릭: 신규 maxCC 가 원본보다 낮아졌는지 → 결과에 표시
5) diff 산출      difflib.unified_diff → agent.diff 이벤트 (파일 쓰기 없음)
6) 적용(명시적)   스냅샷 저장 → 파일 쓰기 → 변경 파일만 재분석 → citymap.delta 방송
```

**[결정 8] 문법 재파싱을 하드 게이트로 둔다.** LLM 이 깨진 코드를 내놓는 건 흔한 일이고,
파서를 이미 갖고 있으므로 무료로 걸러낼 수 있다. 통과 못 하면 사용자에게 diff 를 보여주지 않는다.

---

## 9. 성능 목표 (수용 기준)

| 항목 | 목표 |
|---|---|
| 분석 처리량 | 1000 파일 / ≤ 10s (콜드), ≤ 1s (캐시 히트) |
| 프레임레이트 | 3000 건물 / M2 Pro / ≥ 55fps |
| 최초 렌더 | CityMap 수신 후 ≤ 500ms |
| 단일 파일 재분석 | ≤ 300ms (delta 방송 포함) |
| 리팩토링 첫 토큰 (콜드) | ≤ 5s (8k 프리필 실측 4.5s) |
| 리팩토링 첫 토큰 (같은 파일 재명령) | ≤ 1s (프리필 캐시 실측 0.58s) |
| 리팩토링 완료 (~600 토큰 출력) | 10~25s |

## 10. 리스크

| 리스크 | 영향 | 완화 |
|---|---|---|
| import 해석 실패율이 높음 | 그래프가 거짓말을 함 | `unresolved` 를 UI 에 그대로 노출. 링크 신뢰도를 숨기지 않는다 |
| 원격 LLM 서버 다운/혼잡 | 리팩토링 기능 전면 중단 | `LLMAdapter` 폴백(로컬 Ollama), 헬스체크 후 UI 에 상태 표시, 실패해도 도시 탐색은 계속 동작 |
| 콜드 프리필 4.5s 체감 지연 | 첫 명령이 느리게 느껴짐 | 건물 **선택 시점에** 접두사만 미리 1토큰 요청해 캐시를 데워둔다(프리워밍). 명령 입력 중 이미 캐시 히트 상태 |
| treemap 재배열 | Phase 4 애니메이션이 의미를 잃음 | 이름순 배치 + 25% 여유 면적(결정 6) |
| LLM 이 코드를 망가뜨림 | 사용자 소스 손상 | diff-우선 + 스냅샷 + revert(결정 2) |
| 대형 레포에서 파티클/링크 폭주 | 프레임 드랍 | 상위 N 제한(결정 5) + 선택 기반 링크 필터 |
