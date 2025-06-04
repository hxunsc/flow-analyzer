def summarize_flows(flow_summary):
    import pandas as pd

    # === zone 이름 매핑 ===
    zone_label_map = {
        "1": "1층 출입구",
        "6": "1.5층 출입구",
        "I": "1층 카페 앞",
        "H": "1층 내 쇼파석",
        "A": "1층 문쪽 공간",
        "C": "1층 계단쪽 공간",
        "E": "화장실 앞 복도",
        "L": "1.5층 내부 공간",
        "J": "2층 전시장 앞 공간",
        "K": "2층 전시장 내 공간",
        "M": "1층 바깥쪽 회의실 공간",
        "N": "1층 안쪽 회의실 공간"
    }

    def map_zone_name(z): return zone_label_map.get(z, z)

    # === 체류시간 계산 ===
    flow_summary["start_time"] = pd.to_datetime(flow_summary["start_time"])
    flow_summary["end_time"] = pd.to_datetime(flow_summary["end_time"])
    flow_summary["duration_seconds"] = (flow_summary["end_time"] - flow_summary["start_time"]).dt.total_seconds()

    # 체류시간 구간 분포
    bins = [0, 300, 900, 1800, float("inf")]
    labels = ["0~5분", "5~15분", "15~30분", "30분 이상"]
    flow_summary["duration_category"] = pd.cut(flow_summary["duration_seconds"], bins=bins, labels=labels, right=False)
    duration_distribution = flow_summary["duration_category"].value_counts().sort_index().to_dict()

    # zone_flow 기준 마지막 구역 기준 평균 체류시간
    def extract_last_zone(flow):
        if pd.isna(flow):
            return None
        return flow.strip().split(" → ")[-1]

    flow_summary["last_zone"] = flow_summary["zone_flow"].map(extract_last_zone)
    zone_avg_duration = (
        flow_summary.groupby("last_zone")["duration_seconds"]
        .mean().round(2)
        .rename(map_zone_name)
        .to_dict()
    )

    # 날짜별 흐름 수
    flow_summary["date"] = flow_summary["start_time"].dt.date
    flows_by_date = flow_summary.groupby("date").size().to_dict()

    # top 이동 흐름
    top_multi_flows = flow_summary["zone_flow"].value_counts().head(5).to_dict()

    # start zone 통계
    flow_summary["start_zone"] = flow_summary["zone_flow"].apply(lambda x: x.split(" → ")[0] if pd.notna(x) else None)
    zone_group_map = {
        "1": "1층 출입구", "6": "1.5층 출입구", "L": "1.5층 출입구",
        "E": "화장실 앞 복도", "I": "카페 앞 출입구"
    }

    grouped_counter_start = {}
    for z in flow_summary["start_zone"].dropna():
        key = zone_group_map.get(z, "기타")
        grouped_counter_start[key] = grouped_counter_start.get(key, 0) + 1

    # 최종 정리
    summary = {
        "flow_count": int(len(flow_summary)),
        "duration_distribution": {str(k): int(v) for k, v in duration_distribution.items()},
        "zone_avg_duration": zone_avg_duration,
        "flows_by_date": flows_by_date,
        "top_multi_flows": {k: f"{v}회" for k, v in top_multi_flows.items()},
        "start_zone_stats": grouped_counter_start,
        "avg_duration": round(flow_summary["duration_seconds"].mean(), 2),
        "max_duration": round(flow_summary["duration_seconds"].max(), 2),
    }

    return summary
