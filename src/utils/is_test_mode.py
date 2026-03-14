import os

TEST_FILE_PREFIX = "test_"


def is_test_mode() -> bool:
    return os.getenv("TESTMODE", "false").lower() == "true"
