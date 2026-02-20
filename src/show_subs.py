from src.orchestrator import Orchestrator


def main() -> None:
    orchestrator = Orchestrator()
    orchestrator.prettyprint_subscriptions()


if __name__ == "__main__":
    main()
