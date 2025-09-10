# 2025-1 CapstoneDesign

## Wi-Fi 로그 기반 공간 활용 분석 시스템

Wi-Fi AP 로그를 분석해 사용자 이동 흐름(zone flow) 을 재구성하고, 학습된 zone 분류 모델로 구역을 추정하여 요약 지표를 생성하는 파이프라인입니다.

- 로그에서 ap_name / band / rssi를 추출 → 내부/외부(in/out) 판별 → zone 예측
- 사용자별 세션(Flow) 구성, 이상치 제거, zone 흐름 문자열 생성
- 요약 통계 생성: 체류시간 분포, 시간대별 혼잡도, Top 이동 경로, 허브존 등
- 모델/전처리 번들은 models/real_final_zone_model_bundle.pkl 로 제공

---

### 프로젝트 배경
- 스토리움 공간은 복합 문화 공간으로 설계되었으나, 실제 운영에서는 사용자의 이동 흐름과 체류 패턴이 반영되지 못하고 있음  
- 기존 방식의 한계  
  - 출입구 센서는 단순 출입 현황만 제공하여 내부 이동 패턴을 파악하기 어려움  
  - 실내 환경에서는 GPS 기반 위치 파악이 제한적이어서 이동 경로나 혼잡도 예측에 한계가 있음  

따라서 본 프로젝트는 **Wi-Fi 로그만으로 이동 흐름을 분석**하여, **추가 장비 없이도 공간 활용도를 향상**시키는 것을 목표로 했습니다.

<br>

### 프로젝트 목표
1. **사용자 이동 및 체류 패턴 분석**
   - Wi-Fi 로그 기반 이동 흐름 데이터로 공간 이용 행태 파악  
2. **공간별 활용도 진단 (혼잡/저이용 구역 분석)**  
   - 시간대별 혼잡도와 체류 특성 분석을 통해 공간 운영 개선 방향 제시  
3. **분석 결과 기반 자동화 시스템 구현**  
   - 주간 리포트 자동 생성 및 실시간 대시보드 제공
  
<br>

### 시스템 아키텍처 구성도
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/233916d3-780d-475a-80dc-a90b7bf88e68" />


- **실시간 대시보드**: Grafana를 통해 공간 혼잡도와 사용자 이동 패턴을 시각화  
- **자동화 리포트 발송**: n8n 워크플로우를 통해 주간 공간 활용 리포트 메일 발송  
- **로그 수집 파이프라인**: rsyslog → Promtail → Grafana Loki → Grafana/n8n 

<br>

### 구성 요소
``` bash
.
├─ models/
│  └─ real_final_zone_model_bundle.pkl     # 학습된 전처리기 + 내부/외부 분류기 번들
├─ analyze_zone_flow_from_summary.py       # Flow 요약 테이블 → 통계 요약 dict 생성
├─ flow_analysis.py                        # 원시 로그 DataFrame → flow_summary 생성
├─ main.py                                 # (프로젝트 진입점)
├─ Dockerfile
├─ requirements.txt
├─ 1f.png / 2f.png                         # 지도/시각화용 레퍼런스 이미지
└─ README.md
``` 

<br>

### 입력 데이터 형식 (원시 로그)

flow_analysis.py는 DataFrame 형태의 로그를 입력으로 받습니다.

``` python
import pandas as pd
from flow_analysis import run_flow_analysis
from analyze_zone_flow_from_summary import summarize_flows

# 예시: CSV의 'Line' 컬럼에 원시 로그 문자열이 있음
df_log = pd.read_csv("syslog_raw.csv")   # 반드시 'Line' 컬럼 존재

flow_summary = run_flow_analysis(df_log)             # 사용자 flow 요약 테이블 생성
stats = summarize_flows(flow_summary)                # 요약 통계 dict 생성

print(flow_summary.head())
print(stats)
```

<br>

### 분석 파이프라인
#### A. flow_analysis.run_flow_analysis(df_log)
- 정규식 파싱: 시간/단말/대역/신호 등 추출 후 KST로 변환
- user_id 보완
  - identity 있으면 user@realm → user
  - 없으면 동일 MAC의 최신 identity를 참조
  - 그래도 없으면 client_mac 자체를 user_id로 사용
- Flow 구성(association 기준)
  - 사용자별 연속 이벤트 묶기
  - 7.5초 이하 근접 이벤트는 중복 제거
  - 10분 초과 공백 시 새 Flow 시작
- 이상치 제거: AP/대역 값 불일치 단발 스파이크
- in/out 판별 → zone 예측
  - AP·대역·RSSI 임계치 기반 classify_inout
  - 내부/외부에 따라 별도 RandomForestClassifier 사용
- 결과 컬럼
  - `flow, user_id, start_time, end_time, user_type, zone_flow, inout_flow, duration`

#### B. analyze_zone_flow_from_summary.summarize_flows(flow_summary)
- 체류시간 분포 (5분 ~ 15분 / 15 ~ 30분 / 30분 이상)
- zone별 평균 체류시간
- 시간대별 zone 이동량
- 혼잡 zone & 시간대 (최대 혼잡도, 혼잡 발생 시간대)
- 시작/종료 zone 통계 (입구·복도·카페 앞 등 그룹화)
- Top 5 이동 흐름
- zone 등장 횟수 Top5, 허브존 Top3, 서브플로우 Top5
- 일자별 고유 사용자 수
- 평균/최대 체류시간, 전체 flow 수

<br>

### 모델 번들 (models/real_final_zone_model_bundle.pkl)
#### 포함 객체
- preprocessor : OneHotEncoder + 수치 passthrough
- internal_model : 내부 zone용 RandomForestClassifier
- external_model : 외부 zone용 RandomForestClassifier

#### 내부/외부 판별 규칙 (classify_inout)
일부 예시:
- ap1: (band=2 & rssi ≤ 38.71) OR (band=5 & rssi ≤ 19.44) OR (band=6 & rssi ≤ 17.22) → 외부
- ap4: (band=2 & rssi ≤ 48.37) OR (band=5 & rssi ≤ 35.14) OR (band=6 & rssi ≤ 32.60) → 외부
- ap9: (band=2 & rssi ≤ 32.29) OR (band=5 & rssi ≤ 19.44) OR (band=6 & rssi ≤ 32.06) → 외부
- 그 외 조건 미해당 시 기본값 내부
> 외부 zone 후보는 ["1","6"] 범위에서만 예측되도록 설계되어 있습니다.

<br>

### (참고) 모델 학습 개요
- 데이터: CSV (zone, ap_name, band(int), rssi(float))
- 전처리: ap_name 원-핫, band/rssi 그대로 사용
- 분리
  - 내부: zone ∉ ["1","6"]
  - 외부: zone ∈ ["1","6"]
- 불균형 보정
  - 내부: SMOTE
  - 외부: RandomOverSampler
- 모델
  - 내부: RandomForestClassifier(n_estimators=300, max_depth=15, min_samples_leaf=2)
  - 외부: RandomForestClassifier(random_state=42)
- 저장: models/real_final_zone_model_bundle.pkl

<br>

### 팀 정보
팀명: Wi-Not

팀원: 김나영, 이영채, 조현서

과목: 2025-1 소프트웨어캡스톤디자인

주제: Wi-Fi 로그 기반 공간 활용 분석 시스템
