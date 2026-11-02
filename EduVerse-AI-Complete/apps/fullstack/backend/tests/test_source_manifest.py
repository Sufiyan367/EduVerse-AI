"""Unit and cross-user isolation tests for Source Manifest System Note."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from quicklearn.db.enums import SourceKind, SourceOrigin, SourceStatus
from quicklearn.db.models import Base, Segment, Source, User
from quicklearn.rag.manifest import (
    SourceManifestItem,
    UserSourceManifest,
    get_user_source_manifest,
    render_manifest_note,
)
from quicklearn import prompts


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        # Create User 1 and User 2
        u1 = User(id=1, email="student1@eduverse.ai", username="student1", full_name="Student One", hashed_password="hash")
        u2 = User(id=2, email="student2@eduverse.ai", username="student2", full_name="Student Two", hashed_password="hash")
        session.add_all([u1, u2])
        session.flush()

        # User 1 has two sources (one ready, one processing)
        s1 = Source(
            id=10,
            user_id=1,
            title="Operating Systems Concepts.pdf",
            kind=SourceKind.PDF,
            origin=SourceOrigin.UPLOAD,
            status=SourceStatus.READY,
            page_count=24,
            size_bytes=1048576,
        )
        s2 = Source(
            id=11,
            user_id=1,
            title="Database Internals.pdf",
            kind=SourceKind.PDF,
            origin=SourceOrigin.UPLOAD,
            status=SourceStatus.PROCESSING,
            page_count=15,
            size_bytes=524288,
        )
        # User 2 has one failed source and one ready source with duplicate name
        s3 = Source(
            id=20,
            user_id=2,
            title="Secret Research Notes.pdf",
            kind=SourceKind.PDF,
            origin=SourceOrigin.UPLOAD,
            status=SourceStatus.FAILED,
            error="Corrupt header bytes",
            page_count=0,
            size_bytes=12000,
        )
        s4 = Source(
            id=21,
            user_id=2,
            title="Secret Research Notes.pdf",  # Duplicate title
            kind=SourceKind.PDF,
            origin=SourceOrigin.UPLOAD,
            status=SourceStatus.READY,
            page_count=8,
            size_bytes=45000,
        )
        session.add_all([s1, s2, s3, s4])
        session.flush()

        # Add segments for User 1's ready source
        seg1 = Segment(source_id=10, index=0, page_no=1, text="Introduction to CPU scheduling.")
        seg2 = Segment(source_id=10, index=1, page_no=2, text="Multi-level feedback queues.")
        session.add_all([seg1, seg2])
        session.commit()

        yield session


def test_manifest_user_isolation(test_db):
    """User 1's manifest must contain ONLY User 1's sources."""
    manifest_u1 = get_user_source_manifest(user_id=1, session=test_db)
    assert manifest_u1.user_id == 1
    assert manifest_u1.total_sources == 2
    assert manifest_u1.ready_sources == 1
    assert manifest_u1.pending_sources == 1
    assert manifest_u1.failed_sources == 0
    assert manifest_u1.total_pages == 39
    assert manifest_u1.total_segments == 2

    titles_u1 = [item.title for item in manifest_u1.items]
    assert "Operating Systems Concepts.pdf" in titles_u1
    assert "Database Internals.pdf" in titles_u1
    assert "Secret Research Notes.pdf" not in titles_u1  # User 2's source never leaks!


def test_manifest_user2_and_duplicate_titles(test_db):
    """User 2's manifest isolates User 2's files and cleanly handles duplicate titles and failed status."""
    manifest_u2 = get_user_source_manifest(user_id=2, session=test_db)
    assert manifest_u2.user_id == 2
    assert manifest_u2.total_sources == 2
    assert manifest_u2.ready_sources == 1
    assert manifest_u2.failed_sources == 1

    note = render_manifest_note(manifest_u2)
    # Both sources have the same title, so IDs must be appended to disambiguate
    assert "Source ID: 20" in note
    assert "Source ID: 21" in note
    assert "Ingestion Failed: Corrupt header bytes" in note
    # User 1's files must NOT appear
    assert "Operating Systems Concepts.pdf" not in note


def test_manifest_empty_library(test_db):
    """A user with no uploaded sources receives a clear, honest empty inventory."""
    manifest_empty = get_user_source_manifest(user_id=999, session=test_db)
    assert manifest_empty.total_sources == 0
    assert manifest_empty.ready_sources == 0
    assert len(manifest_empty.items) == 0

    note = render_manifest_note(manifest_empty)
    assert "0 uploaded sources" in note
    assert "no documents are uploaded yet" in note


def test_manifest_scope_filtering(test_db):
    """Scoping to a specific source ID filters the manifest strictly to that source."""
    manifest_scoped = get_user_source_manifest(
        user_id=1,
        scope_type="source",
        scope_id=10,
        session=test_db,
    )
    assert manifest_scoped.total_sources == 1
    assert manifest_scoped.items[0].id == 10
    assert manifest_scoped.items[0].title == "Operating Systems Concepts.pdf"


def test_chat_system_prompt_renders_manifest(test_db):
    """Verify that chat_system template correctly renders the manifest note into the prompt."""
    manifest_u1 = get_user_source_manifest(user_id=1, session=test_db)
    note = render_manifest_note(manifest_u1)

    rendered = prompts.render(
        "chat_system",
        excerpts=[],
        scope_description="Entire Library",
        manifest_note=note,
    )

    assert "## Available Document Inventory" in rendered
    assert "Operating Systems Concepts.pdf" in rendered
    assert "Database Internals.pdf" in rendered
    assert "Inventory & file questions" in rendered
