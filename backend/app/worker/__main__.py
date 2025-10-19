"""ARQ worker entry point."""

from arq import run_worker

from app.worker.arq_config import WorkerSettings


def main() -> None:
    """Run ARQ worker."""
    # ARQ type stubs expect WorkerSettingsBase but accept subclasses at runtime
    run_worker(WorkerSettings)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
