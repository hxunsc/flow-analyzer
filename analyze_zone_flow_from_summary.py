def summarize_flows(flow_summary):
    import pandas as pd

    # 상위 zone 이동 경로 top 5
    top_zone_flows = flow_summary["zone_flow"].value_counts().head(5)

    # start zone별 다음 zone 분포도
    flow_summary["start_zone"] = flow_summary["zone_flow"].apply(
        lambda x: x.split(" → ")[0] if pd.notna(x) else None
    )

    zone_stats = {}
    for zone in ["1", "6", "E"]:
        next_zone_counts = (
            flow_summary[flow_summary["start_zone"] == zone]["zone_flow"]
            .dropna()
            .apply(lambda x: x.split(" → ")[1] if " → " in x else None)
            .value_counts()
            .to_dict()
        )
        zone_stats[zone] = next_zone_counts

    # JSON 직렬화 가능한 형태로 반환
    return {
        "top_zone_flows": top_zone_flows.to_dict(),
        "start_zone_stats": zone_stats,
        "flow_count": int(len(flow_summary)),
    }

