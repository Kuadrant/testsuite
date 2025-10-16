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

## Commits

1. Consider using https://www.conventionalcommits.org/en/v1.0.0/  (.gitmessage)

## Creating PRs

1. To promote quality code, request 2 reviewers
1. Link relevant issues, and/or summarize the changes
1. Consider providing a verification steps in the PR description (might have a tool for that)

## Reviewing PRs

1. Focus on readability
1. Is the test placed in correct path?
1. Consider test structure and design, can it be improved without impacting runtime?
1. Is the test easy to debug on Failure or Error?

### precommit hook

Consider using some secret guarding precommit hooks in your git setup, to prevent secret leaking.

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

