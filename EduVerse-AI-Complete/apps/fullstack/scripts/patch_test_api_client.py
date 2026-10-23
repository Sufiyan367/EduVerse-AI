from pathlib import Path

# 1. Update test_api.py fixture
test_api_path = Path("S:/SY/SEM 3/MP/EduVerse_Web_Demo/backend/tests/test_api.py")
content = test_api_path.read_text(encoding="utf-8")

old_client = """@pytest_asyncio.fixture
async def client(config: Config, store: Any) -> AsyncIterator[httpx.AsyncClient]:
    \"\"\"API client with the mock provider configured.

    The worker pool is deliberately not started — tests drain jobs explicitly with
    :func:`drain`, so assertions run against a finished pipeline instead of polling.
    \"\"\"
    app = create_app(config)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        yield client"""

new_client = """@pytest_asyncio.fixture
async def client(config: Config, store: Any) -> AsyncIterator[httpx.AsyncClient]:
    \"\"\"API client with the mock provider configured and authenticated demo session.

    The worker pool is deliberately not started — tests drain jobs explicitly with
    :func:`drain`, so assertions run against a finished pipeline instead of polling.
    \"\"\"
    from quicklearn import auth
    from quicklearn.db.session import session_scope

    app = create_app(config)
    transport = httpx.ASGITransport(app=app)

    with session_scope() as session:
        demo_user = auth.seed_default_demo_user(session)
        token = auth.create_access_token(demo_user.id, demo_user.username, demo_user.email)

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1", headers=headers) as client:
        yield client"""

if old_client in content:
    content = content.replace(old_client, new_client, 1)
    test_api_path.write_text(content, encoding="utf-8")
    print("Updated test_api.py client fixture with authenticated demo token.")
else:
    print("old_client not found in test_api.py")

# 2. Strict auth on sources.py (anonymous upload rejected)
ROOT = Path("S:/SY/SEM 3/MP/EduVerse_Web_Demo/backend/quicklearn")
sources_p = ROOT / "api/sources.py"
s_code = sources_p.read_text(encoding="utf-8")

old_upload = """    source_id = await run_db(
        acquire.create_source,
        title=Path(filename).stem.replace("_", " ").replace("-", " ").strip() or filename,
        kind=kind,
        origin=SourceOrigin.UPLOAD,
        folder_id=folder_id,
        user_id=user.id if user else None,
        original_filename=filename,
    )"""

new_upload = """    if user is None:
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

if old_upload in s_code:
    s_code = s_code.replace(old_upload, new_upload, 1)
    sources_p.write_text(s_code, encoding="utf-8")
    print("Enforced strict authentication on upload_source in sources.py")

# 3. Strict auth on system.py (anonymous settings mutation rejected)
sys_p = ROOT / "api/system.py"
sys_code = sys_p.read_text(encoding="utf-8")

old_sys = """@router.patch("/settings")
def patch_settings(payload: SettingsPatch, user: User | None = Depends(get_optional_user)) -> dict[str, Any]:
    import os
    if (os.environ.get("EDUVERSE_ENV") == "production" or os.environ.get("ENVIRONMENT") == "production") and user is None:
        raise ForbiddenError("Authentication required to modify system settings in production.")"""

new_sys = """@router.patch("/settings")
def patch_settings(payload: SettingsPatch, user: User | None = Depends(get_optional_user)) -> dict[str, Any]:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required to modify system settings.")"""

if old_sys in sys_code:
    sys_code = sys_code.replace(old_sys, new_sys, 1)
    sys_p.write_text(sys_code, encoding="utf-8")
    print("Enforced strict authentication on patch_settings in system.py")
