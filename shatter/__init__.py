"""Shatter: controlled, auditable fragmentation of synthetic ingestion records."""
from .engine import shatter
from .schemas import FragmentationReport
__all__=['shatter','FragmentationReport']
