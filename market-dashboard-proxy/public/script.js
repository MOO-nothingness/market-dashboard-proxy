// public/script.js

// --- HTML 요소 업데이트 함수 ---
function updateElementText(id, text) {
    const element = document.getElementById(id);
    if (element) {
        element.innerText = text;
    } else {
        console.warn(`Element with ID "${id}" not found.`);
    }
}

function updateOverallAssessment(data) {
    const card = document.getElementById("overall-assessment-card");
    if (card) {
        card.className = `overall-assessment ${data.overall_color_class || 'neutral'}`; // 클래스 변경
    }
    updateElementText("total-score", data.total_score ?? '?');
    updateElementText("overall-assessment-text", data.overall_assessment || '평가 불가');
    updateElementText("overall-explanation", data.overall_explanation || '');
}

function createIndicatorCardHTML(name, result) {
    const errorHtml = result.error ? `
        <div class="card-footer error-message">
           <span class="material-symbols-outlined">error</span> 오류: ${result.error}
        </div>` : "";

    // 값이 '오류'일 경우 특정 스타일 적용하지 않도록 함
    const valueClass = result.value === '오류' ? '' : result.color_class;

    return `
        <div class="indicator-card ${result.color_class || 'neutral'}">
            <div class="card-header">
                <h3 class="indicator-name">${name}</h3>
                <span class="indicator-score">(${result.score ?? '?'})</span>
            </div>
            <div class="card-body">
                <p class="indicator-value ${valueClass}">${result.value ?? 'N/A'}</p>
                <p class="indicator-status">${result.status ?? 'N/A'}</p>
                <p class="indicator-explanation">
                    <span class="material-symbols-outlined">help_outline</span>
                    ${result.explanation ?? '설명 없음'}
                </p>
            </div>
            ${errorHtml}
        </div>`;
}

function updateIndicatorsGrid(analysisData) {
    const grid = document.getElementById("indicators-grid");
    if (!grid) return;

    grid.innerHTML = ""; // 로딩 인디케이터 제거 및 내용 초기화

    if (!analysisData || Object.keys(analysisData).length === 0) {
        grid.innerHTML = "<p>분석된 지표 데이터가 없습니다.</p>";
        return;
    }

    // 정의된 순서대로 또는 알파벳 순서대로 정렬 (선택 사항)
    const sortedKeys = Object.keys(analysisData).sort();

    for (const name of sortedKeys) {
    // for (const name in analysisData) { // 원래 순서대로
        if (analysisData.hasOwnProperty(name)) {
            const result = analysisData[name];
            const cardHtml = createIndicatorCardHTML(name, result);
            grid.innerHTML += cardHtml;
        }
    }
}

// --- 데이터 가져오기 및 대시보드 업데이트 ---
async function fetchAndUpdateDashboard() {
    console.log("Fetching data from /api/data...");
    const grid = document.getElementById("indicators-grid");
    const loadingIndicator = `
        <div class="loading-indicator">
            <p>데이터를 가져오고 분석하는 중입니다... 잠시만 기다려 주세요.</p>
            <div class="spinner"></div>
        </div>`;

    if (grid) grid.innerHTML = loadingIndicator; // 로딩 표시

    try {
        // 서버리스 함수 호출 (Vercel 배포 시 상대 경로 사용)
        const response = await fetch('/api/data');

        if (!response.ok) {
            throw new Error(`API 요청 실패 (상태: ${response.status})`);
        }

        const data = await response.json();
        console.log("Data received:", data);

        // 대시보드 업데이트
        updateElementText("current-time", `기준 시간: ${data.last_updated || 'N/A'}`);
        updateOverallAssessment(data);
        updateIndicatorsGrid(data.analysis);
        updateElementText("last-updated-time", `데이터 업데이트: ${data.last_updated || 'N/A'}`);
        if (data.processing_time_ms) {
             updateElementText("processing-time", `(서버 처리 시간: ${data.processing_time_ms.toFixed(0)}ms)`);
        }


    } catch (error) {
        console.error("Error fetching or updating dashboard:", error);
        if (grid) {
            grid.innerHTML = `<p class="error-message" style="color: red; grid-column: 1 / -1; text-align: center;">
                              <span class="material-symbols-outlined">error</span> 대시보드 데이터를 가져오는 중 오류가 발생했습니다: ${error.message}
                              <br>잠시 후 다시 시도해 주세요.</p>`;
        }
        // 종합 평가 부분도 오류 표시
        updateElementText("overall-assessment-text", "데이터 로드 오류");
        updateElementText("overall-explanation", error.message);
        const overallCard = document.getElementById("overall-assessment-card");
         if (overallCard) overallCard.className = "overall-assessment error"; // 오류 스타일
    }
}

// 페이지 로드 시 데이터 가져오기 실행
document.addEventListener('DOMContentLoaded', fetchAndUpdateDashboard);