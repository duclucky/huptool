import os


APP_VERSION = "1.4.7"
DEFAULT_UPDATE_MANIFEST_URL = os.environ.get("HUP_UPDATE_MANIFEST_URL", "").strip()


def get_update_manifest_url():
    env_url = os.environ.get("HUP_UPDATE_MANIFEST_URL", "").strip()
    if env_url:
        return env_url
    try:
        from config import get_app_dir

        url_file = os.path.join(get_app_dir(), "update_manifest_url.txt")
        if os.path.exists(url_file):
            with open(url_file, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return DEFAULT_UPDATE_MANIFEST_URL
