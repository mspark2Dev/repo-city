# epoCity — 구현 계획 (v0.1)

`docs/DESIGN.md` 의 설계를 실행 순서로 편 것. 각 Phase 는 **그 자체로 돌아가는 산출물**과
**검증 가능한 수용 기준**을 갖는다. 기준을 못 채우면 다음 Phase 로 넘어가지 않는다.

## 리포지토리 구조

```
repo-city/
├─ apps/web/                  # Vite + React 19 + TS + R3F
├─ services/analyzer/         # Python 3.12 + FastAPI (uv 관리)
│   ├─ epocity/
│   │   ├─ scan.py            # 파일 워커 + ignore
│   │   ├─ parse.py           # tree-sitter 래퍼
│   │   ├─ metrics/           # loc.py, complexity.py, cc_rules.yaml
│   │   ├─ imports/           # python.py, tsjs.py, resolver.py
│   │   ├─ layout.py          # squarified treemap
│   │   ├─ schema.py          # Pydantic = 스키마 단일 진실 공급원
│   │   ├─ cache.py
│   │   ├─ agent/             # context.py, llm.py, verify.py, patch.py
│   │   └─ api/               # rest.py, ws.py, jobs.py
│   └─ tests/
├─ fixtures/                  # 분석 대상 더미 프로젝트 (파이썬 30~50 파일)
├─ docs/                      # DESIGN.md, ROADMAP.md
└─ .epocity/                  # 런타임 산출물(cache, snapshots) — gitignore
```

## 기술 스택 (확정)

| 레이어 | 선택 | 이유 |
|---|---|---|
| 프론트 | Vite, React 19, TypeScript, @react-three/fiber v9 + drei | R3F 표준 조합 |
| 상태 | zustand | 3D 씬과 패널이 같은 스토어를 값싸게 구독 |
| 에디터 | @monaco-editor/react (`DiffEditor` 포함) | diff 검토가 워크플로의 핵심 |
| 스타일 | Tailwind | HUD 위주라 디자인 시스템까진 불필요 |
| 백엔드 | Python 3.12(uv), FastAPI, uvicorn, Pydantic v2 | 시스템 파이썬 3.9 는 사용하지 않는다 |
| 파싱 | tree-sitter + tree-sitter-language-pack | 언어별 빌드 없이 다국어 |
| 잡 큐 | asyncio + in-process 워커 | 로컬 단일 사용자에 Celery/Redis 는 과잉 |
| LLM | vLLM `Qwen3.6-27B` (OpenAI 호환, 주소는 `.env`) | 실측 완료 — 120k ctx, APC, json_schema, tool_calls 전부 지원 |
| 타입 동기화 | Pydantic → JSON Schema → json-schema-to-typescript | 스키마 드리프트 차단 |

---

## Phase 1 — Data & Mock 3D
**목표: 더미 프로젝트가 상자와 선으로 화면에 뜬다.**

1. 모노레포 스캐폴딩 (`pnpm workspace`, `uv init`), `.gitignore`, `.env.example`
2. `fixtures/` 에 더미 파이썬 프로젝트 생성 (30~50 파일, 의도적 순환 의존 1쌍 + CC 30 짜리 함수 1개 포함)
3. `schema.py` 로 CityMap 모델 정의 → `scripts/gen-types` 로 TS 타입 생성 파이프라인 연결
4. `scan → parse → metrics(LOC만) → layout(treemap)` 파이프라인, CLI 진입점
   `uv run epocity analyze ./fixtures -o citymap.json`
5. `GET /api/v1/projects/{id}/citymap` + `POST /api/v1/analyze`(동기 처리로 시작)
6. R3F 캔버스: district 평면 + 건물 박스(높이=LOC) + 직선 링크, OrbitControls

**수용 기준**
- [ ] `citymap.json` 이 스키마 검증을 통과하고 fixtures 의 파일 수와 일치
- [ ] 같은 입력 두 번 분석 → **바이트 동일한 JSON** (레이아웃 결정성 증명)
- [ ] 브라우저에서 도시가 뜨고 궤도 회전/줌이 동작
- [ ] 건물 클릭 → 콘솔에 building id 출력 (피킹 경로 확보)

---

## Phase 2 — Visual Polish
**목표: 도시가 정보를 준다. 어디가 썩었는지 한눈에 보인다.**

1. 순환 복잡도 계산 (`cc_rules.yaml` 기반, Python/TS/JS)
2. import 해석기 (Python 상대·절대, TS `paths` 별칭) + `unresolved` 집계
3. grade 산출 및 4-버킷 `InstancedMesh` 렌더링, 재질/셰이더 (유리 → 녹슨 콘크리트)
4. 베지어 링크 + 선택 기반 필터링, 양방향 의존 강조
5. `critical` 상위 12개 먼지 파티클, bloom 포스트프로세싱
6. Inspector 패널: 메트릭 + 의존성 목록 + Monaco 읽기 뷰
   (`GET /api/v1/metrics/{node_id}`)
7. 카메라 튜닝: 각도 클램프, 더블클릭 포커스, `F` 프레이밍
8. 파일 캐시(`mtime+size`) 도입

**수용 기준**
- [ ] fixtures 의 의도된 CC 30 함수가 `critical` 붉은 건물로 렌더
- [ ] 의도된 순환 의존 1쌍이 굵은 붉은 선으로 표시
- [ ] 실제 중형 레포(1000+ 파일) 분석 ≤ 10s, 재분석 ≤ 1s
- [ ] 3000 건물에서 ≥ 55fps (통계 오버레이로 측정)
- [ ] `unresolved` 비율이 UI 에 노출됨

---

## Phase 3 — Agentic Integration
**목표: 붉은 건물을 골라 명령하면 diff 가 돌아온다.**

1. `LLMAdapter` (OpenAI 호환, 스트리밍) + 기동 시 `/v1/models` 헬스체크 → UI 배지
2. 컨텍스트 빌더: 대상 파일 전문 + 1-hop 본문(예산 60k), **정적→동적 조립 순서 고정**(설계 결정 1-a)
2b. 건물 선택 시 접두사 프리워밍 요청(max_tokens=1)으로 프리필 캐시 데우기
3. 잡 큐 + `POST /api/v1/agent/refactor` → `taskId`
4. WS `/ws/stream`: `agent.plan` / `agent.token` / `agent.diff` / `agent.error`
4b. plan 단계는 `response_format: json_schema` 로 강제 (파싱 실패 경로 자체를 제거)
5. 자체 검증: tree-sitter 재파싱 하드 게이트 + 심볼 소실 경고 + CC 개선치 계산
6. CommandBar UI (선택 건물 컨텍스트 표시) + 스트리밍 로그
7. Monaco `DiffEditor` 로 제안 검토, **Apply / Discard** 버튼
8. `POST /agent/apply` (스냅샷 → 쓰기), `POST /agent/revert`

**수용 기준**
- [ ] "이 파일의 가장 복잡한 함수를 쪼개줘" → 콜드 5s / 재명령 1s 내 첫 토큰, diff 수신
- [ ] 같은 파일에 두 번째 명령을 던졌을 때 TTFT 가 첫 명령보다 유의미하게 짧다 (캐시 규약 회귀 테스트)
- [ ] vLLM 서버를 끈 상태에서도 도시 탐색/분석 기능은 정상 동작
- [ ] 문법이 깨진 생성물은 diff 로 노출되지 않고 재시도 후 `agent.error`
- [ ] Apply 후 파일이 실제로 바뀌고, Revert 로 바이트 단위 복원
- [ ] LLM 호출 실패 시 UI 가 명확한 에러를 보여주고 도시 상태는 그대로 유지

---

## Phase 4 — Interaction
**목표: 리팩토링이 도시를 실시간으로 바꾼다.**

1. 변경 파일 단위 증분 재분석 → `citymap.delta` 방송
2. 프론트 delta 리듀서 (add / update / remove), ID 안정성 계약 활용
3. 트랜지션: 기존 건물 폭발 파티클 → 붕괴 → 신규 건물 상승(스프링 이징), 색 전이
4. Before/After 토글 (리팩토링 전 스냅샷 도시와 비교)
5. 분석 진행률 오버레이 (`analysis.progress`)

**수용 기준**
- [ ] Apply → 300ms 내 delta 도착, 해당 건물만 애니메이션 (도시 재배열 없음)
- [ ] 파일이 3개로 쪼개지면 건물 1개가 사라지고 3개가 같은 구역에서 솟아오름
- [ ] CC 가 낮아지면 색이 붉은색 → 파란색으로 전이
- [ ] Before/After 토글로 개선 수치(maxCC, LOC)를 나란히 확인 가능

---

## 즉시 착수 가능한 첫 5개 태스크
1. `uv init services/analyzer` + FastAPI 헬스체크 + `pnpm create vite apps/web`
2. `fixtures/` 더미 프로젝트 작성 (순환 의존·고복잡도 함수 심어둘 것 — 이후 전 Phase 의 테스트 기준점)
3. `schema.py` CityMap Pydantic 모델 + 타입 생성 스크립트
4. `scan.py` + `metrics/loc.py` + `layout.py` → `citymap.json` 산출 CLI
5. R3F 캔버스에 `citymap.json` 정적 로드해서 박스 렌더

## 미해결 결정 사항 (진행 중 확정 필요)
- **분석 대상 레포 지정 방식**: 로컬 경로 입력만 지원할지, git clone 도 지원할지 → Phase 1 은 로컬 경로만
- **다중 프로젝트 동시 보유**: 현재 설계는 `projectId` 로 다중을 전제하나 UI 는 단일 프로젝트 → Phase 2 말에 재검토
- **인증/원격 접근**: 백엔드는 `127.0.0.1` 바인딩 유지. LLM 만 사내망으로 나간다
- **코드 유출 경계**: 분석 대상 코드가 LLM 서버로 전송된다. 사내망이라 문제없다는 전제이며,
  외부 레포/고객 코드를 다룰 일이 생기면 이 전제를 다시 확인해야 한다
