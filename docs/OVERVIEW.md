# Overview

## Why this exists

Reading an unfamiliar codebase is mostly navigation. You open files, follow imports, and slowly
build a mental model of where the weight sits and where the mess is. Tools that measure complexity
give you the answer as a table — a list of file paths sorted by a number — which is accurate and
almost impossible to hold in your head.

Spatial memory is better at this than list-reading. If a codebase is a place, "the huge rusted tower
in the corner of `src/core`" is something you remember after seeing it once. That is the entire
premise: put the metrics in space, and let the shape of the codebase be something you recognize
rather than something you look up.

The second half of the premise is that once you have found the mess, you should be able to do
something about it without leaving. So the same surface that shows you the problem lets you hand it
to an agent, review the diff, and watch the city change.

This idea is not new — [CodeCity](https://wettel.github.io/codecity.html) (Wettel & Lanza, 2007)
established the city metaphor for software visualization. epoCity differs in two ways: it targets
modern polyglot repositories through tree-sitter, and it closes the loop by wiring an LLM agent into
the visualization so that inspection and modification are the same workflow.

## How the pieces fit

```
   repository on disk
          │
          ▼
   ┌─────────────┐   scan → parse → metrics → resolve imports → layout
   │  analyzer   │
   └──────┬──────┘
          │  CityMap.json  (deterministic, stable IDs)
          ▼
   ┌─────────────┐   districts, buildings, links → InstancedMesh
   │  3D canvas  │
   └──────┬──────┘
          │  user selects a building, types a command
          ▼
   ┌─────────────┐   target file + 1-hop dependencies → LLM → unified diff
   │   agent     │
   └──────┬──────┘
          │  user accepts
          ▼
   write files → re-analyze changed files only → CityMap delta → animate
```

### The analyzer

A Python service that walks the repository, parses each file with tree-sitter, and computes lines of
code, cyclomatic complexity, and symbol counts. It resolves import statements into a file-to-file
graph — relative and absolute imports for Python, path aliases from `tsconfig.json` for TypeScript.
Anything it cannot resolve is reported as unresolved rather than silently dropped, because the
honesty of that number is the honesty of the whole graph.

Layout is a squarified treemap: directories become nested floor tiles, files become buildings placed
inside them. Placement is sorted by filename rather than by size, and each district reserves extra
area, so a file gaining a few hundred lines does not reshuffle the city.

### The canvas

React Three Fiber. Buildings are drawn as four instanced meshes — one per complexity grade — so a
repository with thousands of files still costs a handful of draw calls. Import links are filtered
rather than drawn all at once, because a few thousand curves rendered simultaneously communicate
nothing.

### The agent

The agent gets the target file in full, its direct dependencies, and the file's metrics. It returns
a plan, then a rewritten file, streamed token by token over a WebSocket. Before the diff reaches the
user it must re-parse cleanly — a syntax check we get for free, since the parser is already there.

The agent proposes; it does not write. Applying a change is a separate, explicit action that
snapshots the originals first.

## Non-goals

- **Not an IDE.** There is an editor pane, but it exists to review agent output, not to be where you
  write code.
- **Not a CI gate.** Nothing here blocks a build or fails a pipeline.
- **Not a metrics authority.** Cyclomatic complexity computed from an AST is a heuristic for finding
  interesting places, not a score to optimize.
- **Not multi-user.** It runs locally against a checkout on your disk.
