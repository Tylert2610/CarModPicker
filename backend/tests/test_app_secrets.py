import importlib.util
import json
import logging
import os
import warnings
from pathlib import Path
from types import ModuleType

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from app.core import config as config_module
from app.core.config import Settings
from app.core.secrets import apply_app_secrets, load_app_secrets, reset_cache

MISSING_SECRET_ARN = "arn:aws:secretsmanager:us-west-2:123456789012:secret:carmodpicker-test/missing-AbCdEf"


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
