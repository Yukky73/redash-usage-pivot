#!/usr/bin/env python3
"""Export daily usage from Redash and write a pivot CSV."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
import tempfile
import time
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ENV_EXAMPLE = Path(__file__).resolve().parents[1] / "assets" / ".env.example"
TEAM_TEMPLATE_NAME = "redash-team.env.example"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} を .env に設定してください。")
    return value


def request_json(url: str, *, method: str = "GET", headers: dict[str, str], body: Optional[dict] = None) -> dict:
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request_headers = {"Accept": "application/json", **headers}
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=payload, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"Redash APIからHTTP {error.code}が返りました。") from error
    except URLError as error:
        raise RuntimeError(f"接続に失敗しました: {error.reason}") from error


def request_bytes(url: str, *, headers: dict[str, str]) -> bytes:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=120) as response:
            return response.read()
    except HTTPError as error:
        raise RuntimeError(f"Redash APIからHTTP {error.code}が返りました。") from error
    except URLError as error:
        raise RuntimeError(f"接続に失敗しました: {error.reason}") from error


def wait_for_result(base_url: str, user_key: str, query_id: str, org_id: str, start: date, end: date) -> str:
    headers = {"Authorization": f"Key {user_key}"}
    body = {
        "max_age": 0,
        "parameters": {
            "org_id": org_id,
            "期間": {"start": start.isoformat(), "end": end.isoformat()},
            "集計": "DAY",
        },
    }
    response = request_json(f"{base_url}/api/queries/{query_id}/results", method="POST", headers=headers, body=body)
    job = response.get("job")
    if not job:
        raise RuntimeError("Redashから実行ジョブが返りませんでした。")

    job_id = job["id"]
    for _ in range(120):
        status = request_json(f"{base_url}/api/jobs/{job_id}", headers=headers).get("job", {})
        code = status.get("status")
        if code == 3:
            return str(status["query_result_id"])
        if code in (4, 5):
            raise RuntimeError("Redashジョブが失敗しました。Redashでクエリの実行状況を確認してください。")
        time.sleep(2)
    raise RuntimeError(f"Redash ジョブが4分以内に完了しませんでした: {job_id}")


def safe_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", name).strip(" .")
    return cleaned or "org"


def export_csv(base_url: str, query_id: str, result_id: str, user_key: str, destination: Path) -> None:
    headers = {"Authorization": f"Key {user_key}"}
    data = request_bytes(f"{base_url}/api/queries/{query_id}/results/{result_id}.csv", headers=headers)
    destination.write_bytes(data)


def format_duration(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


def create_pivot_csv(source: Path, destination: Path) -> None:
    required_columns = {"period", "org_id", "space_name", "user_name", "duration_min"}
    values: dict[tuple[str, str, str], dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    periods: set[str] = set()

    with source.open("r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file)
        headers = set(reader.fieldnames or [])
        missing = required_columns - headers
        if missing:
            raise RuntimeError(f"ピボット元CSVに必要な列がありません: {', '.join(sorted(missing))}")
        for line_number, row in enumerate(reader, start=2):
            period = (row.get("period") or "").strip()
            org_id = (row.get("org_id") or "").strip()
            space_name = (row.get("space_name") or "").strip()
            user_name = (row.get("user_name") or "").strip()
            try:
                duration = Decimal((row.get("duration_min") or "").strip())
            except InvalidOperation as error:
                raise RuntimeError(f"ピボット元CSVの{line_number}行目に不正なduration_minがあります。") from error
            if not period:
                raise RuntimeError(f"ピボット元CSVの{line_number}行目にperiodがありません。")
            periods.add(period)
            values[(org_id, space_name, user_name)][period] += duration

    ordered_periods = sorted(periods)
    period_totals: dict[str, Decimal] = defaultdict(Decimal)
    grand_total = Decimal()
    # Excel on Windows detects UTF-8 reliably when the BOM is present.
    with destination.open("w", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(["org_id", "space_name", "user_name", *ordered_periods, "Totals"])
        for row_key in sorted(values):
            row_values = values[row_key]
            total = sum(row_values.values(), Decimal())
            for period, duration in row_values.items():
                period_totals[period] += duration
            grand_total += total
            writer.writerow([
                *row_key,
                *(format_duration(row_values.get(period, Decimal())) for period in ordered_periods),
                format_duration(total),
            ])
        writer.writerow([
            "Totals",
            "",
            "",
            *(format_duration(period_totals[period]) for period in ordered_periods),
            format_duration(grand_total),
        ])


def validate_pivot_csv(source: Path, pivot: Path) -> None:
    with source.open(encoding="utf-8-sig", newline="") as input_file:
        source_total = sum((Decimal(row["duration_min"]) for row in csv.DictReader(input_file)), Decimal())
    with pivot.open(encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file)
        columns = reader.fieldnames or []
        rows = list(reader)
    if not rows or rows[-1].get("org_id") != "Totals" or "Totals" not in columns:
        raise RuntimeError("ピボットCSVの合計行・列を確認できません。")
    periods = columns[3:-1]
    for row in rows:
        if sum((Decimal(row[period]) for period in periods), Decimal()) != Decimal(row["Totals"]):
            raise RuntimeError("ピボットCSVの行合計が一致しません。")
    for column in [*periods, "Totals"]:
        if sum((Decimal(row[column]) for row in rows[:-1]), Decimal()) != Decimal(rows[-1][column]):
            raise RuntimeError("ピボットCSVの列合計が一致しません。")
    if Decimal(rows[-1]["Totals"]) != source_total.quantize(Decimal("0.01")):
        raise RuntimeError("生CSVとピボットCSVの総合計が一致しません。")


def init_env(path: Path) -> None:
    team_template = path.parent / TEAM_TEMPLATE_NAME
    template_path = team_template if team_template.is_file() else ENV_EXAMPLE
    try:
        with template_path.open("rb") as template, path.open("xb") as destination:
            shutil.copyfileobj(template, destination)
    except FileExistsError:
        print(".env は作成済みです。")
        return
    fields = (
        "REDASH_USER_API_KEY"
        if template_path == team_template
        else "REDASH_BASE_URL、REDASH_QUERY_ID、REDASH_USER_API_KEY"
    )
    print(f".env を作成しました。{fields} を入力してください。\n{path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Redashの日別利用時間をピボットCSVに出力します。")
    parser.add_argument("--workspace", type=Path, default=Path.cwd(), help=".env と出力先を置く作業フォルダ")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="作業フォルダに .env のひな形を作成")
    export = commands.add_parser("export", help="利用実績を取得してCSVに出力")
    export.add_argument("--org-id", required=True, help="対象の組織ID")
    export.add_argument("--days", type=int, help="取得期間（日数、日付の指定がなければ既定90日）")
    export.add_argument("--start", type=date.fromisoformat, help="開始日（YYYY-MM-DD）")
    export.add_argument("--end", type=date.fromisoformat, help="終了日（YYYY-MM-DD）")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        parser.error("作業フォルダが見つかりません。")
    env_path = workspace / ".env"
    if args.command == "init":
        init_env(env_path)
        return 0

    org_id = args.org_id.strip()
    if not org_id:
        export.error("--org-id を指定してください。")
    if args.start is not None or args.end is not None:
        if args.start is None or args.end is None or args.days is not None:
            export.error("--start と --end を指定するか、--days だけを指定してください。")
        start, end = args.start, args.end
    else:
        days = 90 if args.days is None else args.days
        end = date.today()
        if not 1 <= days < end.toordinal():
            export.error("--days は有効な日付範囲に収まる正の整数にしてください。")
        start = end - timedelta(days=days)
    if start > end:
        export.error("開始日は終了日以前にしてください。")

    load_dotenv(env_path)
    user_key = required("REDASH_USER_API_KEY")
    base_url = required("REDASH_BASE_URL").rstrip("/")
    query_id = required("REDASH_QUERY_ID")
    result_id = wait_for_result(base_url, user_key, query_id, org_id, start, end)
    csv_dir = workspace / "csv"
    csv_dir.mkdir(exist_ok=True)
    output = csv_dir / f"usage_{safe_filename(org_id)}_{start}_{end}_pivot.csv"
    with tempfile.TemporaryDirectory(prefix=".redash-", dir=csv_dir) as temporary:
        raw = Path(temporary) / "raw.csv"
        pivot = Path(temporary) / "pivot.csv"
        export_csv(base_url, query_id, result_id, user_key, raw)
        create_pivot_csv(raw, pivot)
        validate_pivot_csv(raw, pivot)
        pivot.replace(output)
    print(output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError, ArithmeticError, csv.Error) as error:
        print(f"エラー: {error}", file=sys.stderr)
        raise SystemExit(1)
