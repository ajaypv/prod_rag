from prodrag.observability import RequestMetrics


def test_request_metrics_exposes_latency_histogram() -> None:
    metrics = RequestMetrics()
    metrics.observe("POST", "/v1/query", 200, 0.75)

    rendered = metrics.render()

    assert 'path="/v1/query",le="1"} 1' in rendered
    assert 'path="/v1/query",le="0.5"} 0' in rendered
    assert 'path="/v1/query",le="+Inf"} 1' in rendered
    assert 'prodrag_http_request_duration_seconds_count{method="POST"' in rendered
