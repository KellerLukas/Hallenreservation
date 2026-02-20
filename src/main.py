from src.orchestrator import Orchestrator
from src.utils.setup_logging import setup_logging_to_file


setup_logging_to_file()


def main() -> None:
    orchestrator = Orchestrator()
    orchestrator.run()


if __name__ == "__main__":
    main()
