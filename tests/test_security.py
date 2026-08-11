import pytest

from prodrag.config import Settings
from prodrag.security import authorize_tenant, require_query_key


def test_tenant_key_authenticates_only_its_tenant(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        tenant_query_api_keys={"acme": "a" * 32},
    )
    monkeypatch.setattr("prodrag.security.get_settings", lambda: settings)

    auth = require_query_key("a" * 32)

    assert auth.tenant_id == "acme"
    authorize_tenant(auth, "acme")
    with pytest.raises(Exception) as exc_info:
        authorize_tenant(auth, "other")
    assert exc_info.value.status_code == 403


def test_production_requires_tenant_keys_and_upload_scanning() -> None:
    with pytest.raises(ValueError, match="RAG_TENANT_ADMIN_API_KEYS"):
        Settings(
            _env_file=None,
            environment="production",
            oci_compartment_id="ocid1.compartment.oc1..example",
        )


def test_complete_production_security_configuration_is_valid() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        oci_compartment_id="ocid1.compartment.oc1..example",
        tenant_admin_api_keys={"acme": "a" * 32},
        tenant_query_api_keys={"acme": "q" * 32},
        uploads_prevalidated=True,
    )

    assert settings.environment == "production"
