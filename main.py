import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# 페이지 기본 설정
st.set_page_config(
    page_title="일별 기온 및 바람 날씨 정보",
    page_icon="🌤️",
    layout="wide"
)

@st.cache_data
def load_data():
    url = "https://raw.githubusercontent.com/jingyu20631/Weather/main/open-meteo-36.50N127.75E175m.csv"
    
    # 1. 파일 전체를 문자열 로드로 읽어와 주석(#) 제외
    try:
        # comment='#'로 주석 라인 무시하고 읽기
        raw_df = pd.read_csv(url, comment='#', header=None)
    except Exception as e:
        st.error(f"CSV 파일을 읽을 수 없습니다: {e}")
        return pd.DataFrame(), None

    if raw_df.empty:
        return pd.DataFrame(), raw_df

    # 2. 헤더 행 감지 (첫 번째 열에 'time'이나 'date'가 들어있는 행 찾기)
    header_idx = None
    for idx, row in raw_df.iterrows():
        first_cell = str(row.iloc[0]).lower()
        if 'time' in first_cell or 'date' in first_cell:
            header_idx = idx
            break

    # 헤더를 못 찾은 경우 0번 행을 헤더로 설정
    if header_idx is None:
        header_idx = 0

    # 3. 헤더 설정 및 데이터 재구성
    df = raw_df.iloc[header_idx + 1:].copy()
    df.columns = raw_df.iloc[header_idx].values
    
    # 컬럼명 공백 제거
    df.columns = [str(c).strip().replace('"', '') for c in df.columns]

    # 4. 첫 번째 데이터 행이 단위(iso8601, °C, m/s 등)인지 확인하고 제거
    first_val = str(df.iloc[0, 0]).lower()
    if 'iso' in first_val or 'unit' in first_val or 'gmt' in first_val or '°c' in first_val:
        df = df.iloc[1:].reset_index(drop=True)

    # 5. 시간/날짜 컬럼 처리 (첫번째 컬럼)
    time_col_name = df.columns[0]
    df['datetime'] = pd.to_datetime(df[time_col_name], errors='coerce')
    df = df.dropna(subset=['datetime'])
    df['date'] = df['datetime'].dt.date

    # 6. 컬럼 동적 매핑 (기온, 체감온도, 풍속)
    temp_col, app_col, wind_col = None, None, None

    for col in df.columns:
        c_low = col.lower()
        if 'temperature_2m' in c_low and 'apparent' not in c_low:
            temp_col = col
        elif 'apparent' in c_low:
            app_col = col
        elif 'wind' in c_low:
            wind_col = col

    # 매핑 실패 시 컬럼 인덱스 위치(1, 2, 3번째 열) 기준 fallback
    if not temp_col and len(df.columns) > 1:
        temp_col = df.columns[1]
    if not app_col and len(df.columns) > 2:
        app_col = df.columns[2]
    if not wind_col and len(df.columns) > 3:
        wind_col = df.columns[3]

    # 7. 수치형 데이터 강제 변환
    df['temperature'] = pd.to_numeric(df[temp_col], errors='coerce')
    df['apparent_temperature'] = pd.to_numeric(df[app_col], errors='coerce')
    df['wind_speed'] = pd.to_numeric(df[wind_col], errors='coerce')

    # 수치 데이터가 모두 NaN인 행 제외
    valid_df = df.dropna(subset=['temperature', 'apparent_temperature', 'wind_speed'])

    return valid_df, raw_df

try:
    df, raw_df = load_data()

    if df is None or df.empty:
        st.error("⚠️ 데이터를 불러왔으나 유효한 날씨 데이터 행을 추출하지 못했습니다.")
        
        # 원본 구조 디버깅 영역
        if raw_df is not None and not raw_df.empty:
            with st.expander("🔍 [디버그] 읽어온 원본 CSV 파일 상단 10줄 확인하기"):
                st.write("CSV 파일의 실제 행 구조입니다:")
                st.dataframe(raw_df.head(10))
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
    st.error(f"데이터 처리 중 에러가 발생했습니다: {e}")
