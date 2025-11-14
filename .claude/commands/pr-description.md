---
description: Generate a comprehensive PR description based on git diff and commit history
---

## PR Title Format (Conventional Commits)

Since PRs are squash-merged, the PR title becomes the commit message. All PR titles **must** follow conventional commit format:

```
<type>[optional scope]: <description>
```

**Examples:**
```
feat: add rate limiting policy for gateways
fix: resolve authorization timeout issue
test: add tests for DNS policy reconciliation
docs: update installation guide
refactor(authorino): simplify identity verification
```

**Allowed types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `style` - Code style changes (formatting, no logic change)
- `refactor` - Code refactoring
- `perf` - Performance improvements
- `test` - Adding or updating tests
- `build` - Build system changes
- `ci` - CI/CD changes
- `chore` - Other changes (dependencies, tooling)
- `revert` - Revert a previous commit

**Optional scopes:** `authorino`, `limitador`, `gateway`, `dns`, `tls`, `multicluster`, `ci`, `docs`, `chore`, `perf`, `refactor`, `style`, `test`

The GitHub workflow `.github/workflows/validate-pr-title.yml` validates PR titles automatically.

---

## Generating PR Description

Analyze the current branch and generate a comprehensive pull request description.

Follow these steps to minimize token usage:

1. Run `git diff --name-status main...HEAD` to see which files changed
2. Run `git diff --stat main...HEAD` to see change summary
3. Run `git log main..HEAD --oneline` to see commit history
4. Run `git diff --name-only main...HEAD | grep -E 'test.*\.py$'` to find test files
5. Only if needed for understanding complex changes, run `git diff -U1 main...HEAD` for condensed diff

Based on the analysis, generate a PR description with the following structure:

## Description
- Provide 2-4 concise bullet points summarizing the key changes
- Focus on WHAT changed and WHY (not just the technical details)

## Changes
- List the main changes organized by category (e.g., New Features, Bug Fixes, Refactoring, Tests, Documentation)
- Be specific but concise
- For test changes, briefly mention what is being tested

## Verification steps
- If there are 2 or more test files added, suggest running tests in parallel: `poetry run pytest -vv -n4 <test_file_paths>`
- If there is only 1 test file added, suggest running tests sequentially: `poetry run pytest -vv <test_file_path>`
- List all test file paths that were added or modified in the PR

Format the output in a markdown code block (triple backticks) so it can be directly copied into a GitHub PR description with all formatting preserved.
All file names, function names, method names, class names, and code elements should be wrapped in backticks for proper code formatting.

IMPORTANT: Wrap the entire PR description in a markdown code block like this:
```markdown
## Description
...
```

This ensures that when the user copies the text, all backticks are preserved.