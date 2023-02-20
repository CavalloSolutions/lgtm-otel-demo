## Overview

The purpose of this repository is to demonstrate how we could use the OpenTelemetry Collector with the Grafana LGTM stack to collect, correlate, and visualize our application's logs, traces and metrics. It uses a simple load generator against a .Net web service that has been instrumented with the [OpenTelemetry SDK](https://opentelemetry.io/docs/instrumentation/net/).

Links:

- https://opentelemetry.io/docs/concepts/observability-primer/

## Running the demo

- Spin up the [docker-compose file](./docker-compose.yaml) in the repo root.
- When the demo service endpoint receives a request it does a couple of different things:
  - simulates periodic delays and exceptions
  - demonstrates auto-instrumented HTTP clients and SQL Clients
  - demonstrates manually definied inner trace spans
- Navigate to the [Grafana Dashboard](http://localhost:3000/d/4xdgpH1Vz/red)
  - This dashboard shows graphs for the demo service endpoint's [RED](https://www.weave.works/blog/the-red-method-key-metrics-for-microservices-architecture/) metrics along with the durations of some of the endpoint's inner trace spans.
  - Some of the graphs include exemplars that are instances of traces at particular points in time, providing correlation between metrics and traces.
  - When viewing a trace, we can also click a button on each span to query the logs for that particular span.

## Architecture

The Grafana LGTM stack provides storage and visualisation of application logs, metrics, and traces.

- [Loki](https://grafana.com/oss/loki/) is a storage and query engine for logs. It exposes an endpoint that logs can be pushed to.
- [Tempo](https://grafana.com/oss/tempo/) is a storage and query engine for traces. It exposes an endpoint that traces can be pushed to.
- [Mimir](https://grafana.com/oss/mimir/) is a long term storage engine for metrics. It is tightly coupled with Prometheus for querying and ingesting metrics. This demo is using prometheus without Mimir, scraping configured target endpoints.
- [Grafana](https://grafana.com/oss/grafana/) is a powerful visualization tool that can connect to all of the above data sources and more. It can also handle alerts and notifications.

The [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/) is a proxy and processing layer between instrumented applications and the various backends. It is not limited to the LGTM stack.

![Imgur](https://i.imgur.com/MQPnK2p.png)

### Collector Configuration

[otel-config.yml](./otel/otel-config.yml)

The Otel Collector is configured to use two receivers.

- The OTLP (OpenTelemetry Protocol) receiver is an HTTP or gRPC endpoint that instrumented applications can push logs, traces, and metrics (signals) to.
- The Prometheus receiver has most of the functionality of a typical prometheus instance. It can scrape the prometheus endpoint of instrumented applications or, in this case, the collector's own metrics endpoint.

```
receivers:
  otlp:
    protocols:
      http:
      grpc:
  prometheus:
    config:
      scrape_configs:
        - job_name: "otel-collector"
          scrape_interval: 10s
          static_configs:
            - targets: ["0.0.0.0:8888"] # The collector's own metrics port
```

From there, signals are routed through processors. There are numerous additional processors available in the [contrib distro](https://github.com/open-telemetry/opentelemetry-collector-contrib). In this demo, we are using two processors:

- Resource/Attributes takes attributes from the OTel logs and converts them into Loki Labels that can be used for correlation and easier querying.
- spanmetrics takes traces and derives RED metrics from trace spans, adding any specified trace attributes as metric labels and attaching trace exemplars to the metrics.

```
processors:
  spanmetrics:
    metrics_exporter: prometheus
    dimensions:
      - name: http.url
      - name: http.status_code
      - name: db.system
  resource:
    attributes:
      - action: insert
        key: service_name
        from_attribute: service.name
      - action: insert
        key: service_namespace
        from_attribute: service.namespace
      - action: insert
        key: service_instance_id
        from_attribute: service.instance.id
      - action: insert
        key: service_version
        from_attribute: service.version
      - action: insert
        key: loki.resource.labels
        value: service_name, service_namespace, service_instance_id, service_version
```

Once signals have been processed, they are sent to exporters. This demo uses 3 exporters:

- The Loki exporter pushes OTel logs to a Loki endpoint
- The OTLP exporter pushes signals to another OTLP receiver
- The Prometheus exporter exposes a port where metrics can be scraped from.

```
exporters:
  loki:
    endpoint: "http://loki:3100/api/prom/push"
  otlp:
    endpoint: "tempo:4317"
    tls:
      insecure: true
  prometheus:
    endpoint: "0.0.0.0:8889"
    resource_to_telemetry_conversion:
      enabled: true
    enable_open_metrics: true
```

With the collector components configured, we can then stitch them together into pipelines

```
service:
  pipelines:
    logs:
      receivers: [otlp]
      processors: [resource]
      exporters: [loki]
    traces:
      receivers: [otlp]
      exporters: [otlp]
      processors: [spanmetrics]
    metrics:
      receivers: [otlp, prometheus]
      exporters: [prometheus]
```

### Grafana Configuration

Grafana datasources require a bit of configuration to enable log, metric, and trace correlation

[datasources.yaml](./grafana/datasources.yaml)

#### Tempo Datasource

- the `mappedTags` takes attributes from the traces and maps them to attributes on the logs. When you navigate from a trace/span to its logs, grafana creates a Loki query using the `mappedTags`.
- The generated loki query can also include the trace and span ids (`filterByTraceID`, `filterBySpanID`) so you only see logs for that specific trace/span
  - log auto instrumentation SDKs should automatically handle adding the trace and span ids to log attributes.

```
...
tracesToLogs:
    datasourceUid: "loki"
    filterBySpanID: true
    filterByTraceID: true
    mapTagNamesEnabled: true
    mappedTags:
        - key: service.name
        value: service_name
    spanEndTimeShift: "1s"
```

#### Loki Datasource

- the `derivedFields` config allows generating hyperlinks from log attributes. Here it is configured to extract the `traceid` and link it back to the Tempo datasource so we can easily navigate from logs to traces.

```
derivedFields:
- name: TraceID
    datasourceUid: tempo
    matcherRegex: '"traceid":"(\w+)"'
    url: $${__value.raw}
```

#### Prometheus Datasource

- `exemplarTraceIdDestination` is what enables linking from an exemplar to the actual trace in Tempo.

```
exemplarTraceIdDestinations:
- name: trace_id
    datasourceUid: tempo
```
