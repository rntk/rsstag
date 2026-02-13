import argparse
import logging
import os
import sys
from typing import TYPE_CHECKING, Any, Dict, Optional

from rsstag.utils import load_config

if TYPE_CHECKING:
    from rsstag.workers.dispatcher import RSSTagWorkerDispatcher
    from rsstag.workers.external_worker import ExternalWorkerRunner


def _build_default_api_base_url(config: Dict[str, Any]) -> str:
    host_name_raw: str = config["settings"].get("host_name", "127.0.0.1:8885")
    host_name: str = host_name_raw.strip()
    if host_name.startswith("http://") or host_name.startswith("https://"):
        return host_name.rstrip("/")
    return f"http://{host_name.rstrip('/')}"


def _configure_logging(config: Dict[str, Any], log_file: Optional[str] = None) -> None:
    target_log_file: str = (
        log_file
        or config["settings"].get("worker_log_file", config["settings"]["log_file"])
    )
    logging.basicConfig(
        filename=target_log_file,
        filemode="a",
        level=getattr(logging, config["settings"]["log_level"].upper()),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Run RSSTag worker in internal or external mode."
    )
    parser.add_argument(
        "config_path",
        nargs="?",
        default="rsscloud.conf",
        help="Path to config file. Default: rsscloud.conf",
    )
    parser.add_argument(
        "--mode",
        choices=("internal", "external"),
        default="internal",
        help="Worker mode. 'internal' is legacy DB worker, 'external' uses token API.",
    )
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("RSSTAG_API_BASE_URL", "").strip(),
        help="Base URL for external worker API, e.g. http://127.0.0.1:8885.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("RSSTAG_WORKER_TOKEN", "").strip(),
        help="Worker API token (or set RSSTAG_WORKER_TOKEN).",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="External mode polling interval in seconds.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=60.0,
        help="External mode request timeout in seconds.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="External mode: process at most one claim cycle and exit.",
    )
    return parser


def main() -> int:
    parser: argparse.ArgumentParser = _build_parser()
    args: argparse.Namespace = parser.parse_args()

    if args.mode == "internal":
        from rsstag.workers.dispatcher import RSSTagWorkerDispatcher

        worker: RSSTagWorkerDispatcher = RSSTagWorkerDispatcher(args.config_path)
        worker.start()
        return 0

    config: Optional[Dict[str, Any]] = load_config(args.config_path)
    if not config:
        parser.error(f"Unable to load config from: {args.config_path}")
        return 2

    _configure_logging(config)
    token: str = str(args.token or "").strip()
    if not token:
        parser.error(
            "External mode requires --token or RSSTAG_WORKER_TOKEN environment variable."
        )
        return 2

    api_base_url: str = (
        str(args.api_base_url).strip() or _build_default_api_base_url(config)
    )
    from rsstag.workers.external_worker import ExternalWorkerRunner

    external_worker: ExternalWorkerRunner = ExternalWorkerRunner(
        config=config,
        api_base_url=api_base_url,
        token=token,
        poll_interval_seconds=float(args.poll_interval),
        request_timeout_seconds=float(args.request_timeout),
    )
    external_worker.start(once=bool(args.once))
    return 0

if __name__ == "__main__":
    sys.exit(main())
