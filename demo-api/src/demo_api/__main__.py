from typing import Annotated
from fastapi import FastAPI
import typer
import uvicorn
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry import metrics, trace
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics import MeterProvider
import demo_api.routes as routes

app = typer.Typer()

tracer_provider = TracerProvider()
tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(insecure=True)))
trace.set_tracer_provider(tracer_provider)

meter_provider = MeterProvider(
    metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter(insecure=True))]
)
metrics.set_meter_provider(meter_provider)


@app.command()
def api(
    host: Annotated[str, typer.Option(help="web service listen host")] = "0.0.0.0",
    port: Annotated[int, typer.Option(help="web service listen port")] = 8080,
    root_path: Annotated[
        str, typer.Option(help="the path to this app when behind a proxy")
    ] = "",
    reload: Annotated[
        bool, typer.Option(help="reload the app when source files change")
    ] = False,
) -> None:
    """
    start the api. use the swagger docs at /docs
    """
    fastapi = FastAPI()
    fastapi.include_router(routes.router)
    FastAPIInstrumentor.instrument_app(fastapi)

    uvicorn.run(
        fastapi,
        port=port,
        host=host,
        reload=reload,
        factory=False,
        root_path=root_path,
        log_level="debug",
    )


if __name__ == "__main__":
    app()
