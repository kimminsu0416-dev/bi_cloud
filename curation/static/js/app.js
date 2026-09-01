/**
 * AI 뉴스 큐레이션 대시보드 인터랙션 스크립트
 * - 모노크롬 다크 테마 & 80% 컴팩트 스케일
 * - 네이버 API 무료 한도 실시간 모니터링 및 과금 방지 위젯
 * - 키워드별 고유 테두리 컬러 매핑
 * - 실시간 키워드 우선순위 순서 조정 (드래그 앤 드롭 / ▲▼ 이동)
 * - 실존 기사 전용 & 기사 부재 시 정직한 '해당 기간중 기사가 없습니다' 렌더링
 */

document.addEventListener('DOMContentLoaded', () => {
    // ----------------------------------------------------
    // 1. 키워드별 고유 컬러 팔레트 (16색)
    // ----------------------------------------------------
    const KEYWORD_COLORS = [
        '#6366F1', // Indigo
        '#10B981', // Emerald
        '#F59E0B', // Amber
        '#06B6D4', // Cyan
        '#F43F5E', // Rose
        '#8B5CF6', // Purple
        '#0EA5E9', // Sky
        '#84CC16', // Lime
        '#D946EF', // Fuchsia
        '#14B8A6', // Teal
        '#F97316', // Orange
        '#38BDF8', // Light Blue
        '#E11D48', // Crimson
        '#EAB308', // Gold
        '#A855F7', // Violet
        '#2DD4BF'  // Mint
    ];

    function getKeywordColor(keyword) {
        let hash = 0;
        for (let i = 0; i < keyword.length; i++) {
            hash = keyword.charCodeAt(i) + ((hash << 5) - hash);
        }
        const index = Math.abs(hash) % KEYWORD_COLORS.length;
        return KEYWORD_COLORS[index];
    }

    // ----------------------------------------------------
    // 2. 상태 변수
    // ----------------------------------------------------
    let currentKeywordsObjects = [];
    let currentResults = [];
    let currentUsageStats = null;

    // 초기 사용량 데이터 파싱
    try {
        const rawUsageJson = document.getElementById('initialUsageData').textContent;
        currentUsageStats = JSON.parse(rawUsageJson || '{}');
    } catch (e) {
        currentUsageStats = null;
    }

    // 탭 요소
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    // 키워드 컨트롤
    const keywordChipsContainer = document.getElementById('keywordChipsContainer');
    const btnSelectAll = document.getElementById('btnSelectAll');
    const btnDeselectAll = document.getElementById('btnDeselectAll');
    const selectedCountBadge = document.getElementById('selectedCountBadge');
    const tabKeywordCount = document.getElementById('tabKeywordCount');
    const customKeywordsInput = document.getElementById('customKeywordsInput');
    const tagButtons = document.querySelectorAll('.btn-tag');

    // 날짜 기간 컨트롤
    const periodButtons = document.querySelectorAll('.period-btn');
    const customDateRangeBox = document.getElementById('customDateRangeBox');
    const startDatePicker = document.getElementById('startDatePicker');
    const endDatePicker = document.getElementById('endDatePicker');
    const dateRangeNotice = document.getElementById('dateRangeNotice');

    // 프롬프트 및 옵션 컨트롤
    const promptChips = document.querySelectorAll('.prompt-chip');
    const filterPromptInput = document.getElementById('filterPromptInput');
    const countSelect = document.getElementById('countPerKeyword');

    // 실행 & 뷰 상태
    const btnCurate = document.getElementById('btnCurate');
    const btnQuickStartDefault = document.getElementById('btnQuickStartDefault');
    const emptyState = document.getElementById('emptyState');
    const loadingState = document.getElementById('loadingState');
    const resultsHeader = document.getElementById('resultsHeader');
    const curationResultsContainer = document.getElementById('curationResultsContainer');

    // 통계 & 도구
    const statKeywords = document.getElementById('statKeywords');
    const statArticles = document.getElementById('statArticles');
    const statPeriod = document.getElementById('statPeriod');
    const statPrompt = document.getElementById('statPrompt');
    const resultFilterSearch = document.getElementById('resultFilterSearch');
    const btnCopyAll = document.getElementById('btnCopyAll');

    // 모달 - API 사용량 모니터링
    const apiUsageWidget = document.getElementById('apiUsageWidget');
    const widgetDailyText = document.getElementById('widgetDailyText');
    const widgetMonthlyText = document.getElementById('widgetMonthlyText');
    const widgetProgressBar = document.getElementById('widgetProgressBar');
    const badgeUsageStatus = document.getElementById('badgeUsageStatus');
    const usageDetailModal = document.getElementById('usageDetailModal');
    const btnCloseUsageModal = document.getElementById('btnCloseUsageModal');
    const btnDoneUsageModal = document.getElementById('btnDoneUsageModal');
    const modalDailyCount = document.getElementById('modalDailyCount');
    const modalDailyBar = document.getElementById('modalDailyBar');
    const modalDailyRemaining = document.getElementById('modalDailyRemaining');
    const modalDailyPercent = document.getElementById('modalDailyPercent');
    const modalMonthlyCount = document.getElementById('modalMonthlyCount');
    const modalMonthlyBar = document.getElementById('modalMonthlyBar');
    const modalMonthlyRemaining = document.getElementById('modalMonthlyRemaining');
    const modalMonthlyPercent = document.getElementById('modalMonthlyPercent');
    const modalMonthStr = document.getElementById('modalMonthStr');

    // 모달 - API 설정
    const btnOpenEnvGuide = document.getElementById('btnOpenEnvGuide');
    const envGuideModal = document.getElementById('envGuideModal');
    const btnCloseModal = document.getElementById('btnCloseModal');
    const btnConfirmModal = document.getElementById('btnConfirmModal');

    // 모달 - 키워드 순서 & 관리
    const btnOpenKeywordModal = document.getElementById('btnOpenKeywordModal');
    const keywordModal = document.getElementById('keywordModal');
    const btnCloseKeywordModal = document.getElementById('btnCloseKeywordModal');
    const btnDoneKeywordModal = document.getElementById('btnDoneKeywordModal');
    const newKeywordInput = document.getElementById('newKeywordInput');
    const btnAddKeyword = document.getElementById('btnAddKeyword');
    const modalKeywordList = document.getElementById('modalKeywordList');
    const modalKeywordCount = document.getElementById('modalKeywordCount');
    const btnResetKeywords = document.getElementById('btnResetKeywords');

    // ----------------------------------------------------
    // 3. API 사용량 모니터링 위젯 갱신
    // ----------------------------------------------------
    function updateUsageUi(stats) {
        if (!stats) return;
        currentUsageStats = stats;

        const dCount = stats.daily_count || 0;
        const dLimit = stats.daily_limit || 25000;
        const mCount = stats.monthly_count || 0;
        const mLimit = stats.monthly_limit || 775000;
        const dPercent = Math.min(stats.daily_percent || 0, 100);
        const mPercent = Math.min(stats.monthly_percent || 0, 100);

        // 상단 미니 위젯 갱신
        widgetDailyText.textContent = `${dCount.toLocaleString()} / ${dLimit.toLocaleString()}`;
        widgetMonthlyText.textContent = `${mCount.toLocaleString()} / ${mLimit.toLocaleString()}`;
        widgetProgressBar.style.width = `${Math.max(dPercent, 1)}%`;

        if (stats.status === 'danger') {
            badgeUsageStatus.className = 'badge-usage-danger';
            badgeUsageStatus.textContent = '🔴 한도 임박';
            widgetProgressBar.style.background = '#EF4444';
        } else if (stats.status === 'warning') {
            badgeUsageStatus.className = 'badge-usage-warning';
            badgeUsageStatus.textContent = '🟡 주의 구간';
            widgetProgressBar.style.background = '#F59E0B';
        } else {
            badgeUsageStatus.className = 'badge-usage-safe';
            badgeUsageStatus.textContent = '🟢 무료 안전';
            widgetProgressBar.style.background = '#10B981';
        }

        // 상세 모달 갱신
        modalDailyCount.textContent = dCount.toLocaleString();
        modalDailyBar.style.width = `${dPercent}%`;
        modalDailyRemaining.textContent = (stats.daily_remaining || 0).toLocaleString();
        modalDailyPercent.textContent = `${dPercent}% 사용`;

        modalMonthlyCount.textContent = mCount.toLocaleString();
        modalMonthlyBar.style.width = `${mPercent}%`;
        modalMonthlyRemaining.textContent = (stats.monthly_remaining || 0).toLocaleString();
        modalMonthlyPercent.textContent = `${mPercent}% 사용`;

        if (stats.month_str) {
            modalMonthStr.textContent = stats.month_str;
        }
    }

    if (currentUsageStats) {
        updateUsageUi(currentUsageStats);
    }

    apiUsageWidget?.addEventListener('click', () => {
        usageDetailModal.style.display = 'flex';
    });
    btnCloseUsageModal?.addEventListener('click', () => { usageDetailModal.style.display = 'none'; });
    btnDoneUsageModal?.addEventListener('click', () => { usageDetailModal.style.display = 'none'; });

    // ----------------------------------------------------
    // 4. 날짜 기간 계산 헬퍼 함수
    // ----------------------------------------------------
    function getFormattedDate(date) {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    }

    function calculateDateRange(periodType) {
        const today = new Date();
        const end = getFormattedDate(today);
        let start = null;

        if (periodType === '3d') {
            const d = new Date(today);
            d.setDate(d.getDate() - 3);
            start = getFormattedDate(d);
        } else if (periodType === '1w') {
            const d = new Date(today);
            d.setDate(d.getDate() - 7);
            start = getFormattedDate(d);
        } else if (periodType === '2w') {
            const d = new Date(today);
            d.setDate(d.getDate() - 14);
            start = getFormattedDate(d);
        } else if (periodType === '1m') {
            const d = new Date(today);
            d.setMonth(d.getMonth() - 1);
            start = getFormattedDate(d);
        } else if (periodType === 'custom') {
            start = startDatePicker.value || null;
            const customEnd = endDatePicker.value || end;
            return { start, end: customEnd, label: start ? `${start} ~ ${customEnd}` : '직접 지정' };
        } else {
            return { start: null, end: null, label: '전체 (최신순)' };
        }

        return { start, end, label: `최근 ${periodType.replace('d','일').replace('w','주일').replace('m','개월')} (${start} ~ ${end})` };
    }

    const todayStr = getFormattedDate(new Date());
    endDatePicker.value = todayStr;
    const defaultStart = new Date();
    defaultStart.setDate(defaultStart.getDate() - 7);
    startDatePicker.value = getFormattedDate(defaultStart);

    periodButtons.forEach(btn => {
        const radio = btn.querySelector('input[type="radio"]');
        btn.addEventListener('click', () => {
            periodButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            radio.checked = true;

            if (radio.value === 'custom') {
                customDateRangeBox.style.display = 'flex';
                dateRangeNotice.textContent = `지정: ${startDatePicker.value} ~ ${endDatePicker.value}`;
            } else {
                customDateRangeBox.style.display = 'none';
            }
        });
    });

    [startDatePicker, endDatePicker].forEach(input => {
        input.addEventListener('change', () => {
            if (startDatePicker.value && endDatePicker.value) {
                dateRangeNotice.textContent = `지정: ${startDatePicker.value} ~ ${endDatePicker.value}`;
            }
        });
    });

    // ----------------------------------------------------
    // 5. 탭 전환
    // ----------------------------------------------------
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(targetTab).classList.add('active');
        });
    });

    // ----------------------------------------------------
    // 6. 키워드 칩 렌더링 & 선택 제어
    // ----------------------------------------------------
    function renderKeywordChips(keywordsList) {
        keywordChipsContainer.innerHTML = '';
        tabKeywordCount.textContent = keywordsList.length;

        keywordsList.forEach(kw => {
            const kwColor = getKeywordColor(kw);
            const label = document.createElement('label');
            label.className = 'keyword-chip selected';
            label.innerHTML = `
                <input type="checkbox" name="keyword_chip" value="${escapeHtml(kw)}" checked>
                <span class="chip-label" style="border-left: 3px solid ${kwColor}"># ${escapeHtml(kw)}</span>
            `;
            
            const cb = label.querySelector('input');
            cb.addEventListener('change', () => {
                if (cb.checked) label.classList.add('selected');
                else label.classList.remove('selected');
                updateSelectedCount();
            });

            keywordChipsContainer.appendChild(label);
        });

        updateSelectedCount();
    }

    function updateSelectedCount() {
        const checkedChips = keywordChipsContainer.querySelectorAll('input[type="checkbox"]:checked');
        const total = keywordChipsContainer.querySelectorAll('input[type="checkbox"]').length;
        selectedCountBadge.textContent = `${checkedChips.length}/${total} 선택됨`;
    }

    btnSelectAll?.addEventListener('click', () => {
        keywordChipsContainer.querySelectorAll('.keyword-chip').forEach(chip => {
            const cb = chip.querySelector('input');
            cb.checked = true;
            chip.classList.add('selected');
        });
        updateSelectedCount();
    });

    btnDeselectAll?.addEventListener('click', () => {
        keywordChipsContainer.querySelectorAll('.keyword-chip').forEach(chip => {
            const cb = chip.querySelector('input');
            cb.checked = false;
            chip.classList.remove('selected');
        });
        updateSelectedCount();
    });

    tagButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const insertVal = btn.getAttribute('data-insert');
            const current = customKeywordsInput.value.trim();
            customKeywordsInput.value = current ? `${current}, ${insertVal}` : insertVal;
            customKeywordsInput.focus();
        });
    });

    promptChips.forEach(chip => {
        chip.addEventListener('click', () => {
            filterPromptInput.value = chip.getAttribute('data-prompt');
            filterPromptInput.focus();
        });
    });

    // ----------------------------------------------------
    // 7. 키워드 순서 조정 & 관리 모달 (드래그 & 드롭 / ▲▼ 이동)
    // ----------------------------------------------------
    async function loadKeywordsFromApi() {
        try {
            const res = await fetch('/api/keywords/');
            const data = await res.json();
            if (data.success) {
                currentKeywordsObjects = data.keywords;
                renderModalKeywordReorderList(currentKeywordsObjects);
                const names = currentKeywordsObjects.map(k => k.name);
                renderKeywordChips(names);
            }
        } catch (e) {
            console.error('Failed to load keywords:', e);
        }
    }

    function renderModalKeywordReorderList(keywords) {
        modalKeywordList.innerHTML = '';
        modalKeywordCount.textContent = keywords.length;

        if (keywords.length === 0) {
            modalKeywordList.innerHTML = '<p style="color:var(--text-muted);font-size:11px;padding:8px;">등록된 키워드가 없습니다.</p>';
            return;
        }

        keywords.forEach((kw, index) => {
            const kwColor = getKeywordColor(kw.name);
            const item = document.createElement('div');
            item.className = 'reorder-item';
            item.setAttribute('draggable', 'true');
            item.setAttribute('data-id', kw.id);
            item.setAttribute('data-index', index);
            item.style.setProperty('--kw-border-color', kwColor);

            item.innerHTML = `
                <div class="reorder-left">
                    <span class="drag-handle" title="드래그하여 순서 변경">☰</span>
                    <span class="order-badge">${index + 1}</span>
                    <span class="reorder-kw-name" style="color:${kwColor}"># ${escapeHtml(kw.name)}</span>
                </div>
                <div class="reorder-actions">
                    <button class="btn-move btn-top" title="맨 위로 (최우선 순위)" data-index="${index}">🔝</button>
                    <button class="btn-move btn-up" title="위로 이동" data-index="${index}" ${index === 0 ? 'disabled' : ''}>▲</button>
                    <button class="btn-move btn-down" title="아래로 이동" data-index="${index}" ${index === keywords.length - 1 ? 'disabled' : ''}>▼</button>
                    <button class="btn-remove-row" data-id="${kw.id}" title="키워드 삭제">&times;</button>
                </div>
            `;

            item.querySelector('.btn-top').addEventListener('click', (e) => {
                e.stopPropagation();
                moveKeywordToIndex(index, 0);
            });

            item.querySelector('.btn-up').addEventListener('click', (e) => {
                e.stopPropagation();
                if (index > 0) moveKeywordToIndex(index, index - 1);
            });

            item.querySelector('.btn-down').addEventListener('click', (e) => {
                e.stopPropagation();
                if (index < keywords.length - 1) moveKeywordToIndex(index, index + 1);
            });

            item.querySelector('.btn-remove-row').addEventListener('click', async (e) => {
                e.stopPropagation();
                if (confirm(`'${kw.name}' 키워드를 삭제하시겠습니까?`)) {
                    await deleteKeyword(kw.id);
                }
            });

            item.addEventListener('dragstart', (e) => {
                item.classList.add('dragging');
                e.dataTransfer.setData('text/plain', index);
            });

            item.addEventListener('dragend', () => {
                item.classList.remove('dragging');
                document.querySelectorAll('.reorder-item').forEach(el => el.classList.remove('drag-over'));
            });

            item.addEventListener('dragover', (e) => {
                e.preventDefault();
                item.classList.add('drag-over');
            });

            item.addEventListener('dragleave', () => {
                item.classList.remove('drag-over');
            });

            item.addEventListener('drop', (e) => {
                e.preventDefault();
                item.classList.remove('drag-over');
                const fromIndex = parseInt(e.dataTransfer.getData('text/plain'), 10);
                const toIndex = index;
                if (fromIndex !== toIndex) {
                    moveKeywordToIndex(fromIndex, toIndex);
                }
            });

            modalKeywordList.appendChild(item);
        });
    }

    async function moveKeywordToIndex(fromIdx, toIdx) {
        if (fromIdx === toIdx || fromIdx < 0 || toIdx < 0 || fromIdx >= currentKeywordsObjects.length || toIdx >= currentKeywordsObjects.length) {
            return;
        }

        const item = currentKeywordsObjects.splice(fromIdx, 1)[0];
        currentKeywordsObjects.splice(toIdx, 0, item);

        renderModalKeywordReorderList(currentKeywordsObjects);
        const names = currentKeywordsObjects.map(k => k.name);
        renderKeywordChips(names);

        const orderedIds = currentKeywordsObjects.map(k => k.id);
        try {
            await fetch('/api/keywords/reorder/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ordered_ids: orderedIds })
            });
        } catch (e) {
            console.error('Failed to save order to server:', e);
        }
    }

    async function addKeyword(name) {
        const trimmed = name.trim();
        if (!trimmed) return;

        try {
            const res = await fetch('/api/keywords/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: trimmed })
            });
            const data = await res.json();
            if (data.success) {
                newKeywordInput.value = '';
                await loadKeywordsFromApi();
            } else {
                alert(data.error || '키워드 추가 실패');
            }
        } catch (e) {
            alert('키워드 추가 중 통신 오류가 발생했습니다.');
        }
    }

    async function deleteKeyword(keywordId) {
        try {
            const res = await fetch(`/api/keywords/${keywordId}/`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                await loadKeywordsFromApi();
            } else {
                alert(data.error || '키워드 삭제 실패');
            }
        } catch (e) {
            alert('키워드 삭제 중 오류가 발생했습니다.');
        }
    }

    async function resetKeywords() {
        if (!confirm('사전 정의된 기본 23개 키워드로 초기화하시겠습니까?')) return;

        try {
            const res = await fetch('/api/keywords/reset/', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                currentKeywordsObjects = data.keywords;
                renderModalKeywordReorderList(currentKeywordsObjects);
                const names = currentKeywordsObjects.map(k => k.name);
                renderKeywordChips(names);
            }
        } catch (e) {
            alert('초기화 중 오류가 발생했습니다.');
        }
    }

    btnAddKeyword?.addEventListener('click', () => addKeyword(newKeywordInput.value));
    newKeywordInput?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            addKeyword(newKeywordInput.value);
        }
    });

    btnResetKeywords?.addEventListener('click', resetKeywords);

    btnOpenKeywordModal?.addEventListener('click', () => {
        keywordModal.style.display = 'flex';
        loadKeywordsFromApi();
    });
    btnCloseKeywordModal?.addEventListener('click', () => { keywordModal.style.display = 'none'; });
    btnDoneKeywordModal?.addEventListener('click', () => { keywordModal.style.display = 'none'; });

    btnOpenEnvGuide?.addEventListener('click', () => { envGuideModal.style.display = 'flex'; });
    btnCloseModal?.addEventListener('click', () => { envGuideModal.style.display = 'none'; });
    btnConfirmModal?.addEventListener('click', () => { envGuideModal.style.display = 'none'; });

    window.addEventListener('click', (e) => {
        if (e.target === keywordModal) keywordModal.style.display = 'none';
        if (e.target === envGuideModal) envGuideModal.style.display = 'none';
        if (e.target === usageDetailModal) usageDetailModal.style.display = 'none';
    });

    loadKeywordsFromApi();

    // ----------------------------------------------------
    // 8. 뉴스 큐레이션 실행 API 호출 및 사용량 실시간 업데이트
    // ----------------------------------------------------
    async function executeCuration(targetMode = null) {
        const activeTabBtn = document.querySelector('.tab-btn.active');
        const mode = targetMode || (activeTabBtn.getAttribute('data-tab') === 'defaultTab' ? 'default' : 'custom');

        let keywordsToSearch = [];

        if (mode === 'default') {
            const checkedBoxes = keywordChipsContainer.querySelectorAll('input[type="checkbox"]:checked');
            keywordsToSearch = Array.from(checkedBoxes).map(cb => cb.value);
            if (keywordsToSearch.length === 0) {
                alert('최소 1개 이상의 기본 키워드를 선택해주세요.');
                return;
            }
        } else {
            const text = customKeywordsInput.value.trim();
            if (!text) {
                alert('검색할 키워드를 입력해주세요.');
                customKeywordsInput.focus();
                return;
            }
            keywordsToSearch = text.split(/[\n,]+/).map(k => k.trim()).filter(k => k.length > 0);
        }

        const selectedPeriodRadio = document.querySelector('input[name="date_period"]:checked');
        const periodType = selectedPeriodRadio ? selectedPeriodRadio.value : 'all';
        const dateRange = calculateDateRange(periodType);

        const filterPrompt = filterPromptInput.value.trim();
        const countPerKeyword = parseInt(countSelect.value, 10);

        emptyState.style.display = 'none';
        resultsHeader.style.display = 'none';
        curationResultsContainer.innerHTML = '';
        loadingState.style.display = 'block';

        resultsHeader.scrollIntoView({ behavior: 'smooth' });

        try {
            const response = await fetch('/api/curate/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mode: mode,
                    keywords: keywordsToSearch,
                    filter_prompt: filterPrompt,
                    count_per_keyword: countPerKeyword,
                    start_date: dateRange.start,
                    end_date: dateRange.end
                })
            });

            if (!response.ok) {
                throw new Error(`서버 응답 오류 (Status: ${response.status})`);
            }

            const data = await response.json();
            
            if (data.success) {
                currentResults = data.data.results;
                renderResults(currentResults, filterPrompt, dateRange, data.data);

                // 사용량 실시간 업데이트
                if (data.usage) {
                    updateUsageUi(data.usage);
                }
            } else {
                alert(`큐레이션 실패: ${data.error || '알 수 없는 오류'}`);
                emptyState.style.display = 'block';
            }
        } catch (error) {
            console.error('Curation Error:', error);
            alert(`큐레이션 요청 중 오류가 발생했습니다: ${error.message}`);
            emptyState.style.display = 'block';
        } finally {
            loadingState.style.display = 'none';
        }
    }

    btnCurate.addEventListener('click', () => executeCuration());
    btnQuickStartDefault?.addEventListener('click', () => {
        tabBtns[0].click();
        executeCuration('default');
    });

    // ----------------------------------------------------
    // 9. 결과 렌더링 (우선순위 순서대로 출력)
    // ----------------------------------------------------
    function renderResults(results, filterPrompt, dateRange, meta) {
        if (!results || results.length === 0) {
            emptyState.style.display = 'block';
            emptyState.querySelector('h3').textContent = '검색된 키워드 결과가 없습니다.';
            emptyState.querySelector('p').textContent = '검색할 키워드를 선택 후 다시 실행해주세요.';
            return;
        }

        resultsHeader.style.display = 'flex';
        statKeywords.textContent = `${meta.total_keywords}개 키워드`;
        statArticles.textContent = `${meta.total_articles}개 실제 기사 수집됨`;

        if (dateRange.label) {
            statPeriod.textContent = `📅 ${dateRange.label}`;
            statPeriod.style.display = 'inline-block';
        } else {
            statPeriod.style.display = 'none';
        }

        if (filterPrompt) {
            statPrompt.textContent = `🎯 적용 필터: "${filterPrompt.length > 20 ? filterPrompt.slice(0, 20) + '...' : filterPrompt}"`;
            statPrompt.style.display = 'inline-block';
        } else {
            statPrompt.style.display = 'none';
        }

        curationResultsContainer.innerHTML = '';

        results.forEach(group => {
            const keyword = group.keyword;
            const kwColor = getKeywordColor(keyword);
            const articles = group.articles || [];

            if (articles.length === 0) {
                const emptyCard = document.createElement('article');
                emptyCard.className = 'curation-card no-articles-card';
                emptyCard.style.setProperty('--kw-border-color', kwColor);
                emptyCard.setAttribute('data-keyword', keyword.toLowerCase());
                emptyCard.setAttribute('data-content', keyword.toLowerCase() + ' 해당 기간중 기사가 없습니다');

                emptyCard.innerHTML = `
                    <div class="card-top">
                        <div class="card-meta-row">
                            <span class="kw-badge" style="color:${kwColor}; border-color:${kwColor}"># ${escapeHtml(keyword)}</span>
                            <span class="date-text">조회 완료</span>
                        </div>
                    </div>
                    <div class="no-articles-body">
                        <div class="no-articles-icon">📭</div>
                        <div class="no-articles-text">해당 기간중 기사가 없습니다.</div>
                    </div>
                    <div class="card-footer">
                        <span style="font-size:10px; color:var(--text-muted);">실제 기사 없음</span>
                    </div>
                `;
                curationResultsContainer.appendChild(emptyCard);
                return;
            }

            articles.forEach(art => {
                const card = document.createElement('article');
                card.className = 'curation-card';
                card.style.setProperty('--kw-border-color', kwColor);
                card.setAttribute('data-keyword', keyword.toLowerCase());
                card.setAttribute('data-content', (art.title + ' ' + (art.summary_points || []).join(' ')).toLowerCase());

                const summaryListHtml = (art.summary_points || []).map(p => `<li>${escapeHtml(p)}</li>`).join('');

                card.innerHTML = `
                    <div class="card-top">
                        <div class="card-meta-row">
                            <span class="kw-badge" style="color:${kwColor}; border-color:${kwColor}"># ${escapeHtml(keyword)}</span>
                            <span class="date-text">${escapeHtml(art.pub_date || '')}</span>
                        </div>
                        <h3 class="card-title">
                            <a href="${escapeHtml(art.link)}" target="_blank" rel="noopener noreferrer">
                                ${escapeHtml(art.title)}
                            </a>
                        </h3>
                    </div>

                    <div class="card-body">
                        <div class="ai-summary-box">
                            <div class="summary-header">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                                    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                                </svg>
                                AI 핵심 3줄 브리핑
                            </div>
                            <ul class="summary-list">
                                ${summaryListHtml}
                            </ul>
                        </div>
                    </div>

                    <div class="card-footer">
                        <span class="source-tag">실제 기사</span>
                        <a href="${escapeHtml(art.link)}" target="_blank" rel="noopener noreferrer" class="btn-read-more">
                            원문 기사 보기 ➔
                        </a>
                    </div>
                `;

                curationResultsContainer.appendChild(card);
            });
        });
    }

    // ----------------------------------------------------
    // 10. 결과 내 실시간 검색
    // ----------------------------------------------------
    resultFilterSearch?.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        const cards = curationResultsContainer.querySelectorAll('.curation-card');
        
        cards.forEach(card => {
            const kw = card.getAttribute('data-keyword') || '';
            const content = card.getAttribute('data-content') || '';
            if (kw.includes(query) || content.includes(query)) {
                card.style.display = 'flex';
            } else {
                card.style.display = 'none';
            }
        });
    });

    // ----------------------------------------------------
    // 11. 경영진 보고서 복사
    // ----------------------------------------------------
    btnCopyAll?.addEventListener('click', () => {
        if (!currentResults || currentResults.length === 0) {
            alert('복사할 큐레이션 결과가 없습니다.');
            return;
        }

        let reportText = `[AI 뉴스 큐레이션 및 인텔리전스 보고서]\n`;
        reportText += `작성일시: ${new Date().toLocaleString('ko-KR')}\n`;
        
        const periodRadio = document.querySelector('input[name="date_period"]:checked');
        const periodLabel = periodRadio ? periodRadio.parentElement.querySelector('span').textContent : '전체';
        reportText += `조회기간: ${periodLabel}\n`;

        const prompt = filterPromptInput.value.trim();
        if (prompt) {
            reportText += `적용 필터링 프롬프트: "${prompt}"\n`;
        }
        reportText += `========================================\n\n`;

        currentResults.forEach(group => {
            reportText += `📌 키워드: ${group.keyword}\n`;
            const articles = group.articles || [];
            if (articles.length === 0) {
                reportText += `  • 해당 기간중 기사가 없습니다.\n\n`;
                return;
            }
            articles.forEach((art, idx) => {
                reportText += `\n[기사 ${idx + 1}] ${art.title}\n`;
                reportText += `• 발행일: ${art.pub_date || '최신'}\n`;
                reportText += `• AI 핵심 요약:\n`;
                (art.summary_points || []).forEach(p => {
                    reportText += `  - ${p}\n`;
                });
                reportText += `• 기사 원문: ${art.link}\n`;
            });
            reportText += `\n----------------------------------------\n`;
        });

        navigator.clipboard.writeText(reportText).then(() => {
            const originalText = btnCopyAll.innerHTML;
            btnCopyAll.innerHTML = `
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                복사 완료!
            `;
            setTimeout(() => {
                btnCopyAll.innerHTML = originalText;
            }, 2000);
        }).catch(err => {
            alert('클립보드 복사 중 오류가 발생했습니다.');
        });
    });

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
});
