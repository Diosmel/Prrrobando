import os
from pathlib import Path

_BROWSER_DATA_ROOT = Path(
    os.environ.get("BROWSER_DATA_DIR", str(Path.home() / ".autogpt" / "browser"))
)
SESSIONS_DIR = _BROWSER_DATA_ROOT / "sessions"
DOWNLOADS_DIR = _BROWSER_DATA_ROOT / "downloads"


def ensure_browser_dirs() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


def build_llm(provider: str, model_name: str, api_key: str):
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model_name, api_key=api_key, max_tokens=8096)  # type: ignore[call-arg]
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model_name, api_key=api_key)  # type: ignore[call-arg]
    raise ValueError(
        f"Proveedor '{provider}' no soportado. Usa credenciales de Anthropic u OpenAI."
    )


def chromium_executable() -> str | None:
    """Return system chromium path if browser-use should use it instead of downloading."""
    system_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    if system_path and Path(system_path).exists():
        return system_path
    candidates = ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]
    return next((p for p in candidates if Path(p).exists()), None)
