"""
scripts/run_heartbeat.py

Manual heartbeat trigger for testing.
Starts the heartbeat scheduler and keeps it running.
Press Ctrl+C to stop.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


async def main() -> None:
    from src.core.heartbeat import start_scheduler, stop_scheduler, list_jobs

    print("Starting heartbeat scheduler...")
    await start_scheduler()

    jobs = list_jobs()
    print(f"\nRegistered {len(jobs)} heartbeat jobs:")
    for job in jobs:
        print(f"  {job['id']}: next_run={job['next_run']}")

    print("\nScheduler running. Press Ctrl+C to stop.")

    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, stop_event.set)
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)

    await stop_event.wait()

    print("\nStopping scheduler...")
    await stop_scheduler()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
