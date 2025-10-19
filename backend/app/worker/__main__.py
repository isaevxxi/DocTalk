"""ARQ worker entry point."""

from arq import run_worker

from app.worker.arq_config import WorkerSettings


def main() -> None:
    """Run ARQ worker."""
    run_worker(WorkerSettings)


if __name__ == "__main__":
    main()
