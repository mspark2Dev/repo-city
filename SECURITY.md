# Security

## What repoCity does with your code

Two things are worth knowing before you point it at a repository.

**It clones what you point it at.** A git URL is cloned into
`~/.local/share/repocity/clones/`. Only https, http, ssh, git and scp-style remotes are
accepted; transport helpers such as `ext::`, which git treats as a command to run, are
refused, as is any value beginning with `-`. git is invoked with an argument list and never
a shell, with prompting disabled so a private repository fails instead of hanging.

**It reads whatever path you give it.** The analyzer walks that directory and reads every
file it can parse. The backend binds to loopback by default for exactly this reason — do
not expose it on a network interface.

**It sends source code to a model endpoint.** When you ask the agent to refactor a file,
that file and its direct dependencies are sent to whatever `LLM_BASE_URL` points at. If
that endpoint is not one you control, treat it as publishing the code. Analysis and
visualization work with no endpoint configured at all.

**It writes to your files only when you say so.** The agent produces a diff. Pressing Apply
is what writes, and the original is copied to `~/.local/share/repocity/snapshots/` first so
Revert can restore it byte for byte. Writes outside the analyzed project root are refused.

## Reporting a vulnerability

Open a [security advisory](https://github.com/mspark2Dev/repo-city/security/advisories/new)
rather than a public issue. Include what you did, what happened, and what you expected.
