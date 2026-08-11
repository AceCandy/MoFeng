from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "app/api/routers/llm_config.py"


def _source() -> str:
    return ROUTER.read_text(encoding="utf-8")


def test_provider_model_and_stage_route_endpoints_exist():
    source = _source()

    assert '@router.get("/providers"' in source
    assert '@router.post("/providers"' in source
    assert '@router.patch("/providers/{provider_id}"' in source
    assert '@router.delete("/providers/{provider_id}"' in source
    assert '@router.get("/providers/{provider_id}/models"' in source
    assert '@router.get("/user-models"' in source
    assert '@router.post("/user-models"' in source
    assert '@router.patch("/user-models/{model_id}"' in source
    assert '@router.delete("/user-models/{model_id}"' in source
    assert '@router.get("/stage-routes"' in source
    assert '@router.put("/stage-routes"' in source


def test_new_endpoints_require_current_user():
    source = _source()

    for name in [
        "list_providers",
        "create_provider",
        "patch_provider",
        "delete_provider",
        "list_provider_models",
        "list_user_models",
        "create_user_model",
        "patch_user_model",
        "delete_user_model",
        "list_stage_routes",
        "put_stage_routes",
    ]:
        block = source.split(f"async def {name}", 1)[1].split(") ->", 1)[0]
        assert "current_user: UserInDB = Depends(get_current_user)" in block
