# Version-control workflow

The user authorized routine commits and pushes for this project, including minor meaningful changes. This authorization supersedes older README instructions to ask before every ordinary commit. Production deployment is not authorized.

Originally requested account: `PARAMCLOUD1`, with public repository `https://github.com/PARAMCLOUD1/FailureVerse-AI`.

On 15 November 2026 (local time), the existing Git Credential Manager account was verified as `PARAMCLOUD1`. An authenticated lookup found no target repository, and the requested repository was created and verified as **public**, with `main` as the default branch. No existing repository or history was overwritten. Authentication values were used only through the credential flow and were not printed or saved in the project.

The portable official GitHub CLI is installed in ignored `.tools/gh/bin/gh.exe`. Git pushes can use the existing credential helper; no additional login was needed for setup. If reauthentication or a separate CLI login is needed later, use:

```powershell
& ./.tools/gh/bin/gh.exe auth login --hostname github.com --git-protocol https --web
```

Do not paste a password or token into chat. After login, verify the account, check the existing repository, and create a new **public** repository only if it is absent. Preserve any existing history. Do not change an existing repository's visibility or overwrite its content without the required confirmation.

GitHub subsequently redirected that original address to the canonical public repository **[paramjeetkaur04/FailureVerse-AI](https://github.com/paramjeetkaur04/FailureVerse-AI)**. Authenticated API checks verified both addresses resolve to repository ID `1458622146`, with `private=false`, default branch `main`, and owner matching the authenticated `paramjeetkaur04` account. The local origin and active documentation links follow that canonical address. No repository transfer or visibility change was performed during this follow-up; the existing history was preserved.

The verified Phase 2.1 feature branch was fast-forwarded into `main`, preserving all commits. Remote commit history and [GitHub Actions](https://github.com/paramjeetkaur04/FailureVerse-AI/actions/workflows/ci.yml) are the authoritative publication and CI state; verify the exact reviewed SHA rather than inferring success from a local test result.

Phase 1 already existed as commit `94dd605`. The original local `master` branch was renamed to `main` without changing that commit. The earlier `.git` directory is owned by the prior sandbox account, so authorized host Git writes use a trust exception limited to this exact workspace (`git -c safe.directory=...`); no global wildcard trust was added.

For each logical change:

1. Review `git status` and the actual staged diff.
2. Check `.env` and runtime/build exclusions; run `scripts/check_secrets.py --staged`.
3. Run appropriate tests, lint and build checks. Resolve failures before pushing.
4. Create a Conventional Commit describing the change; never create empty commits.
5. Keep larger work on a feature branch until verified, then merge into `main` without rewriting shared history.
6. Push `main`, confirm the remote commit, and inspect the GitHub Actions run for that exact SHA.

Never commit credentials, local models/tools, virtual environments, caches, logs, SQLite files, generated builds or evaluation JSON. Never force-push, delete branches, alter existing visibility or change production deployment settings without confirmation. CI performs verification only; there is no automatic deployment workflow.
