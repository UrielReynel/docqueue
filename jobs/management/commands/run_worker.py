import signal
import time

from django.core.management.base import BaseCommand

from jobs.worker import run_once


class Command(BaseCommand):
    help = "Process queued jobs. Runs until stopped, or once with --once."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Drain the queue once and exit")
        parser.add_argument(
            "--sleep", type=float, default=2.0, help="Seconds to wait when the queue is empty"
        )

    def handle(self, *args, once, sleep, **options):
        self._stop = False
        signal.signal(signal.SIGTERM, self._request_stop)
        signal.signal(signal.SIGINT, self._request_stop)

        while not self._stop:
            job = run_once()
            if job:
                self.stdout.write(f"{job.pk} {job.original_name}: {job.status} (attempt {job.attempts})")
                continue
            if once:
                break
            time.sleep(sleep)
        self.stdout.write("worker stopped")

    def _request_stop(self, *_):
        self._stop = True
