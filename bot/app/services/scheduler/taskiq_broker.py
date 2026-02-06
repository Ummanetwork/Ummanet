import logging
from typing import Any, Awaitable, Callable

from config.config import settings

if settings.features.enable_taskiq:
    from taskiq import TaskiqEvents, TaskiqScheduler, TaskiqState
    from taskiq.schedule_sources import LabelScheduleSource
    from taskiq_nats import NatsBroker
    from taskiq_redis import RedisScheduleSource

    broker = NatsBroker(servers=settings.nats.servers, queue="taskiq_tasks")

    redis_source = RedisScheduleSource(
        url=f"redis://{settings.redis.host}:{settings.redis.port}"
    )

    scheduler = TaskiqScheduler(broker, [redis_source, LabelScheduleSource(broker)])

    @broker.on_event(TaskiqEvents.WORKER_STARTUP)
    async def startup(state: TaskiqState) -> None:
        logging.basicConfig(level=settings.logs.level_name, format=settings.logs.format)
        logger = logging.getLogger(__name__)
        logger.info("Starting scheduler...")

        state.logger = logger

    @broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
    async def shutdown(state: TaskiqState) -> None:
        state.logger.info("Scheduler stopped")
else:

    class _DummyBroker:
        async def startup(self) -> None:  # pragma: no cover - simple stub
            logging.getLogger(__name__).info("Taskiq broker disabled")

        async def shutdown(self) -> None:  # pragma: no cover - simple stub
            logging.getLogger(__name__).info("Taskiq broker disabled")

        def task(
            self, *args: Any, **kwargs: Any
        ) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
            def decorator(
                func: Callable[..., Awaitable[Any]]
            ) -> Callable[..., Awaitable[Any]]:
                return func

            return decorator

        def on_event(
            self, *_: Any, **__: Any
        ) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
            def decorator(
                func: Callable[..., Awaitable[Any]]
            ) -> Callable[..., Awaitable[Any]]:
                return func

            return decorator

    broker = _DummyBroker()
    redis_source = None
    scheduler = None
