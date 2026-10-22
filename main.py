import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import io

# 페이지 기본 설정
st.set_page_config(
    page_title="일별 기온 및 바람 날씨 정보",
    page_icon="🌤️",
    layout="wide"
)

@st.cache_data
def load_data():
    url = "https://raw.githubusercontent.com/jingyu20631/Weather/main/open-meteo-36.50N127.75E175m.csv"
    
    # 1. 텍스트로 먼져 받아와서 주석(#)이 아닌 줄만 필터링
    res = requests.get(url)
    res.raise_for_status()
    lines = [line for line in res.text.splitlines() if not line.strip().startswith('#')]
    
    if not lines:
        st.error("데이터 파일이 비어 있거나 주석만 존재합니다.")
        return pd.DataFrame()
    
    # 2. CSV 로드
    csv_data = "\n".join(lines)
    df = pd.read_csv(io.StringIO(csv_data))
    
    # 컬럼명 정리
    df.columns = df.columns.str.strip().str.replace('"', '')
    
    # 3. 만약 0번째 행이 단위(iso8601, °C, m/s 등)인 경우 데이터에서 제거
    # 첫 행의 time/date 컬럼 값이 숫자로 변환되지 않거나 iso8601 문구가 들어있는지 확인
    first_val = str(df.iloc[0, 0]).lower()
    if 'iso8601' in first_val or 'unixtime' in first_val or 'gmt' in first_val:
        df = df.iloc[1:].reset_index(drop=True)
    
    # 4. 시간/날짜 컬럼 탐색 및 변환
    time_col = [c for c in df.columns if 'time' in c.lower() or 'date' in c.lower()]
    if not time_col:
        st.error("시간(time) 컬럼을 찾을 수 없습니다.")
        return pd.DataFrame()
    
    t_name = time_col[0]
    df['datetime'] = pd.to_datetime(df[t_name], errors='coerce')
    df = df.dropna(subset=['datetime'])
    df['date'] = df['datetime'].dt.date

    # 5. 기온, 체감온도, 풍속 컬럼 탐색
    temp_col = [c for c in df.columns if 'temperature_2m' in c.lower() and 'apparent' not in c.lower()]
    app_col = [c for c in df.columns if 'apparent' in c.lower()]
    wind_col = [c for c in df.columns if 'wind' in c.lower()]

    # 찾지 못한 경우 대체 컬럼 탐색 (컬럼 순서 기반 감지)
    if not temp_col and len(df.columns) > 1:
        temp_col = [df.columns[1]]
    if not app_col and len(df.columns) > 2:
        app_col = [df.columns[2]]
    if not wind_col and len(df.columns) > 3:
        wind_col = [df.columns[3]]

    # 6. 수치형 데이터 강제 변환
    df['temperature'] = pd.to_numeric(df[temp_col[0]], errors='coerce')
    df['apparent_temperature'] = pd.to_numeric(df[app_col[0]], errors='coerce')
    df['wind_speed'] = pd.to_numeric(df[wind_col[0]], errors='coerce')

    # NaN 데이터 제거
    df = df.dropna(subset=['temperature', 'apparent_temperature', 'wind_speed'])
    
    return df

try:
    df = load_data()

    if df.empty:
        st.error("데이터를 불러왔으나 유효한 날씨 데이터가 없습니다.")
    else:
        st.title("🌤️ 일별 날씨 & 바람 정보 데이터 세트")
        st.markdown("Open-Meteo 데이터셋 기반 **기온, 체감온도, 풍속** 상태 분석")

        # 사이드바: 날짜 선택
        available_dates = df['date'].unique()
        selected_date = st.sidebar.selectbox("📅 조회할 날짜를 선택하세요", available_dates)

        # 선택된 날짜의 데이터 필터링
        daily_df = df[df['date'] == selected_date].copy()

        # 하루 통계 계산
        max_temp = daily_df['temperature'].max()
        min_temp = daily_df['temperature'].min()
        avg_temp = daily_df['temperature'].mean()
        
        max_app_temp = daily_df['apparent_temperature'].max()
        min_app_temp = daily_df['apparent_temperature'].min()
        
        avg_wind = daily_df['wind_speed'].mean()
        max_wind = daily_df['wind_speed'].max()

        st.subheader(f"📌 {selected_date} 일기 요약")

        # 메트릭 카드 배치
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(label="최고 기온 / 체감", value=f"{max_temp:.1f} °C", delta=f"체감 {max_app_temp:.1f} °C")
        with col2:
            st.metric(label="최저 기온 / 체감", value=f"{min_temp:.1f} °C", delta=f"체감 {min_app_temp:.1f} °C", delta_color="inverse")
        with col3:
            st.metric(label="평균 기온", value=f"{avg_temp:.1f} °C")
        with col4:
            st.metric(label="최대 풍속", value=f"{max_wind:.1f} m/s", delta=f"평균 {avg_wind:.1f} m/s")

        st.markdown("---")

        # 그래프 1: 시간별 기온 및 체감온도
        st.subheader("🌡️ 시간별 기온 및 체감온도 변화")
        fig_temp = go.Figure()
        fig_temp.add_trace(go.Scatter(
            x=daily_df['datetime'], y=daily_df['temperature'],
            mode='lines+markers', name='실제 기온 (°C)',
            line=dict(color='#FF5733', width=2)
        ))
        fig_temp.add_trace(go.Scatter(
            x=daily_df['datetime'], y=daily_df['apparent_temperature'],
            mode='lines+markers', name='체감 온도 (°C)',
            line=dict(color='#FFC300', width=2, dash='dash')
        ))
        fig_temp.update_layout(
            xaxis_title="시간",
            yaxis_title="온도 (°C)",
            hovermode="x unified",
            margin=dict(l=20, r=20, t=30, b=20)
        )
        st.plotly_chart(fig_temp, use_container_width=True)

        # 그래프 2: 시간별 바람 속도
        st.subheader("💨 시간별 바람 속도 변화")
        fig_wind = go.Figure()
        fig_wind.add_trace(go.Bar(
            x=daily_df['datetime'], y=daily_df['wind_speed'],
            name='풍속 (m/s)',
            marker_color='#33A8FF'
        ))
        fig_wind.update_layout(
            xaxis_title="시간",
            yaxis_title="풍속 (m/s)",
            hovermode="x unified",
            margin=dict(l=20, r=20, t=30, b=20)
        )
        st.plotly_chart(fig_wind, use_container_width=True)

        # 상세 데이터 테이블
        with st.expander("📋 원본 데이터 보기"):
            st.dataframe(daily_df[['datetime', 'temperature', 'apparent_temperature', 'wind_speed']], use_container_width=True)

except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
