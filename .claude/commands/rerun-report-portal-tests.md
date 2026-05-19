---
description: Run tests from a test list with options to copy or execute
---

# Run Tests

Fetch failed tests from Report Portal using rptool, or accept a manually provided test list, then build a pytest command to either copy to clipboard or execute directly and analyze results.

## Input Format

The user provides one of the following:
- **rptool arguments**: An RP project, launch name, and test target to fetch failed tests from Report Portal (e.g., `rp project nightly-testsuite launch name "nightly-all #565" test target kuadrant`)
- **A list of test names** in either format:
  - **Pytest path format** (preferred): `testsuite/tests/singlecluster/gateway/test_basic.py::test_gateway_basic_dns_tls`
  - **Dot-notation format** (legacy): `testsuite.tests.singlecluster.gateway.test_basic.test_gateway_basic_dns_tls`
- **No input**: The user will be asked how they want to provide tests

Optional: pytest flags (e.g., `-n4`, `-vv`, `--dist loadfile`)

## Instructions

### Step 0: Determine input source

1. **If the user's message contains rptool-related arguments** (a launch name and/or test target for Report Portal), go to **Step 1a** (Fetch from Report Portal).
2. **If the user's message contains test names** (either pytest path format or dot-notation), go to **Step 1b** (Parse test names).
3. **Otherwise**, ask the user via AskUserQuestion:

   **"How would you like to provide the tests?"**

   Options:
   1. **Fetch from Report Portal** — Fetch failed tests from a Report Portal launch using rptool
   2. **Provide test list manually** — Paste a list of failed tests

   - If "Fetch from Report Portal" is selected, go to **Step 1a**
   - If "Provide test list manually" is selected, ask the user for the list, then go to **Step 1b**

### Step 1a: Fetch failed tests from Report Portal

1. If the user has not already provided all required values, ask for the missing ones:
   - **RP project** (optional) — e.g., `nightly-testsuite`. If not provided, omit the `--rp-project` flag and rptool will use the default from the user's configuration.
   - **Launch name** (required) — e.g., `"nightly-all #565"`
   - **Test target** (required) — e.g., `kuadrant`

2. Run the rptool command via Bash:
   ```
   rptool query [--rp-project <rp-project>] --launch-name "<launch-name>" --test-target <test-target> --status FAILED --names-only
   ```

3. Parse the output — each line is a test name in pytest path format (e.g., `testsuite/tests/.../test_file.py::test_name`).

4. If no failed tests are found (empty output), inform the user and stop.

5. Show the user the list of failed tests and the count, then continue to **Step 1b** with these test names.

### Step 1b: Parse test names

1. **Detect the format** of the provided test names:
   - **Pytest path format**: Contains `/` and `::` (e.g., `testsuite/tests/singlecluster/gateway/test_basic.py::test_gateway_basic_dns_tls`) — use as-is, no conversion needed.
   - **Dot-notation format**: Contains only dots and no `/` or `::` (e.g., `testsuite.tests.singlecluster.gateway.test_basic.test_gateway_basic_dns_tls`) — convert to pytest path format.

2. **Convert dot-notation names** (only if detected in step 1):
   - Replace dots with `/` up to and including the test file name
   - Add `.py::` before the test function name
   - Example: `testsuite.tests.singlecluster.gateway.test_basic.test_gateway_basic_dns_tls` becomes `testsuite/tests/singlecluster/gateway/test_basic.py::test_gateway_basic_dns_tls`

3. Handle **parameterized tests** (names containing `[...]`):
   - Preserve the bracket and parameter portion (e.g., `test_deny_invalid_org_id[321]` stays as `test_deny_invalid_org_id[321]`)
   - This runs only the specific parameter variant that failed, not all variants
   - Dot-notation example: `testsuite.tests.singlecluster.authorino.test_org.test_deny_invalid_org_id[321]` becomes `testsuite/tests/singlecluster/authorino/test_org.py::test_deny_invalid_org_id[321]`
   - Pytest path example: `testsuite/tests/singlecluster/authorino/test_org.py::test_deny_invalid_org_id[321]` — used as-is

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
6. If "Provide new test list" is selected, go back to Step 0 with the new input
7. Continue this loop until the user selects "Done"

## Important Notes

- NEVER use backslash line continuations — they cause `zsh: no such file or directory` errors
- Use `printf '%s' '...'` piped to the appropriate clipboard tool instead of `echo` to avoid trailing newline issues
- **Clipboard tools**: use `pbcopy` on macOS, `xclip -selection clipboard` on Linux
- When rerunning failed tests, preserve the same flags from the original command (e.g., `-n4`, `-vv`)
- Multicluster or disruptive tests should typically NOT use `-n4` (parallel execution) — warn if detected