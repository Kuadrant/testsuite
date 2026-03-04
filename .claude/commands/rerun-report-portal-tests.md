---
description: Run tests from a dot-notation list with options to copy or execute
---

# Run Tests

Convert a list of test names (dot-notation) into a pytest command, then either copy it to clipboard or execute it directly and analyze results.

## Input Format

The user provides:
- A list of test names in **dot-notation** format (e.g., `testsuite.tests.singlecluster.gateway.test_basic.test_gateway_basic_dns_tls`)
- Optional pytest flags (e.g., `-n4`, `-vv`, `--dist loadfile`)

## Instructions

### Step 1: Parse test names

1. Convert each dot-notation test name to pytest file::function format:
   - Replace dots with `/` up to and including the test file name
   - Add `.py::` before the test function name
   - Example: `testsuite.tests.singlecluster.gateway.test_basic.test_gateway_basic_dns_tls` becomes `testsuite/tests/singlecluster/gateway/test_basic.py::test_gateway_basic_dns_tls`

2. Handle **parameterized tests** (names containing `[...]`):
   - Preserve the bracket and parameter portion (e.g., `test_deny_invalid_org_id[321]` stays as `test_deny_invalid_org_id[321]`)
   - This runs only the specific parameter variant that failed, not all variants
   - Example: `testsuite.tests.singlecluster.authorino.test_org.test_deny_invalid_org_id[321]` becomes `testsuite/tests/singlecluster/authorino/test_org.py::test_deny_invalid_org_id[321]`

### Step 2: Build the pytest command

- Base command: `poetry run pytest -vv`
- Append any user-specified flags (e.g., `-n4`, `--lf`, `-x`)
- If no flags are specified, default to just `-vv`
- Append all converted test paths as space-separated arguments
- **Quote test paths that contain `[...]`** with single quotes to prevent zsh glob expansion (e.g., `'path/to/test.py::test_name[param]'`)
- Test paths without brackets do not need quoting
- Build it as a single-line command (no backslash line continuations — they break in zsh)

### Step 3: Ask user how to proceed

Use AskUserQuestion to ask the user:

**"How would you like to proceed with these {N} tests?"**

Options:
1. **Copy to clipboard** — Copy the command to clipboard (see clipboard note below) so user can paste and run it themselves
2. **Run and analyze** — Execute the command directly, then provide a pass/fail breakdown with failure reasons

### Step 4a: If "Copy to clipboard"

- Detect the OS and use the appropriate clipboard command:
  - **macOS**: `printf '%s' '<command>' | pbcopy`
  - **Linux**: `printf '%s' '<command>' | xclip -selection clipboard` (or `xsel --clipboard` if xclip is unavailable)
- Confirm the command was copied
- Done

### Step 4b: If "Run and analyze"

1. Run the pytest command as a background task
2. When complete, analyze the output and provide a summary table:

| Test | Status | Reason (if failed) |
|------|--------|---------------------|
| test_name | PASSED / FAILED / ERROR / XFAIL / XPASS | Brief failure reason |

3. After presenting results, ask the user:

**"What would you like to do next?"**

Options:
1. **Rerun failed tests** — Build and execute a new command with only the failed tests
2. **Copy failed tests command** — Copy the rerun command to clipboard instead
3. **Provide new test list** — User provides a new set of tests to run
4. **Done** — End the session

4. If "Rerun failed tests" is selected, repeat from Step 4b (run, analyze, ask again)
5. If "Copy failed tests command" is selected, copy to clipboard and ask again with the same options
6. If "Provide new test list" is selected, go back to Step 1 with the new input
7. Continue this loop until the user selects "Done"

## Important Notes

- NEVER use backslash line continuations — they cause `zsh: no such file or directory` errors
- Use `printf '%s' '...'` piped to the appropriate clipboard tool instead of `echo` to avoid trailing newline issues
- **Clipboard tools**: use `pbcopy` on macOS, `xclip -selection clipboard` on Linux
- When rerunning failed tests, preserve the same flags from the original command (e.g., `-n4`, `-vv`)
- Multicluster or disruptive tests should typically NOT use `-n4` (parallel execution) — warn if detected