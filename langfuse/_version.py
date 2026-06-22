from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version


@lru_cache(maxsize=1)
def get_langfuse_version() -> str:
    for distribution_name in ("sea-traces", "langfuse"):
        try:
            return version(distribution_name)
        except PackageNotFoundError:
            continue

    return "0.0.0"


__version__ = get_langfuse_version()
