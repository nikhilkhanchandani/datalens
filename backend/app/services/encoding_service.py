"""CSV text-encoding detection.

`pd.read_csv` must be told the correct text encoding up front — get it
wrong and you either crash with a `UnicodeDecodeError`, or (worse) it
"succeeds" while silently producing mojibake that corrupts every
downstream statistic. This module resolves the encoding once at upload
time so the rest of the pipeline can just trust the result.
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass
from pathlib import Path

from charset_normalizer import from_bytes

from app.core.exceptions import EncodingDetectionError

# Enough bytes to give the statistical detector something to work with,
# without reading an entire large file twice (once to detect, once for the
# real Pandas parse). Demo-scale CSVs are well under this anyway.
_SAMPLE_SIZE = 1_000_000

# We only attempt to recognize the legacy single-byte encodings the spec
# calls out by name. Restricting the candidate set (rather than letting the
# detector choose from its full ~30-encoding catalog) avoids exactly the
# failure mode this module exists to prevent: confidently mislabeling text
# as some rarely-used code page (e.g. Windows-1250/Central European) just
# because it happens to also decode without error.
_CANDIDATE_LEGACY_ENCODINGS = ["cp1252", "iso8859_1"]

# charset-normalizer's "chaos" score: the fraction of the decoded sample
# that looks like noise/mojibake rather than plausible text (0 = clean,
# 1 = garbage). A detected encoding is only trusted below this threshold;
# above it we fail loudly instead of guessing.
_MAX_ACCEPTABLE_CHAOS = 0.2

_DISPLAY_NAMES = {
    "cp1252": "Windows-1252",
    "iso8859_1": "ISO-8859-1",
}


@dataclass
class DetectedEncoding:
    codec_name: str  # passed straight to pd.read_csv(..., encoding=...)
    display_name: str  # shown in the UI, e.g. "Windows-1252"


def detect_encoding(path: Path) -> DetectedEncoding:
    """Resolve the text encoding of a stored CSV file.

    Raises `EncodingDetectionError` if neither UTF-8 nor a recognized
    legacy encoding can explain the file's bytes with reasonable
    confidence (e.g. the "file" is actually binary content).
    """
    raw = path.read_bytes()
    sample = raw[:_SAMPLE_SIZE]

    utf8_result = _try_utf8(raw, sample)
    if utf8_result is not None:
        return utf8_result

    return _detect_legacy_encoding(sample)


def _try_utf8(raw: bytes, sample: bytes) -> DetectedEncoding | None:
    """UTF-8 (optionally with a BOM) is the preferred, expected encoding.

    `utf-8-sig` decodes plain UTF-8 identically to `utf-8` and additionally
    strips a leading BOM if present, so trying it first covers both cases
    in a single branch.
    """
    try:
        sample.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None

    has_bom = raw.startswith(codecs.BOM_UTF8)
    return DetectedEncoding(
        codec_name="utf-8-sig",
        display_name="UTF-8 (with BOM)" if has_bom else "UTF-8",
    )


def _detect_legacy_encoding(sample: bytes) -> DetectedEncoding:
    """Fall back to statistical detection for common legacy encodings.

    We deliberately do NOT just try `latin-1` and call it a day: every
    byte value is a *valid* Latin-1 character, so a plain `.decode("latin-1")`
    call "succeeds" even on binary garbage — it can never signal failure.
    charset-normalizer instead scores each candidate encoding by how much
    of the decoded text looks like noise vs. real language (its
    "chaos"/"coherence" metrics), so garbage is rejected rather than
    silently accepted as some real encoding.
    """
    best_match = from_bytes(sample, cp_isolation=_CANDIDATE_LEGACY_ENCODINGS).best()

    if best_match is None or best_match.chaos > _MAX_ACCEPTABLE_CHAOS:
        raise EncodingDetectionError(
            "Could not reliably determine this file's text encoding. "
            "Please export/save the CSV as UTF-8 and re-upload."
        )

    codec_name = best_match.encoding
    display_name = _DISPLAY_NAMES.get(codec_name, codec_name)
    return DetectedEncoding(codec_name=codec_name, display_name=display_name)
