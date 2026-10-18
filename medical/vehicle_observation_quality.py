"""Provider-position timestamp quality gates; time is NOT inferred when absent."""
from datetime import datetime, timezone

MAX_AGE_SECONDS=600
FUTURE_TOLERANCE_SECONDS=90


def provider_timestamp(raw):
    if not raw or not str(raw).strip():
        return None
    s=str(raw).strip()
    try:
        if len(s)==14 and s.isdigit():
            dt=datetime.strptime(s,"%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            # Seoul bus service publishes its local clock without a TZ marker.
            from datetime import timedelta
            dt=dt-timedelta(hours=9)
        elif len(s)==19 and s[4]=="-" and s[10]==" ":
            dt=datetime.strptime(s,"%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            from datetime import timedelta
            dt=dt-timedelta(hours=9)
        else:
            dt=datetime.fromisoformat(s.replace("Z","+00:00"))
            if dt.tzinfo is None:
                return None
        return dt.astimezone(timezone.utc)
    except (ValueError,OverflowError):
        return None


def quality_label(row):
    raw=row.get("provider_observation_time")
    t=provider_timestamp(raw)
    if t is None:
        return "unknown_time"
    try:
        request=datetime.fromisoformat(row["request_time_utc"].replace("Z","+00:00"))
        if request.tzinfo is None: return "unknown_time"
    except (KeyError,ValueError,TypeError):
        return "unknown_time"
    age=(request-t).total_seconds()
    if age < -FUTURE_TOLERANCE_SECONDS: return "future_time"
    if age > MAX_AGE_SECONDS: return "stale"
    return "fresh"


def summarize_quality(rows):
    result={"fresh_low_floor_snapshots":0,"fresh_ordinary_snapshots":0,
            "fresh_unknown_type_snapshots":0,"stale_provider_snapshots":0,
            "unknown_time_snapshots":0,"future_time_snapshots":0}
    for row in rows:
        label=quality_label(row)
        if label=="fresh":
            typ=row.get("vehicle_type")
            result[{"low_floor":"fresh_low_floor_snapshots",
                    "ordinary":"fresh_ordinary_snapshots"}.get(typ,"fresh_unknown_type_snapshots")]+=1
        elif label=="stale":result["stale_provider_snapshots"]+=1
        elif label=="future_time":result["future_time_snapshots"]+=1
        else:result["unknown_time_snapshots"]+=1
    assert sum(result.values())==len(rows)
    return result
