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

// ===== 메인 탭 이벤트 =====
document.querySelectorAll('.main-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.main-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.section = btn.dataset.section;
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    $(`${state.section}-section`).classList.add('active');
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
      fetchAndRender(type, btn.dataset.source);
    });
  });
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

// ===== 스켈레톤 =====
function showSkeleton(container) {
  container.innerHTML = `
    <div class="skeleton-list">
      ${Array(10).fill('<div class="skeleton-item"></div>').join('')}
    </div>`;
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

// ===== 초기 로드 =====
fetchAndRender('news', state.news.source);
