"""Names-only configuration and filesystem boundary enforcement."""
import os
from pathlib import Path
from typing import Literal
from pydantic import Field
from .models import Model
from .errors import require

CAPABILITIES = {"read", "propose", "write", "decide", "maintain", "registry"}

def contained(root: Path, relative: str) -> Path:
    part = Path(relative)
    require(not part.anchor and not part.is_absolute() and ".." not in part.parts and ":" not in relative,
            "FORBIDDEN", "Use a contained relative path.", 403)
    root = root.resolve()
    dest = root / part
    current = dest
    while current != root:
        require(not current.is_symlink() and not current.is_junction(),
                "FORBIDDEN", "Linked paths are not allowed.", 403)
        current = current.parent
    require(dest.resolve().is_relative_to(root), "FORBIDDEN", "Path is outside the data root.", 403)
    return dest

class PrincipalConfig(Model):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,47}$")
    token_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    projects: list[str] = Field(default_factory=list)
    capabilities: list[Literal["read", "propose", "write", "decide", "maintain", "registry"]]

class Config(Model):
    schema_version: Literal[1] = 1
    data_root: str = Field(default_factory=lambda: str(Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "DecisionTracking"))
    auth_store: str | None = None
    managed_idle: bool = False
    idle_timeout_minutes: int = Field(default=90, ge=30, le=240)
    local_storage_confirmed: bool = False
    port: int = Field(default=8765, ge=1024, le=65535)
    principals: list[PrincipalConfig] = Field(default_factory=lambda: [
        PrincipalConfig(id="operator", token_env="DT_OPERATOR_TOKEN", projects=["*"], capabilities=sorted(CAPABILITIES))])

    @property
    def root(self):
        p = Path(self.data_root).absolute()
        require(not str(p).startswith(("\\\\", "//")) and not any("onedrive" in x.lower() for x in p.parts),
                "FORBIDDEN", "Active data must be on local nonsynchronized storage.", 403)
        require(self.local_storage_confirmed, "VALIDATION_ERROR",
                "Confirm local nonsynchronized data storage in configuration.")
        for q in [p, *p.parents]:
            require(not q.is_symlink() and not q.is_junction(), "FORBIDDEN", "Data root may not traverse linked paths.", 403)
        return p.resolve()

def load_config(path):
    path = Path(path).resolve()
    cfg = Config.model_validate_json(path.read_text(encoding="utf-8"))
    if not Path(cfg.data_root).is_absolute():
        cfg.data_root = str(path.parent / cfg.data_root)
    if cfg.auth_store and not Path(cfg.auth_store).is_absolute():cfg.auth_store=str(path.parent/cfg.auth_store)
    return cfg
