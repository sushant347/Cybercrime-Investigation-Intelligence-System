import os
import sys

from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = "api"

    def ready(self) -> None:
        """Start warming the OCR/entity stack as soon as the app is loaded.

        Two things must not trigger it:

        * **The autoreloader's watcher process.** Under ``runserver`` only the
          child (``RUN_MAIN`` set) serves requests, so warming in the parent
          would load the models twice and double the memory for no benefit.
        * **Test runs.** The suite swaps in a canned OCR engine precisely so it
          never touches PaddleOCR; warming would load the real models anyway,
          on a thread, for tests that will not use them.
        """
        # Registering the deployment checks must happen even under pytest, so
        # the suite can assert on them; they do no work until `check` runs.
        # Imported for its @register side effects, hence import_module rather
        # than a plain import that would read as an unused name.
        import importlib

        importlib.import_module(".checks", __package__)

        if "pytest" in sys.modules:
            return
        if os.environ.get("RUN_MAIN") == "true" or "RUN_MAIN" not in os.environ:
            from . import engine

            self._close_orphaned_jobs()
            engine.warm_start()

    @staticmethod
    def _close_orphaned_jobs() -> None:
        """Retire jobs abandoned by a previous process (see ``Jobs.reconcile_orphaned``).

        Failure-isolated: the platform store lives under the engine's storage
        directory, which may not be readable yet in an odd deployment, and a
        bookkeeping problem must not stop the API from serving.
        """
        import logging

        try:
            from .store import jobs

            closed = jobs.reconcile_orphaned()
            if closed:
                logging.getLogger("ciis.engine").warning(
                    "closed %d job(s) abandoned by a previous process", closed
                )
        except Exception:  # noqa: BLE001
            logging.getLogger("ciis.engine").exception(
                "could not reconcile abandoned jobs"
            )
