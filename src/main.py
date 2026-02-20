from src.orchestrator import Orchestrator
from src.utils.setup_logging import setup_logging_to_file


# Note: may need to install this and reboot
# sudo sed -i 's/^# *\(de_CH.UTF-8 UTF-8\)/\1/' /etc/locale.gen
# sudo locale-gen
# sudo update-locale


setup_logging_to_file()


def main() -> None:
    orchestrator = Orchestrator()
    orchestrator.run()


if __name__ == "__main__":
    main()
