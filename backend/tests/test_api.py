"""End-to-end API tests for the dataset upload, profiling, quality, and
statistics flows."""

from __future__ import annotations

import io
import json


def _csv_bytes(content: str) -> bytes:
    return content.encode("utf-8")


def _upload(client, content: str, filename: str = "data.csv"):
    return client.post(
        "/api/datasets/upload",
        files={"file": (filename, io.BytesIO(_csv_bytes(content)), "text/csv")},
    )


def test_upload_valid_csv_returns_metadata(client) -> None:
    response = _upload(client, "name,age\nAlice,30\nBob,25\n", filename="people.csv")

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "people.csv"
    assert body["row_count"] == 2
    assert body["column_count"] == 2
    assert "id" in body


def test_upload_timestamp_is_labelled_utc(client) -> None:
    # A naive ISO string is parsed as local time by browsers, which shifted the
    # displayed upload time by the viewer's UTC offset.
    from datetime import datetime, timedelta, timezone

    uploaded = _upload(client, "name,age\nAlice,30\n").json()
    fetched = client.get(f"/api/datasets/{uploaded['id']}").json()
    listed = client.get("/api/datasets").json()[0]

    for body in (uploaded, fetched, listed):
        stamp = datetime.fromisoformat(body["upload_timestamp"].replace("Z", "+00:00"))
        assert stamp.utcoffset() == timedelta(0)
        assert abs(datetime.now(timezone.utc) - stamp) < timedelta(minutes=5)


def test_upload_rejects_non_csv_extension(client) -> None:
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "InvalidFileTypeError"


def test_upload_rejects_empty_file(client) -> None:
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "EmptyFileError"


def test_upload_rejects_malformed_csv(client) -> None:
    response = _upload(client, "a,b,c\n1,2\n3,4,5,6\n", filename="bad.csv")

    assert response.status_code == 422
    assert response.json()["error"] == "CSVParsingError"


def test_upload_detects_plain_utf8_encoding(client) -> None:
    response = _upload(client, "name,city\nAlice,Zürich\n", filename="utf8.csv")

    assert response.status_code == 201
    assert response.json()["encoding"] == "UTF-8"


def test_upload_detects_utf8_bom_encoding(client) -> None:
    content = "name,city\nAlice,Zürich\n".encode("utf-8-sig")

    response = client.post(
        "/api/datasets/upload",
        files={"file": ("bom.csv", io.BytesIO(content), "text/csv")},
    )

    assert response.status_code == 201
    assert response.json()["encoding"] == "UTF-8 (with BOM)"


def test_upload_detects_cp1252_encoding_and_reports_it_on_profile(client) -> None:
    content = (
        "name,note\n"
        "\"O’Brien\",\"price was €25 — café service, we’ll return\"\n"
        "\"André\",\"total charged: €12.50 for the résumé review\"\n"
        "\"Renée\",\"she quoted “€9.99” and smiled warmly\"\n"
    ).encode("cp1252")

    response = client.post(
        "/api/datasets/upload",
        files={"file": ("cp1252.csv", io.BytesIO(content), "text/csv")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["encoding"] == "Windows-1252"

    profile = client.get(f"/api/datasets/{body['id']}/profile").json()
    assert profile["encoding"] == "Windows-1252"


def test_upload_rejects_undetectable_binary_content(client) -> None:
    random_bytes = bytes((i * 37 + 11) % 256 for i in range(4000))

    response = client.post(
        "/api/datasets/upload",
        files={"file": ("binary.csv", io.BytesIO(random_bytes), "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["error"] == "EncodingDetectionError"


def test_get_unknown_dataset_returns_404(client) -> None:
    response = client.get("/api/datasets/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"] == "DatasetNotFoundError"


def test_profile_of_unknown_dataset_returns_404(client) -> None:
    response = client.get("/api/datasets/does-not-exist/profile")

    assert response.status_code == 404


def test_profile_reports_duplicate_rows(client) -> None:
    upload_response = _upload(client, "a,b\n1,2\n1,2\n3,4\n", filename="dupes.csv")
    dataset_id = upload_response.json()["id"]

    profile = client.get(f"/api/datasets/{dataset_id}/profile").json()

    assert profile["duplicate_row_count"] == 1


def test_mixed_type_column_is_handled_without_crashing(client) -> None:
    upload_response = _upload(
        client, "value\n10\n20\nunknown\n30\n", filename="mixed.csv"
    )
    dataset_id = upload_response.json()["id"]

    profile = client.get(f"/api/datasets/{dataset_id}/profile").json()

    value_column = profile["columns"][0]
    assert value_column["kind"] == "categorical"
    assert value_column["missing_count"] == 0


def test_full_upload_list_profile_delete_flow(client) -> None:
    upload_response = _upload(
        client, "name,age,city\nAlice,30,NYC\nBob,25,LA\nCara,,LA\n", filename="people.csv"
    )
    dataset_id = upload_response.json()["id"]

    list_response = client.get("/api/datasets")
    assert list_response.status_code == 200
    assert any(d["id"] == dataset_id for d in list_response.json())

    profile_response = client.get(f"/api/datasets/{dataset_id}/profile")
    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert profile["row_count"] == 3
    assert profile["column_count"] == 3
    age_column = next(c for c in profile["columns"] if c["name"] == "age")
    assert age_column["missing_count"] == 1

    delete_response = client.delete(f"/api/datasets/{dataset_id}")
    assert delete_response.status_code == 204

    get_after_delete = client.get(f"/api/datasets/{dataset_id}")
    assert get_after_delete.status_code == 404


def test_quality_of_unknown_dataset_returns_404(client) -> None:
    response = client.get("/api/datasets/does-not-exist/quality")

    assert response.status_code == 404
    assert response.json()["error"] == "DatasetNotFoundError"


def test_statistics_of_unknown_dataset_returns_404(client) -> None:
    response = client.get("/api/datasets/does-not-exist/statistics")

    assert response.status_code == 404
    assert response.json()["error"] == "DatasetNotFoundError"


def test_quality_endpoint_reports_score_and_issues(client) -> None:
    upload_response = _upload(
        client,
        "name,age,age2\nAlice,30,30\nAlice,30,30\nBob,,25\nCara,40,40\n",
        filename="quality.csv",
    )
    dataset_id = upload_response.json()["id"]

    response = client.get(f"/api/datasets/{dataset_id}/quality")

    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["score"] <= 100
    assert sum(entry["penalty"] for entry in body["breakdown"]) == 100 - body["score"]
    issue_types = {issue["type"] for issue in body["issues"]}
    assert "missing_values" in issue_types
    assert "duplicate_rows" in issue_types


def test_clean_dataset_scores_100_via_api(client) -> None:
    upload_response = _upload(
        client, "name,age\nAlice,30\nBob,25\nCara,40\n", filename="clean.csv"
    )
    dataset_id = upload_response.json()["id"]

    body = client.get(f"/api/datasets/{dataset_id}/quality").json()

    assert body["score"] == 100
    assert body["breakdown"] == []
    assert body["issues"] == []


def test_statistics_endpoint_returns_type_appropriate_stats(client) -> None:
    upload_response = _upload(
        client,
        "age,city,active,hired\n30,NYC,True,2022-01-15\n25,LA,False,2021-06-01\n"
        ",LA,True,2020-03-20\n",
        filename="stats.csv",
    )
    dataset_id = upload_response.json()["id"]

    response = client.get(f"/api/datasets/{dataset_id}/statistics")

    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 3

    age = next(c for c in body["columns"] if c["name"] == "age")
    assert age["kind"] == "numeric"
    assert age["numeric"]["missing_count"] == 1
    assert age["numeric"]["mean"] == 27.5

    city = next(c for c in body["columns"] if c["name"] == "city")
    assert city["kind"] == "categorical"
    assert city["categorical"]["most_frequent_value"] == "LA"

    active = next(c for c in body["columns"] if c["name"] == "active")
    assert active["kind"] == "boolean"
    assert active["boolean"]["true_count"] == 2

    hired = next(c for c in body["columns"] if c["name"] == "hired")
    assert hired["kind"] == "datetime"
    assert hired["datetime"]["valid_count"] == 3


def test_quality_and_statistics_responses_are_valid_json_with_infinite_values(
    client,
) -> None:
    content = "value\n1.0\n2.0\ninf\n-inf\n5.0\n"
    upload_response = _upload(client, content, filename="infinite.csv")
    dataset_id = upload_response.json()["id"]

    quality_response = client.get(f"/api/datasets/{dataset_id}/quality")
    statistics_response = client.get(f"/api/datasets/{dataset_id}/statistics")

    assert quality_response.status_code == 200
    assert statistics_response.status_code == 200

    # `response.json()` (httpx) already requires valid JSON to succeed, but
    # explicitly re-parsing the raw text is a stronger check: it proves the
    # non-standard `Infinity`/`NaN` literals Python's own `json.dumps` can
    # produce never made it into the body (Python's `json.loads` rejects
    # them by default too, matching a browser's `JSON.parse`).
    json.loads(quality_response.text)
    json.loads(statistics_response.text)

    assert "Infinity" not in quality_response.text
    assert "NaN" not in quality_response.text
    assert "Infinity" not in statistics_response.text
    assert "NaN" not in statistics_response.text

    quality_body = quality_response.json()
    infinite_issue = next(
        i for i in quality_body["issues"] if i["type"] == "infinite_values"
    )
    assert infinite_issue["affected_rows"] == 2

    value_stats = statistics_response.json()["columns"][0]["numeric"]
    assert value_stats["count"] == 3  # the two infinities are excluded
