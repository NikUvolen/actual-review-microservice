#!/usr/bin/env python3
"""Run a controlled load test against the Yandex review parser."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import threading
import time
from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DJANGO_ROOT = PROJECT_ROOT / "review_parser"
sys.path.insert(0, str(DJANGO_ROOT))

from common_parser.parsing.exceptions import ProviderRequestError  # noqa: E402
from common_parser.parsing.providers.yandex import YandexParser  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check Yandex parser behavior across many company URLs.",
    )
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "res.txt")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--jitter", type=float, default=0.25)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--stop-after-errors", type=int, default=10)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "yandex_load_test_results.json",
    )
    return parser.parse_args()


def load_urls(path: Path, limit: int | None) -> list[str]:
    urls = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    return urls[:limit] if limit is not None else urls


def result_row(index: int, url: str) -> dict[str, Any]:
    return {
        "index": index,
        "url": url,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": None,
        "http_status": None,
        "elapsed_seconds": None,
        "review_count": None,
        "external_count": None,
        "avg_rating": None,
        "error_type": None,
        "error": None,
    }


def run_one(parser: YandexParser, index: int, url: str) -> dict[str, Any]:
    row = result_row(index, url)
    started = time.perf_counter()

    try:
        result = parser.parse(url)
        row.update(
            status="success",
            review_count=len(result.reviews),
            external_count=result.external_count,
            avg_rating=result.avg_rating,
        )
    except ProviderRequestError as exc:
        row.update(
            status="http_error",
            http_status=exc.status_code,
            error_type=type(exc).__name__,
            error=str(exc)[:1000],
        )
    except requests.Timeout as exc:
        row.update(
            status="timeout",
            error_type=type(exc).__name__,
            error=str(exc)[:1000],
        )
    except requests.RequestException as exc:
        row.update(
            status="network_error",
            error_type=type(exc).__name__,
            error=str(exc)[:1000],
        )
    except Exception as exc:  # Diagnostic runner must record parser failures.
        row.update(
            status="parser_error",
            error_type=type(exc).__name__,
            error=str(exc)[:1000],
        )
    finally:
        row["elapsed_seconds"] = round(time.perf_counter() - started, 3)

    return row


worker_state = threading.local()


def get_worker_parser() -> YandexParser:
    """Return a parser backed by a session private to the current worker."""
    parser = getattr(worker_state, "parser", None)

    if parser is None:
        parser = YandexParser()
        worker_state.parser = parser

    return parser


def run_worker(
    index: int,
    url: str,
    delay: float,
    jitter: float,
) -> dict[str, Any]:
    row = run_one(get_worker_parser(), index, url)
    time.sleep(delay + random.uniform(0, jitter))
    return row


def save_results(path: Path, results: list[dict[str, Any]]) -> None:
    path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    csv_path = path.with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)


def main() -> int:
    args = parse_args()
    urls = load_urls(args.input, args.limit)

    if not urls:
        raise SystemExit(f"No URLs found in {args.input}")
    if args.delay < 0 or args.jitter < 0:
        raise SystemExit("--delay and --jitter must be non-negative")
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be at least 1")

    results: list[dict[str, Any]] = []
    consecutive_errors = 0

    print(
        f"Running Yandex parser for {len(urls)} companies "
        f"with concurrency={args.concurrency}",
        flush=True,
    )

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures: dict[Future[dict[str, Any]], int] = {
            executor.submit(
                run_worker,
                index,
                url,
                args.delay,
                args.jitter,
            ): index
            for index, url in enumerate(urls, start=1)
        }

        for completed, future in enumerate(as_completed(futures), start=1):
            row = future.result()
            results.append(row)
            results.sort(key=lambda result: result["index"])
            save_results(args.output, results)

            if row["status"] == "success":
                consecutive_errors = 0
            else:
                consecutive_errors += 1

            print(
                f"[{completed:03d}/{len(urls):03d}] "
                f"source={row['index']:03d} {row['status']:<13} "
                f"reviews={str(row['review_count']):<4} "
                f"http={str(row['http_status']):<4} "
                f"time={row['elapsed_seconds']:>7.3f}s",
                flush=True,
            )

            if consecutive_errors >= args.stop_after_errors:
                for pending_future in futures:
                    pending_future.cancel()

                print(
                    f"Stopped after {consecutive_errors} consecutive errors",
                    flush=True,
                )
                break

    statuses = Counter(row["status"] for row in results)
    average_time = sum(row["elapsed_seconds"] for row in results) / len(results)
    print(f"Statuses: {dict(statuses)}")
    print(f"Average company time: {average_time:.3f}s")
    print(f"Results: {args.output} and {args.output.with_suffix('.csv')}")

    return 0 if statuses.get("success", 0) == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
