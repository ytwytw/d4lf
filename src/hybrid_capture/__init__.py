"""Offline evidence fusion experiment; not connected to inventory capture or filtering."""

from src.hybrid_capture.fusion import Candidate, CaptureContext, Identity, compare_identity, fuse_evidence

__all__ = ["Candidate", "CaptureContext", "Identity", "compare_identity", "fuse_evidence"]
