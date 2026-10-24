from __future__ import annotations

from prefect import flow
from prefect.schedules import Cron

from data.pipelines.recovery import recover_stale_pipeline_runs
from data.pipelines.weekly_location_performance import weekly_location_performance_flow


@flow(name="weekly-location-performance-scheduled")
def scheduled_weekly_location_performance() -> list[dict[str, object]]:
    recover_stale_pipeline_runs()
    return weekly_location_performance_flow(trigger="scheduled")


if __name__ == "__main__":
    scheduled_weekly_location_performance.serve(
        name="brasaland-weekly-location-performance",
        schedule=Cron(
            "0 12 * * 1",
            timezone="UTC",
        ),
    )