import type { Building } from '../api/types.gen'

/**
 * English is the source of truth: `Messages` is derived from it, so a key missing from
 * Korean is a type error rather than a string that silently falls back.
 */
const en = {
  localeName: 'English',

  loader: {
    placeholder: 'a local path, or https://github.com/owner/repo.git',
    hint: 'Local directory path or git URL (GitHub, GitLab, …)',
    analyze: 'analyze',
    analyzing: 'analyzing…',
  },

  progress: {
    scanning: 'scanning repository…',
    cloning: (url: string) => `cloning ${url}`,
    parsing: (done: number, total: number) => `parsing ${done} / ${total} files`,
  },

  city: {
    title: 'City',
    files: 'files',
    lines: 'lines',
    resolved: 'imports resolved',
    unresolved: 'unresolved imports',
    unresolvedShare: (count: number, share: number) => `${count} (${share}% resolved)`,
    unresolvedNote:
      'Unresolved specifiers are packages or paths this analyzer could not map to a file. ' +
      'They are excluded from the graph, so this share is how much of the dependency picture ' +
      'you are actually seeing.',
    selectHint: 'Click a building to inspect it. Double-click to fly to it.',
    sourceHint:
      'The field at the top left takes a local path or a git URL; remote repositories are ' +
      'cloned shallowly into your data directory.',
  },

  building: {
    lines: 'lines',
    codeComments: 'code / comments',
    functionsClasses: 'functions / classes',
    avgCC: 'avg CC',
    importedBy: 'imported by',
    imports: 'imports from',
    dependencies: 'Dependencies',
    source: 'Source',
    noneResolved: 'none resolved',
    gradeBadge: (grade: string, maxCC: number) => `${grade} · max CC ${maxCC}`,
  },

  grade: {
    clean: 'clean',
    watch: 'watch',
    hot: 'hot',
    critical: 'critical',
  } as Record<Building['grade'], string>,

  agent: {
    online: (model: string) => `agent: ${model}`,
    offline: (detail: string | null) => (detail ? `agent offline — ${detail}` : 'agent offline'),
    connecting: 'connecting to the model…',
    selectFirst: 'Select a building first',
    refactor: (name: string) => `Refactor ${name}…`,
    send: 'send',
    planning: 'planning',
    generating: 'generating',
    writing: 'writing…',
    retrying: (reason: string) => `retrying: ${reason}`,
    suggestions: [
      'Split the most complex function into smaller ones.',
      'Add type hints to every function.',
      'Extract the repeated branches into a lookup table.',
    ],
  },

  proposal: {
    title: 'Proposed change',
    maxCC: (before: number, after: number) => `max CC ${before} → ${after}`,
    lines: (before: number, after: number) => `${before} → ${after} lines`,
    removed: (symbols: string) => `removed: ${symbols}`,
    apply: 'Apply',
    discard: 'Discard',
  },

  applied: {
    message: 'Change applied.',
    revert: 'Revert',
  },

  comparison: {
    title: 'Before / after',
    showBefore: 'show before',
    showingBefore: 'showing before',
    before: 'before',
    after: 'after',
    maxCC: 'max CC',
    lines: 'lines',
    functions: 'functions',
    grade: 'grade',
  },
}

export type Messages = typeof en

const ko: Messages = {
  localeName: '한국어',

  loader: {
    placeholder: '로컬 경로 또는 https://github.com/owner/repo.git',
    hint: '로컬 디렉터리 경로 또는 git URL (GitHub, GitLab, …)',
    analyze: '분석',
    analyzing: '분석 중…',
  },

  progress: {
    scanning: '리포지터리 훑는 중…',
    cloning: (url: string) => `클론 중 ${url}`,
    parsing: (done: number, total: number) => `파싱 중 ${done} / ${total} 파일`,
  },

  city: {
    title: '도시',
    files: '파일',
    lines: '라인',
    resolved: '해석된 import',
    unresolved: '미해석 import',
    unresolvedShare: (count: number, share: number) => `${count}개 (${share}% 해석)`,
    unresolvedNote:
      '미해석 import 는 외부 패키지이거나 분석기가 파일로 연결하지 못한 경로다. ' +
      '그래프에서 제외되므로, 이 비율이 곧 지금 보고 있는 의존 관계의 신뢰도다.',
    selectHint: '건물을 클릭하면 상세가 열린다. 더블클릭하면 그 건물로 이동한다.',
    sourceHint:
      '좌측 상단 입력창은 로컬 경로와 git URL 을 모두 받는다. 원격 리포지터리는 데이터 ' +
      '디렉터리에 얕게 클론된다.',
  },

  building: {
    lines: '라인',
    codeComments: '코드 / 주석',
    functionsClasses: '함수 / 클래스',
    avgCC: '평균 복잡도',
    importedBy: '들어오는 의존',
    imports: '나가는 의존',
    dependencies: '의존 관계',
    source: '원본 코드',
    noneResolved: '해석된 의존 없음',
    gradeBadge: (grade: string, maxCC: number) => `${grade} · 최대 복잡도 ${maxCC}`,
  },

  grade: {
    clean: '양호',
    watch: '주의',
    hot: '과열',
    critical: '위험',
  },

  agent: {
    online: (model: string) => `에이전트: ${model}`,
    offline: (detail: string | null) =>
      detail ? `에이전트 연결 안 됨 — ${detail}` : '에이전트 연결 안 됨',
    connecting: '모델에 연결하는 중…',
    selectFirst: '건물을 먼저 선택하세요',
    refactor: (name: string) => `${name} 리팩토링…`,
    send: '보내기',
    planning: '계획 중',
    generating: '생성 중',
    writing: '작성 중…',
    retrying: (reason: string) => `재시도: ${reason}`,
    suggestions: [
      '가장 복잡한 함수를 작은 함수로 쪼개줘.',
      '모든 함수에 타입 힌트를 붙여줘.',
      '반복되는 분기를 조회 테이블로 빼줘.',
    ],
  },

  proposal: {
    title: '제안된 변경',
    maxCC: (before: number, after: number) => `최대 복잡도 ${before} → ${after}`,
    lines: (before: number, after: number) => `${before} → ${after} 라인`,
    removed: (symbols: string) => `사라진 심볼: ${symbols}`,
    apply: '적용',
    discard: '버리기',
  },

  applied: {
    message: '변경이 적용되었습니다.',
    revert: '되돌리기',
  },

  comparison: {
    title: '변경 전 / 후',
    showBefore: '변경 전 보기',
    showingBefore: '변경 전 표시 중',
    before: '변경 전',
    after: '변경 후',
    maxCC: '최대 복잡도',
    lines: '라인',
    functions: '함수',
    grade: '등급',
  },
}

export const LOCALES = { en, ko }
export type Locale = keyof typeof LOCALES
