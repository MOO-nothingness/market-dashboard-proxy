# api/data.py
import os
import yfinance as yf
import requests
import pandas as pd
from datetime import datetime, timedelta
from fredapi import Fred
from flask import Flask, jsonify

# --- API 키 로드 (Vercel 환경 변수 사용) ---
# Vercel 프로젝트 설정에서 FRED_API_KEY 이름으로 실제 키 값을 설정해야 함
FRED_API_KEY = os.environ.get('FRED_API_KEY')

USE_FRED = FRED_API_KEY is not None
fred = None
if USE_FRED:
    try:
        fred = Fred(api_key=FRED_API_KEY)
        print("FRED API 사용 가능 상태.")
    except Exception as e:
        print(f"경고: FRED API 초기화 실패: {e}. FRED 데이터를 가져올 수 없습니다.")
        USE_FRED = False
else:
     print("경고: FRED API 키 환경 변수가 설정되지 않았습니다. FRED 데이터를 가져올 수 없습니다.")

# --- 데이터 가져오기 함수들 (data_fetcher.py 내용 통합 및 수정) ---

def get_multiple_yf_data(tickers, period='1y'):
    # (이전 답변의 get_multiple_yf_data 함수 내용 복사 붙여넣기 - 오류 처리 강화 버전)
    print(f"yfinance 데이터 로딩 중: {', '.join(tickers)}")
    try:
        data = yf.download(tickers, period=period, progress=False, timeout=15) # 타임아웃 늘림
        if data is None or data.empty: return None, f"yfinance 데이터 없음 ({', '.join(tickers)})"
        if 'Close' not in data.columns and ('Close', tickers[0]) not in data.columns:
             if 'Adj Close' in data.columns or ('Adj Close', tickers[0]) in data.columns:
                 print("   'Adj Close' 컬럼을 대신 사용합니다.")
                 # 실제 사용 로직은 아래에서 처리
             else: return None, f"'Close' 또는 'Adj Close' 컬럼 없음 ({', '.join(tickers)})"

        results = {}
        ticker_list = tickers if isinstance(tickers, list) else tickers.split()

        for ticker in ticker_list:
            try:
                hist_data = None; close_col_name = 'Close'; adj_close_col_name = 'Adj Close'
                # MultiIndex 처리
                if isinstance(data.columns, pd.MultiIndex):
                    close_col = ('Close', ticker); adj_close_col = ('Adj Close', ticker)
                    if close_col in data.columns: hist_data = data[close_col].dropna().to_frame(name=close_col_name)
                    elif adj_close_col in data.columns: hist_data = data[adj_close_col].dropna().to_frame(name=close_col_name); print(f"  {ticker}: Adj Close 사용")
                # 단일 Index 또는 단일 티커 처리
                else:
                    if ticker in data.columns: hist_data = data[[ticker]].dropna().rename(columns={ticker:close_col_name})
                    elif close_col_name in data.columns and len(ticker_list) == 1: hist_data = data[[close_col_name]].dropna()
                    elif adj_close_col_name in data.columns and len(ticker_list) == 1: hist_data = data[[adj_close_col_name]].dropna().rename(columns={adj_close_col_name:close_col_name}); print(f"  {ticker}: Adj Close 사용")

                if hist_data is not None and not hist_data.empty:
                    current_price = hist_data[close_col_name].iloc[-1]
                    ma50 = hist_data[close_col_name].rolling(window=50).mean().iloc[-1] if len(hist_data) >= 50 else None
                    ma200 = hist_data[close_col_name].rolling(window=200).mean().iloc[-1] if len(hist_data) >= 200 else None
                    change_1m = hist_data[close_col_name].pct_change(periods=21).iloc[-1] * 100 if len(hist_data) >= 22 else None

                    results[ticker] = {'price': current_price, 'ma50': ma50, 'ma200': ma200, 'change_1m': change_1m, 'error': None}
                else: results[ticker] = {'error': f'{ticker} 이력 데이터 없음'}
            except Exception as e_inner: results[ticker] = {'error': f'{ticker} 처리 오류: {e_inner}'}
        return results, None
    except Exception as e: return None, f"yfinance 오류: {e}"


def get_etf_pe_ratio(ticker):
    # (이전 코드와 동일)
    try:
        etf = yf.Ticker(ticker)
        info = etf.info
        pe_ratio = info.get('trailingPE') or info.get('forwardPE')
        if pe_ratio: return float(pe_ratio), None
        else: return None, f"{ticker} P/E 정보 없음"
    except Exception as e: return None, f"{ticker} P/E 오류: {e}"


def get_fear_greed_index():
    # (이전 코드와 동일)
    try:
        response = requests.get("https://api.alternative.me/fng/?limit=1")
        response.raise_for_status()
        data = response.json()
        if data and 'data' in data and len(data['data']) > 0: return int(data['data'][0]['value']), None
        else: return None, "F&G 데이터 형식 오류"
    except Exception as e: return None, f"F&G 오류: {e}"


def get_fred_latest_data(series_id):
    # (이전 코드와 동일, fred 객체 사용)
    if not USE_FRED or fred is None: return None, "FRED API 사용 불가"
    try:
        end_date = datetime.now(); start_date = end_date - timedelta(days=370)
        data = fred.get_series(series_id, observation_start=start_date.strftime('%Y-%m-%d'))
        data = data.dropna()
        if data.empty: return None, f"{series_id} 데이터 없음"
        return data.iloc[-1], None
    except Exception as e: return None, f"FRED {series_id} 오류: {e}"


def get_fred_yield_spread(series1='DGS10', series2='DGS2'):
    # (이전 코드와 동일, 오류 처리 강화 버전 사용)
    val1, err1 = get_fred_latest_data(series1)
    val2, err2 = get_fred_latest_data(series2)
    if err1 or err2:
        combined_error = list(filter(None, [err1, err2]))
        return None, ", ".join(combined_error) if combined_error else "금리 데이터 오류"
    try:
        val1_float = float(val1) if val1 is not None else None
        val2_float = float(val2) if val2 is not None else None
        if val1_float is None or val2_float is None: return None, "금리 값 변환 불가"
        spread = val1_float - val2_float
        return spread, None
    except (TypeError, ValueError) as e: return None, f"금리 스프레드 계산 오류: {e}"

# FRED 시리즈 ID
FRED_SERIES = {'10y_yield': 'DGS10', '2y_yield': 'DGS2', 'unemployment': 'UNRATE', 'ism_pmi': 'ISM'}

# --- 데이터 분석 함수 (analyzer.py 내용 통합) ---
def analyze_indicator(name, value, error_msg=None, **kwargs):
    # (이전 답변의 analyze_indicator 함수 내용 전체 복사 붙여넣기 - 최종 버전)
    status, score, color_class, display_value, explanation = "N/A", 0, "neutral", "N/A", "데이터를 분석 중입니다."
    final_error = error_msg

    price = kwargs.get('price')
    ma50 = kwargs.get('ma50')
    ma200 = kwargs.get('ma200')
    change_1m = kwargs.get('change_1m')
    compare_data = kwargs.get('compare_data')

    if final_error:
        status, display_value, color_class, explanation, score = f"오류: {final_error}", "오류", 'error', "데이터 오류가 발생했어요.", 0
    elif value is None and name not in ['Market Trend (MA)', 'Market Breadth (RSP vs SPY)', 'Oil Trend (USO)', 'Gold Trend (GLD)']:
        status, display_value, color_class, explanation, score = '데이터 없음', 'N/A', 'neutral', "관련 데이터를 찾을 수 없어요.", 0
    else:
        try:
            if name == "Market P/E":
                explanation = "시장의 '가격표'가 이익에 비해 얼마나 비싼지 보는 거예요. 높으면 비싸다는 신호일 수 있어요."
                display_value = f"{float(value):.2f}"
                if float(value) < 18: status, score, color_class = "긍정적 (저평가 경향)", 1, 'positive'
                elif float(value) > 25: status, score, color_class = "부정적 (고평가 경향)", -1, 'negative'
                else: status, score, color_class = "중립적", 0, 'neutral'
            # ... (analyzer.py의 나머지 지표 분석 로직 전체 붙여넣기) ...
            elif name == "ISM PMI":
                 explanation = "공장(제조업)들이 얼마나 바쁘게 돌아가는지 알려주는 지표예요. 50보다 높으면 경기가 좋아지고 있다는 뜻이에요."
                 display_value = f"{float(value):.1f}"
                 if float(value) > 55: status, score, color_class = "긍정적 (제조업 확장 강함)", 1, 'positive'
                 elif float(value) < 48: status, score, color_class = "부정적 (제조업 위축)", -1, 'negative'
                 elif float(value) >= 50: status, score, color_class = "중립적 (제조업 확장 약함)", 0, 'neutral'
                 else: status, score, color_class = "중립적 (제조업 위축 약함)", 0, 'neutral'
            else:
                 display_value = str(value) if value is not None else 'N/A'
                 status = "알 수 없음"; explanation = "이 지표 설명을 찾을 수 없어요."
        except (ValueError, TypeError) as e: status, display_value, color_class, explanation, score, final_error = f"값 형식 오류: {e}", '오류', 'error', "데이터 형식을 이해할 수 없어요.", 0, str(e)
        except Exception as e: status, display_value, color_class, explanation, score, final_error = f"분석 오류: {e}", '오류', 'error', "데이터 분석 중 예상치 못한 오류 발생", 0, str(e)

    if final_error or status == '데이터 없음': score = 0
    return {'value': display_value, 'status': status, 'score': score, 'color_class': color_class, 'error': final_error, 'explanation': explanation}

def get_overall_assessment(total_score, num_indicators):
    # (이전 답변의 get_overall_assessment 함수 내용 전체 복사 붙여넣기)
    if num_indicators == 0: return "데이터 부족", 'neutral', "분석할 수 있는 유효한 데이터가 부족합니다."
    positive_threshold = max(2, num_indicators // 4); negative_threshold = -max(2, num_indicators // 4)
    if total_score >= positive_threshold: assessment, color_class, explanation = "시장 분위기: 긍정적 요소 우세 😊", 'positive', "종합적으로 긍정적인 신호들이 더 많이 보여요. 하지만 항상 변동성에 대비하는 자세가 중요합니다!"
    elif total_score <= negative_threshold: assessment, color_class, explanation = "시장 분위기: 부정적 요소 우세 😟", 'negative', "주의가 필요한 신호들이 상대적으로 많아 보입니다. 투자 결정을 내릴 때 더 신중하게 접근하는 것이 좋겠어요."
    else: assessment, color_class, explanation = "시장 분위기: 중립적 / 혼조 🤔", 'neutral', "긍정적인 신호와 부정적인 신호가 혼재되어 있어 방향성을 예측하기 어려운 시기일 수 있습니다."
    return assessment, color_class, explanation

# --- Flask 앱 및 API 엔드포인트 정의 ---
app = Flask(__name__)

@app.route('/api/data', methods=['GET'])
def get_market_data():
    """ 모든 시장 데이터를 가져오고 분석하여 JSON으로 반환하는 API 엔드포인트 """
    print("API 요청 수신: /api/data")
    start_time = datetime.now()
    analysis_results = {}
    total_score = 0
    num_valid_indicators = 0

    # 데이터 로딩
    yf_tickers = ['^GSPC', '^VIX', 'SPY', 'USO', 'GLD', 'KRW=X', 'RSP']
    yf_data, yf_err = get_multiple_yf_data(yf_tickers)
    fred_indicators = {}
    if USE_FRED:
        for key, series_id in FRED_SERIES.items():
            fred_indicators[key] = get_fred_latest_data(series_id)
        fred_indicators['10y_2y_spread'] = get_fred_yield_spread()
    fng_index, fng_err = get_fear_greed_index()
    market_pe, pe_err = get_etf_pe_ratio('SPY')

    # 분석할 데이터 구조화
    def get_yf_value(ticker, key, default=None): return yf_data.get(ticker, {}).get(key, default) if yf_data else default
    def get_yf_error(ticker, default=None):
        base_error = yf_err; ticker_error = yf_data.get(ticker, {}).get('error') if yf_data else None
        return ticker_error or base_error or default
    def get_fred_indicator_data(key):
        if USE_FRED: data_tuple = fred_indicators.get(key, (None, "데이터 없음")); return {'value': data_tuple[0], 'error': data_tuple[1]}
        else: return {'value': None, 'error': "FRED API 사용 불가"}

    indicators_to_analyze_data = {
        "Market Trend (MA)": {'value': None, 'error': get_yf_error('^GSPC'), 'price': get_yf_value('^GSPC', 'price'), 'ma50': get_yf_value('^GSPC', 'ma50'), 'ma200': get_yf_value('^GSPC', 'ma200')}, # MA200 추가
        "Volatility (VIX)": {'value': get_yf_value('^VIX', 'price'), 'error': get_yf_error('^VIX')},
        "Market P/E": {'value': market_pe, 'error': pe_err},
        "Fear & Greed": {'value': fng_index, 'error': fng_err},
        "US 10Y Yield": get_fred_indicator_data('10y_yield'),
        "10Y-2Y Spread": get_fred_indicator_data('10y_2y_spread'),
        "Oil Trend (USO)": {'value': None, 'error': get_yf_error('USO'), 'price': get_yf_value('USO', 'price'), 'ma50': get_yf_value('USO', 'ma50')},
        "Gold Trend (GLD)": {'value': None, 'error': get_yf_error('GLD'), 'price': get_yf_value('GLD', 'price'), 'ma50': get_yf_value('GLD', 'ma50')},
        "USD/KRW": {'value': get_yf_value('KRW=X', 'price'), 'error': get_yf_error('KRW=X')},
        "Market Breadth (RSP vs SPY)": {'value': get_yf_value('SPY', 'change_1m'), 'error': get_yf_error('SPY') or get_yf_error('RSP'), 'compare_data': get_yf_value('RSP', 'change_1m')},
        "Unemployment Rate": get_fred_indicator_data('unemployment'),
        "ISM PMI": get_fred_indicator_data('ism_pmi'),
    }

    # 데이터 분석
    for name, data in indicators_to_analyze_data.items():
        kwargs = {}
        if name == "Market Trend (MA)": kwargs = {'price': data.get('price'), 'ma50': data.get('ma50'), 'ma200': data.get('ma200')}
        elif name in ["Oil Trend (USO)", "Gold Trend (GLD)"]: kwargs = {'price': data.get('price'), 'ma50': data.get('ma50')}
        elif name == "Market Breadth (RSP vs SPY)": kwargs = {'compare_data': data.get('compare_data'), 'change_1m': data.get('value')}

        result = analyze_indicator(name, data.get('value'), data.get('error'), **kwargs)
        analysis_results[name] = result
        # 유효 지표 수 및 점수 합산
        is_valid = result.get('error') is None and result.get('status') != '데이터 없음'
        is_value_present_or_analyzable = result.get('value') not in [None, 'N/A', '오류'] or name in ["Market Trend (MA)", "Oil Trend (USO)", "Gold Trend (GLD)", "Market Breadth (RSP vs SPY)"]
        if is_valid and is_value_present_or_analyzable:
             total_score += result.get('score', 0)
             num_valid_indicators += 1

    # 종합 평가
    overall_assessment, overall_color_class, overall_explanation = get_overall_assessment(total_score, num_valid_indicators)

    # 최종 결과 JSON 생성
    final_data = {
        'analysis': analysis_results,
        'total_score': total_score,
        'overall_assessment': overall_assessment,
        'overall_color_class': overall_color_class,
        'overall_explanation': overall_explanation,
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'processing_time_ms': (datetime.now() - start_time).total_seconds() * 1000
    }
    print(f"API 응답 생성 완료. 유효 지표: {num_valid_indicators}, 총 점수: {total_score}. 처리 시간: {final_data['processing_time_ms']:.0f}ms")
    return jsonify(final_data)

# Vercel에서 Flask 앱을 실행하기 위한 설정 (선택 사항, Vercel이 자동으로 처리할 수도 있음)
# if __name__ == "__main__":
#     app.run(debug=False) # 로컬 테스트 시 사용 가능 (python api/data.py)