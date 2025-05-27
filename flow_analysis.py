import joblib
from datetime import datetime, timedelta
import re
import pandas as pd
import numpy as np


def classify_inout(ap, band, rssi):
    if pd.isna(ap) or pd.isna(band) or pd.isna(rssi):
        return None
    band = int(band)
    rssi = float(rssi)
    if ap == "ap1" and (band == 2 or (band == 5 and rssi <= 20.66) or (band == 6 and rssi <= 22.14)):
        return "외부"
    if ap == "ap2" and (band == 6 and rssi <= 15.36):
        return "외부"
    if ap == "ap3" and (band == 2 or (band == 5 and rssi <= 31.49) or (band == 6 and rssi <= 17.02)):
        return "외부"
    if ap == "ap4" and (band == 2 or (band == 5 and rssi <= 39.55) or (band == 6 and rssi <= 31.63)):
        return "외부"
    if ap == "ap6" and ((band == 5 and rssi <= 16.55) or (band == 6 and rssi <= 18.19)):
        return "외부"
    if ap == "ap9" and ((band == 2 and rssi <= 32.31) or (band == 5 and rssi <= 28.73) or (band == 6 and rssi <= 28.00)):
        return "외부"
    if ap == "ap10" and (band == 5 and rssi <= 14.64):
        return "외부"
    return "내부"


def run_flow_analysis(df_log):
    regex_patterns = {
        "timestamp": r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)\+00:00",
        "ap": r"A_CISCO_storyum_[\w_]+_(ap\d+)",
        "type": r"type=([\w_]+)",
        "client_mac": r"client_mac='([\w:]+)'",
        "identity": r"identity='([^']+)'",
        "band": r"band='?(\d+)'?",
        "rssi": r"rssi='?(\d+)'?",
        "vap": r"vap='?(\d+)'?"
    }

    def extract_log_info(line):
        extracted = {}
        for key, pattern in regex_patterns.items():
            match = re.search(pattern, line)
            extracted[key] = match.group(1) if match else None
        try:
            extracted["timestamp"] = datetime.strptime(extracted["timestamp"], "%Y-%m-%dT%H:%M:%S.%f") + timedelta(hours=9)
        except:
            extracted["timestamp"] = None
        return extracted

    parsed_df = df_log["Line"].apply(extract_log_info).apply(pd.Series)
    parsed_df["rssi"] = pd.to_numeric(parsed_df["rssi"], errors="coerce")
    parsed_df["band"] = pd.to_numeric(parsed_df["band"], errors="coerce")

    identity_map = (
        parsed_df[parsed_df["identity"].notna()]
        .sort_values("timestamp", ascending=False)
        .drop_duplicates(subset=["client_mac"])
    )
    identity_map["user_id"] = identity_map["identity"].apply(lambda x: x.split("@")[0])
    mac_to_user = dict(zip(identity_map["client_mac"], identity_map["user_id"]))

    parsed_df["identity"] = parsed_df["identity"].fillna("anonymous")
    parsed_df = parsed_df.dropna(subset=["ap", "rssi", "band"])
    parsed_df.rename(columns={"ap": "ap_name"}, inplace=True)
    parsed_df["user_type"] = parsed_df["vap"].apply(lambda x: "외부인" if str(x) == "0" else "내부인")

    def assign_user_id(row):
        if row["identity"] != "anonymous":
            return row["identity"].split("@")[0]
        elif row["client_mac"] in mac_to_user:
            return mac_to_user[row["client_mac"]]
        else:
            return row["client_mac"]

    parsed_df["user_id"] = parsed_df.apply(assign_user_id, axis=1)
    parsed_df = parsed_df[parsed_df["timestamp"].apply(lambda x: isinstance(x, datetime))]
    parsed_df = parsed_df.sort_values(by=["user_id", "timestamp"])

    model_bundle = joblib.load("models/zone_model_bundle.pkl")
    preprocessor = model_bundle["preprocessor"]
    internal_clf = model_bundle["internal_model"]
    external_clf = model_bundle["external_model"]

    parsed_df["inout"] = parsed_df.apply(lambda row: classify_inout(row["ap_name"], row["band"], row["rssi"]), axis=1)

    def predict_zone(row):
        X_input = pd.DataFrame([{"ap_name": row["ap_name"], "band": row["band"], "rssi": row["rssi"]}])
        X_pre = preprocessor.transform(X_input)
        if row["inout"] == "내부":
            return internal_clf.predict(X_pre)[0]
        elif row["inout"] == "외부":
            return external_clf.predict(X_pre)[0]
        return None

    parsed_df["zone_pred"] = parsed_df.apply(predict_zone, axis=1)

    assoc_logs = parsed_df[(parsed_df["type"] == "association") & (parsed_df["rssi"] >= 10)].copy()
    assoc_logs = assoc_logs.sort_values(by=["user_id", "timestamp"])

    flow_map = {}
    drop_idx_set = set()
    last_user = None
    last_valid_time = None
    flow_counter = 0

    for idx, row in assoc_logs.iterrows():
        user = row["user_id"]
        time = row["timestamp"]
        if user != last_user:
            flow_counter = 1
            last_valid_time = time
        else:
            gap = (time - last_valid_time).total_seconds()
            if gap <= 7.5:
                drop_idx_set.add(idx)
                flow_id = f"{user}_flow{str(flow_counter).zfill(2)}"
                flow_map[(user, time)] = flow_id
                continue
            elif gap > 600:
                flow_counter += 1
            last_valid_time = time

        flow_id = f"{user}_flow{str(flow_counter).zfill(2)}"
        flow_map[(user, time)] = flow_id
        last_user = user

    parsed_df["flow"] = None
    for idx, row in parsed_df.iterrows():
        user = row["user_id"]
        time = row["timestamp"]
        candidates = assoc_logs[(assoc_logs["user_id"] == user) & (assoc_logs["timestamp"] <= time)]
        if not candidates.empty:
            closest_time = candidates["timestamp"].max()
            parsed_df.at[idx, "flow"] = flow_map.get((user, closest_time))

    flow_df = parsed_df.copy()
    flow_df.loc[list(drop_idx_set), "zone_pred"] = pd.NA
    flow_df.loc[flow_df['rssi'] < 10, 'zone_pred'] = pd.NA

    flow_outlier_idx = set()
    for flow_id, group in flow_df.groupby("flow"):
        if len(group) < 3:
            continue
        group = group.sort_values("timestamp")
        for i in range(1, len(group) - 1):
            prev_ap, curr_ap, next_ap = group.iloc[i - 1]["ap_name"], group.iloc[i]["ap_name"], group.iloc[i + 1]["ap_name"]
            prev_band, curr_band, next_band = group.iloc[i - 1]["band"], group.iloc[i]["band"], group.iloc[i + 1]["band"]
            if curr_ap != prev_ap and curr_ap != next_ap and prev_ap == next_ap:
                flow_outlier_idx.add(group.index[i])
            elif curr_band != prev_band and curr_band != next_band and prev_band == next_band:
                flow_outlier_idx.add(group.index[i])

    flow_df.loc[list(flow_outlier_idx), "zone_pred"] = pd.NA

    flow_summary = (
        flow_df.dropna(subset=["zone_pred", "flow"])
        .groupby("flow")
        .agg(
            user_id=("user_id", "first"),
            start_time=("timestamp", "min"),
            end_time=("timestamp", "max"),
            user_type=("user_type", lambda x: x.mode().iloc[0]),
            zone_flow=("zone_pred", lambda x: " → ".join([v for i, v in enumerate(x.dropna().astype(str)) if i == 0 or v != x.dropna().astype(str).iloc[i - 1]])),
            inout_flow=("inout", lambda x: " → ".join([v for i, v in enumerate(x.dropna().astype(str)) if i == 0 or v != x.dropna().astype(str).iloc[i - 1]]))
        )
        .reset_index()
    )

    flow_summary["duration"] = flow_summary["end_time"] - flow_summary["start_time"]
    flow_summary = flow_summary[flow_summary["duration"] > timedelta(seconds=0)]
    flow_summary["duration"] = flow_summary["duration"].apply(lambda x: str(x).split(" ")[-1].split(".")[0])

    return flow_summary
