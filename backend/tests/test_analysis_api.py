"""API tests for correlation and visualization endpoints."""

from __future__ import annotations

import io
import json


def _upload(client, content: str, filename: str = "data.csv") -> str:
    response = client.post(
        "/api/datasets/upload",
        files={"file": (filename, io.BytesIO(content.encode("utf-8")), "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


CORRELATED_CSV = (
    "x,y_up,y_down,city,when,flat\n"
    "1,2,10,NYC,2023-01-01,5\n"
    "2,4,9,LA,2023-01-08,5\n"
    "3,6,8,NYC,2023-01-15,5\n"
    "4,8,7,SF,2023-01-22,5\n"
    "5,10,6,LA,2023-01-29,5\n"
    "6,12,5,NYC,2023-02-05,5\n"
)


# --- correlations ----------------------------------------------------------


def test_correlations_endpoint_returns_matrix_and_switches_method(client) -> None:
    dataset_id = _upload(client, CORRELATED_CSV)

    pearson = client.get(f"/api/datasets/{dataset_id}/correlations?method=pearson")
    spearman = client.get(f"/api/datasets/{dataset_id}/correlations?method=spearman")

    assert pearson.status_code == 200
    body = pearson.json()
    assert body["method"] == "pearson"
    assert "flat" in {e["name"] for e in body["excluded_columns"]}
    x_index = body["columns"].index("x")
    y_index = body["columns"].index("y_up")
    assert body["matrix"][x_index][y_index] == 1.0
    assert spearman.json()["method"] == "spearman"


def test_correlations_default_method_is_pearson(client) -> None:
    dataset_id = _upload(client, CORRELATED_CSV)

    body = client.get(f"/api/datasets/{dataset_id}/correlations").json()

    assert body["method"] == "pearson"


def test_correlations_rejects_unknown_method(client) -> None:
    dataset_id = _upload(client, CORRELATED_CSV)

    response = client.get(f"/api/datasets/{dataset_id}/correlations?method=kendall")

    assert response.status_code == 400
    assert response.json()["error"] == "InvalidParameterError"


def test_correlations_without_enough_numeric_columns_returns_422(client) -> None:
    dataset_id = _upload(client, "city,state\nNYC,NY\nLA,CA\n", filename="text.csv")

    response = client.get(f"/api/datasets/{dataset_id}/correlations")

    assert response.status_code == 422
    assert response.json()["error"] == "InsufficientDataError"


def test_correlations_payload_is_valid_json(client) -> None:
    dataset_id = _upload(client, "a,b\n1,inf\n2,4\n3,\n4,8\n")

    response = client.get(f"/api/datasets/{dataset_id}/correlations")

    json.loads(response.text)
    assert "Infinity" not in response.text


# --- histogram -------------------------------------------------------------


def test_histogram_endpoint_counts_sum_to_observations(client) -> None:
    dataset_id = _upload(client, "v,label\n1,a\n2,b\n3,c\n4,d\n5,e\n,f\n")

    response = client.get(f"/api/datasets/{dataset_id}/visualizations/histogram?column=v")

    assert response.status_code == 200
    body = response.json()
    assert sum(b["count"] for b in body["bins"]) == body["total_observations"] == 5
    assert body["missing_count"] == 1


def test_histogram_endpoint_rejects_categorical_column(client) -> None:
    dataset_id = _upload(client, CORRELATED_CSV)

    response = client.get(f"/api/datasets/{dataset_id}/visualizations/histogram?column=city")

    assert response.status_code == 422
    assert response.json()["error"] == "IncompatibleColumnTypeError"


def test_histogram_endpoint_rejects_missing_column(client) -> None:
    dataset_id = _upload(client, CORRELATED_CSV)

    response = client.get(f"/api/datasets/{dataset_id}/visualizations/histogram?column=nope")

    assert response.status_code == 404
    assert response.json()["error"] == "ColumnNotFoundError"


def test_histogram_endpoint_rejects_invalid_bins(client) -> None:
    dataset_id = _upload(client, CORRELATED_CSV)

    response = client.get(
        f"/api/datasets/{dataset_id}/visualizations/histogram?column=x&bins=0"
    )

    assert response.status_code == 400
    assert response.json()["error"] == "InvalidParameterError"


# --- categorical -----------------------------------------------------------


def test_categorical_endpoint_returns_frequencies(client) -> None:
    dataset_id = _upload(client, CORRELATED_CSV)

    body = client.get(
        f"/api/datasets/{dataset_id}/visualizations/categorical?column=city&top_n=2"
    ).json()

    assert body["total_count"] == 6
    assert body["items"][0]["value"] == "NYC"
    assert body["items"][0]["count"] == 3
    assert body["items"][-1]["value"] == "Other"


def test_categorical_endpoint_rejects_numeric_column(client) -> None:
    dataset_id = _upload(client, CORRELATED_CSV)

    response = client.get(f"/api/datasets/{dataset_id}/visualizations/categorical?column=x")

    assert response.status_code == 422


# --- scatter ---------------------------------------------------------------


def test_scatter_endpoint_returns_points_and_correlation(client) -> None:
    dataset_id = _upload(client, CORRELATED_CSV)

    body = client.get(
        f"/api/datasets/{dataset_id}/visualizations/scatter?x=x&y=y_up"
    ).json()

    assert body["returned_points"] == 6
    assert body["sampled"] is False
    assert body["pearson_r"] == 1.0


def test_scatter_endpoint_rejects_same_axis(client) -> None:
    dataset_id = _upload(client, CORRELATED_CSV)

    response = client.get(f"/api/datasets/{dataset_id}/visualizations/scatter?x=x&y=x")

    assert response.status_code == 400


def test_scatter_endpoint_requires_numeric_axes(client) -> None:
    dataset_id = _upload(client, CORRELATED_CSV)

    response = client.get(f"/api/datasets/{dataset_id}/visualizations/scatter?x=x&y=city")

    assert response.status_code == 422


# --- distribution ----------------------------------------------------------


def test_distribution_endpoint_returns_summary(client) -> None:
    dataset_id = _upload(client, "v\n1\n2\n3\n4\n5\n6\n7\n8\n9\n")

    body = client.get(
        f"/api/datasets/{dataset_id}/visualizations/distribution?column=v"
    ).json()

    assert body["minimum"] == 1.0
    assert body["median"] == 5.0
    assert body["iqr"] == 4.0


# --- datetime trend --------------------------------------------------------


def test_datetime_trend_endpoint_aggregates(client) -> None:
    dataset_id = _upload(client, CORRELATED_CSV)

    response = client.get(
        f"/api/datasets/{dataset_id}/visualizations/datetime-trend"
        "?datetime_column=when&value_column=y_up"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_observations"] == 6
    assert sum(p["count"] for p in body["points"]) == 6


def test_datetime_trend_endpoint_requires_datetime_column(client) -> None:
    dataset_id = _upload(client, CORRELATED_CSV)

    response = client.get(
        f"/api/datasets/{dataset_id}/visualizations/datetime-trend"
        "?datetime_column=city&value_column=y_up"
    )

    assert response.status_code == 422


# --- dataset-level errors --------------------------------------------------


def test_analysis_endpoints_return_404_for_unknown_dataset(client) -> None:
    paths = [
        "/api/datasets/missing/correlations",
        "/api/datasets/missing/visualizations/histogram?column=x",
        "/api/datasets/missing/visualizations/categorical?column=x",
        "/api/datasets/missing/visualizations/scatter?x=a&y=b",
        "/api/datasets/missing/visualizations/distribution?column=x",
        "/api/datasets/missing/visualizations/datetime-trend?datetime_column=a&value_column=b",
    ]

    for path in paths:
        response = client.get(path)
        assert response.status_code == 404, path
        assert response.json()["error"] == "DatasetNotFoundError", path
