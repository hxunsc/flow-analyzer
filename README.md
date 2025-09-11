# Wi-Fi 로그 기반 공간 활용 분석 시스템

**팀명**: Wi-Not | **팀원**: 김나영, 이영채, 조현서

> **Wi-Fi 로그만으로 이동 흐름 파악이 가능** → **추가 장비 없이 공간 활용도 향상**

## 수상 내역
**2025학년도 1학기 캡스톤디자인 우수작품 경진대회 은상 수상** (소프트웨어중심대학사업단 주최)

## 프로젝트 개요

### 프로젝트 배경

**현재 공간 활용도 저조**
- 스토리움 공간은 복합 문화 공간으로 설계되었으나, 사용자의 이동 흐름과 체류 패턴을 반영한 공간 운영이 이뤄지지 않음

**기존 방식의 한계**
- 출입구 센서로도 가능하지만, 단순 출입 현황만 제공
  → 공간 안에서의 사용자 이동 패턴은 알기 어려움
- 실내에서는 GPS를 통한 위치 파악이 어려움
  → 이동 경로, 혼잡도 예측에 한계

### 프로젝트 목표

**효율적 공간 관리 기반 마련**

1. **사용자 이동 및 체류 패턴 분석**
   - 사용자 흐름 데이터를 기반으로 공간 이용 행태 파악

2. **공간별 활용도 진단 (혼잡도/저이용 구역 분석)**
   - 시간대별 혼잡도 및 체류 특성 분석을 통해 공간 운영 개선방향 제시

3. **분석 결과 기반의 자동화 시스템 구현**
   - 주간 리포트 자동 생성 + 실시간 대시보드 구축

## 시스템 아키텍처

<img width="1920" height="1080" alt="시스템 아키텍처 구성도" src="https://github.com/user-attachments/assets/233916d3-780d-475a-80dc-a90b7bf88e68" />

**주요 구성 요소**:
- **실시간 대시보드**: Grafana를 통해 공간 혼잡도와 사용자 이동 패턴을 시각화
- **자동화 리포트 발송**: n8n 워크플로우를 통해 주간 공간 활용 리포트 메일 발송
- **로그 수집 파이프라인**: rsyslog → Promtail → Grafana Loki → Grafana/n8n

## 데이터 수집

### 분석 대상 공간
- 전남대학교 스토리움

### 데이터 수집 장비
- 기존 설치된 Cisco Meraki AP 10대

### 데이터 수집 항목
- Wi-Fi 무선 접속 로그 (eduroam, JNU)
- 현재 시스템은 AP 연결/해제 이벤트 발생 시 로그만 생성됨
  → 이를 활용해 분석 진행

### 주요 필드 소개

- **RSSI**: Wi-Fi 신호의 세기를 나타내는 수치
- **Band**: Wi-Fi가 사용하는 주파수 대역 (예: 2.4GHz, 5GHz, 6GHz)
- **Identity**: 네트워크에 접속할 때 인증된 계정 정보 (ex. 포털 아이디)

※ 본 프로젝트에서 수집된 RSSI 값은 Cisco Meraki 장비의 특성상 양수 값(0-100 범위)으로 제공됨

## 존 구역 예측

### 사용자 로그 기반 구역 예측

#### 모델 생성 과정
수집된 Wi-Fi 데이터를 기반으로 사용자의 위치를 예측하는 머신러닝 모델을 개발했습니다. 내부/외부 구역을 분리하여 각각 최적화된 모델을 구축했습니다.

- **내부**: SMOTE 오버샘플링 → RandomForest 학습 → 실내 모델 저장
- **외부**: RandomOverSampler → RandomForest 학습 → 출입구 모델 저장

#### 구역 예측 정확도 평가

**총 데이터 수**: 1,062개

**정확도 평가 방법**: 학습:검증 = 8:2 비율로 분할

**결과**:
- **실내 예측 정확도**: 82%
- **출입구 예측 정확도**: 91%

## 사용자 이동 흐름 분석

### 1차 전처리
**MAC-identity 통합**: MAC 주소 랜덤화, 단말 유저의 여러 기기 보유 가능성 고려
→ identity + MAC address 기준으로 사용자 통합 처리

### 흐름 예측 정확도 테스트
**예측 모델 적용 결과**:
- 순체하지 않는 흐름까지 포함된 잘못된 분석 결과가 도출됨

**비정상 연결(AP-Band팀, 짧은 체류)로 실제 방문하지 않은 구역까지 이동 경로에 포함되는 문제 발생**

## Tech Stack

**Backend**: Python, pandas, scikit-learn, RandomForest  
**Visualization**: Grafana, Grafana Loki  
**Automation**: n8n workflow  
**Infrastructure**: Docker, rsyslog, Promtail  
**ML Pipeline**: SMOTE, RandomOverSampler, OneHotEncoder

## 프로젝트 구조

```bash
.
├─ models/
│  └─ real_final_zone_model_bundle.pkl     # 학습된 전처리기 + 내부/외부 분류기 번들
├─ analyze_zone_flow_from_summary.py       # Flow 요약 테이블 → 통계 요약 dict 생성
├─ flow_analysis.py                        # 원시 로그 DataFrame → flow_summary 생성
├─ main.py                                 # 프로젝트 진입점
├─ Dockerfile
├─ requirements.txt
├─ 1f.png / 2f.png                         # 지도/시각화용 레퍼런스 이미지
└─ README.md
```

## 입력 데이터 형식

flow_analysis.py는 DataFrame 형태의 로그를 입력으로 받습니다.

```python
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

## 분석 파이프라인

### A. flow_analysis.run_flow_analysis(df_log)
- **정규식 파싱**: 시간/단말/대역/신호 등 추출 후 KST로 변환
- **user_id 보완**
  - identity 존재 시: user@realm → user
  - identity 없을 시: 동일 MAC의 최신 identity 참조
  - 그래도 없으면: client_mac 자체를 user_id로 사용
- **Flow 구성** (association 기준)
  - 사용자별 연속 이벤트 묶기
  - 7.5초 이하 근접 이벤트는 중복 제거
  - 10분 초과 공백 시 새 Flow 시작
- **이상치 제거**: AP/대역 값 불일치 단발 스파이크 제거
- **in/out 판별 → zone 예측**
  - AP·대역·RSSI 임계치 기반 classify_inout
  - 내부/외부에 따라 별도 RandomForestClassifier 사용

**결과 컬럼**: `flow, user_id, start_time, end_time, user_type, zone_flow, inout_flow, duration`

### B. analyze_zone_flow_from_summary.summarize_flows(flow_summary)
- 체류시간 분포 (5분 ~ 15분 / 15 ~ 30분 / 30분 이상)
- zone별 평균 체류시간
- 시간대별 zone 이동량
- 혼잡 zone & 시간대 (최대 혼잡도, 혼잡 발생 시간대)
- 시작/종료 zone 통계 (입구·복도·카페 앞 등 그룹화)
- Top 5 이동 흐름, zone 등장 횟수 Top5, 허브존 Top3, 서브플로우 Top5
- 일자별 고유 사용자 수, 평균/최대 체류시간, 전체 flow 수

## 모델 성능

### 모델 번들 (models/real_final_zone_model_bundle.pkl)
**포함 객체**:
- `preprocessor`: OneHotEncoder + 수치 passthrough
- `internal_model`: 내부 zone용 RandomForestClassifier
- `external_model`: 외부 zone용 RandomForestClassifier

## 분석 결과 대시보드

![2025-09-107-ezgif com-video-to-gif-converter](https://github.com/user-attachments/assets/2443fd24-53a5-43a6-b935-ac31befd0c5d)


### 내부/외부 판별 규칙 (classify_inout)
```python
# 일부 예시 규칙
# ap1: (band=2 & rssi ≤ 38.71) OR (band=5 & rssi ≤ 19.44) OR (band=6 & rssi ≤ 17.22) → 외부
# ap4: (band=2 & rssi ≤ 48.37) OR (band=5 & rssi ≤ 35.14) OR (band=6 & rssi ≤ 32.60) → 외부
# ap9: (band=2 & rssi ≤ 32.29) OR (band=5 & rssi ≤ 19.44) OR (band=6 & rssi ≤ 32.06) → 외부
# 조건 미해당 시 기본값: 내부
```

> 외부 zone 후보는 ["1","6"] 범위에서만 예측되도록 설계

### 모델 학습 개요
- **데이터**: CSV (zone, ap_name, band(int), rssi(float))
- **전처리**: ap_name 원-핫 인코딩, band/rssi 수치 그대로 사용
- **데이터 분리**
  - 내부: zone ∉ ["1","6"]
  - 외부: zone ∈ ["1","6"]
- **불균형 보정**
  - 내부: SMOTE
  - 외부: RandomOverSampler
- **모델 설정**
  - 내부: RandomForestClassifier(n_estimators=300, max_depth=15, min_samples_leaf=2)
  - 외부: RandomForestClassifier(random_state=42)

---

**과목**: 2025-1 소프트웨어캡스톤디자인
