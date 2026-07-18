from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp_for_filename():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

