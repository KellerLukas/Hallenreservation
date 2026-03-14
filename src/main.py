import logging
from src.orchestrator import Orchestrator
from src.utils.setup_logging import setup_logging_to_file
from src.utils.is_test_mode import is_test_mode

setup_logging_to_file()


def main() -> None:
    if is_test_mode():
        logging.info("Running in test mode")
    orchestrator = Orchestrator()
    orchestrator.run()


if __name__ == "__main__":
    main()
