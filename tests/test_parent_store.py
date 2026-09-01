from pathlib import Path

from prodrag.domain import ParentSection
from prodrag.parent_store import SQLiteParentStore


def _section(
    section_id: str,
    text: str,
    order: int,
    *,
    part: int = 1,
    part_count: int = 1,
    previous_parent_id: str | None = None,
    next_parent_id: str | None = None,
) -> ParentSection:
    return ParentSection(
        section_id=section_id,
        heading=f"Section {order}",
        text=text,
        order=order,
        part=part,
        part_count=part_count,
        previous_parent_id=previous_parent_id,
        next_parent_id=next_parent_id,
    )


def test_parent_store_persists_prunes_and_isolates_tenants(tmp_path: Path) -> None:
    path = tmp_path / "parents.sqlite3"
    store = SQLiteParentStore(path)
    store.upsert_revision(
        [
            _section("p1", "old one", 0, part_count=2, next_parent_id="p2"),
            _section(
                "p2",
                "old two",
                1,
                part=2,
                part_count=2,
                previous_parent_id="p1",
            ),
        ],
        tenant_id="acme",
        document_id="guide",
        checksum="revision-1",
        product="router",
        version="1.0",
    )
    store.upsert_revision(
        [_section("p1", "other tenant", 0)],
        tenant_id="other",
        document_id="guide",
        checksum="other-revision",
        product=None,
        version=None,
    )

    # Reopen the database to verify this is durable storage, not process memory.
    reopened = SQLiteParentStore(path)
    stored = reopened.get_parent(
        tenant_id="acme", document_id="guide", parent_id="p1"
    )
    assert stored is not None
    assert stored.text == "old one"
    assert stored.product == "router"
    assert stored.part == 1
    assert stored.part_count == 2
    assert stored.next_parent_id == "p2"

    reopened.upsert_revision(
        [_section("p2", "new two", 0), _section("p3", "new three", 1)],
        tenant_id="acme",
        document_id="guide",
        checksum="revision-2",
        product="router",
        version="2.0",
    )
    reopened.prune_revision(
        "revision-2", tenant_id="acme", document_id="guide"
    )

    assert (
        reopened.get_parent(tenant_id="acme", document_id="guide", parent_id="p1")
        is None
    )
    current = reopened.get_parent(
        tenant_id="acme", document_id="guide", parent_id="p2"
    )
    assert current is not None
    assert current.text == "new two"
    assert current.checksum == "revision-2"
    assert (
        reopened.get_parent(tenant_id="other", document_id="guide", parent_id="p1")
        is not None
    )
    assert reopened.ping() is True

    reopened.delete_document("guide", tenant_id="acme")
    assert (
        reopened.get_parent(tenant_id="acme", document_id="guide", parent_id="p2")
        is None
    )
    assert (
        reopened.get_parent(tenant_id="other", document_id="guide", parent_id="p1")
        is not None
    )
