/* static/js/script.js */

// =========================================================
// 共通機能
// =========================================================

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('active');
    document.getElementById('overlay').classList.toggle('active');
}

function checkAdminPass(event) {
    const ADMIN_PASS = "shoot123";
    var pass = prompt("管理者パスワードを入力してください:", "");
    if (pass === ADMIN_PASS) {
        return true;
    } else {
        if (pass !== null) alert("パスワードが違います。");
        if (event) event.preventDefault();
        return false;
    }
}

function openTab(evt, tabName) {
    var tabContent = document.getElementsByClassName("tab-content");
    for (var i = 0; i < tabContent.length; i++) {
        tabContent[i].style.display = "none";
    }
    var tabLinks = document.getElementsByClassName("tab-btn");
    for (var i = 0; i < tabLinks.length; i++) {
        tabLinks[i].className = tabLinks[i].className.replace(" active", "");
    }
    document.getElementById(tabName).style.display = "block";
    if (evt) evt.currentTarget.className += " active";
}


// =========================================================
// index.html (トップページ) 用
// =========================================================

function openGoalModal() {
    document.getElementById('goalModal').style.display = 'block';
}

function closeGoalModal() {
    document.getElementById('goalModal').style.display = 'none';
}

window.onclick = function (event) {
    var modal = document.getElementById('goalModal');
    if (event.target == modal) {
        modal.style.display = "none";
    }
}

function initIndexCharts(chartData) {
    for (const [event, data] of Object.entries(chartData)) {
        const ctx = document.getElementById(`chart-${event}`);
        if (ctx) {
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels,
                    datasets: [
                        {
                            label: '男子', data: data.male,
                            borderColor: 'rgba(54, 162, 235, 1)', backgroundColor: 'rgba(54, 162, 235, 0.2)',
                            tension: 0.1, fill: false, spanGaps: true
                        },
                        {
                            label: '女子', data: data.female,
                            borderColor: 'rgba(255, 99, 132, 1)', backgroundColor: 'rgba(255, 99, 132, 0.2)',
                            tension: 0.1, fill: false, spanGaps: true
                        }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { position: 'bottom', labels: { boxWidth: 12, padding: 10 } },
                        title: { display: true, text: event + ' 平均点推移', font: { size: 16, weight: 'bold' }, padding: { top: 10, bottom: 10 } },
                        tooltip: { callbacks: { label: function (context) { return context.dataset.label + ': ' + context.parsed.y + '点'; } } }
                    },
                    scales: { y: { beginAtZero: false } }
                }
            });
        }
    }
}


// =========================================================
// player.html (選手詳細) 用
// =========================================================

function filterHistory() {
    var matchFilter = document.getElementById("filterMatch").value;
    var eventFilter = document.getElementById("filterEvent").value;
    var rows = document.getElementsByClassName("history-row");
    for (var i = 0; i < rows.length; i++) {
        var row = rows[i];
        var rowMatch = row.getAttribute("data-match");
        var rowEvent = row.getAttribute("data-event");
        if ((matchFilter === "" || rowMatch === matchFilter) && (eventFilter === "" || rowEvent === eventFilter)) {
            row.style.display = "";
        } else {
            row.style.display = "none";
        }
    }
}

let playerChartInstances = [];

function initPlayerCharts(labels, datasets, playerGoals, playerGender) {
    const goalLabelText = (playerGender === '男' ? '男子目標' : (playerGender === '女' ? '女子目標' : 'チーム目標'));

    datasets.forEach((dataset, index) => {
        const ctx = document.getElementById(`chart-${index}`);
        if (ctx) {
            const eventName = dataset.label;
            const teamGoalScore = playerGoals[eventName];
            const chartDatasets = [dataset];

            if (teamGoalScore !== undefined) {
                const goalData = new Array(labels.length).fill(teamGoalScore);
                chartDatasets.push({
                    label: goalLabelText,
                    data: goalData,
                    borderColor: 'rgba(220, 53, 69, 0.8)',
                    borderWidth: 2, borderDash: [10, 5], pointRadius: 0, fill: false, order: 1
                });
            }

            const chart = new Chart(ctx, {
                type: 'line',
                data: { labels: labels, datasets: chartDatasets },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { display: true, position: 'bottom' },
                        tooltip: { callbacks: { label: function (context) { return context.dataset.label + ': ' + context.parsed.y + '点'; } } }
                    },
                    scales: {
                        y: { beginAtZero: false, title: { display: true, text: '点数' } },
                        x: { title: { display: true, text: '日付' } }
                    }
                }
            });
            playerChartInstances.push(chart);
        }
    });
}

function updateTargetLine(chartIndex, targetValue) {
    const chart = playerChartInstances[chartIndex];
    const val = parseFloat(targetValue);
    let targetDataset = chart.data.datasets.find(d => d.label === '個人目標');

    if (isNaN(val)) {
        if (targetDataset) chart.data.datasets = chart.data.datasets.filter(d => d.label !== '個人目標');
    } else {
        const targetData = new Array(chart.data.labels.length).fill(val);
        if (targetDataset) {
            targetDataset.data = targetData;
        } else {
            chart.data.datasets.push({
                label: '個人目標', data: targetData,
                borderColor: 'rgba(40, 167, 69, 1)', borderWidth: 2, borderDash: [5, 5],
                pointRadius: 0, fill: false, order: 0
            });
        }
    }
    chart.update();
}


// =========================================================
// match_years.html (年度一覧・グラフ) 用
// =========================================================
let trendChart = null;
let globalMatchYearsDatasets = [];
let globalMatchYearsLabels = [];

function initMatchYearsChart(labels, datasets) {
    globalMatchYearsLabels = labels;
    globalMatchYearsDatasets = datasets;

    // 初期表示
    updateMatchYearsChart('AR60');
}

function updateMatchYearsChart(targetEvent) {
    // タブの見た目更新
    const tabs = document.querySelectorAll('.graph-tab-btn');
    if (tabs.length > 0) {
        tabs.forEach(btn => btn.classList.remove('active'));
        const activeBtn = document.querySelector(`.graph-tab-btn[data-event="${targetEvent}"]`);
        if (activeBtn) activeBtn.classList.add('active');
    }

    // データフィルタリング
    const filteredDatasets = [];
    globalMatchYearsDatasets.forEach(ds => {
        if (ds.label.includes(targetEvent)) {
            let newDs = { ...ds };
            if (newDs.label.includes('男')) {
                newDs.borderColor = 'rgba(54, 162, 235, 1)';
                newDs.backgroundColor = 'rgba(54, 162, 235, 1)';
                newDs.borderDash = [];
            } else if (newDs.label.includes('女')) {
                newDs.borderColor = 'rgba(255, 99, 132, 1)';
                newDs.backgroundColor = 'rgba(255, 99, 132, 1)';
                newDs.borderDash = [];
            } else {
                newDs.borderDash = [];
            }
            filteredDatasets.push(newDs);
        }
    });

    const canvas = document.getElementById('teamTrendChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (trendChart) {
        trendChart.destroy();
    }

    trendChart = new Chart(ctx, {
        type: 'line',
        data: { labels: globalMatchYearsLabels, datasets: filteredDatasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'bottom', labels: { usePointStyle: true, padding: 20 } },
                tooltip: { callbacks: { title: function (c) { return c[0].label + '年度'; }, label: function (c) { return c.dataset.label + ': ' + c.parsed.y + '点'; } } }
            },
            scales: {
                y: { beginAtZero: false, title: { display: true, text: '合計点' } },
                x: { title: { display: true, text: '年度' } }
            }
        }
    });
}


// =========================================================
// ranking.html (ランキング) 用
// =========================================================
let currentRankMode = 'avg';
let currentRankEvent = 'AR60';

function switchRankMode(mode) {
    currentRankMode = mode;
    document.querySelectorAll('.mode-btn').forEach(btn => btn.classList.remove('active'));
    if (mode === 'avg') document.querySelector('.mode-btn:nth-child(1)').classList.add('active');
    else document.querySelector('.mode-btn:nth-child(2)').classList.add('active');

    document.querySelectorAll('.mode-content').forEach(content => content.classList.remove('active'));
    document.getElementById('mode-' + mode).classList.add('active');

    updateRankEventDisplay();
}

function switchRankEvent(event) {
    currentRankEvent = event;
    document.querySelectorAll('.event-tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.event-tab-btn').forEach(btn => {
        if (btn.getAttribute('data-event') === event) btn.classList.add('active');
    });

    updateRankEventDisplay();
}

function updateRankEventDisplay() {
    document.querySelectorAll('.event-content').forEach(el => el.classList.remove('active'));
    const targetId = currentRankMode + '-' + currentRankEvent;
    const targetEl = document.getElementById(targetId);
    if (targetEl) targetEl.classList.add('active');
}

function filterRanking(containerId, inputId) {
    const input = document.getElementById(inputId);
    const filter = input.value.replace(/\s+/g, '').toLowerCase();
    const container = document.getElementById(containerId);
    const rows = container.getElementsByClassName('rank-row');

    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const nameCell = row.getElementsByClassName('player-name-cell')[0];
        if (nameCell) {
            const txtValue = nameCell.textContent || nameCell.innerText;
            const cleanTxt = txtValue.replace(/\s+/g, '').toLowerCase();
            if (cleanTxt.indexOf(filter) > -1) {
                row.style.display = "";
                if (filter.length > 0) row.classList.add('highlight-row');
                else row.classList.remove('highlight-row');
            } else {
                row.style.display = "none";
                row.classList.remove('highlight-row');
            }
        }
    }
}

function resetRanking(containerId, inputId) {
    document.getElementById(inputId).value = "";
    const container = document.getElementById(containerId);
    const rows = container.getElementsByClassName('rank-row');
    for (let i = 0; i < rows.length; i++) {
        rows[i].style.display = "";
        rows[i].classList.remove('highlight-row');
    }
}