from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from data.pipelines import pipeline


def _mock_run_flow(week_start, trigger):
    """Mock que devuelve un resultado exitoso sin tocar base de datos."""
    return [
        {
            "run_id": "00000000-0000-0000-0000-000000000001",
            "week_start": (
                week_start.isoformat() if week_start else "2026-10-19"
            ),
            "status": "completed",
            "events_read": 10,
            "events_discarded": 0,
            "rows_upserted": 14,
        }
    ]


@pytest.fixture(autouse=True)
def _mock_database_deps():
    """Evita que cualquier test toque base de datos real."""
    with (
        patch.object(pipeline, "_run_flow", side_effect=_mock_run_flow),
        patch.object(pipeline, "recover_stale_pipeline_runs"),
    ):
        yield


def test_main_returns_zero_without_args() -> None:
    """Ejecucion sin args debe retornar 0 (exito)."""
    exit_code = pipeline.main([])
    assert exit_code == 0


def test_main_with_week_start_arg() -> None:
    """--week-start en formato ISO debe ser aceptado."""
    exit_code = pipeline.main(["--week-start", "2026-10-19"])
    assert exit_code == 0


def test_main_with_trigger_scheduled() -> None:
    """--trigger scheduled debe ser aceptado."""
    exit_code = pipeline.main(["--trigger", "scheduled"])
    assert exit_code == 0


def test_main_with_trigger_manual() -> None:
    """--trigger manual debe ser aceptado (default)."""
    exit_code = pipeline.main(["--trigger", "manual"])
    assert exit_code == 0


def test_main_with_validate_creates_eval_file(tmp_path: Path) -> None:
    """--validate debe crear un archivo JSON en data/eval/."""
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir(parents=True)

    with patch.object(pipeline, "EVAL_DIR", eval_dir):
        exit_code = pipeline.main(
            ["--week-start", "2026-10-19", "--validate"]
        )

    assert exit_code == 0
    json_files = list(eval_dir.glob("pipeline-run-*.json"))
    assert len(json_files) >= 1

    content = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert content["pipeline"] == "weekly_location_performance"
    assert "runs" in content
    assert "executed_at" in content


def test_parse_args_defaults() -> None:
    """Argumentos por defecto."""
    args = pipeline._parse_args([])
    assert args.week_start is None
    assert args.trigger == "manual"
    assert args.validate is False


def test_parse_args_week_start() -> None:
    """--week-start debe parsearse como date."""
    args = pipeline._parse_args(["--week-start", "2026-10-19"])
    assert args.week_start == date(2026, 10, 19)


def test_parse_args_trigger_scheduled() -> None:
    """--trigger scheduled."""
    args = pipeline._parse_args(["--trigger", "scheduled"])
    assert args.trigger == "scheduled"


def test_parse_args_validate() -> None:
    """--validate activa el flag."""
    args = pipeline._parse_args(["--validate"])
    assert args.validate is True


def test_parse_args_invalid_week_start() -> None:
    """Fecha invalida debe lanzar error del sistema (por argparse)."""
    with pytest.raises(SystemExit):
        pipeline._parse_args(["--week-start", "not-a-date"])


def test_parse_args_invalid_trigger() -> None:
    """Trigger invalido debe lanzar SystemExit."""
    with pytest.raises(SystemExit):
        pipeline._parse_args(["--trigger", "invalid"])


def test_save_validation_creates_json(tmp_path: Path) -> None:
    """_save_validation debe escribir un JSON con metadatos."""
    with patch.object(pipeline, "EVAL_DIR", tmp_path):
        flow_result: list[dict[str, object]] = [
            {
                "run_id": "test-uuid",
                "week_start": "2026-10-19",
                "status": "completed",
                "events_read": 10,
                "events_discarded": 0,
                "rows_upserted": 14,
            }
        ]
        path = pipeline._save_validation(flow_result, 1.5)

    assert path.exists()
    assert path.suffix == ".json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["pipeline"] == "weekly_location_performance"
    assert data["elapsed_seconds"] == 1.5
    assert len(data["runs"]) == 1


def test_print_summary_does_not_raise() -> None:
    """_print_summary imprime sin errores."""
    flow_result = [
        {
            "run_id": "uuid-1",
            "week_start": "2026-10-19",
            "status": "completed",
            "events_read": 10,
            "events_discarded": 0,
            "rows_upserted": 14,
        },
    ]
    # Debe ejecutarse sin excepcion
    pipeline._print_summary(flow_result)