from importlib.metadata import version

import langfuse
import sea_traces


def test_package_version_matches_distribution_metadata():
    assert langfuse.__version__ == version("sea-traces")


def test_sea_traces_version_matches_langfuse_compatibility_module():
    assert sea_traces.__version__ == langfuse.__version__
