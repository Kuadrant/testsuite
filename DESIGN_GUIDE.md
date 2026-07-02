# The Design Guide - How to design tests, and how to review them

This is not a rule book, just a compilation of guidelines, tips, and thoughts.

## Atomic tests

While atomic test cases are a great way of designing test at unit test level,
for End-to-End tests it might not be great Return of Investment. But please consider
atomic test case design principles in your test design.

* Is it possible to extract some portion of my test into fixture/setup?
* Could some of it be reused by multiple test cases?
* Is that possible to do, while not destroying tests runtime or making complex fixture desing?

Just considering the principles, might give you an idea of new test cases, that
might be useful to write.

## Fixture Design

1. Use simple, descriptive names: `route`, `authorization`, `backend`, `gateway`, `hostname`, `client`
1. For multiple instances of the same resource, append a number to secondary resources: `route2`, `backend2`, `authorization2`
1. The primary resource always uses the plain name without a number
1. Use `blame()` to generate unique, scoped names for Kubernetes resources: `blame("gw")` → `"gw-alice-tc-abc"`
1. Choose appropriate fixture scope:
   * `scope="session"` - Created once per test run (e.g., `cluster`, `backend`, `gateway`)
   * `scope="module"` - Created per test module (e.g., `route`, `authorization`, `rate_limit`)
   * `scope="function"` - Created per test (rarely used, only for parametrized or stateful tests)

## Code Quality

1. **Every module and fixture must have a short, descriptive docstring**
   * Module docstrings describe the test scope
   * Fixture docstrings describe what they create or return, not how
1. **Always look for a more correct solution before disabling a pylint warning**
   * Legitimate uses: `# pylint: disable=unused-argument` for pytest dependency ordering
   * Legitimate uses: `# pylint: disable=invalid-name` for Kubernetes API camelCase fields

## Commits

1. Consider using https://www.conventionalcommits.org/en/v1.0.0/  (.gitmessage)
1. Run `make reformat` and `make commit-acceptance` locally to catch code analysis or formatting issues before committing and pushing
1. Sign off commits by adding the `-s` flag (`git commit -s`)
1. Optionally, sign commits with the `-S` flag (`git commit -S`) if you have a GPG or SSH key configured — this verifies commit authenticity on GitHub

## Creating PRs

1. To promote quality code, request 2 reviewers
1. Link relevant issues, and/or summarize the changes
1. Use the `/pr-description` command to generate comprehensive PR descriptions with verification steps
1. Ensure CI checks pass before opening a PR (e.g., DCO sign-off, code analysis, GitGuardian)
1. Use a draft PR to share work in progress and gather early feedback before marking it ready for review

## Reviewing PRs

1. Focus on readability
1. Is the test placed in correct path?
1. Consider test structure and design, can it be improved without impacting runtime?
1. Is the test easy to debug on Failure or Error?

### precommit hook

Consider using secret guarding precommit hooks in your git setup to prevent secret leaking:

1. Install pre-commit framework: https://pre-commit.com/
1. Use gitleaks (https://github.com/gitleaks/gitleaks) or similar tools to detect hardcoded secrets
1. Example `.pre-commit-config.yaml`:
   ```yaml
   repos:
     - repo: https://github.com/gitleaks/gitleaks
       rev: v8.18.2
       hooks:
         - id: gitleaks
   ```
1. Install hooks: `pre-commit install`

### .gitmessage

Currently optional, you may use a file (conventionally) named `.gitmessage`,
and configure your git to use it as a commit message template.

For example `.gitmessage`:

```text
# test: 
# test():

# Description:


# Footer:


# See also: https://www.conventionalcommits.org/en/v1.0.0/
```

And git configuration:

```shell
git config commit.template=.gitmessage
```

next time you commit, your editor will be prefilled with the templates, and as
usual, anything that is a comment `#` will be ignored.

