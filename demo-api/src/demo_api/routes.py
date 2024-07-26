import asyncio
from datetime import timedelta
from functools import wraps
import os
from demo_api.cache import cache
from fastapi import APIRouter
from random import choices
from opentelemetry import metrics, trace

router = APIRouter()

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

error_counter = meter.create_counter(
    "errors", unit="1", description="Counts the number of errors"
)


def count_errors(route):
    """
    Increment the error counter whenever a decorated function
    throws an unhandled exception
    """

    def inner(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except:
                error_counter.add(1, {"http.route": route})
                raise

        return wrapper

    return inner


@router.get("/hello-world")
@count_errors("/hello-world")
async def hello_world() -> str:
    # randomly chose a sleep time between 100ms and 5s to simulate some work
    # faster sleep times are weighted heavier
    request_times_sec: list[float] = [0.1, 0.2, 0.3, 0.5, 1, 2, 5]
    weights = [0.7, 0.1, 0.1, 0.05, 0.03, 0.01, 0.01]
    sleep_time = choices(request_times_sec, weights)[0]

    # wrap simulated work in a span, so we can see the precisce timing
    # add the sleep_time variable as a span attribute to demonstrate
    # how we can add contextual information to spans
    with tracer.start_as_current_span(
        "random sleep", attributes={"operation.sleep_time": sleep_time}
    ) as span:
        await asyncio.sleep(sleep_time)

    # Throw an error occasionally
    if choices([True, False], [0.1, 0.9])[0]:
        raise Exception("Error!")

    return "Hello World!"


@router.get("/cached-result")
@count_errors("/cached-result")
async def get_cached_result() -> str:
    # attempt to get the result from the cache
    result = cache.get("result")

    if not result:
        # on a cache miss, simulate some work
        await asyncio.sleep(2)
        result = "foo"
        cache.set("result", result, timedelta(seconds=int(os.getenv("CACHE_TTL", 30))))

    return result
