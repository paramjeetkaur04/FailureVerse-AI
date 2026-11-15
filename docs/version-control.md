# Version-control workflow

The user authorized routine commits and pushes for this project, including minor meaningful changes. This authorization supersedes older README instructions to ask before every ordinary commit. Production deployment is not authorized.

Target account: `PARAMCLOUD1`. Requested public repository: `https://github.com/PARAMCLOUD1/FailureVerse-AI`.

At the last authentication check, GitHub CLI was not logged in. Unauthenticated repository checks returned 404; that does not prove absence because a private repository can also return 404. Repository creation, public accessibility, pushes and remote CI must not be reported as successful until authenticated checks confirm them.

The portable official GitHub CLI is installed in ignored `.tools/gh/bin/gh.exe`. Complete login as the requested account using:

```powershell
& ./.tools/gh/bin/gh.exe auth login --hostname github.com --git-protocol https --web
```

Do not paste a password or token into chat. After login, verify the account, check the existing repository, and create a new **public** repository only if it is absent. Preserve any existing history. Do not change an existing repository's visibility or overwrite its content without the required confirmation.

Phase 1 already existed as commit `94dd605`. The original local `master` branch was renamed to `main` without changing that commit. The earlier `.git` directory is owned by the prior sandbox account, so authorized host Git writes use a trust exception limited to this exact workspace (`git -c safe.directory=...`); no global wildcard trust was added.

For each logical change:

1. Review `git status` and the actual staged diff.
2. Check `.env` and runtime/build exclusions; run `scripts/check_secrets.py --staged`.
3. Run appropriate tests, lint and build checks. Resolve failures before pushing.
4. Create a Conventional Commit describing the change; never create empty commits.
5. Keep larger work on a feature branch until verified, then merge into `main` without rewriting shared history.
6. Push `main`, confirm the remote commit, and inspect the GitHub Actions run for that exact SHA.

Never commit credentials, local models/tools, virtual environments, caches, logs, SQLite files, generated builds or evaluation JSON. Never force-push, delete branches, alter existing visibility or change production deployment settings without confirmation. CI performs verification only; there is no automatic deployment workflow.
