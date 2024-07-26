from theine import Cache
from opentelemetry import metrics


cache = Cache("tlfu", 10000)

meter = metrics.get_meter(__name__)

# periodically check the cache miss count
meter.create_observable_counter(
    "cache.miss",
    unit="1",
    callbacks=[
        lambda _: [metrics.Observation(cache.stats().miss_count if cache._total else 0)]
    ],
)

# periodically check the cache request count. Combined with the miss count, we can graph & alert on the cache miss percentage.
meter.create_observable_counter(
    "cache.request",
    unit="1",
    callbacks=[
        lambda _: [
            metrics.Observation(cache.stats().request_count if cache._total else 0)
        ]
    ],
)
