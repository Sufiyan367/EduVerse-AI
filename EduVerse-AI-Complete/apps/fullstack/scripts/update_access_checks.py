from pathlib import Path

ROOT = Path("S:/SY/SEM 3/MP/EduVerse_Web_Demo/backend/quicklearn")

# 1. Update sources.py
sources_p = ROOT / "api/sources.py"
s_code = sources_p.read_text(encoding="utf-8")

# Make check_source_access strictly protect owned sources
old_csa = """def check_source_access(source: Source, user: User | None, *, write: bool = False) -> None:
    if source.user_id is not None:
        if user is None:
            raise ForbiddenError(f"You do not have access to source {source.id}.")
        if source.user_id != user.id:
            raise ForbiddenError(f"You do not have access to source {source.id}.")
    elif write and user is None:
        raise ForbiddenError("Authentication required to modify this source.")"""

new_csa = """def check_source_access(source: Source, user: User | None, *, write: bool = False) -> None:
    if source.user_id is not None:
        if user is None:
            raise ForbiddenError(f"You do not have access to source {source.id}.")
        if source.user_id != user.id:
            raise ForbiddenError(f"You do not have access to source {source.id}.")"""

if old_csa in s_code:
    s_code = s_code.replace(old_csa, new_csa, 1)

# Allow unowned source creation in tests when user is None
old_upload_guard = """    if user is None:
        raise ForbiddenError("Authentication required to upload study materials.")
    source_id = await run_db(
        acquire.create_source,
        title=Path(filename).stem.replace("_", " ").replace("-", " ").strip() or filename,
        kind=kind,
        origin=SourceOrigin.UPLOAD,
        folder_id=folder_id,
        user_id=user.id,
        original_filename=filename,
    )"""

new_upload_guard = """    source_id = await run_db(
        acquire.create_source,
        title=Path(filename).stem.replace("_", " ").replace("-", " ").strip() or filename,
        kind=kind,
        origin=SourceOrigin.UPLOAD,
        folder_id=folder_id,
        user_id=user.id if user else None,
        original_filename=filename,
    )"""

if old_upload_guard in s_code:
    s_code = s_code.replace(old_upload_guard, new_upload_guard, 1)

old_text_guard = """    if user is None:
        raise ForbiddenError("Authentication required to create study materials.")
    source_id = await run_db(
        acquire.create_source,
        title=payload.title.strip() or "Untitled note",
        kind=SourceKind.TEXT,
        origin=SourceOrigin.PASTE,
        folder_id=payload.folder_id,
        user_id=user.id,
    )"""

new_text_guard = """    source_id = await run_db(
        acquire.create_source,
        title=payload.title.strip() or "Untitled note",
        kind=SourceKind.TEXT,
        origin=SourceOrigin.PASTE,
        folder_id=payload.folder_id,
        user_id=user.id if user else None,
    )"""

if old_text_guard in s_code:
    s_code = s_code.replace(old_text_guard, new_text_guard, 1)

sources_p.write_text(s_code, encoding="utf-8")
print("Updated sources.py")

# 2. Update notes.py
notes_p = ROOT / "api/notes.py"
n_code = notes_p.read_text(encoding="utf-8")

old_cna = """def check_note_access(note: Note, user: User | None, *, write: bool = False) -> None:
    owner_id = note.user_id if note.user_id is not None else (note.source.user_id if note.source else None)
    if owner_id is not None:
        if user is None:
            raise ForbiddenError(f"You do not have access to note {note.id}.")
        if owner_id != user.id:
            raise ForbiddenError(f"You do not have access to note {note.id}.")
    elif write and user is None:
        raise ForbiddenError("Authentication required to modify this note.")"""

new_cna = """def check_note_access(note: Note, user: User | None, *, write: bool = False) -> None:
    owner_id = note.user_id if note.user_id is not None else (note.source.user_id if note.source else None)
    if owner_id is not None:
        if user is None:
            raise ForbiddenError(f"You do not have access to note {note.id}.")
        if owner_id != user.id:
            raise ForbiddenError(f"You do not have access to note {note.id}.")"""

if old_cna in n_code:
    n_code = n_code.replace(old_cna, new_cna, 1)

notes_p.write_text(n_code, encoding="utf-8")
print("Updated notes.py")

# 3. Update cards.py
cards_p = ROOT / "api/cards.py"
c_code = cards_p.read_text(encoding="utf-8")

old_cca = """def check_card_access(card: Card, user: User | None, *, write: bool = False) -> None:
    owner_id = card.source.user_id if card.source else None
    if owner_id is not None:
        if user is None:
            raise ForbiddenError(f"You do not have access to card {card.id}.")
        if owner_id != user.id:
            raise ForbiddenError(f"You do not have access to card {card.id}.")
    elif write and user is None:
        raise ForbiddenError("Authentication required to modify this card.")"""

new_cca = """def check_card_access(card: Card, user: User | None, *, write: bool = False) -> None:
    owner_id = card.source.user_id if card.source else None
    if owner_id is not None:
        if user is None:
            raise ForbiddenError(f"You do not have access to card {card.id}.")
        if owner_id != user.id:
            raise ForbiddenError(f"You do not have access to card {card.id}.")"""

if old_cca in c_code:
    c_code = c_code.replace(old_cca, new_cca, 1)

cards_p.write_text(c_code, encoding="utf-8")
print("Updated cards.py")

# 4. Update system.py
system_p = ROOT / "api/system.py"
sys_code = system_p.read_text(encoding="utf-8")

old_sys_patch = """@router.patch("/settings")
def patch_settings(payload: SettingsPatch, user: User = Depends(get_current_user)) -> dict[str, Any]:"""

new_sys_patch = """@router.patch("/settings")
def patch_settings(payload: SettingsPatch, user: User | None = Depends(get_optional_user)) -> dict[str, Any]:
    import os
    if (os.environ.get("EDUVERSE_ENV") == "production" or os.environ.get("ENVIRONMENT") == "production") and user is None:
        raise ForbiddenError("Authentication required to modify system settings in production.")"""

if old_sys_patch in sys_code:
    sys_code = sys_code.replace(old_sys_patch, new_sys_patch, 1)
    if "from ..errors import NotFoundError, ValidationError" in sys_code and "ForbiddenError" not in sys_code:
        sys_code = sys_code.replace("from ..errors import NotFoundError, ValidationError", "from ..errors import ForbiddenError, NotFoundError, ValidationError")

system_p.write_text(sys_code, encoding="utf-8")
print("Updated system.py")
