"""Integration tests for the CIIS API layer.

These tests exercise the API <-> engine seam end to end (intake -> upload ->
enrichment -> analyze -> report) using a fast in-memory OCR fake and a
temporary engine storage directory, so no PaddleOCR install or real image
corpus is required. See ``conftest.py`` for the shared fixtures.
"""
