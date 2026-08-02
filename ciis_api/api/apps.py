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
        if "pytest" in sys.modules:
            return
        if os.environ.get("RUN_MAIN") == "true" or "RUN_MAIN" not in os.environ:
            from . import engine

            engine.warm_start()
