"""Render a policy bulletin from a risk summary JSON and optional PNG map."""
import argparse
import json
import logging
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

LOGGER = logging.getLogger(__name__)


def _relative_png(map_png: Path | None, output: Path) -> str | None:
    if map_png is None:
        return None
    try:
        return str(Path(map_png).resolve().relative_to(output.resolve().parent))
    except ValueError:
        return str(map_png)


def render_bulletin(summary_json: Path, map_png: Path | None, output: Path, region: str = "Western Australia") -> None:
    with summary_json.open(encoding="utf-8") as f:
        payload = json.load(f)

    summary = payload["summary"]
    time_meta = payload.get("time_metadata", {})

    def pct(key: str) -> str:
        val = summary[key]["percentage"] * 100
        if val > 0 and val < 0.1:
            return "< 0.1"
        return f"{val:.1f}"

    def clean_date(s: str) -> str:
        return s[:10] if s and len(s) >= 10 else s

    context = {
        "region": region,
        "time_start": clean_date(time_meta.get("time_start", "unknown")),
        "time_end": clean_date(time_meta.get("time_end", "unknown")),
        "run_date": date.today().isoformat(),
        "critical_count": summary["critical"]["count"],
        "alert_count":    summary["alert"]["count"],
        "watch_count":    summary["watch"]["count"],
        "low_count":      summary["low"]["count"],
        "valid_count":    summary["valid_cells"]["count"],
        "invalid_count":  summary["invalid"]["count"],
        "critical_pct": pct("critical"),
        "alert_pct":    pct("alert"),
        "watch_pct":    pct("watch"),
        "low_pct":      pct("low"),
        "map_png": _relative_png(map_png, output),
    }

    templates_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)), keep_trailing_newline=True)
    template = env.get_template("bulletin_template.j2")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(template.render(**context), encoding="utf-8")
    LOGGER.info("Bulletin written to %s", output)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Render a drought risk bulletin from a summary JSON.")
    parser.add_argument("--summary-json", required=True, type=Path, help="Path to *_summary.json")
    parser.add_argument("--map-png", default=None, type=Path, help="Path to risk map PNG (optional)")
    parser.add_argument("--output", required=True, type=Path, help="Output Markdown path")
    parser.add_argument("--region", default="Western Australia", help="Region label used in bulletin title and text (default: 'Western Australia')")
    args = parser.parse_args()
    render_bulletin(args.summary_json, args.map_png, args.output, region=args.region)
