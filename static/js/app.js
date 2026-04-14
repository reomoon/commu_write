'use strict';

const PAGE_SIZE = 20;

// ===== 상태 관리 =====
const CLIENT_CACHE_TTL = 10 * 60 * 1000; // 10분 (ms)

const state = {
  community: { source: 'bobaedream', cache: {}, cacheTs: {}, shown: {} },
  news:      { source: 'ent',        cache: {}, cacheTs: {}, shown: {} },
  hotdeal:   { source: 'ppomppu',    cache: {}, cacheTs: {}, shown: {} },
  section:   'news',
};

// ===== DOM =====
const $ = id => document.getElementById(id);
const containers = {
  community: $('community-list'),
  news:      $('news-list'),
  hotdeal:   $('hotdeal-list'),
};
const sentinels = {
  community: $('community-sentinel'),
  news:      $('news-sentinel'),
  hotdeal:   $('hotdeal-sentinel'),
};
const updateTime = $('update-time');
const refreshBtn = $('refreshBtn');

// ===== 무한 스크롤 (IntersectionObserver) =====
const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    const type = entry.target.dataset.section;
    if (type !== state.section) return;
    loadMore(type);
  });
}, { rootMargin: '0px 0px 300px 0px' });

Object.entries(sentinels).forEach(([type, el]) => {
  el.dataset.section = type;
  observer.observe(el);
});

// ===== 탭 상태 저장 (새로고침 시 복원용) =====
function saveTabState() {
  sessionStorage.setItem('tabState', JSON.stringify({
    section: state.section,
    community: state.community.source,
    news: state.news.source,
    hotdeal: state.hotdeal.source,
  }));
}

// ===== 메인 탭 이벤트 =====
document.querySelectorAll('.main-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.main-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.section = btn.dataset.section;
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    $(`${state.section}-section`).classList.add('active');

    // 해당 섹션 서브탭을 첫 번째로 리셋
    const type = state.section;
    const subTabs = document.querySelectorAll(`#${type}-section .sub-tab`);
    subTabs.forEach(b => b.classList.remove('active'));
    const first = subTabs[0];
    if (first) {
      first.classList.add('active');
      state[type].source = first.dataset.source;
    }

    saveTabState();
    loadCurrent();
  });
});

// ===== 서브 탭 이벤트 (공통) =====
['community', 'news', 'hotdeal'].forEach(type => {
  document.querySelectorAll(`#${type}-section .sub-tab`).forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.source === state[type].source) return;
      document.querySelectorAll(`#${type}-section .sub-tab`).forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state[type].source = btn.dataset.source;
      saveTabState();
      fetchAndRender(type, btn.dataset.source);
    });
  });
});

// ===== 로고 클릭 → 홈 (모든 탭 디폴트 초기화) =====
document.querySelector('.logo').addEventListener('click', () => {
  // 모든 섹션의 서브탭을 첫 번째로 초기화
  ['news', 'community', 'hotdeal'].forEach(type => {
    const subTabs = document.querySelectorAll(`#${type}-section .sub-tab`);
    subTabs.forEach(b => b.classList.remove('active'));
    const first = subTabs[0];
    if (first) {
      first.classList.add('active');
      state[type].source = first.dataset.source;
    }
  });

  // 뉴스 메인탭으로
  document.querySelectorAll('.main-tab').forEach(b => b.classList.remove('active'));
  document.querySelector('.main-tab[data-section="news"]').classList.add('active');
  state.section = 'news';
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  $('news-section').classList.add('active');

  // 맨 위로 스크롤
  window.scrollTo({ top: 0, behavior: 'smooth' });
  saveTabState();
  fetchAndRender('news', state.news.source);
});

// ===== 새로고침 =====
refreshBtn.addEventListener('click', () => {
  const type = state.section;
  const st = state[type];
  delete st.cache[st.source];
  delete st.shown[st.source];
  fetchAndRender(type, st.source);
  refreshBtn.classList.add('spinning');
  setTimeout(() => refreshBtn.classList.remove('spinning'), 800);
});

// ===== 로딩 스피너 =====
function showSkeleton(container) {
  container.innerHTML = `<div class="spinner-wrap"><div class="spinner"></div></div>`;
}

// ===== 아이템 HTML 생성 =====
function makeItemHtml(item, idx) {
  const rank = item.rank || (idx + 1);
  const rankClass = rank <= 3 ? ` r${rank}` : '';
  const isHot = rank <= 3;
  return `
    <a class="post-item" href="${escHtml(item.url)}">
      <span class="post-rank${rankClass}">${rank}</span>
      <span class="post-title">${escHtml(item.title)}</span>
      ${isHot ? '<span class="post-hot">HOT</span>' : ''}
    </a>`;
}

// ===== 초기 렌더링 =====
function renderList(container, items) {
  if (!items) { showSkeleton(container); return; }
  if (!items.length) {
    container.innerHTML = '<p class="empty-msg">데이터를 불러올 수 없습니다.</p>';
    return;
  }
  container.innerHTML = items.slice(0, PAGE_SIZE).map(makeItemHtml).join('');
}

// ===== 추가 로드 (무한 스크롤) =====
function loadMore(type) {
  const st = state[type];
  const source = st.source;
  const allItems = st.cache[source];
  if (!allItems) return;

  const shown = st.shown[source] || PAGE_SIZE;
  if (shown >= allItems.length) return;

  const next = Math.min(shown + PAGE_SIZE, allItems.length);
  const newHtml = allItems.slice(shown, next).map(makeItemHtml).join('');
  containers[type].insertAdjacentHTML('beforeend', newHtml);
  st.shown[source] = next;
}

// ===== API 호출 =====
const ENDPOINTS = {
  community: s => `/api/community/${s}`,
  news:      s => `/api/news/${s}`,
  hotdeal:   s => `/api/hotdeal/${s}`,
};

function isCacheStale(type, source) {
  const ts = state[type].cacheTs[source];
  return !ts || (Date.now() - ts) > CLIENT_CACHE_TTL;
}

async function fetchAndRender(type, source, silent = false) {
  const st = state[type];
  const container = containers[type];

  if (st.cache[source] && !isCacheStale(type, source)) {
    st.shown[source] = PAGE_SIZE;
    renderList(container, st.cache[source]);
    setUpdateTime();
    return;
  }

  if (!silent) showSkeleton(container);

  try {
    const res = await fetch(ENDPOINTS[type](source));
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = data.items || [];
    st.cache[source] = items;
    st.cacheTs[source] = Date.now();
    st.shown[source] = PAGE_SIZE;
    renderList(container, items);
    setUpdateTime();
  } catch (e) {
    if (!silent) {
      container.innerHTML = `<p class="error-msg">오류가 발생했습니다.<br><small>${e.message}</small></p>`;
    }
  }
}

function loadCurrent() {
  const type = state.section;
  fetchAndRender(type, state[type].source);
}

function setUpdateTime() {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, '0');
  const mm = String(now.getMinutes()).padStart(2, '0');
  updateTime.textContent = `${hh}:${mm} 업데이트`;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ===== 탭 순서: localStorage =====
const TAB_ORDER_KEY = s => `tabOrder:${s}`;

function applyTabOrder(section) {
  const saved = localStorage.getItem(TAB_ORDER_KEY(section));
  if (!saved) return;
  let order;
  try { order = JSON.parse(saved); } catch { return; }

  const nav = document.querySelector(`#${section}-section .sub-tabs`);
  if (!nav) return;

  order.forEach(source => {
    const btn = nav.querySelector(`.sub-tab[data-source="${source}"]`);
    if (btn) nav.appendChild(btn);
  });

  // 첫 번째 탭을 해당 섹션의 기본 소스로 설정
  const first = nav.querySelector('.sub-tab');
  if (first) state[section].source = first.dataset.source;
}

['news', 'community', 'hotdeal'].forEach(applyTabOrder);

// 저장된 순서에 따라 active 클래스도 동기화
['news', 'community', 'hotdeal'].forEach(section => {
  const nav = document.querySelector(`#${section}-section .sub-tabs`);
  if (!nav) return;
  nav.querySelectorAll('.sub-tab').forEach(b => b.classList.remove('active'));
  const first = nav.querySelector('.sub-tab');
  if (first) first.classList.add('active');
});

// ===== 바텀시트 =====
const tabSheet = $('tabSheet');
let _sheetSection = null;

function openTabSheet(section) {
  _sheetSection = section;
  const nav = document.querySelector(`#${section}-section .sub-tabs`);
  const list = $('tabSheetList');

  list.innerHTML = '';
  nav.querySelectorAll('.sub-tab').forEach(btn => {
    const li = document.createElement('li');
    li.className = 'sheet-item';
    li.dataset.source = btn.dataset.source;
    li.innerHTML = `<span class="drag-handle" aria-hidden="true">⠿</span>
      <span class="sheet-item-label">${btn.textContent.trim()}</span>`;
    list.appendChild(li);
  });

  tabSheet.hidden = false;
  requestAnimationFrame(() => tabSheet.classList.add('open'));
  initSheetDrag(list);
}

function closeTabSheet() {
  tabSheet.classList.remove('open');
  tabSheet.addEventListener('transitionend', () => { tabSheet.hidden = true; }, { once: true });
}

$('tabSheetClose').addEventListener('click', closeTabSheet);
$('tabSheet').addEventListener('click', e => { if (e.target === tabSheet) closeTabSheet(); });

document.querySelectorAll('.edit-tabs-btn').forEach(btn => {
  btn.addEventListener('click', () => openTabSheet(btn.dataset.section));
});

$('tabSheetDone').addEventListener('click', () => {
  const section = _sheetSection;
  const order = [...$('tabSheetList').querySelectorAll('.sheet-item')].map(li => li.dataset.source);

  localStorage.setItem(TAB_ORDER_KEY(section), JSON.stringify(order));

  // 실제 탭 DOM 재정렬
  const nav = document.querySelector(`#${section}-section .sub-tabs`);
  order.forEach(source => {
    const btn = nav.querySelector(`.sub-tab[data-source="${source}"]`);
    if (btn) nav.appendChild(btn);
  });

  closeTabSheet();
});

// ===== 드래그 정렬 (Pointer Events) =====
function initSheetDrag(list) {
  let dragged = null;

  list.addEventListener('pointerdown', e => {
    const item = e.target.closest('.sheet-item');
    if (!item) return;
    dragged = item;
    item.setPointerCapture(e.pointerId);
    item.classList.add('dragging');
  });

  list.addEventListener('pointermove', e => {
    if (!dragged) return;
    const under = document.elementFromPoint(e.clientX, e.clientY);
    const target = under?.closest('.sheet-item');
    if (target && target !== dragged) {
      const rect = target.getBoundingClientRect();
      if (e.clientY < rect.top + rect.height / 2) {
        list.insertBefore(dragged, target);
      } else {
        list.insertBefore(dragged, target.nextSibling);
      }
    }
  });

  const endDrag = () => {
    if (!dragged) return;
    dragged.classList.remove('dragging');
    dragged = null;
  };
  list.addEventListener('pointerup', endDrag);
  list.addEventListener('pointercancel', endDrag);
}

// ===== 서브탭 스와이프 애니메이션 (iOS 스타일) =====
['news', 'community', 'hotdeal'].forEach(type => {
  const container = containers[type];

  // 클리핑 래퍼
  const wrapper = document.createElement('div');
  wrapper.style.cssText = 'overflow:hidden;position:relative;';
  container.parentNode.insertBefore(wrapper, container);
  wrapper.appendChild(container);
  container.style.willChange = 'transform';

  let startX = 0, startY = 0, startTime = 0;
  let isHorizontal = null, animating = false, blocked = false;
  let ghost = null, swipeDir = 0;
  const section = $(`${type}-section`);
  const EASING = 'cubic-bezier(0.25, 0.46, 0.45, 0.94)';

  function getTabs() {
    return [...document.querySelectorAll(`#${type}-section .sub-tab`)];
  }
  function getNextTab(dir) {
    const tabs = getTabs();
    return tabs[tabs.findIndex(t => t.dataset.source === state[type].source) + dir] || null;
  }
  function removeGhost() {
    if (ghost) { ghost.remove(); ghost = null; }
  }

  const subTabsBar = section.querySelector('.sub-tabs-bar');

  section.addEventListener('touchstart', e => {
    if (animating) return;
    // 서브탭 바는 자체 좌우 스크롤 전용 — 스와이프 제스처 완전 차단
    if (subTabsBar && subTabsBar.contains(e.target)) {
      blocked = true;
      return;
    }
    blocked = false;
    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
    startTime = e.timeStamp;
    isHorizontal = null;
    removeGhost();
    container.style.transition = 'none';
  }, { passive: true });

  section.addEventListener('touchmove', e => {
    if (animating || blocked) return;
    const dx = e.touches[0].clientX - startX;
    const dy = e.touches[0].clientY - startY;

    if (isHorizontal === null) {
      if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
      isHorizontal = Math.abs(dx) > Math.abs(dy);
      if (isHorizontal) {
        swipeDir = dx < 0 ? 1 : -1;
        if (getNextTab(swipeDir)) {
          // 다음 패널 미리 생성 (손가락 따라 같이 움직임)
          ghost = document.createElement('div');
          ghost.className = 'list-container';
          ghost.style.cssText = `position:absolute;top:0;left:0;width:100%;will-change:transform;` +
            `transform:translateX(${swipeDir > 0 ? '100%' : '-100%'});`;
          ghost.innerHTML = `<div class="spinner-wrap"><div class="spinner"></div></div>`;
          wrapper.appendChild(ghost);
        }
      }
    }
    if (!isHorizontal) return;
    e.preventDefault();

    const tabs = getTabs();
    const idx = tabs.findIndex(t => t.dataset.source === state[type].source);
    const atEdge = (dx > 0 && idx === 0) || (dx < 0 && idx === tabs.length - 1);
    const t = atEdge ? dx * 0.15 : dx;

    // 현재·다음 패널이 함께 이동
    container.style.transform = `translateX(${t}px)`;
    if (ghost) {
      ghost.style.transition = 'none';
      ghost.style.transform = `translateX(calc(${swipeDir > 0 ? '100%' : '-100%'} + ${t}px))`;
    }
  }, { passive: false });

  section.addEventListener('touchend', e => {
    if (blocked) return;
    if (animating || isHorizontal !== true) {
      removeGhost();
      container.style.transition = `transform 300ms ${EASING}`;
      container.style.transform = 'translateX(0)';
      return;
    }

    const dx = e.changedTouches[0].clientX - startX;
    const velocity = Math.abs(dx) / Math.max(1, e.timeStamp - startTime); // px/ms
    const shouldCommit = ghost && (Math.abs(dx) > 50 || velocity > 0.35);

    if (shouldCommit) {
      animating = true;
      const w = container.offsetWidth;
      // 빠를수록 짧게
      const dur = Math.max(200, Math.min(340, 320 - velocity * 120)) | 0;

      container.style.transition = `transform ${dur}ms ${EASING}`;
      container.style.transform = `translateX(${dx < 0 ? -w : w}px)`;
      ghost.style.transition = `transform ${dur}ms ${EASING}`;
      ghost.style.transform = 'translateX(0)';

      container.addEventListener('transitionend', () => {
        // 위치 초기화 후 탭 전환
        container.style.transition = 'none';
        container.style.transform = 'translateX(0)';
        container.innerHTML = '';
        removeGhost();
        const nextTab = getNextTab(swipeDir);
        if (nextTab) {
          nextTab.click();
          nextTab.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        }
        animating = false;
      }, { once: true });
    } else {
      // 스냅백
      removeGhost();
      container.style.transition = `transform 300ms ${EASING}`;
      container.style.transform = 'translateX(0)';
    }
  }, { passive: true });
});

// ===== 서울 날씨 + 미세먼지 =====
const WMO_ICON = {
  0:'☀️', 1:'🌤', 2:'⛅', 3:'☁️',
  45:'🌫', 48:'🌫',
  51:'🌦', 53:'🌦', 55:'🌧',
  61:'🌧', 63:'🌧', 65:'🌧',
  71:'🌨', 73:'🌨', 75:'🌨', 77:'🌨',
  80:'🌦', 81:'🌧', 82:'🌧',
  95:'⛈', 96:'⛈', 99:'⛈',
};

async function loadWeather() {
  try {
    const [wRes, aRes] = await Promise.all([
      fetch('https://api.open-meteo.com/v1/forecast?latitude=37.5665&longitude=126.9780&current=temperature_2m,weathercode&timezone=Asia/Seoul'),
      fetch('https://air-quality-api.open-meteo.com/v1/air-quality?latitude=37.5665&longitude=126.9780&current=pm10&timezone=Asia/Seoul'),
    ]);
    const w = await wRes.json();
    const a = await aRes.json();

    const temp  = Math.round(w.current.temperature_2m);
    const code  = w.current.weathercode;
    const pm10  = Math.round(a.current.pm10);
    const icon  = WMO_ICON[code] ?? '🌡';

    const [dustLabel, dustColor] =
      pm10 <= 30  ? ['미세 좋음',    '#4caf50'] :
      pm10 <= 80  ? ['미세 보통',    '#ff9800'] :
      pm10 <= 150 ? ['미세 나쁨',    '#f44336'] :
                    ['미세 매우나쁨','#9c27b0'];

    const el = $('weatherInfo');
    el.innerHTML =
      `<span class="weather-temp">${icon} ${temp}°</span>` +
      `<span class="weather-dust" style="color:${dustColor}">${dustLabel}</span>`;
  } catch { /* 조용히 실패 */ }
}

loadWeather();

// ===== 자동 갱신: 10분마다 현재 탭 새로고침 =====
setInterval(() => {
  const type = state.section;
  fetchAndRender(type, state[type].source, true);
}, CLIENT_CACHE_TTL);

// ===== 탭 복귀 시 만료된 데이터 자동 갱신 =====
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState !== 'visible') return;
  const type = state.section;
  const source = state[type].source;
  if (isCacheStale(type, source)) {
    fetchAndRender(type, source, true);
  }
});

// ===== 초기 로드 (새로고침 시 탭 상태 복원) =====
(function initTabState() {
  const saved = sessionStorage.getItem('tabState');
  if (!saved) {
    fetchAndRender('news', state.news.source);
    return;
  }
  try {
    const ts = JSON.parse(saved);
    const section = ts.section || 'news';

    // 각 섹션의 source 복원
    ['news', 'community', 'hotdeal'].forEach(type => {
      if (ts[type]) state[type].source = ts[type];
    });
    state.section = section;

    // 메인 탭 DOM 동기화
    document.querySelectorAll('.main-tab').forEach(b => {
      b.classList.toggle('active', b.dataset.section === section);
    });
    document.querySelectorAll('.section').forEach(s => {
      s.classList.toggle('active', s.id === `${section}-section`);
    });

    // 서브 탭 DOM 동기화
    ['news', 'community', 'hotdeal'].forEach(type => {
      const source = state[type].source;
      document.querySelectorAll(`#${type}-section .sub-tab`).forEach(b => {
        b.classList.toggle('active', b.dataset.source === source);
      });
    });

    fetchAndRender(section, state[section].source);
  } catch {
    fetchAndRender('news', state.news.source);
  }
})();
