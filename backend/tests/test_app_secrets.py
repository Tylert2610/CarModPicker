import importlib.util
import json
import logging
import os
import subprocess  # nosec B404 - fixed argv, no shell, no user input
import sys
import warnings
from pathlib import Path
from types import ModuleType

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws
from webbpulse.config import SecretNotJsonObjectError

from app.composition.domains import ENTRYPOINT_MODULES
from app.core import config as config_module
from app.core.config import Settings
from app.core.secrets import apply_app_secrets, fetch_app_secrets, load_app_secrets, reset_cache

MISSING_SECRET_ARN = "arn:aws:secretsmanager:us-west-2:123456789012:secret:carmodpicker-test/missing-AbCdEf"

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APP_SECRETS_ARN", "SECRET_KEY", "SENTRY_DSN", "NOT_A_SETTING", "ACCESS_TOKEN_EXPIRE_MINUTES"):
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    # The fetched blob is cached for the life of the execution environment, so a
    # test that changes what the secret holds has to drop it first.
    reset_cache()


def create_app_secret(payload: dict[str, object]) -> tuple[object, str]:
    client = boto3.client("secretsmanager", region_name="us-west-2")
    arn = client.create_secret(Name="carmodpicker-test/app", SecretString=json.dumps(payload))["ARN"]
    return client, arn


def import_fresh_config() -> ModuleType:
    spec = importlib.util.spec_from_file_location("config_under_test", Path(config_module.__file__))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@mock_aws
def test_load_app_secrets_populates_env_before_settings_are_built(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, arn = create_app_secret({"SECRET_KEY": "from-secret", "SENTRY_DSN": "https://k@sentry.example/1"})
    monkeypatch.setenv("APP_SECRETS_ARN", arn)
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")

    applied = load_app_secrets(client=client)

    assert applied == {"SECRET_KEY": "from-secret", "SENTRY_DSN": "https://k@sentry.example/1"}
    assert os.environ["SECRET_KEY"] == "from-secret"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        built = Settings()
    assert built.SECRET_KEY == "from-secret"
    assert built.SENTRY_DSN == "https://k@sentry.example/1"
    assert not [w for w in caught if "SECRET_KEY is empty" in str(w.message)]


@mock_aws
def test_load_app_secrets_logs_and_raises_when_secret_unreadable(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("APP_SECRETS_ARN", MISSING_SECRET_ARN)

    with caplog.at_level(logging.ERROR, logger="app.core.secrets"):
        with pytest.raises(ClientError):
            load_app_secrets()

    assert "Failed to load application secrets" in caplog.text
    assert "SECRET_KEY" not in os.environ


@mock_aws
def test_load_app_secrets_rejects_non_object_payload(clean_env: None) -> None:
    client = boto3.client("secretsmanager", region_name="us-west-2")
    arn = client.create_secret(Name="carmodpicker-test/app", SecretString=json.dumps(["not", "a", "dict"]))["ARN"]

    with pytest.raises(ValueError):
        load_app_secrets(secret_arn=arn, client=client)


def test_load_app_secrets_is_noop_without_arn(clean_env: None) -> None:
    assert load_app_secrets() == {}
    assert "SECRET_KEY" not in os.environ


@mock_aws
def test_config_module_overlays_secrets_before_constructing_settings(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, arn = create_app_secret({"SECRET_KEY": "from-secret", "SENTRY_DSN": ""})
    monkeypatch.setenv("APP_SECRETS_ARN", arn)
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fresh = import_fresh_config()

    # Resolved on read, not at import, and an absent key reads as empty.
    assert fresh.settings.SECRET_KEY == "from-secret"
    assert fresh.settings.SENTRY_DSN == ""
    assert not [w for w in caught if "SECRET_KEY is empty" in str(w.message)]


@mock_aws
def test_config_module_imports_without_reading_the_secret(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Importing config makes no Secrets Manager call, even when the ARN is set
    and unreadable.

    This is the contract the per domain split needs: every entrypoint must be
    importable with no AWS credentials and no network so the route contract test
    can import all nine of them. The failure moved from import time to the first
    read of a secret.
    """
    monkeypatch.setenv("APP_SECRETS_ARN", MISSING_SECRET_ARN)

    fresh = import_fresh_config()

    assert fresh.settings.APP_SECRETS_ARN == MISSING_SECRET_ARN


@mock_aws
def test_reading_a_secret_fails_loudly_when_the_secret_is_unreadable(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The loud failure is preserved, just deferred to the point of use."""
    monkeypatch.setenv("APP_SECRETS_ARN", MISSING_SECRET_ARN)
    fresh = import_fresh_config()

    with caplog.at_level(logging.ERROR, logger="app.core.secrets"):
        with pytest.raises(ClientError):
            _ = fresh.settings.SECRET_KEY

    assert "Failed to load application secrets" in caplog.text


@mock_aws
def test_require_secrets_raises_when_a_secret_is_absent(clean_env: None) -> None:
    from app.core.config import Settings

    settings = Settings()

    with pytest.raises(ValueError, match="SECRET_KEY"):
        settings.require_secrets("SECRET_KEY")


@mock_aws
def test_require_secrets_passes_when_the_secret_resolves(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings

    _, arn = create_app_secret({"SECRET_KEY": "from-secret"})
    monkeypatch.setenv("APP_SECRETS_ARN", arn)

    settings = Settings()

    settings.require_secrets("SECRET_KEY")
    assert settings.SECRET_KEY == "from-secret"


def test_require_secrets_rejects_an_unknown_name(clean_env: None) -> None:
    from app.core.config import Settings

    with pytest.raises(ValueError, match="Unknown secret"):
        Settings().require_secrets("NOT_A_SECRET")


def test_env_var_wins_over_the_secret(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """An environment variable short circuits the fetch entirely, which is what
    keeps local development and the test suite free of AWS."""
    from app.core.config import Settings

    monkeypatch.setenv("APP_SECRETS_ARN", MISSING_SECRET_ARN)
    monkeypatch.setenv("SECRET_KEY", "from-env")

    assert Settings().SECRET_KEY == "from-env"


@mock_aws
def test_apply_app_secrets_sets_env_and_settings(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    client, arn = create_app_secret({"SECRET_KEY": "from-secret", "SENTRY_DSN": "https://k@sentry.example/1"})
    monkeypatch.setenv("APP_SECRETS_ARN", arn)

    settings = Settings(SECRET_KEY="", SENTRY_DSN="")
    applied = apply_app_secrets(settings, client=client)

    assert applied == {"SECRET_KEY": "from-secret", "SENTRY_DSN": "https://k@sentry.example/1"}
    assert settings.SECRET_KEY == "from-secret"
    assert settings.SENTRY_DSN == "https://k@sentry.example/1"
    assert os.environ["SECRET_KEY"] == "from-secret"
    assert os.environ["SENTRY_DSN"] == "https://k@sentry.example/1"


@mock_aws
def test_apply_app_secrets_skips_null_and_unknown_fields(clean_env: None) -> None:
    client, arn = create_app_secret({"SECRET_KEY": None, "NOT_A_SETTING": "x", "ACCESS_TOKEN_EXPIRE_MINUTES": 42})

    settings = Settings(SECRET_KEY="")
    applied = apply_app_secrets(settings, secret_arn=arn, client=client)

    assert applied == {"NOT_A_SETTING": "x", "ACCESS_TOKEN_EXPIRE_MINUTES": "42"}
    assert settings.SECRET_KEY == ""
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 42
    assert os.environ["NOT_A_SETTING"] == "x"
    assert "SECRET_KEY" not in os.environ


def test_apply_app_secrets_is_noop_without_arn(clean_env: None) -> None:
    settings = Settings(SECRET_KEY="unchanged")

    assert apply_app_secrets(settings) == {}
    assert settings.SECRET_KEY == "unchanged"
    assert "SECRET_KEY" not in os.environ


def test_config_imports_with_no_aws_credentials_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """The prerequisite for the per domain split.

    `app.core.config` used to call Secrets Manager at import, which made the
    module un importable without credentials and would have made the nine per
    domain entrypoints un importable by the route contract test. Importing it
    with every AWS variable stripped and an ARN set must now succeed and make no
    call. Runs outside `mock_aws` on purpose: any real call would fail here.
    """
    for name in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
        "AWS_DEFAULT_REGION",
        "AWS_REGION",
        "SECRET_KEY",
        "SENTRY_DSN",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_SECRETS_ARN", MISSING_SECRET_ARN)
    reset_cache()

    fresh = import_fresh_config()

    assert fresh.settings.APP_SECRETS_ARN == MISSING_SECRET_ARN


# --- The shared loader is the one that fetches ----------------------------------
#
# `app.core.secrets` is a thin adapter over `webbpulse.config.load_json_secret`:
# the boto3 client, the `json.loads` and the per-ARN cache all live in the shared
# package now. These tests assert the properties that adapter has to keep, and
# they count calls rather than trust the code, because the whole point of the
# lazy path is a number of Secrets Manager calls (zero at import, one per
# execution environment thereafter) and only counting can see it.


class CallCountingSecretsClient:
    """A stand-in for the shared loader's boto3 client that counts its calls.

    Patched over `webbpulse.config._secrets_client` so the adapter reaches it
    through the ordinary `load_json_secret` path, cache and all, rather than
    through the injected-client branch. That is the path production takes, so it
    is the one worth counting.
    """

    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls = 0

    def get_secret_value(self, SecretId: str) -> dict[str, str]:  # noqa: N803 - botocore's spelling
        self.calls += 1
        return {"SecretString": json.dumps(self.payload)}


@pytest.fixture
def counting_client(monkeypatch: pytest.MonkeyPatch):
    """Install a call-counting client under the shared loader and hand it back.

    The shared loader caches its client with an `lru_cache`, so the patch has to
    replace that function rather than the client it returns, and both caches are
    cleared on the way in and on the way out. Nothing here touches AWS.
    """

    def install(payload: object) -> CallCountingSecretsClient:
        client = CallCountingSecretsClient(payload)
        # Patched at `boto3.client` rather than over `_secrets_client` itself:
        # the shared loader's `reset_secret_cache` calls `.cache_clear()` on that
        # function, so replacing it with a plain callable would break the very
        # reset these tests exercise. Patching what it constructs leaves the
        # `lru_cache` intact and still means no AWS is reached.
        monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: client)
        reset_cache()
        return client

    yield install
    reset_cache()


# Modules whose import must cost nothing: the settings, the composition layer,
# and every per domain entrypoint.
ENTRYPOINT_IMPORT_TARGETS = [
    "app.core.config",
    "app.composition.app",
    "app.composition.domains",
    "app.composition.wiring",
] + [f"app.entrypoints.{module}" for module in sorted(ENTRYPOINT_MODULES.values())]

# Import the named module in a fresh interpreter with `boto3.client` replaced by
# something that raises, then report whether it was reached. A fetch on the
# import path is therefore a hard failure rather than a count to compare, and
# because the interpreter is fresh it cannot be confused by a module another
# test reloaded. Printed as JSON on the last line so an import-time log line on
# stdout cannot corrupt the result.
NO_FETCH_PROBE = """
import json, boto3


def _forbidden(*args, **kwargs):
    raise AssertionError("boto3.client was called during import")


boto3.client = _forbidden
import {module}  # noqa: E402
print(json.dumps({{"imported": "{module}"}}))
"""


def run_probe(code: str, env: dict[str, str] | None = None) -> dict[str, object]:
    """Run one snippet in a fresh interpreter with an all but empty environment.

    The stripped environment is the point: no credentials, no region, nothing
    but what the interpreter itself needs. Any real AWS call would fail here,
    which is a second line of defence behind the patched `boto3.client`.
    """
    environment = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(BACKEND),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    environment.update(env or {})
    result = subprocess.run(  # nosec B603 - fixed argv, no shell
        [sys.executable, "-c", code],
        cwd=str(BACKEND),
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, f"subprocess failed:\n{result.stderr}"
    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("module_name", ENTRYPOINT_IMPORT_TARGETS)
def test_importing_a_module_makes_no_secrets_manager_call(module_name: str) -> None:
    """Importing the settings, the composition layer or any per domain
    entrypoint fetches nothing.

    With an ARN configured and a `boto3.client` that raises if it is touched,
    the import must still succeed: nothing on the import path reads a
    secret-backed field. Importing the module is what a Lambda cold start does
    before the handler is ever called, so a fetch here would be a Secrets
    Manager call on the cold start of every function, one of which is meant to
    run with no `secretsmanager:GetSecretValue` grant at all.
    """
    probe = run_probe(
        NO_FETCH_PROBE.format(module=module_name),
        env={"APP_SECRETS_ARN": MISSING_SECRET_ARN},
    )

    assert probe["imported"] == module_name


def test_first_read_fetches_once_and_later_reads_do_not(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, counting_client
) -> None:
    """One fetch per execution environment, no matter how many reads.

    Three fields across two settings objects is one call: the blob is cached, so
    a warm Lambda invocation makes no Secrets Manager call at all and reading
    `SECRET_KEY` on every request costs nothing after the first.
    """
    client = counting_client(
        {"SECRET_KEY": "from-secret", "SENTRY_DSN": "https://k@sentry.example/1", "EXTENSION_API_KEY": "ext-key"}
    )
    monkeypatch.setenv("APP_SECRETS_ARN", "arn:aws:secretsmanager:us-west-2:123456789012:secret:cmp/app-AbCdEf")

    settings = Settings()
    assert client.calls == 0

    assert settings.SECRET_KEY == "from-secret"
    assert client.calls == 1

    assert settings.SECRET_KEY == "from-secret"
    assert settings.SENTRY_DSN == "https://k@sentry.example/1"
    assert settings.EXTENSION_API_KEY == "ext-key"
    assert Settings().SECRET_KEY == "from-secret"
    assert client.calls == 1


def test_reset_cache_forces_a_refetch(clean_env: None, monkeypatch: pytest.MonkeyPatch, counting_client) -> None:
    """`reset_cache` clears the shared loader's cache as well as the local map.

    Clearing only the local map would refill it from the shared loader's stale
    parse and the second read would still see the old value, which is what makes
    this worth asserting on the value and not only on the call count.
    """
    client = counting_client({"SECRET_KEY": "first"})
    monkeypatch.setenv("APP_SECRETS_ARN", "arn:aws:secretsmanager:us-west-2:123456789012:secret:cmp/app-AbCdEf")

    assert Settings().SECRET_KEY == "first"
    assert client.calls == 1

    client.payload = {"SECRET_KEY": "second"}
    assert Settings().SECRET_KEY == "first"
    assert client.calls == 1

    reset_cache()

    assert Settings().SECRET_KEY == "second"
    assert client.calls == 2


def test_malformed_secret_raises_a_value_error(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, counting_client
) -> None:
    """A JSON array is not a JSON object, and reading a field says so.

    The shared loader raises `SecretNotJsonObjectError`, which subclasses
    `ValueError`, so this is the same error type the local parse used to raise
    and every existing `pytest.raises(ValueError)` still holds.
    """
    counting_client(["not", "a", "dict"])
    monkeypatch.setenv("APP_SECRETS_ARN", "arn:aws:secretsmanager:us-west-2:123456789012:secret:cmp/app-AbCdEf")

    with pytest.raises(ValueError):
        _ = Settings().SECRET_KEY

    assert issubclass(SecretNotJsonObjectError, ValueError)


def test_malformed_secret_through_an_injected_client_raises_the_same_error(clean_env: None) -> None:
    """The injected-client branch agrees with the shared loader on what is bad.

    `_fetch_with` exists because `load_json_secret` owns its client and leaves no
    seam for one passed in. Since it repeats the checks rather than sharing them,
    it is worth asserting the two paths raise the same type on the same input.
    """
    client = CallCountingSecretsClient(["not", "a", "dict"])

    with pytest.raises(ValueError):
        fetch_app_secrets(
            secret_arn="arn:aws:secretsmanager:us-west-2:123456789012:secret:cmp/app-AbCdEf", client=client
        )


def test_no_arn_makes_no_call_at_all(clean_env: None, counting_client) -> None:
    """Local development and the suite: no ARN, no client, no AWS.

    The env-var path short circuits before the fetch, which is what keeps a
    checkout with no AWS credentials working without stubbing anything.
    """
    client = counting_client({"SECRET_KEY": "from-secret"})

    assert Settings().SECRET_KEY == ""
    assert fetch_app_secrets() == {}
    assert client.calls == 0
