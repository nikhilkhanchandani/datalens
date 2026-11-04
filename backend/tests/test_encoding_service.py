"""Unit tests for CSV text-encoding detection."""

from __future__ import annotations

import pytest

from app.core.exceptions import EncodingDetectionError
from app.services.encoding_service import detect_encoding


def test_plain_utf8_is_detected(tmp_path) -> None:
    path = tmp_path / "plain.csv"
    path.write_bytes("name,city\nAlice,Zürich\n".encode("utf-8"))

    detected = detect_encoding(path)

    assert detected.codec_name == "utf-8-sig"
    assert detected.display_name == "UTF-8"


def test_utf8_with_bom_is_detected(tmp_path) -> None:
    path = tmp_path / "bom.csv"
    path.write_bytes("name,city\nAlice,Zürich\n".encode("utf-8-sig"))

    detected = detect_encoding(path)

    assert detected.codec_name == "utf-8-sig"
    assert detected.display_name == "UTF-8 (with BOM)"


def test_cp1252_with_curly_quotes_and_accents_is_detected(tmp_path) -> None:
    path = tmp_path / "cp1252.csv"
    content = (
        "name,note\n"
        "\"O’Brien\",\"price was €25 — café service, we’ll return\"\n"
        "\"André\",\"total charged: €12.50 for the résumé review\"\n"
        "\"Renée\",\"she quoted “€9.99” and smiled warmly\"\n"
    )
    path.write_bytes(content.encode("cp1252"))

    detected = detect_encoding(path)

    assert detected.codec_name == "cp1252"
    assert detected.display_name == "Windows-1252"


def test_binary_content_raises_encoding_detection_error(tmp_path) -> None:
    path = tmp_path / "binary.bin"
    path.write_bytes(bytes((i * 37 + 11) % 256 for i in range(4000)))

    with pytest.raises(EncodingDetectionError):
        detect_encoding(path)
