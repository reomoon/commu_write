'use strict';

const PAGE_SIZE = 20;

// ===== 상태 관리 =====
const state = {
  community: { source: 'bobaedream', cache: {}, shown: {} },
  news:      { source: 'ent',        cache: {}, shown: {} },
  section:   'community',
};

// ===== DOM =====
const $ = id => document.getElementById(id);
const communityList     = $('community-list');
const newsList          = $('news-list');
const communitySentinel = $('community-sentinel');
const newsSentinel      = $('news-sentinel');
const updateTime        = $('update-time');
const refreshBtn        = $('refreshBtn');

// ===== 무한 스크롤 (IntersectionObserver) =====
const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    const type = entry.target.id === 'community-sentinel' ? 'community' : 'news';
    loadMore(type);
  });
}, { rootMargin: '0px 0px 200px 0px' });

observer.observe(communitySentinel);
observer.observe(newsSentinel);

// ===== 탭 이벤트 =====
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

document.querySelectorAll('#community-section .sub-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    if (btn.dataset.source === state.community.source) return;
    document.querySelectorAll('#community-section .sub-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.community.source = btn.dataset.source;
    fetchAndRender('community', btn.dataset.source);
  });
});

document.querySelectorAll('#news-section .sub-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    if (btn.dataset.source === state.news.source) return;
    document.querySelectorAll('#news-section .sub-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.news.source = btn.dataset.source;
    fetchAndRender('news', btn.dataset.source);
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
  const slice = items.slice(0, PAGE_SIZE);
  container.innerHTML = slice.map(makeItemHtml).join('');
}

// ===== 추가 로드 (무한 스크롤) =====
function loadMore(type) {
  const st = state[type];
  const source = st.source;
  const allItems = st.cache[source];
  if (!allItems) return;

  const shown = st.shown[source] || PAGE_SIZE;
  if (shown >= allItems.length) return;  // 더 이상 없음

  const next = Math.min(shown + PAGE_SIZE, allItems.length);
  const container = type === 'community' ? communityList : newsList;
  const newHtml = allItems.slice(shown, next).map(makeItemHtml).join('');
  container.insertAdjacentHTML('beforeend', newHtml);
  st.shown[source] = next;
}

// ===== API 호출 =====
async function fetchAndRender(type, source) {
  const st = state[type];
  const container = type === 'community' ? communityList : newsList;

  if (st.cache[source]) {
    st.shown[source] = PAGE_SIZE;
    renderList(container, st.cache[source]);
    setUpdateTime();
    return;
  }

  showSkeleton(container);
  const endpoint = type === 'community'
    ? `/api/community/${source}`
    : `/api/news/${source}`;

  try {
    const res = await fetch(endpoint);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = data.items || [];
    st.cache[source] = items;
    st.shown[source] = PAGE_SIZE;
    renderList(container, items);
    setUpdateTime();
  } catch (e) {
    container.innerHTML = `<p class="error-msg">오류가 발생했습니다.<br><small>${e.message}</small></p>`;
  }
}

function loadCurrent() {
  const type = state.section;
  const st = state[type];
  fetchAndRender(type, st.source);
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

// ===== 초기 로드 =====
fetchAndRender('community', state.community.source);
