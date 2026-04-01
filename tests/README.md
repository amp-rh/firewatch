# Running Tests for Firewatch

This directory contains tests for the Firewatch project. The tests are designed to ensure the correctness and reliability of the codebase.

## Structure

The tests are organized into subdirectories that mirror the structure of the source code. Each test file corresponds to a specific module or class in the source code.

## Running the Unit Tests

You can use tox from command line to execute the unit tests. The tox.ini file defines the tox config for automatically running the tests. Tox installs the project dependencies and runs the tests using pytest command.
To invoke the pytest test execution command using tox, simply run the following command at project root directory:

```sh
tox
```

This will run all the tests under the directory tests/unittests with specified coverage.

To run all tests in a single file/module, you can execute pytest command with necessary options, for example:

```sh
pytest -c ./tests/unittests/pytest.ini --verbose ./tests/unittests/objects/job/test_firewatch_objects_job_check_is_rehearsal.py
```

To run a single unit test from a module, you can specify the function name like below:

```sh
pytest --verbose ./tests/unittests/objects/job/test_firewatch_objects_job_check_is_rehearsal.py::test_rehearsal_job_true
```

Alternatively you can use the python `unittest` framework. The following command will discover and run all the tests in the `tests/unittests` directory:

```sh
python -m unittest discover -s tests/unittests
```

You can run tests in a specific test file using option like below:

```sh
python -m unittest tests.unittests.objects.job.test_firewatch_objects_job_check_is_rehearsal
```

## Running the E2E Tests

E2E tests live under `tests/e2e`. They exercise the `firewatch` CLI against a real Jira project and download real job artifacts for a pinned build, so they are not part of the default `tox` run (which only collects `tests/unittests` per `pyproject.toml`).

Set these environment variables before running:

- `JIRA_TOKEN` (required)
- `JIRA_SERVER_URL` (required)
- `JIRA_EMAIL` (optional; forwarded into the generated Jira config when present)

```sh
pytest tests/e2e
```

Or select by marker:

```sh
pytest -m e2e tests/e2e
```

In GitHub Actions, the `e2e-tests` workflow (`workflow_dispatch` only) runs the same command and expects repository secrets `JIRA_TOKEN`, `JIRA_SERVER_URL`, and optionally `JIRA_EMAIL`.

## Mocking (unit tests vs E2E)

Unit tests under `tests/unittests` use `pytest` and `unittest.mock` to mock external systems such as the Jira API and the filesystem where appropriate, so they run in CI without secrets.

E2E tests call the real Jira API and perform real downloads for the first phase of the flow; only the second phase monkeypatches `Job` log and JUnit download paths to simulate a passing run. Do not assume E2E tests mock Jira end to end.

## Adding New Tests

For unit tests, add files under `tests/unittests` following the existing layout and use mocks as needed. For E2E, add modules under `tests/e2e`, mark tests with `@pytest.mark.e2e` (or module-level `pytestmark = pytest.mark.e2e`), and document any new environment variables or pinned job data in this file.
