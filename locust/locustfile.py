import time
from urllib.parse import urlparse
from uuid import uuid4

from requests import PreparedRequest
from locust import HttpUser, task, between

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry import metrics, trace
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.trace.span import Span

tracer_provider = TracerProvider()
tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(insecure=True)))
trace.set_tracer_provider(tracer_provider)

meter_provider = MeterProvider(
    metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter(insecure=True))]
)
metrics.set_meter_provider(meter_provider)


# auto instrument the requests package, and add a callback that
# lets us add attributes from the http request to the current span.
def request_hook(span: Span, request: PreparedRequest) -> None:
    url = urlparse(request.url)
    span.set_attribute("http.route", url.path)
    span.set_attribute("http.header.user-id", request.headers.get("user-id"))

RequestsInstrumentor().instrument(request_hook=request_hook)


class DemoUser(HttpUser):
    wait_time = between(1, 5)

    @task
    def hello_world(self):
        self.client.get("/hello-world", headers={"user-id": self.userId})

    @task
    def cached_result(self):
        self.client.get("/cached-result", headers={"user-id": self.userId})

    def on_start(self):
        self.userId = str(uuid4())
