# Kuadrant Testsuite Contribution Guide

This document outlines how to contribute to the Kuadrant testsuite. Before contributing, ensure you have reviewed the [README](https://github.com/Kuadrant/testsuite/blob/main/README.md) for details on running tests, configuration, and environment requirements.

### Contributing Guidelines

The Kuadrant testsuite accepts contributions from **forks**, including from contributors outside the Kuadrant or Red Hat organisation.

Contributors must:

* Fork the repository
* Create feature branches in their own fork (not in the main repo)  
* Open a Pull Request from \<user\>/testsuite:\<branch\> → Kuadrant/testsuite:main

**Note for external contributors:** 
If you are contributing from outside Red Hat, you will need to run the tests on a Kubernetes cluster that does not require internal VPN access. A local KIND cluster (or any accessible Kubernetes cluster) is supported. Tests can be run either locally with Python/Poetry or via the container image. Refer to the [README](https://github.com/Kuadrant/testsuite/blob/main/README.md) for more details on running tests.

### Forking the Repository

Fork the repository first, then clone and navigate into your fork:

```shell
git clone git@github.com:<your-username>/testsuite.git
cd testsuite
```

Add the upstream remote to easily pull the latest changes from the main repository:

```shell
git remote add upstream git@github.com:Kuadrant/testsuite.git
```

To prevent pushing to upstream, configure it as fetch-only:

```shell
git remote set-url --push upstream no_push
```

You can verify your remote configuration with `git remote -v`. You should see that you can only push to `origin` (your fork):

```shell
origin    git@github.com:<your-username>/testsuite.git (fetch)
origin    git@github.com:<your-username>/testsuite.git (push)
upstream  git@github.com:Kuadrant/testsuite.git (fetch)
upstream  no_push (push)
```

### Coding Rules / Guidelines

**Test Naming Conventions:**

- Test files use the pattern `test_<feature>.py` (e.g., `test_authorino_metrics.py`)
- Test functions must use the `test_` prefix and clearly describe the behaviour being tested (e.g., `test_dnspolicy_removal`)
- Fixture names should be short, lower-case, and reflect their purpose (e.g.,
gateway, route, authorization)
- Parametrised tests should use meaningful parameter IDs (ids=) to improve readability in test output

**Common Testing Patterns:**

- Every test and fixture should include a meaningful docstring
- Mark tests appropriately with pytest markers (`@pytest.mark authorino`, `@pytest.mark.limitador`, etc.)
- Use `autouse=True` on fixtures when resources should be automatically applied before tests
- Use `request.addfinalizer()` to ensure cleanup/teardown of resources
- Follow policy lifecycle: `create → configure → commit → wait_for_ready → delete`

**Test Organization:**

- `singlecluster/` for single-cluster scenarios
- `multicluster/` for multi-cluster scenarios
- Group tests by feature area (authorino, limitador, gateway, etc.)

### Reformat, Commit Acceptance & Cleanup

Before committing your changes, make sure the code is properly formatted, and all commit checks pass. Otherwise, your pull request may fail the GitHub Actions **Code Static Analysis** checks.

**Reformat code:**

```shell
make reformat
```

This runs ‘black’ through Poetry to automatically format all source files according to the project’s code style.

**Commit acceptance:**

```shell
make commit-acceptance
```

This performs a final validation before committing by running:

* **Black** in check mode for code formatting  
* **Pylint** for linting and code quality  
* **Mypy** for static type checking

**Cleanup:**  
Once you’re done testing, if any resources created during the tests remain in the cluster, you can clean them up by running:

```shell
make clean
```

### Committing changes & Opening a Pull Request

**1\. Stage changes:**

To add all files:
```shell
git add .
```

Or stage specific files:
```shell
git add <filename1> <filename2> 
```

**2\. Commit with sign-off and GPG signature:**

```shell
git commit -s -S -m "Your commit message here"
```

* **\-s** adds a Signed-off-by line (required for GitHub Actions checks such as DCO compliance)  
* **\-S** signs the [**commit with your GPG key**](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits) for verified commits  
* We also follow the [**conventional commits**](https://www.conventionalcommits.org/) format for commit messages

If you make additional changes, or if a reviewer requests updates, or if your commit fails the commit-acceptance checks, **do not create a new commit**. Instead, amend the previous commit to keep the history clean (we typically prefer one commit per feature/fix).

To amend the previous commit and edit the message:
```shell
git commit --amend -s -S
```

To amend the previous commit without changing the existing message:
```shell
git commit --amend -s -S --no-edit
```
If multiple commits are created during development, they [should be squashed](https://www.git-tower.com/learn/git/faq/git-squash) into a single commit before the PR is merged.

**3\. Push to your branch:**

```shell
git push origin <branch-name>
```

After amending a commit that was already pushed, you must force-push to update the branch:

```shell
git push --force-with-lease
```

**4\. Open a Pull Request:**

1. You can create the PR either directly from your fork or by navigating to the **Pull Requests** tab in the main repository  
2. Click **“Compare & pull request”** (GitHub usually shows this automatically)  
3. Ensure the target is **Kuadrant/testsuite:main** and the source is **your-fork:\<branch\>**  
4. Add a clear [**conventional commit**](https://www.conventionalcommits.org/) based title and description, then submit the PR
5. Read more **https://docs.github.com/en/pull-requests/collaborating-with-pull-requests**

**5\. Pull Request Review:**

Before a PR can be merged into `main`, it requires:

1. Approval from **two** maintainers
2. No pending change requests
3. All review conversations resolved
4. All automated checks passing
