
function hideBootLoader() {
  const loader = document.getElementById('boot-loader');
  if (!loader) return;
  loader.classList.add('hide');
  setTimeout(() => { loader.style.display = 'none'; }, 300);
}

function showBootLoader(then) {
  const loader = document.getElementById('boot-loader');
  const bar = document.getElementById('boot-bar');
  const pct = document.getElementById('boot-pct');
  if (!loader) {
    if (typeof then === 'function') then();
    return;
  }
  loader.classList.remove('hide');
  loader.style.display = 'flex';
  let n = 0;
  const timer = setInterval(() => {
    try {
      n = Math.min(100, n + 15 + Math.floor(Math.random() * 10));
      if (bar) bar.style.width = n + '%';
      if (pct) pct.textContent = n + '%';
      if (n >= 100) {
        clearInterval(timer);
        setTimeout(() => {
          hideBootLoader();
          if (typeof then === 'function') {
            try { then(); } catch (err) { console.error('boot callback', err); showAuth(); }
          }
        }, 150);
      }
    } catch (err) {
      clearInterval(timer);
      hideBootLoader();
      if (typeof then === 'function') then();
    }
  }, 60);
  // safety: never stuck more than 4s
  setTimeout(() => {
    clearInterval(timer);
    if (loader && loader.style.display !== 'none') {
      hideBootLoader();
      if (typeof then === 'function') {
        try { then(); } catch (e) { showAuth(); }
      }
    }
  }, 4000);
}

const API = '';
let token = localStorage.getItem('token');
let currentUser = null;
let currentPage = 'home';
let currentChatId = null;
let ws = null;
function userRole() { return String((currentUser && currentUser.role) || '').toLowerCase(); }
function canManageClass() { return ['starosta', 'moderator', 'admin'].includes(userRole()); }


async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(API + path, { ...options, headers });
  if (res.status === 401) {
    // only kick to login for protected endpoints, not during login itself
    if (!path.includes('/auth/login') && !path.includes('/auth/register')) {
      token = null;
      localStorage.removeItem('token');
      showAuth();
    }
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'Требуется вход');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    let msg = data.detail || data.message || 'Ошибка';
    if (Array.isArray(msg)) msg = msg.map(e => e.msg || JSON.stringify(e)).join('; ');
    else if (typeof msg === 'object') msg = JSON.stringify(msg);
    throw new Error(msg);
  }
  return data;
}

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

function showAuth() {
  hideBootLoader();
  const auth = document.getElementById('auth-screen');
  const main = document.getElementById('main-screen');
  if (auth) auth.classList.add('active');
  if (main) main.classList.remove('active');
}

function showMain() {
  showBootLoader(async () => {
    $('#auth-screen').classList.remove('active');
    $('#main-screen').classList.add('active');
    try {
      await loadUser();
    } catch (e) {
      console.error(e);
    }
    if (!token || !currentUser) {
      showAuth();
      return;
    }
    navigate('home');
    connectWS();
    if (window.Notification && Notification.permission === 'default') {
      Notification.requestPermission().catch(()=>{});
    }
  });
}

async function loadUser() {
  try {
    currentUser = await api('/api/auth/me');
    if (!currentUser || !currentUser.id) {
      console.error('loadUser: no user');
      return;
    }
    const role = userRole();
    const badge = $('#user-pro-badge');
    if (badge) badge.style.display = currentUser.is_pro ? 'inline' : 'none';
    const an = $('#admin-nav'); const sn = $('#starosta-nav');
    if (an) an.style.display = (role === 'admin') ? 'flex' : 'none';
    if (sn) sn.style.display = (role === 'starosta') ? 'flex' : 'none';
    const rn = $('#reels-nav');
    if (rn) rn.style.display = (role === 'starosta') ? 'none' : 'flex';
    const classPages = ['homework','schedule','announcements','polls','events','collections','classmates','starosta'];
    classPages.forEach(pg => {
      const ni = document.querySelector('.nav-item[data-page="' + pg + '"]');
      if (ni) {
        if (role === 'admin') ni.style.display = 'none';
        else ni.style.display = '';
      }
    });
    if (role === 'admin' || role === 'starosta') {
      currentUser.is_pro = true;
      if (badge) badge.style.display = 'inline';
    }
    const av = $('#user-avatar');
    if (av) {
      av.src = currentUser.avatar_url || ('https://ui-avatars.com/api/?name=' + encodeURIComponent(currentUser.display_name || '?') + '&background=4f46e5&color=fff');
    }
    updateSep1Countdown();
    const seen = localStorage.getItem('social_seen_' + currentUser.id);
    if (!seen && role === 'student') {
      setTimeout(showSocialModal, 800);
    }
  } catch (e) {
    console.error('loadUser error', e);
    // only logout if token is invalid
    if (String(e.message || '').includes('вход') || String(e.message || '').includes('Unauthorized')) {
      logout();
    }
  }
}

function updateSep1Countdown() {
  const el = $('#sep1-countdown');
  if (!el) return;
  const now = new Date();
  let y = now.getFullYear();
  let target = new Date(y, 8, 1); // Sep 1
  if (now >= target) target = new Date(y + 1, 8, 1);
  const days = Math.ceil((target - now) / 86400000);
  el.innerHTML = `До 1 сент: <strong>${days}</strong> дн.`;
}

let socialOpened = new Set();
function showSocialModal() {
  const m = $('#social-modal');
  if (!m || !currentUser) return;
  m.style.display = 'flex';
  socialOpened = new Set();
  const claim = $('#btn-social-claim');
  if (claim) claim.disabled = true;
  $$('.social-btn').forEach(b => {
    b.classList.remove('visited');
    b.onclick = () => {
      socialOpened.add(b.dataset.net);
      b.classList.add('visited');
      if (socialOpened.size >= 1 && claim) claim.disabled = false;
    };
  });
}
document.addEventListener('click', async (e) => {
  if (e.target && e.target.id === 'btn-social-skip') {
    try { await api('/api/pro/social-skip', { method: 'POST' }); } catch(x) {}
    if (currentUser) localStorage.setItem('social_seen_' + currentUser.id, '1');
    const m = $('#social-modal'); if (m) m.style.display = 'none';
  }
  if (e.target && e.target.id === 'btn-social-claim') {
    try {
      const r = await api('/api/pro/social-bonus', { method: 'POST' });
      alert(r.message || 'PRO на 2 дня!');
      if (currentUser) localStorage.setItem('social_seen_' + currentUser.id, '1');
      const m = $('#social-modal'); if (m) m.style.display = 'none';
      await loadUser();
    } catch (err) { alert(err.message); }
  }
});

function logout() {
  token = null;
  localStorage.removeItem('token');
  currentUser = null;
  try { if (ws) ws.close(); } catch (e) {}
  hideBootLoader();
  showAuth();
}

$$('.tab').forEach(t => t.addEventListener('click', () => {
  $$('.tab').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  $$('.auth-form').forEach(f => f.classList.remove('active'));
  $(`#${t.dataset.tab}-form`).classList.add('active');
}));

const _loginForm = $('#login-form'); if (_loginForm) _loginForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  $('#auth-error').textContent = '';
  try {
    const form = new FormData();
    form.append('username', $('#login-username').value);
    form.append('password', $('#login-password').value);
    const res = await fetch('/api/auth/login', { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Ошибка входа');
    token = data.access_token;
    localStorage.setItem('token', token);
    showMain();
  } catch (err) { $('#auth-error').textContent = err.message; }
});

const _regForm = $('#register-form'); if (_regForm) _regForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  $('#auth-error').textContent = '';
  try {
    await api('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        invite_code: $('#reg-invite').value,
        username: $('#reg-username').value,
        display_name: $('#reg-displayname').value,
        password: $('#reg-password').value
      })
    });
    const form = new FormData();
    form.append('username', $('#reg-username').value);
    form.append('password', $('#reg-password').value);
    const res = await fetch('/api/auth/login', { method: 'POST', body: form });
    const data = await res.json();
    token = data.access_token;
    localStorage.setItem('token', token);
    showMain();
  } catch (err) { $('#auth-error').textContent = err.message; }
});

const _logoutBtn = $('#logout-btn'); if (_logoutBtn) _logoutBtn.addEventListener('click', async () => {
  try { await api('/api/auth/logout', { method: 'POST' }); } catch(e) {}
  logout();
});

const _themeBtn = $('#theme-toggle'); if (_themeBtn) _themeBtn.addEventListener('click', () => {
  const html = document.documentElement;
  const dark = html.getAttribute('data-theme') === 'dark';
  html.setAttribute('data-theme', dark ? 'light' : 'dark');
  localStorage.setItem('theme', dark ? 'light' : 'dark');
  const _ti = $('#theme-toggle i'); if (_ti) _ti.className = dark ? 'fas fa-moon' : 'fas fa-sun';
});
if (localStorage.getItem('theme') === 'dark') {
  document.documentElement.setAttribute('data-theme', 'dark');
  const _ti2 = $('#theme-toggle i'); if (_ti2) _ti2.className = 'fas fa-sun';
}

$$('.nav-item').forEach(item => {
  item.addEventListener('click', (e) => {
    e.preventDefault();
    const page = item.dataset.page;
    if (page) navigate(page);
  });
});

const _menuBtn = $('#menu-toggle'); if (_menuBtn) _menuBtn.addEventListener('click', () => {
  $('.sidebar').classList.toggle('open');
});
document.addEventListener('click', (e) => {
  const sidebar = $('.sidebar');
  const toggle = $('#menu-toggle');
  if (!sidebar || !sidebar.classList.contains('open')) return;
  if (sidebar.contains(e.target) || (toggle && toggle.contains(e.target))) return;
  sidebar.classList.remove('open');
});

const titles = {
  home: 'Главная', chats: 'Чаты', classmates: 'Одноклассники', homework: 'Домашка',
  schedule: 'Расписание', announcements: 'Объявления', polls: 'Опросы', events: 'События',
  collections: 'Сборы', files: 'Файлы', notifications: 'Уведомления',
  pro: 'ClassMate PRO', profile: 'Профиль', admin: 'Админ-панель', starosta: 'Управление классом', reels: 'Reels', settings: 'Настройки'
};

async function navigate(page) {
  document.body.classList.remove('chat-open');
  currentPage = page;
  currentChatId = null;
  $$('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.page === page));
  const _pt = $('#page-title'); if (_pt) _pt.textContent = titles[page] || page;
  const _sb = $('.sidebar'); if (_sb) _sb.classList.remove('open');
  const content = $('#page-content');
  content.innerHTML = '<div class="empty"><i class="fas fa-spinner fa-spin"></i></div>';
  try {
    switch (page) {
      case 'home': await renderHome(content); break;
      case 'chats': await renderChats(content); break;
      case 'classmates': await renderClassmates(content); break;
      case 'homework': await renderHomework(content); break;
      case 'schedule': await renderSchedule(content); break;
      case 'announcements': await renderAnnouncements(content); break;
      case 'polls': await renderPolls(content); break;
      case 'events': await renderEvents(content); break;
      case 'collections': await renderCollections(content); break;
      case 'files': await renderFiles(content); break;
      case 'notifications': await renderNotifications(content); break;
      case 'pro': await renderPro(content); break;
      case 'profile': await renderProfile(content); break;
      case 'admin': await renderAdmin(content); break;
      case 'starosta': await renderStarosta(content); break;
      case 'reels': await renderReels(content); break;
      case 'settings': await renderSettings(content); break;
      default: content.innerHTML = '<div class="empty"><p>Скоро...</p></div>';
    }
  } catch (e) {
    content.innerHTML = `<div class="empty"><p>${e.message}</p></div>`;
  }
}

async function renderHome(el) {
  let online = [], hw = [], events = [], notifs = [], chats = [];
  try {
    [online, hw, events, notifs, chats] = await Promise.all([
      api('/api/users/online').catch(() => []),
      api('/api/homework/').catch(() => []),
      api('/api/events/').catch(() => []),
      api('/api/notifications/').catch(() => []),
      api('/api/chats/').catch(() => []),
    ]);
  } catch (e) {}
  const nearestHw = (hw || []).filter(h => h.status !== 'done').sort((a,b) => new Date(a.due_date) - new Date(b.due_date))[0];
  const nearestEvent = (events || []).filter(e => new Date(e.start_at) > new Date())[0];
  const unread = (notifs || []).filter(n => !n.is_read).length;
  const chatUnread = (chats || []).reduce((s,c) => s + (c.unread_count || 0), 0);
  const now = new Date();
  let y = now.getFullYear();
  let target = new Date(y, 8, 1);
  if (now >= target) target = new Date(y + 1, 8, 1);
  const daysLeft = Math.ceil((target - now) / 86400000);

  const av = (u) => u.avatar_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(u.display_name||'?')}&background=4f46e5&color=fff&size=64`;

  el.innerHTML = `
    <div class="countdown-big">
      <div style="opacity:.9;font-size:13px">До 1 сентября</div>
      <div class="num">${daysLeft}</div>
      <div style="opacity:.9;font-size:13px">дней</div>
    </div>
    <div class="home-grid">
      <div class="card stat-card"><div class="value">${(online||[]).length}</div><div class="label">Онлайн</div></div>
      <div class="card stat-card"><div class="value">${unread}</div><div class="label">Уведомления</div></div>
      <div class="card stat-card"><div class="value">${chatUnread}</div><div class="label">Новые в чатах</div></div>
    </div>
    <div class="card">
      <div class="card-title"><i class="fas fa-circle" style="color:var(--success);font-size:10px"></i> Кто в сети</div>
      <div class="online-avatars">
        ${(online||[]).length ? (online||[]).map(u => `
          <div class="oa">
            <img src="${av(u)}" alt="">
            <span>${(u.display_name||'').split(' ')[0]}</span>
          </div>`).join('') : '<span class="empty">Никого нет</span>'}
      </div>
    </div>
    <div class="card">
      <div class="card-title"><i class="fas fa-comments"></i> Чаты</div>
      <div class="mini-chat-preview">
        ${(chats||[]).slice(0,5).map(c => `
          <div class="mc-row" style="cursor:pointer" onclick="openChat(${c.id}, '${(c.name||'Чат').replace(/'/g,"\\'")}')">
            <strong>${c.name || 'Чат'}</strong>
            ${c.unread_count ? `<span class="unread">${c.unread_count}</span>` : ''}
            <div style="color:var(--text-secondary);font-size:12px">${c.last_message ? (c.last_message.content || '📎').slice(0,60) : 'Нет сообщений'}</div>
          </div>`).join('') || '<p class="empty">Нет чатов</p>'}
      </div>
      <button class="btn btn-primary" style="width:auto;margin-top:10px;padding:8px 14px;font-size:13px" onclick="navigate('chats')">Все чаты</button>
    </div>
    <div class="card">
      <div class="card-title"><i class="fas fa-book"></i> Ближайшее ДЗ</div>
      ${nearestHw ? `<p><strong>${nearestHw.subject}</strong>: ${nearestHw.title}<br><small>до ${new Date(nearestHw.due_date).toLocaleDateString('ru')}</small></p>` : '<p class="empty">Нет заданий</p>'}
    </div>
    <div class="card">
      <div class="card-title"><i class="fas fa-star"></i> Ближайшее событие</div>
      ${nearestEvent ? `<p><strong>${nearestEvent.title}</strong><br><small>${new Date(nearestEvent.start_at).toLocaleString('ru')}</small></p>` : '<p class="empty">Нет событий</p>'}
    </div>
    ${currentUser.is_pro ? '<div class="card" style="border:1px solid var(--pro)"><div class="card-title"><i class="fas fa-crown" style="color:var(--pro)"></i> PRO активен</div><p style="font-size:13px">Спасибо за поддержку ClassMate!</p></div>' : '<div class="card"><div class="card-title"><i class="fas fa-crown"></i> ClassMate PRO</div><p style="font-size:13px;margin-bottom:8px">Темы, статистика, больше места — от 25 смн</p><button class="btn btn-primary" style="width:auto;padding:8px 14px;font-size:13px" onclick="navigate(\'pro\')">Смотреть тарифы</button></div>'}
  `;
  const b = $('#chat-badge'); if (b) b.textContent = chatUnread || '';
  const nb = $('#notif-badge'); if (nb) nb.textContent = unread || '';
}

async function renderChats(el) {
  let chats;
  try {
    chats = await api('/api/chats/');
  } catch (e) {
    el.innerHTML = `<div class="empty"><i class="fas fa-exclamation-triangle"></i><p>${e.message || 'Ошибка загрузки'}</p>
      <button class="btn btn-primary" style="width:auto;margin-top:12px" onclick="navigate('chats')">Повторить</button></div>`;
    return;
  }
  if (!chats || !chats.length) {
    el.innerHTML = '<div class="empty"><i class="fas fa-comments"></i><p>Нет чатов</p></div>';
    return;
  }
  el.innerHTML = `<div class="chat-list">${chats.map(c => {
    const safe = (c.name || 'Чат').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    const preview = c.last_message ? (c.last_message.content || (c.last_message.file_name ? '📎 файл' : 'Сообщение')) : 'Нет сообщений';
    return `<div class="chat-item" onclick="openChat(${c.id}, '${safe}')">
      <div class="avatar">${(c.name || 'Ч')[0]}</div>
      <div class="info">
        <div class="name">${c.name || 'Чат'}</div>
        <div class="preview">${(preview || '').replace(/</g, '&lt;')}</div>
      </div>
      <div class="meta">
        ${c.unread_count ? `<span class="unread">${c.unread_count}</span>` : ''}
      </div>
    </div>`;
  }).join('')}</div>`;
}

window.openChat = async function(chatId, name) {
  currentChatId = chatId;
  document.body.classList.add('chat-open');
  $('#page-title').textContent = name || 'Чат';
  const el = $('#page-content');
  el.innerHTML = '<div class="empty"><i class="fas fa-spinner fa-spin"></i></div>';
  let messages;
  try {
    messages = await api(`/api/chats/${chatId}/messages?limit=80`);
    // mark as read - clear badge
    try { await api(`/api/chats/${chatId}/read`, { method: 'POST' }); } catch(x) {}
    const b = $('#chat-badge'); if (b) b.textContent = '';
  } catch (e) {
    document.body.classList.remove('chat-open');
    el.innerHTML = `<div class="empty"><p>${e.message}</p>
      <button class="btn btn-primary" style="width:auto;margin-top:12px" onclick="navigate('chats')">Назад</button></div>`;
    return;
  }
  el.innerHTML = `
    <div class="messages-area fullscreen-chat">
      <div class="chat-back-bar">
        <button type="button" class="back-btn" onclick="closeChat()"><i class="fas fa-arrow-left"></i></button>
        <div class="chat-title">${(name || 'Чат').replace(/</g, '&lt;')}</div>
        <div id="typing-indicator" class="typing-indicator" style="display:none">печатает...</div>
      </div>
      <div class="messages-list" id="messages-list">
        ${(messages || []).map(m => renderMessage(m)).join('') || '<div class="empty" style="padding:30px"><p>Нет сообщений</p></div>'}
      </div>
      <div class="message-input-area">
        <label class="attach-btn" title="Фото" style="display:flex;align-items:center;justify-content:center;cursor:pointer">
          <i class="fas fa-camera"></i>
          <input type="file" id="msg-photo" accept="image/*" capture="environment" style="display:none" onchange="sendPhotoMsg()">
        </label>
        <input type="text" id="msg-input" placeholder="Написать сообщение..." autocomplete="off"
          onkeydown="if(event.key==='Enter')sendMsg()" oninput="notifyTyping()">
        <button type="button" onclick="sendMsg()"><i class="fas fa-paper-plane"></i></button>
      </div>
    </div>
  `;
  const list = $('#messages-list');
  if (list) list.scrollTop = list.scrollHeight;
  const inp = $('#msg-input');
  if (inp) setTimeout(() => inp.focus(), 50);
};
window.closeChat = function() {
  document.body.classList.remove('chat-open');
  currentChatId = null;
  navigate('chats');
};
let typingTimer = null;
window.notifyTyping = function() {
  if (!ws || ws.readyState !== 1 || !currentChatId) return;
  if (typingTimer) return;
  try { ws.send(JSON.stringify({ type: 'typing', chat_id: currentChatId })); } catch(e) {}
  typingTimer = setTimeout(() => { typingTimer = null; }, 1500);
};

function renderMessage(m) {
  const mine = currentUser && m.sender_id === currentUser.id;
  const sender = (m.sender && m.sender.display_name) ? String(m.sender.display_name).replace(/</g, '&lt;') : '';
  let body = '';
  const isImg = m.file_url && (String(m.file_type || '').indexOf('image') === 0 || /\.(jpg|jpeg|png|gif|webp)(\?|$)/i.test(m.file_url));
  if (isImg) {
    body = `<img class="msg-photo" src="${m.file_url}" alt="">`;
    if (m.content) body = m.content.replace(/</g,'&lt;') + '<br>' + body;
  } else {
    body = (m.content || (m.file_name ? '📎 ' + m.file_name : '') || '').replace(/</g, '&lt;');
  }
  return `<div class="message ${mine ? 'mine' : 'other'}">
    ${!mine && sender ? `<div class="sender">${sender}</div>` : ''}
    <div>${body}</div>
    <div class="time">${m.created_at ? new Date(m.created_at).toLocaleTimeString('ru', {hour:'2-digit',minute:'2-digit'}) : ''}</div>
  </div>`;
}
window.sendPhotoMsg = async function() {
  const input = $('#msg-photo');
  const f = input && input.files && input.files[0];
  if (!f || !currentChatId) return;
  try {
    const fd = new FormData(); fd.append('file', f);
    const up = await fetch('/api/uploads/image', { method:'POST', headers:{Authorization:'Bearer '+token}, body:fd });
    const data = await up.json().catch(()=>({}));
    if (!up.ok) throw new Error(data.detail || 'Ошибка загрузки');
    const msg = await api(`/api/chats/${currentChatId}/messages`, {
      method:'POST', body: JSON.stringify({ content: null, file_url: data.url, file_name: f.name, file_type: f.type || 'image/jpeg' })
    });
    const list = $('#messages-list');
    if (list) { list.insertAdjacentHTML('beforeend', renderMessage(msg)); list.scrollTop = list.scrollHeight; }
  } catch(e) { alert(e.message); }
  if (input) input.value = '';
};


window.sendMsg = async function() {
  const input = $('#msg-input');
  const text = input && input.value.trim();
  if (!text || !currentChatId) return;
  input.value = '';
  try {
    const msg = await api(`/api/chats/${currentChatId}/messages`, {
      method: 'POST', body: JSON.stringify({ content: text })
    });
    const list = $('#messages-list');
    if (list) {
      list.insertAdjacentHTML('beforeend', renderMessage(msg));
      list.scrollTop = list.scrollHeight;
    }
  } catch (e) { alert(e.message); }
};

async function renderClassmates(el) {
  const users = await api('/api/users/classmates');
  el.innerHTML = `
    <input class="search-box" placeholder="Поиск..." oninput="filterUsers(this.value)">
    <div class="grid" id="users-grid">
      ${(users||[]).map(u => `
        <div class="card user-card">
          <div class="avatar-wrap">
            <div class="avatar">${u.display_name[0]}</div>
            ${u.is_online ? '<div class="online-dot"></div>' : ''}
          </div>
          <div>
            <div style="font-weight:600">${u.display_name} ${u.is_pro ? '<span class="pro-badge">PRO</span>' : ''}</div>
            <div style="color:var(--text-secondary);font-size:13px">@${u.username}</div>
            <div style="font-size:12px;color:var(--text-secondary)">${u.status || (u.is_online ? 'онлайн' : 'оффлайн')}</div>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

window.filterUsers = function(q) {
  $$('#users-grid .user-card').forEach(c => {
    c.style.display = c.textContent.toLowerCase().includes(q.toLowerCase()) ? '' : 'none';
  });
};

async function renderHomework(el) {
  const items = await api('/api/homework/');
  const canCreate = canManageClass();
  let html = '';
  if (canCreate) {
    html += `<button class="btn btn-primary" style="width:auto;margin-bottom:12px" onclick="document.getElementById('hw-create').classList.toggle('open')"><i class="fas fa-plus"></i> Создать ДЗ</button>
    <div class="card create-form" id="hw-create">
      <div class="form-group"><label>Предмет</label><input id="hw-subject" class="search-box"></div>
      <div class="form-group"><label>Название</label><input id="hw-title" class="search-box"></div>
      <div class="form-group"><label>Описание</label><input id="hw-desc" class="search-box"></div>
      <div class="form-group"><label>Срок</label><input id="hw-due" type="datetime-local" class="search-box"></div>
      <div class="form-group"><label>PDF / файл (необязательно)</label><input type="file" id="hw-file" accept=".pdf,image/*,application/pdf" class="search-box"></div>
      <button class="btn btn-primary" style="width:auto" onclick="createHomework()">Сохранить</button>
    </div>`;
  }
  if (!items || !items.length) {
    html += '<div class="empty"><i class="fas fa-book"></i><p>Нет домашних заданий</p></div>';
    el.innerHTML = html; return;
  }
  html += items.map(h => `
    <div class="card hw-card ${h.status}">
      <div style="display:flex;justify-content:space-between;align-items:start">
        <div>
          <div style="font-size:12px;color:var(--text-secondary)">${h.subject}</div>
          <div style="font-weight:600;margin:4px 0">${h.title}</div>
          <div style="font-size:13px;color:var(--text-secondary)">${h.description || ''}</div>
          <div style="font-size:12px;margin-top:8px">до ${new Date(h.due_date).toLocaleString('ru')}</div>
          ${h.file_url ? `<div style="margin-top:6px"><a href="${h.file_url}" target="_blank" rel="noopener">📎 Скачать файл</a></div>` : ''}
        </div>
        <span class="status-badge status-${h.status}">${{new:'Новое',in_progress:'Выполняется',done:'Выполнено',overdue:'Просрочено'}[h.status]||h.status}</span>
      </div>
      ${h.status !== 'done' ? `<button class="btn btn-primary" style="margin-top:12px;width:auto;padding:8px 16px;font-size:13px" onclick="markHwDone(${h.id})">Отметить выполненным</button>` : ''}
    </div>
  `).join('');
  el.innerHTML = html;
}
window.createHomework = async function() {
  try {
    const due = $('#hw-due') && $('#hw-due').value;
    if (!$('#hw-subject').value || !$('#hw-title').value || !due) { alert('Заполните поля'); return; }
    let file_url = null;
    const f = $('#hw-file') && $('#hw-file').files && $('#hw-file').files[0];
    if (f) {
      const fd = new FormData(); fd.append('file', f);
      const up = await fetch('/api/uploads/image', { method:'POST', headers:{Authorization:'Bearer '+token}, body:fd });
      const data = await up.json().catch(()=>({}));
      if (!up.ok) throw new Error(data.detail || 'Ошибка файла');
      file_url = data.url;
    }
    await api('/api/homework/', { method: 'POST', body: JSON.stringify({
      subject: $('#hw-subject').value, title: $('#hw-title').value,
      description: ($('#hw-desc')||{}).value || '', due_date: new Date(due).toISOString(),
      file_url
    })});
    navigate('homework');
  } catch (e) { alert(e.message); }
};
window.markHwDone = async function(id) {
  await api(`/api/homework/${id}/status?status=done`, { method: 'PUT' });
  navigate('homework');
};

async function renderSchedule(el) {
  const items = await api('/api/schedule/');
  const days = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];
  const canCreate = canManageClass();
  let html = '';
  if (canCreate) {
    html += `<button class="btn btn-primary" style="width:auto;margin-bottom:12px" onclick="document.getElementById('sch-create').classList.toggle('open')"><i class="fas fa-plus"></i> Добавить урок</button>
    <div class="card create-form" id="sch-create">
      <div class="form-group"><label>День</label>
        <select id="sch-day" class="search-box">
          <option value="0">Пн</option><option value="1">Вт</option><option value="2">Ср</option>
          <option value="3">Чт</option><option value="4">Пт</option><option value="5">Сб</option><option value="6">Вс</option>
        </select>
      </div>
      <div class="form-group"><label>Номер урока</label><input id="sch-num" type="number" min="1" class="search-box" value="1"></div>
      <div class="form-group"><label>Предмет</label><input id="sch-subj" class="search-box"></div>
      <div class="form-group"><label>Кабинет</label><input id="sch-room" class="search-box"></div>
      <div class="form-group"><label>Учитель</label><input id="sch-teacher" class="search-box"></div>
      <div class="form-group"><label>Начало</label><input id="sch-start" class="search-box" value="08:00"></div>
      <div class="form-group"><label>Конец</label><input id="sch-end" class="search-box" value="08:45"></div>
      <button class="btn btn-primary" style="width:auto" onclick="createScheduleItem()">Сохранить</button>
    </div>`;
  }
  if (!items || !items.length) {
    html += '<div class="empty"><i class="fas fa-calendar-alt"></i><p>Расписание пока пустое</p></div>';
    el.innerHTML = html; return;
  }
  const byDay = {};
  items.forEach(s => { (byDay[s.day_of_week] = byDay[s.day_of_week] || []).push(s); });
  html += Object.keys(byDay).sort((a,b)=>a-b).map(d => `
    <div class="card">
      <div class="card-title">${days[d] || d}</div>
      ${byDay[d].map(s => `
        <div style="display:flex;gap:12px;padding:8px 0;border-bottom:1px solid var(--border)">
          <div style="font-weight:600;min-width:30px">${s.lesson_number}</div>
          <div style="flex:1">
            <div>${s.subject}</div>
            <div style="font-size:12px;color:var(--text-secondary)">${s.teacher || ''} ${s.room ? '· каб. '+s.room : ''}</div>
          </div>
          <div style="font-size:12px;color:var(--text-secondary)">${(s.start_time||'').toString().slice(0,5)}–${(s.end_time||'').toString().slice(0,5)}</div>
        </div>
      `).join('')}
    </div>
  `).join('');
  el.innerHTML = html;
}
window.createScheduleItem = async function() {
  const subject = ($('#sch-subj').value || '').trim();
  const start = ($('#sch-start').value || '').trim();
  const end = ($('#sch-end').value || '').trim();
  if (!subject || !start || !end) { alert('Заполните предмет и время'); return; }
  const toTime = t => { const p = t.split(':'); return p.length >= 2 ? `${p[0].padStart(2,'0')}:${p[1].padStart(2,'0')}:00` : t; };
  try {
    await api('/api/schedule/', { method:'POST', body: JSON.stringify({
      day_of_week: parseInt($('#sch-day').value, 10),
      lesson_number: parseInt($('#sch-num').value, 10) || 1,
      subject,
      room: ($('#sch-room').value || '').trim() || null,
      teacher: ($('#sch-teacher').value || '').trim() || null,
      start_time: toTime(start), end_time: toTime(end)
    })});
    navigate('schedule');
  } catch (e) { alert(e.message); }
};

async function renderAnnouncements(el) {
  const items = await api('/api/announcements/');
  const canCreate = canManageClass();
  let html = '';
  if (canCreate) {
    html += `<button class="btn btn-primary" style="width:auto;margin-bottom:12px" onclick="document.getElementById('ann-create').classList.toggle('open')"><i class="fas fa-plus"></i> Создать объявление</button>
    <div class="card create-form" id="ann-create">
      <div class="form-group"><label>Заголовок</label><input id="ann-title" class="search-box"></div>
      <div class="form-group"><label>Текст</label><textarea id="ann-content" class="search-box" rows="3"></textarea></div>
      <label style="display:flex;align-items:center;gap:8px;margin:8px 0"><input type="checkbox" id="ann-important"> Важно</label>
      <button class="btn btn-primary" style="width:auto" onclick="createAnnouncement()">Опубликовать</button>
    </div>`;
  }
  if (!items || !items.length) {
    html += '<div class="empty"><i class="fas fa-bullhorn"></i><p>Нет объявлений</p></div>';
    el.innerHTML = html; return;
  }
  html += items.map(a => `
    <div class="card" style="${a.is_important ? 'border-left:4px solid var(--danger)' : ''}">
      ${a.is_pinned ? '<i class="fas fa-thumbtack" style="color:var(--primary);margin-right:6px"></i>' : ''}
      <strong>${a.title}</strong>
      ${a.is_important ? '<span class="status-badge status-overdue" style="margin-left:8px">Важно</span>' : ''}
      <p style="margin:8px 0;font-size:14px">${a.content}</p>
      <small style="color:var(--text-secondary)">${new Date(a.created_at).toLocaleString('ru')}</small>
    </div>
  `).join('');
  el.innerHTML = html;
}
window.createAnnouncement = async function() {
  try {
    await api('/api/announcements/', { method:'POST', body: JSON.stringify({
      title: $('#ann-title').value,
      content: $('#ann-content').value,
      is_important: ($('#ann-important')||{}).checked || false
    })});
    navigate('announcements');
  } catch(e) { alert(e.message); }
};

async function renderPolls(el) {
  const items = await api('/api/polls/');
  const canCreate = canManageClass();
  let html = '';
  if (canCreate) {
    html += `<button class="btn btn-primary" style="width:auto;margin-bottom:12px" onclick="document.getElementById('poll-create').classList.toggle('open')"><i class="fas fa-plus"></i> Создать опрос</button>
    <div class="card create-form" id="poll-create">
      <div class="form-group"><label>Вопрос</label><input id="poll-q" class="search-box"></div>
      <div class="form-group"><label>Варианты (каждый с новой строки)</label><textarea id="poll-opts" class="search-box" rows="4" placeholder="Да\nНет\nВозможно"></textarea></div>
      <button class="btn btn-primary" style="width:auto" onclick="createPoll()">Создать</button>
    </div>`;
  }
  if (!items || !items.length) {
    html += '<div class="empty"><i class="fas fa-poll"></i><p>Нет опросов</p></div>';
    el.innerHTML = html; return;
  }
  html += items.map(p => `
    <div class="card">
      <div class="card-title">${p.question}</div>
      ${(p.options||[]).map(o => `
        <div style="display:flex;align-items:center;gap:10px;padding:8px 0;cursor:pointer" onclick="${p.user_voted ? '' : `votePoll(${p.id},${o.id})`}">
          <div style="flex:1;background:var(--bg);border-radius:8px;height:32px;position:relative;overflow:hidden">
            <div style="background:var(--primary);opacity:0.3;height:100%;width:${(p.options||[]).reduce((s,x)=>s+x.votes_count,0) ? (o.votes_count/(p.options||[]).reduce((s,x)=>s+x.votes_count,0)*100) : 0}%"></div>
            <span style="position:absolute;left:10px;top:6px;font-size:13px">${o.text}</span>
          </div>
          <span style="font-size:13px;min-width:30px">${o.votes_count}</span>
        </div>
      `).join('')}
      ${p.user_voted ? '<small style="color:var(--text-secondary)">Вы уже проголосовали</small>' : ''}
    </div>
  `).join('');
  el.innerHTML = html;
}
window.createPoll = async function() {
  try {
    const opts = ($('#poll-opts').value || '').split('\n').map(s => s.trim()).filter(Boolean);
    if (opts.length < 2) { alert('Минимум 2 варианта'); return; }
    await api('/api/polls/', { method:'POST', body: JSON.stringify({
      question: $('#poll-q').value,
      options: opts
    })});
    navigate('polls');
  } catch(e) { alert(e.message); }
};

window.votePoll = async function(pollId, optionId) {
  await api(`/api/polls/${pollId}/vote?option_id=${optionId}`, { method: 'POST' });
  navigate('polls');
};

async function renderEvents(el) {
  const items = await api('/api/events/');
  const canCreate = canManageClass();
  let html = '';
  if (canCreate) {
    html += `<button class="btn btn-primary" style="width:auto;margin-bottom:12px" onclick="document.getElementById('ev-create').classList.toggle('open')"><i class="fas fa-plus"></i> Создать событие</button>
    <div class="card create-form" id="ev-create">
      <div class="form-group"><label>Название</label><input id="ev-title" class="search-box"></div>
      <div class="form-group"><label>Описание</label><input id="ev-desc" class="search-box"></div>
      <div class="form-group"><label>Начало</label><input id="ev-start" type="datetime-local" class="search-box"></div>
      <div class="form-group"><label>Место</label><input id="ev-loc" class="search-box"></div>
      <button class="btn btn-primary" style="width:auto" onclick="createEvent()">Сохранить</button>
    </div>`;
  }
  if (!items || !items.length) {
    html += '<div class="empty"><i class="fas fa-star"></i><p>Нет событий</p></div>';
    el.innerHTML = html; return;
  }
  html += items.map(e => `
    <div class="card">
      <div style="font-weight:600">${e.title}</div>
      <div style="font-size:13px;color:var(--text-secondary);margin:4px 0">${e.description || ''}</div>
      <div style="font-size:13px"><i class="fas fa-clock"></i> ${new Date(e.start_at).toLocaleString('ru')}</div>
      ${e.location ? `<div style="font-size:13px"><i class="fas fa-map-marker-alt"></i> ${e.location}</div>` : ''}
    </div>
  `).join('');
  el.innerHTML = html;
}
window.createEvent = async function() {
  try {
    const start = $('#ev-start').value;
    if (!start) { alert('Укажите дату'); return; }
    await api('/api/events/', { method:'POST', body: JSON.stringify({
      title: $('#ev-title').value,
      description: $('#ev-desc').value || null,
      start_at: new Date(start).toISOString(),
      location: $('#ev-loc').value || null
    })});
    navigate('events');
  } catch(e) { alert(e.message); }
};

/* ========== СБОРЫ ДЕНЕГ ========== */
async function renderCollections(el) {
  const items = await api('/api/collections/');
  const canCreate = canManageClass();

  let html = '';
  if (canCreate) {
    html += `
      <div class="card">
        <div class="card-title"><i class="fas fa-plus-circle"></i> Создать сбор (только староста)</div>
        <div class="form-group"><label>Название</label><input id="col-title" class="search-box" placeholder="На экскурсию"></div>
        <div class="form-group"><label>Описание</label><input id="col-desc" class="search-box" placeholder="Необязательно"></div>
        <div class="form-group"><label>Сколько всего нужно собрать (₽)</label><input id="col-target" class="search-box" type="number" min="1" placeholder="5000"></div>
        <div class="form-group"><label>Сумма с одного человека (₽)</label><input id="col-suggested" class="search-box" type="number" min="1" placeholder="250"></div>
        <div class="form-group"><label>Ваши реквизиты</label><textarea id="col-details" class="search-box" rows="3" placeholder="Сбер: 4276... Получатель: Иван"></textarea></div>
        <button class="btn btn-primary" style="width:auto" onclick="createCollection()">Создать сбор</button>
      </div>
    `;
  }

  if (!items || !items.length) {
    html += '<div class="empty"><i class="fas fa-hand-holding-usd"></i><p>Активных сборов нет</p></div>';
    el.innerHTML = html;
    return;
  }

  html += items.map(c => {
    const statusLabel = { active: 'Идёт сбор', completed: 'Собрано 100%', closed: 'Закрыт' }[c.status] || c.status;
    const statusColor = c.status === 'completed' ? 'var(--success)' : (c.status === 'closed' ? 'var(--text-secondary)' : 'var(--primary)');
    return `
      <div class="card" style="border-left:4px solid ${statusColor}">
        <div style="display:flex;justify-content:space-between;align-items:start;flex-wrap:wrap;gap:8px">
          <div>
            <div style="font-weight:700;font-size:16px">${c.title}</div>
            <div style="font-size:13px;color:var(--text-secondary);margin:4px 0">${c.description || ''}</div>
            <div style="font-size:13px">Создал: ${c.creator_name || '—'}</div>
          </div>
          <span class="status-badge" style="background:${statusColor}22;color:${statusColor}">${statusLabel}</span>
        </div>

        <div style="margin:16px 0">
          <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px">
            <span>Собрано: <strong>${c.collected_amount} ₽</strong> из ${c.target_amount} ₽</span>
            <span><strong>${c.progress_percent}%</strong></span>
          </div>
          <div style="background:var(--bg);border-radius:10px;height:14px;overflow:hidden">
            <div style="background:linear-gradient(90deg,var(--primary),var(--success));height:100%;width:${c.progress_percent}%;transition:width 0.4s"></div>
          </div>
          <div style="font-size:12px;color:var(--text-secondary);margin-top:4px">
            Рекомендуемо с человека: ${c.suggested_amount} ₽ · Одобрено: ${c.approved_count}
          </div>
        </div>

        <div style="display:flex;flex-wrap:wrap;gap:8px">
          ${c.status === 'active' && c.user_payment_status !== 'approved' && c.user_payment_status !== 'pending' ? `
            <button class="btn btn-primary" style="width:auto;padding:8px 16px;font-size:13px" onclick="openPayForm(${c.id})">Оплатить</button>
          ` : ''}
          ${c.user_payment_status === 'pending' ? `<span class="status-badge status-in_progress">Заявка на проверке</span>` : ''}
          ${c.user_payment_status === 'approved' ? `<span class="status-badge status-done">Вы оплатили ✓</span>` : ''}
          ${c.user_payment_status === 'rejected' ? `<span class="status-badge status-overdue">Отклонено — можно снова</span>
            <button class="btn btn-primary" style="width:auto;padding:8px 16px;font-size:13px" onclick="openPayForm(${c.id})">Оплатить снова</button>` : ''}
          <button class="btn" style="width:auto;padding:8px 16px;font-size:13px;background:var(--bg)" onclick="viewCollection(${c.id})">Подробнее</button>
        </div>
        <div id="pay-form-${c.id}" style="display:none;margin-top:16px;padding-top:16px;border-top:1px solid var(--border)"></div>
        <div id="col-detail-${c.id}" style="display:none;margin-top:16px"></div>
      </div>
    `;
  }).join('');

  el.innerHTML = html;
}

window.createCollection = async function() {
  const title = $('#col-title').value.trim();
  const target = parseFloat($('#col-target').value);
  const suggested = parseFloat($('#col-suggested').value);
  const details = $('#col-details').value.trim();
  if (!title || !target || !suggested || !details) {
    alert('Заполните все обязательные поля');
    return;
  }
  try {
    await api('/api/collections/', {
      method: 'POST',
      body: JSON.stringify({
        title,
        description: $('#col-desc').value.trim() || null,
        target_amount: target,
        suggested_amount: suggested,
        payment_details: details
      })
    });
    alert('Сбор создан! Одноклассники получили уведомление.');
    navigate('collections');
  } catch (e) { alert(e.message); }
};

window.openPayForm = async function(collectionId) {
  const box = $(`#pay-form-${collectionId}`);
  if (box.style.display === 'block') { box.style.display = 'none'; return; }

  // Получаем сбор с реквизитами (после нажатия они станут доступны через API, но для UX подгрузим)
  let col;
  try {
    col = await api(`/api/collections/${collectionId}`);
  } catch (e) { alert(e.message); return; }

  // Если реквизиты ещё не видны — сначала создаём «намерение», но в нашей логике
  // реквизиты показываются после любой заявки. Покажем suggested и попросим сумму.
  box.style.display = 'block';
  box.innerHTML = `
    <div style="background:var(--bg);padding:12px;border-radius:10px;margin-bottom:12px;font-size:13px;white-space:pre-line">
      <strong>Реквизиты для перевода:</strong><br>
      ${col.payment_details || 'Нажмите «Отправить заявку» — после этого реквизиты появятся у старосты, а вам придёт подтверждение. Или посмотрите в уведомлении.'}
      ${!col.payment_details ? '<br><br><em>Реквизиты отображаются после создания заявки или у старосты.</em>' : ''}
    </div>
    <div class="form-group"><label>Сумма (₽) — можно больше ${col.suggested_amount}</label>
      <input id="pay-amount-${collectionId}" class="search-box" type="number" min="1" value="${col.suggested_amount}">
    </div>
    <div class="form-group"><label>Ссылка на скриншот чека / описание</label>
      <input id="pay-screenshot-${collectionId}" class="search-box" placeholder="https://... или текст">
    </div>
    <div class="form-group"><label>Комментарий</label>
      <input id="pay-comment-${collectionId}" class="search-box" placeholder="Необязательно">
    </div>
    <button class="btn btn-primary" style="width:auto" onclick="submitCollectionPay(${collectionId})">Отправить заявку</button>
  `;

  // Если реквизитов нет — запросим их через «пустую» логику: после submit они появятся.
  // Для удобства сразу покажем suggested и попросим загрузить чек.
};

window.submitCollectionPay = async function(collectionId) {
  const amount = parseFloat($(`#pay-amount-${collectionId}`).value);
  if (!amount || amount <= 0) { alert('Укажите сумму'); return; }
  try {
    await api(`/api/collections/${collectionId}/pay`, {
      method: 'POST',
      body: JSON.stringify({
        amount,
        screenshot_url: $(`#pay-screenshot-${collectionId}`).value || null,
        comment: $(`#pay-comment-${collectionId}`).value || null
      })
    });
    alert('Заявка отправлена старосте на проверку!');
    navigate('collections');
  } catch (e) { alert(e.message); }
};

window.viewCollection = async function(collectionId) {
  const box = $(`#col-detail-${collectionId}`);
  if (box.style.display === 'block') { box.style.display = 'none'; return; }

  const [col, payments] = await Promise.all([
    api(`/api/collections/${collectionId}`),
    api(`/api/collections/${collectionId}/payments`)
  ]);

  const isManager = currentUser && (
    currentUser.id === col.created_by ||
    canManageClass()
  );

  let payHtml = (payments || []).map(p => `
    <div style="padding:10px 0;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
      <div>
        <strong>${p.display_name || p.username}</strong>
        ${p.is_overpay ? '<span class="pro-badge" style="margin-left:6px">Больше суммы</span>' : ''}
        <div style="font-size:13px">${p.amount} ₽ · ${p.status}
          ${p.screenshot_url ? ` · <a href="${p.screenshot_url}" target="_blank">чек</a>` : ''}
        </div>
        ${p.comment ? `<div style="font-size:12px;color:var(--text-secondary)">${p.comment}</div>` : ''}
      </div>
      ${isManager && p.status === 'pending' ? `
        <div style="display:flex;gap:6px">
          <button class="btn btn-primary" style="width:auto;padding:6px 12px;font-size:12px" onclick="approveColPay(${collectionId},${p.id})">Одобрить</button>
          <button class="btn" style="width:auto;padding:6px 12px;font-size:12px;background:var(--danger);color:#fff" onclick="rejectColPay(${collectionId},${p.id})">Отклонить</button>
        </div>
      ` : ''}
    </div>
  `).join('') || '<p class="empty">Пока нет платежей</p>';

  box.style.display = 'block';
  box.innerHTML = `
    <div class="card-title">Платежи по сбору</div>
    ${col.payment_details ? `<div style="font-size:13px;background:var(--bg);padding:10px;border-radius:8px;margin-bottom:12px;white-space:pre-line"><strong>Реквизиты:</strong><br>${col.payment_details}</div>` : ''}
    ${payHtml}
    ${isManager && col.status === 'active' ? `
      <button class="btn" style="width:auto;margin-top:12px;background:var(--bg)" onclick="closeCollection(${collectionId})">Закрыть сбор</button>
    ` : ''}
  `;
};

window.approveColPay = async function(collectionId, paymentId) {
  try {
    const res = await api(`/api/collections/${collectionId}/payments/${paymentId}/approve`, { method: 'POST' });
    alert(`Одобрено! Прогресс: ${res.progress_percent}%`);
    navigate('collections');
  } catch (e) { alert(e.message); }
};

window.rejectColPay = async function(collectionId, paymentId) {
  const reason = prompt('Причина отказа:') || 'Чек не подтверждён';
  try {
    await api(`/api/collections/${collectionId}/payments/${paymentId}/reject?reason=${encodeURIComponent(reason)}`, { method: 'POST' });
    navigate('collections');
  } catch (e) { alert(e.message); }
};

window.closeCollection = async function(collectionId) {
  if (!confirm('Закрыть сбор?')) return;
  try {
    await api(`/api/collections/${collectionId}/close`, { method: 'POST' });
    navigate('collections');
  } catch (e) { alert(e.message); }
};

async function renderFiles(el) {
  let items = [];
  try { items = await api('/api/files/') || []; }
  catch (e) {
    el.innerHTML = `<div class="empty"><i class="fas fa-folder"></i><p>${e.message || 'Ошибка'}</p></div>`;
    return;
  }
  let html = `
    <div class="card">
      <div class="card-title"><i class="fas fa-upload"></i> Загрузить файл</div>
      <div class="form-group"><label>Категория</label>
        <select id="file-cat" class="search-box">
          <option value="study">Учёба</option>
          <option value="documents">Документы</option>
          <option value="photos">Фото</option>
          <option value="other">Другое</option>
        </select>
      </div>
      <input type="file" id="file-upload" class="search-box">
      <button class="btn btn-primary" style="width:auto;margin-top:8px" onclick="uploadClassFile()">Загрузить</button>
    </div>`;
  if (!items.length) {
    html += '<div class="empty"><i class="fas fa-folder-open"></i><p>Файлов пока нет</p></div>';
    el.innerHTML = html; return;
  }
  const cats = { study: 'Учёба', documents: 'Документы', photos: 'Фото', other: 'Другое' };
  html += items.map(f => `
    <div class="card" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
      <div style="font-size:24px;color:var(--primary)"><i class="fas fa-file"></i></div>
      <div style="flex:1;min-width:120px">
        <div style="font-weight:600">${(f.original_name || f.filename || '').replace(/</g,'&lt;')}</div>
        <div style="font-size:12px;color:var(--text-secondary)">${cats[f.category] || f.category || ''}</div>
      </div>
      <a class="btn btn-primary" style="width:auto;padding:8px 14px;font-size:13px;text-decoration:none" href="${f.file_url}" target="_blank">Открыть</a>
    </div>
  `).join('');
  el.innerHTML = html;
}
window.uploadClassFile = async function() {
  const f = $('#file-upload') && $('#file-upload').files && $('#file-upload').files[0];
  if (!f) { alert('Выберите файл'); return; }
  const fd = new FormData();
  fd.append('file', f);
  fd.append('category', ($('#file-cat') && $('#file-cat').value) || 'other');
  try {
    const res = await fetch('/api/files/upload', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + token },
      body: fd
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'Ошибка загрузки');
    navigate('files');
  } catch (e) { alert(e.message); }
};

async function renderNotifications(el) {
  const items = await api('/api/notifications/');
  if (!items || !items.length) {
    el.innerHTML = '<div class="empty"><i class="fas fa-bell"></i><p>Нет уведомлений</p></div>';
    return;
  }
  el.innerHTML = items.map(n => `
    <div class="card" style="${n.is_read ? 'opacity:0.6' : ''}">
      <strong>${n.title}</strong>
      <p style="font-size:13px;margin:4px 0">${n.body || ''}</p>
      <small style="color:var(--text-secondary)">${new Date(n.created_at).toLocaleString('ru')}</small>
    </div>
  `).join('');
}

async function renderPro(el) {
  const [plans, status, details, coinPkgs, coinBal] = await Promise.all([
    api('/api/pro/plans'),
    api('/api/pro/status'),
    api('/api/pro/payment-details'),
    api('/api/coins/packages').catch(() => []),
    api('/api/coins/balance').catch(() => ({balance:0})),
  ]);
  el.innerHTML = `
    <div class="pro-hero">
      <h2><i class="fas fa-crown"></i> ClassMate PRO</h2>
      <p>Расширенные возможности для учёбы и общения</p>
      ${status.active ? `<p style="margin-top:12px;font-weight:600">Активен до ${new Date(status.pro_until).toLocaleDateString('ru')}</p>` : ''}
    </div>
    <div class="card">
      <div class="card-title">Преимущества PRO</div>
      <ul class="pro-features">
        <li><i class="fas fa-check"></i> Дополнительные темы и кастомизация</li>
        <li><i class="fas fa-check"></i> Расширенные реакции и оформление сообщений</li>
        <li><i class="fas fa-check"></i> Больше места для файлов</li>
        <li><i class="fas fa-check"></i> Статистика домашних заданий</li>
        <li><i class="fas fa-check"></i> Приоритетные уведомления</li>
        <li><i class="fas fa-check"></i> PRO-бейдж в профиле</li>
      </ul>
    </div>
    <div class="card">
      <div class="card-title">Монеты (баланс: ${coinBal.balance||0})</div>
      <p style="font-size:13px;margin-bottom:8px">1 монета ≈ 1 смн. Минимум покупки: 10. Купленные монеты нельзя вывести.</p>
      <div class="home-grid">
        ${(coinPkgs||[]).map(p => `
          <div class="card" style="margin:0;text-align:center">
            <div style="font-size:22px;font-weight:700">${p.amount} 🪙</div>
            <div style="color:var(--primary)">${p.price_smn} смн</div>
            <button class="btn btn-primary" style="width:auto;margin-top:8px;padding:6px 12px;font-size:13px" onclick="buyCoins(${p.amount})">Купить</button>
          </div>`).join('')}
      </div>
      <div class="form-group" style="margin-top:12px">
        <label>Или своё количество (≥10)</label>
        <input type="number" id="custom-coins" class="search-box" min="10" value="10">
        <button class="btn btn-primary" style="width:auto" onclick="buyCoins(parseInt(($('#custom-coins')||{}).value||10,10))">Купить</button>
      </div>
    </div>
    <div class="grid">
      ${(plans||[]).map(p => `
        <div class="card" style="text-align:center">
          <div style="font-weight:700;font-size:18px">${p.name}</div>
          <div style="font-size:28px;color:var(--primary);margin:12px 0">${p.price} смн</div>
          <div style="color:var(--text-secondary);font-size:13px;margin-bottom:16px">${p.description || p.duration_days + ' дней'}</div>
          <button class="btn btn-primary" onclick="startPayment(${p.id}, ${Number(p.price)})">Оплатить PRO</button>
        </div>
      `).join('')}
    </div>
    <div class="card" id="payment-form" style="display:none">
      <div class="card-title">Оплата</div>
      <p style="white-space:pre-line;font-size:14px;margin-bottom:12px">${details.details}</p>
      <p style="font-size:13px;color:var(--text-secondary);margin-bottom:12px">${details.instruction}</p>
      <p>Ваш User ID: <strong>${details.user_id}</strong></p>
      <div class="form-group" style="margin-top:12px">
        <label>Загрузите скриншот чека</label>
        <input type="file" id="screenshot-file" accept="image/*" class="search-box">
      </div>
      <div class="form-group">
        <label>Или ссылка / комментарий</label>
        <input type="text" id="screenshot-url" placeholder="https://... или текст">
      </div>
      <button class="btn btn-primary" id="submit-payment">Отправить на проверку</button>
    </div>
  `;
}

let selectedPlanId = null, selectedAmount = null;
let selectedCoins = 0;
window.buyCoins = async function(amount) {
  amount = parseInt(amount, 10);
  if (!amount || amount < 10) { alert('Минимум 10 монет'); return; }
  selectedCoins = amount;
  let form = document.getElementById('coin-payment-form');
  if (!form) {
    const wrap = document.createElement('div');
    wrap.innerHTML = `<div class="card" id="coin-payment-form" style="margin-top:12px">
      <div class="card-title">Оплата монет</div>
      <p id="coin-pay-amount" style="font-weight:600;margin-bottom:8px"></p>
      <div id="coin-pay-details" style="background:var(--bg);padding:12px;border-radius:10px;font-size:13px;margin-bottom:12px;white-space:pre-wrap"></div>
      <div class="form-group"><label>Скриншот чека с устройства</label>
        <input type="file" id="coin-screenshot-file" accept="image/*" class="search-box"></div>
      <div class="form-group"><label>Или ссылка / комментарий</label>
        <input type="text" id="coin-screenshot-url" class="search-box" placeholder="https://... или текст"></div>
      <button class="btn btn-primary" style="width:auto" onclick="submitCoinPayment()">Отправить на проверку</button>
      <button class="btn" style="width:auto;background:var(--bg);margin-left:8px" onclick="document.getElementById('coin-payment-form').style.display='none'">Отмена</button>
    </div>`;
    const proPage = document.getElementById('page-content');
    if (proPage) proPage.appendChild(wrap.firstChild);
    form = document.getElementById('coin-payment-form');
  }
  form.style.display = 'block';
  const amt = document.getElementById('coin-pay-amount');
  if (amt) amt.textContent = selectedCoins + ' монет ≈ ' + selectedCoins + ' смн';
  try {
    const details = await api('/api/pro/payment-details');
    const box = document.getElementById('coin-pay-details');
    if (box) box.textContent = (details && (details.details || details.payment_details || details.text)) || 'Реквизиты уточните у администратора.';
  } catch(e) {
    const box = document.getElementById('coin-pay-details');
    if (box) box.textContent = 'Оплатите по реквизитам из раздела PRO и прикрепите чек.';
  }
  form.scrollIntoView({ behavior: 'smooth' });
};
window.submitCoinPayment = async function() {
  if (!selectedCoins || selectedCoins < 10) { alert('Выберите пакет'); return; }
  try {
    let screenshot_url = (document.getElementById('coin-screenshot-url') && document.getElementById('coin-screenshot-url').value) || null;
    const fi = document.getElementById('coin-screenshot-file');
    const f = fi && fi.files && fi.files[0];
    if (f) {
      const fd = new FormData();
      fd.append('file', f);
      const up = await fetch('/api/uploads/media', { method:'POST', headers:{ Authorization:'Bearer '+token }, body:fd });
      const data = await up.json().catch(()=>({}));
      if (!up.ok) throw new Error(data.detail || 'Ошибка загрузки чека');
      screenshot_url = data.url;
    }
    if (!screenshot_url) { alert('Загрузите скриншот чека или укажите комментарий'); return; }
    const r = await api('/api/coins/buy', { method:'POST', body: JSON.stringify({ coins: selectedCoins, screenshot_url }) });
    alert(r.message || 'Заявка отправлена. Ждите одобрения админа.');
    const form = document.getElementById('coin-payment-form');
    if (form) form.style.display = 'none';
    navigate('pro');
  } catch(e) { alert(e.message); }
};
window.startPayment = function(planId, amount) {
  selectedPlanId = planId;
  selectedAmount = Number(amount);
  const form = $('#payment-form');
  if (!form) { alert('Форма оплаты не найдена'); return; }
  form.style.display = 'block';
  form.scrollIntoView({ behavior: 'smooth' });
};

document.addEventListener('click', async (e) => {
  if (e.target && e.target.id === 'submit-payment') {
    try {
      if (!selectedPlanId) { alert('Сначала выберите тариф'); return; }
      let screenshot_url = ($('#screenshot-url') && $('#screenshot-url').value) || null;
      const fileInput = $('#screenshot-file');
      const f = fileInput && fileInput.files && fileInput.files[0];
      if (f) {
        const fd = new FormData();
        fd.append('file', f);
        const up = await fetch('/api/uploads/image', {
          method: 'POST',
          headers: { Authorization: 'Bearer ' + token },
          body: fd
        });
        const data = await up.json().catch(() => ({}));
        if (!up.ok) throw new Error(data.detail || 'Ошибка загрузки чека');
        screenshot_url = data.url;
      }
      if (!screenshot_url) {
        alert('Загрузите скриншот чека или укажите комментарий');
        return;
      }
      await api('/api/pro/payments', {
        method: 'POST',
        body: JSON.stringify({
          plan_id: selectedPlanId,
          amount: selectedAmount,
          screenshot_url: screenshot_url
        })
      });
      alert('Платёж отправлен на проверку. Ожидайте подтверждения администратора.');
      navigate('pro');
    } catch (err) { alert(err.message); }
  }
});

async function renderProfile(el) {
  const role = userRole();
  let stats = { followers_count: currentUser.followers_count || 0, following_count: currentUser.following_count || 0, posts_count: currentUser.posts_count || 0 };
  let posts = [];
  try {
    const data = await api('/api/reels/user/' + currentUser.id);
    if (data.user) { stats = data.user; posts = data.posts || []; }
  } catch (e) {}
  const av = currentUser.avatar_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(currentUser.display_name||'?')}&background=4f46e5&color=fff&size=120`;
  const roleLabel = {admin:'Администратор',starosta:'Староста',moderator:'Модератор',student:'Ученик'}[role] || role;
  el.innerHTML = `
    <div class="card" style="text-align:center">
      <img src="${av}" style="width:96px;height:96px;border-radius:50%;object-fit:cover;margin-bottom:12px">
      <h3>${currentUser.display_name||''} ${currentUser.is_pro ? '<span class="pro-badge">PRO</span>' : ''}</h3>
      <p style="color:var(--text-secondary)">@${currentUser.username||''}</p>
      <p style="font-size:13px;margin-top:4px">${roleLabel}</p>
      <div style="display:flex;justify-content:center;gap:28px;margin:16px 0;font-size:14px">
        <div><strong>${stats.posts_count||0}</strong><br><span style="color:var(--text-secondary);font-size:12px">публикаций</span></div>
        <div><strong>${stats.followers_count||0}</strong><br><span style="color:var(--text-secondary);font-size:12px">подписчиков</span></div>
        <div><strong>${stats.following_count||0}</strong><br><span style="color:var(--text-secondary);font-size:12px">подписок</span></div>
      </div>
      <button class="btn" style="width:auto;background:var(--bg)" onclick="navigate('settings')">⚙️ Настройки</button>
    </div>
    <div class="card-title" style="margin:12px 0 8px">Публикации</div>
    <div class="home-grid">
      ${(posts||[]).map(r => `
        <div class="card" style="margin:0;padding:0;overflow:hidden;cursor:pointer;aspect-ratio:1" onclick="openReelViewerById(${r.id})">
          ${r.media_type==='video'
            ? `<video src="${r.media_url}" style="width:100%;height:100%;object-fit:cover" muted></video>`
            : `<img src="${r.media_url}" style="width:100%;height:100%;object-fit:cover" onerror="this.parentElement.style.display='none'">`}
        </div>`).join('') || '<p class="empty">Нет публикаций</p>'}
    </div>
  `;
}

async function renderSettings(el) {
  const av = currentUser.avatar_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(currentUser.display_name||'?')}&background=4f46e5&color=fff&size=120`;
  el.innerHTML = `
    <div class="card" style="text-align:center">
      <img id="profile-av" src="${av}" style="width:80px;height:80px;border-radius:50%;object-fit:cover;margin-bottom:8px">
      <p>@${currentUser.username||''}</p>
    </div>
    <div class="card">
      <div class="card-title">Аватар</div>
      <input type="file" id="avatar-file" accept="image/*" capture="environment" class="search-box">
      <button class="btn btn-primary" style="width:auto" onclick="uploadAvatar()">Сохранить аватар</button>
    </div>
    <div class="card">
      <div class="card-title">Имя</div>
      <input class="search-box" id="new-display" value="${(currentUser.display_name||'').replace(/"/g,'&quot;')}">
      <button class="btn btn-primary" style="width:auto" onclick="updateDisplayName()">Сохранить имя</button>
    </div>
    <div class="card">
      <div class="card-title">Статус</div>
      <input class="search-box" id="new-status" value="${(currentUser.status||'').replace(/"/g,'&quot;')}" placeholder="Ваш статус">
      <button class="btn btn-primary" style="width:auto" onclick="updateStatus()">Сохранить статус</button>
    </div>
    <div class="card">
      <div class="card-title">Монеты 🪙</div>
      <p>Баланс: <strong id="coin-bal">...</strong></p>
      <button class="btn btn-primary" style="width:auto;margin:4px" onclick="navigate('pro')">Купить монеты / PRO</button>
      <button class="btn" style="width:auto;margin:4px;background:var(--bg)" onclick="showWithdraw()">Вывод</button>
    </div>
    <div class="card">
      <div class="card-title">Смена пароля</div>
      <input type="password" class="search-box" id="old-pass" placeholder="Старый пароль">
      <input type="password" class="search-box" id="new-pass" placeholder="Новый пароль (мин. 6)">
      <button class="btn btn-primary" style="width:auto" onclick="changePassword()">Сменить пароль</button>
    </div>
  `;
  try {
    const b = await api('/api/coins/balance');
    const elb = $('#coin-bal');
    if (elb) elb.textContent = b.balance + ' (вывод: ' + b.withdrawable + ')';
  } catch(x) {}
}
(async () => { try { const b = await api('/api/coins/balance'); const el = $('#coin-bal'); if (el) el.textContent = b.balance + ' (вывод: ' + b.withdrawable + ')'; } catch(x){} })();
window.showWithdraw = async function() {
  const b = await api('/api/coins/balance');
  const coins = prompt('Сколько монет вывести? (мин 500, доступно ' + b.withdrawable + ')');
  if (!coins) return;
  const card = prompt('Номер карты:');
  const bank = prompt('Банк:');
  if (!card || !bank) return;
  try {
    const r = await api('/api/coins/withdraw', { method:'POST', body: JSON.stringify({ coins: parseInt(coins,10), card_number: card, bank_name: bank }) });
    alert('Заявка на ' + r.amount_smn + ' смн отправлена');
  } catch(e) { alert(e.message); }
};
window.uploadAvatar = async function() {
  const f = $('#avatar-file') && $('#avatar-file').files && $('#avatar-file').files[0];
  if (!f) { alert('Выберите фото'); return; }
  const fd = new FormData(); fd.append('file', f);
  try {
    const res = await fetch('/api/uploads/avatar', { method:'POST', headers:{Authorization:'Bearer '+token}, body:fd });
    const data = await res.json().catch(()=>({}));
    if (!res.ok) throw new Error(data.detail || 'Ошибка');
    await loadUser(); navigate('profile');
  } catch(e) { alert(e.message); }
};
window.updateDisplayName = async function() {
  const v = ($('#new-display') && $('#new-display').value || '').trim();
  if (!v) return;
  await api('/api/users/me', { method:'PUT', body: JSON.stringify({ display_name: v }) });
  await loadUser(); navigate('profile');
};
window.updateStatus = async function() {
  await api('/api/users/me', { method:'PUT', body: JSON.stringify({ status: ($('#new-status')||{}).value || '' }) });
  await loadUser(); navigate('profile');
};
window.changePassword = async function() {
  const oldp = ($('#old-pass')||{}).value, newp = ($('#new-pass')||{}).value;
  if (!oldp || !newp || newp.length < 6) { alert('Заполните поля (новый пароль от 6 символов)'); return; }
  try {
    await api('/api/auth/password', { method:'PUT', body: JSON.stringify({ old_password: oldp, new_password: newp }) });
    alert('Пароль изменён');
  } catch(e) { alert(e.message); }
}

window.updateStatus = async function() {
  await api('/api/users/me', { method: 'PUT', body: JSON.stringify({ status: $('#new-status').value }) });
  await loadUser();
  navigate('profile');
};

async function renderAdmin(el) {
  if ((currentUser.role || '').toLowerCase() !== 'admin') {
    el.innerHTML = '<div class="empty"><p>Доступ только для администратора</p></div>';
    return;
  }
  let stats = {}, payments = [], plans = [], classes = [], users = [];
  try {
    [stats, payments, plans, classes, users] = await Promise.all([
      api('/api/admin/stats').catch(() => ({})),
      api('/api/admin/payments?status=pending').catch(() => []),
      api('/api/admin/plans').catch(() => []),
      api('/api/admin/classes').catch(() => []),
      api('/api/admin/users').catch(() => []),
    ]);
  } catch (e) {}
  el.innerHTML = `
    <div class="grid">
      <div class="card stat-card"><div class="value">${stats.users||0}</div><div class="label">Пользователей</div></div>
      <div class="card stat-card"><div class="value">${stats.pro_users||0}</div><div class="label">PRO</div></div>
      <div class="card stat-card"><div class="value">${stats.pending_payments||0}</div><div class="label">Заявки</div></div>
      <div class="card stat-card"><div class="value">${(classes||[]).length}</div><div class="label">Классов</div></div>
    </div>

    <div class="card">
      <div class="card-title">1. Создать класс</div>
      <input id="new-class-name" class="search-box" placeholder="Имя класса">
      <input id="new-class-code" class="search-box" placeholder="Код приглашения">
      <button class="btn btn-primary" style="width:auto" onclick="adminCreateClass()">Создать</button>
    </div>

    <div class="card">
      <div class="card-title">2. Список пользователей</div>
      <input class="search-box" placeholder="Поиск..." oninput="filterAdminUsers(this.value)">
      <div id="admin-users-list" style="max-height:280px;overflow-y:auto">
        ${(users||[]).map(u => `
          <div class="admin-user-row" data-search="${(u.username+' '+u.display_name).toLowerCase()}" style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border);gap:8px;flex-wrap:wrap">
            <div>
              <strong>${u.display_name||''}</strong> @${u.username}
              <span style="font-size:12px;color:var(--text-secondary)"> ${u.role||''}</span>
              ${u.is_pro?'<span class="pro-badge">PRO</span>':''}
            </div>
            <div style="display:flex;gap:6px">
              <button class="btn" style="width:auto;padding:6px 10px;font-size:12px;background:var(--pro);color:#000" onclick="adminGrantPro(${u.id})">PRO</button>
              <button class="btn" style="width:auto;padding:6px 10px;font-size:12px;background:var(--danger);color:#fff" onclick="adminDeleteUser(${u.id})">Удалить</button>
            </div>
          </div>`).join('') || '<p class="empty">Нет пользователей</p>'}
      </div>
    </div>

    <div class="card">
      <div class="card-title">3. Рассылка</div>
      <input id="broadcast-title" class="search-box" placeholder="Заголовок">
      <textarea id="broadcast-body" class="search-box" rows="3" placeholder="Текст всем пользователям"></textarea>
      <button class="btn btn-primary" style="width:auto" onclick="adminBroadcast()">Отправить всем</button>
    </div>

    <div class="card">
      <div class="card-title">4. Цены тарифов PRO (смн)</div>
      ${(plans||[]).map(p => `
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap">
          <span style="min-width:120px;font-weight:600">${p.name}</span>
          <input id="plan-price-${p.id}" type="number" step="0.01" value="${p.price}" class="search-box" style="width:100px;margin:0">
          <span>смн / ${p.duration_days} дн.</span>
          <button class="btn btn-primary" style="width:auto;padding:8px 12px" onclick="adminUpdatePlan(${p.id})">Сохранить</button>
        </div>`).join('') || '<p class="empty">Нет тарифов</p>'}
    </div>

    <div class="card">
      <div class="card-title">5. Instagram в рекламе после регистрации</div>
      <input id="social-ig" class="search-box" placeholder="https://instagram.com/..." value="">
      <button class="btn btn-primary" style="width:auto" onclick="adminSaveSocial()">Сохранить ссылку</button>
    </div>

    <div class="card">
      <div class="card-title">6. Все классы</div>
      <div class="home-grid">
        ${(classes||[]).map(c => `
          <div class="card" style="margin:0">
            <div style="font-weight:700">${c.name}</div>
            <div style="font-size:12px;color:var(--text-secondary)">Код: <strong>${c.invite_code}</strong></div>
            <div style="font-size:13px;margin-top:6px">Учеников: ${c.members||0}</div>
          </div>`).join('') || '<p class="empty">Нет классов</p>'}
      </div>
    </div>

    <div class="card">
      <div class="card-title">7. Очистка кеша</div>
      <p style="font-size:13px;color:var(--text-secondary);margin-bottom:8px">Очистить локальный кеш браузера приложения у вас</p>
      <button class="btn btn-primary" style="width:auto" onclick="adminClearCache()">Очистить кеш</button>
    </div>
    <div class="card" style="border:2px solid var(--danger)">
      <div class="card-title" style="color:var(--danger)">⚠ Сброс системы</div>
      <p style="font-size:13px;margin-bottom:8px">Удалит все классы, чаты, ДЗ, Reels, заявки. Останется только аккаунт <strong>admin</strong>. Действие необратимо.</p>
      <button class="btn" style="width:auto;background:var(--danger);color:#fff" onclick="adminSystemReset()">Сбросить всё приложение</button>
    </div>

    <div class="card">
      <div class="card-title">8. Заявки на PRO</div>
      ${(payments||[]).length ? (payments||[]).map(p => `
        <div style="padding:12px 0;border-bottom:1px solid var(--border)">
          <strong>${p.username||p.user_id}</strong> — ${p.plan_name||''} — ${p.amount} смн
          ${p.screenshot_url ? `<div style="margin:6px 0"><a href="${p.screenshot_url}" target="_blank" rel="noopener">📎 Открыть чек</a></div>` : ''}
          <div style="margin-top:8px">
            <button class="btn btn-primary" style="width:auto;padding:6px 12px;margin-right:6px" onclick="approvePayment(${p.id})">Одобрить</button>
            <button class="btn" style="width:auto;padding:6px 12px;background:var(--danger);color:#fff" onclick="rejectPayment(${p.id})">Отклонить</button>
          </div>
        </div>`).join('') : '<p class="empty">Нет заявок</p>'}
    </div>

    <div class="card" id="coin-orders-box">
      <div class="card-title">8b. Заявки на монеты / вывод</div>
      <div id="admin-coin-orders"><button class="btn" style="width:auto;background:var(--bg)" onclick="loadAdminCoinOrders()">Загрузить</button></div>
    </div>
    <div class="card">
      <div class="card-title">10. Реквизиты оплаты</div>
      <textarea id="pay-details" class="search-box" rows="4" placeholder="Карта / номер / банк"></textarea>
      <button class="btn btn-primary" style="width:auto" onclick="adminSavePayDetails()">Сохранить реквизиты</button>
    </div>
  `;
  try {
    const cfg = await api('/api/admin/settings').catch(() => ({}));
    if (cfg.instagram_url && $('#social-ig')) $('#social-ig').value = cfg.instagram_url;
    if (cfg.payment_details && $('#pay-details')) $('#pay-details').value = cfg.payment_details;
  } catch(x) {}
}
window.filterAdminUsers = function(q) {
  q = (q||'').toLowerCase();
  $$('#admin-users-list .admin-user-row').forEach(r => {
    r.style.display = (r.dataset.search||'').includes(q) ? '' : 'none';
  });
};
window.adminGrantPro = async function(uid) {
  try { await api(`/api/admin/users/${uid}/grant-pro?days=30`, { method:'POST' }); alert('PRO выдан на 30 дней'); navigate('admin'); }
  catch(e){ alert(e.message); }
};
window.adminDeleteUser = async function(uid) {
  if (!confirm('Удалить пользователя?')) return;
  try { await api(`/api/admin/users/${uid}`, { method:'DELETE' }); navigate('admin'); }
  catch(e){ alert(e.message); }
};
window.adminBroadcast = async function() {
  const title = ($('#broadcast-title')||{}).value||'';
  const body = ($('#broadcast-body')||{}).value||'';
  if (!title && !body) return;
  try { await api('/api/admin/broadcast', { method:'POST', body: JSON.stringify({ title, body }) }); alert('Рассылка отправлена'); }
  catch(e){ alert(e.message); }
};
window.adminSaveSocial = async function() {
  const url = ($('#social-ig')||{}).value||'';
  try { await api('/api/admin/settings', { method:'PUT', body: JSON.stringify({ instagram_url: url }) }); alert('Сохранено'); }
  catch(e){ alert(e.message); }
};
window.adminSavePayDetails = async function() {
  const payment_details = ($('#pay-details')||{}).value||'';
  try { await api('/api/admin/settings', { method:'PUT', body: JSON.stringify({ payment_details }) }); alert('Реквизиты сохранены'); }
  catch(e){ alert(e.message); }
};
window.loadAdminCoinOrders = async function() {
  try {
    const rows = await api('/api/coins/admin/orders?status=pending');
    const box = $('#admin-coin-orders');
    if (!box) return;
    box.innerHTML = (rows||[]).length ? (rows||[]).map(o => `
      <div style="padding:10px 0;border-bottom:1px solid var(--border)">
        <strong>${o.type}</strong> @${o.username} — ${o.coins} 🪙 / ${o.amount_smn} смн
        ${o.card_number ? `<div style="font-size:12px">${o.bank_name||''} ${o.card_number}</div>` : ''}
        <div style="margin-top:6px">
          <button class="btn btn-primary" style="width:auto;padding:6px 10px" onclick="approveCoinOrder(${o.id})">Одобрить</button>
          <button class="btn" style="width:auto;padding:6px 10px;background:var(--danger);color:#fff" onclick="rejectCoinOrder(${o.id})">Отклонить</button>
        </div>
      </div>`).join('') : '<p class="empty">Нет заявок</p>';
  } catch(e) { alert(e.message); }
};
window.approveCoinOrder = async function(id) {
  await api('/api/coins/admin/orders/' + id + '/approve', { method:'POST' });
  loadAdminCoinOrders();
};
window.rejectCoinOrder = async function(id) {
  await api('/api/coins/admin/orders/' + id + '/reject', { method:'POST' });
  loadAdminCoinOrders();
};
window.adminSystemReset = async function() {
  if (!confirm('Точно сбросить ВСЮ систему? Классы, чаты, ученики, Reels — всё удалится. Останется только admin.')) return;
  if (!confirm('Последнее предупреждение. Это нельзя отменить. Продолжить?')) return;
  try {
    const r = await api('/api/admin/system-reset?confirm=RESET', { method: 'POST' });
    alert((r && r.message) || 'Система сброшена');
    token = null;
    localStorage.removeItem('token');
    location.href = '/';
  } catch(e) { alert('Ошибка сброса: ' + e.message); }
};
window.adminClearCache = function() {
  const keep = token;
  localStorage.clear();
  if (keep) localStorage.setItem('token', keep);
  alert('Локальный кеш очищен');
  location.reload();
};

window.adminCreateClass = async function() {
  const name = ($('#new-class-name') && $('#new-class-name').value || '').trim();
  if (!name) { alert('Укажите название класса'); return; }
  const code = ($('#new-class-code') && $('#new-class-code').value || '').trim();
  const q = new URLSearchParams({ name });
  if (code) q.set('invite_code', code);
  try {
    const r = await api('/api/admin/classes?' + q.toString(), { method: 'POST' });
    alert(r.message || ('Класс создан. Староста: ' + r.starosta_username + ' / ' + r.starosta_password));
    navigate('admin');
  } catch(e) { alert(e.message); }
};
window.adminUpdatePlan = async function(id) {
  const price = parseFloat(($('#plan-price-' + id) || {}).value);
  if (isNaN(price)) return;
  await api(`/api/admin/plans/${id}?price=${price}`, { method: 'PUT' });
  alert('Цена сохранена (смн)');
};




let _reelFeedCache = [];
let _reelViewerIdx = 0;

window.openReelViewerById = function(id) {
  const idx = (_reelFeedCache || []).findIndex(r => r.id === id);
  if (idx >= 0) openReelViewer(idx);
  else navigate('reels');
};

window.openReelViewer = function(idx) {
  if (!_reelFeedCache || !_reelFeedCache.length) return;
  _reelViewerIdx = Math.max(0, Math.min(idx, _reelFeedCache.length - 1));
  let overlay = document.getElementById('reel-viewer');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'reel-viewer';
    overlay.className = 'reel-viewer';
    document.body.appendChild(overlay);
  }
  const r = _reelFeedCache[_reelViewerIdx];
  if (!r) return;
  const a = r.author || {};
  const av = a.avatar_url || ('https://ui-avatars.com/api/?name=' + encodeURIComponent(a.display_name || '?') + '&background=4f46e5&color=fff');
  const isVideo = r.media_type === 'video';
  const media = isVideo
    ? '<video class="reel-viewer-media" src="' + r.media_url + '" playsinline autoplay loop muted></video>'
    : '<img class="reel-viewer-media" src="' + r.media_url + '" alt="">';
  const role = userRole();
  const canPost = role !== 'admin' && role !== 'starosta';
  overlay.innerHTML =
    '<button type="button" class="reel-viewer-back" id="reel-back-btn"><i class="fas fa-arrow-left"></i></button>' +
    (canPost ? '<button type="button" class="reel-viewer-plus" id="reel-plus-btn"><i class="fas fa-plus"></i></button>' : '') +
    '<div class="reel-viewer-stage" id="reel-stage">' + media +
    '<div class="reel-viewer-ui">' +
    '<div class="reel-author" id="reel-author-tap" data-uid="' + (a.id || '') + '">' +
    '<img src="' + av + '" alt=""><div><strong>' + (a.display_name || '').replace(/</g,'&lt;') + '</strong> ' +
    (a.is_pro ? '<span class="pro-badge">PRO</span>' : '') +
    '<div style="font-size:12px;opacity:.85">@' + (a.username || '') + '</div></div></div>' +
    '<div class="reel-caption">' + (r.caption || '').replace(/</g,'&lt;') + '</div>' +
    '<div class="reel-actions-v">' +
    '<button type="button" class="' + (r.liked_by_me ? 'liked' : '') + '" id="reel-like-btn"><i class="fas fa-heart"></i><span>' + (r.likes_count||0) + '</span></button>' +
    '<button type="button" id="reel-cmt-btn"><i class="fas fa-comment"></i><span>' + (r.comments_count||0) + '</span></button>' +
    '<button type="button" id="reel-share-btn"><i class="fas fa-share"></i></button>' +
    ((a.id === (currentUser && currentUser.id) || userRole() === 'admin') ? '<button type="button" id="reel-del-btn"><i class="fas fa-trash"></i></button>' : '') +
    '</div></div>' +
    '<div id="reel-cmt-panel" class="reel-cmt-panel" style="display:none"></div>' +
    '</div>' +
    '<div class="reel-viewer-hint">двойной тап = лайк · свайп ↑↓</div>';

  overlay.style.display = 'flex';
  document.body.classList.add('reel-open');
  try { history.pushState({ reel: true, idx: _reelViewerIdx }, ''); } catch(e) {}
  try { api('/api/reels/' + r.id + '/view', { method: 'POST' }); } catch(e) {}

  document.getElementById('reel-back-btn').onclick = function() { closeReelViewer(); };
  const plus = document.getElementById('reel-plus-btn');
  if (plus) plus.onclick = function(e) { e.stopPropagation(); showCreateReelInViewer(); };
  document.getElementById('reel-author-tap').onclick = function(e) {
    e.stopPropagation();
    const uid = parseInt(this.getAttribute('data-uid'), 10);
    if (uid) { closeReelViewer(); openUserProfile(uid); }
  };
  document.getElementById('reel-like-btn').onclick = function(e) {
    e.stopPropagation();
    toggleReelLike(r.id, this).then(function() {
      const item = _reelFeedCache[_reelViewerIdx];
      if (item) { item.liked_by_me = this.classList.contains('liked'); }
    }.bind(this));
  };
  document.getElementById('reel-cmt-btn').onclick = function(e) {
    e.stopPropagation();
    toggleReelCommentsPanel(r.id);
  };
  document.getElementById('reel-share-btn').onclick = function(e) {
    e.stopPropagation();
    shareReel(r.id);
  };
  const delBtn = document.getElementById('reel-del-btn');
  if (delBtn) delBtn.onclick = async function(e) {
    e.stopPropagation();
    if (!confirm('Удалить публикацию?')) return;
    try {
      await api('/api/reels/' + r.id, { method: 'DELETE' });
      _reelFeedCache = _reelFeedCache.filter(function(x) { return x.id !== r.id; });
      if (!_reelFeedCache.length) { closeReelViewer(); navigate('reels'); return; }
      openReelViewer(Math.min(_reelViewerIdx, _reelFeedCache.length - 1));
    } catch (err) { alert(err.message); }
  };

  // double-tap like
  const stage = document.getElementById('reel-stage');
  let lastTap = 0;
  stage.onclick = function(e) {
    if (e.target.closest('button') || e.target.closest('a') || e.target.closest('.reel-author') || e.target.closest('.reel-cmt-panel')) return;
    const now = Date.now();
    if (now - lastTap < 300) {
      const btn = document.getElementById('reel-like-btn');
      toggleReelLike(r.id, btn);
      showLikeHeart(stage);
      lastTap = 0;
    } else {
      lastTap = now;
    }
  };

  let startY = 0;
  stage.ontouchstart = function(e) { startY = e.touches[0].clientY; };
  stage.ontouchend = function(e) {
    const dy = e.changedTouches[0].clientY - startY;
    if (dy < -50) openReelViewer(_reelViewerIdx + 1);
    else if (dy > 50) openReelViewer(_reelViewerIdx - 1);
  };
  stage.onwheel = function(e) {
    if (e.deltaY > 30) openReelViewer(_reelViewerIdx + 1);
    else if (e.deltaY < -30) openReelViewer(_reelViewerIdx - 1);
  };
};

window.showLikeHeart = function(stage) {
  const h = document.createElement('div');
  h.className = 'reel-heart-burst';
  h.innerHTML = '<i class="fas fa-heart"></i>';
  stage.appendChild(h);
  setTimeout(function() { h.remove(); }, 800);
};

window.toggleReelCommentsPanel = async function(reelId) {
  const panel = document.getElementById('reel-cmt-panel');
  if (!panel) return;
  if (panel.style.display === 'flex') {
    panel.style.display = 'none';
    return;
  }
  panel.style.display = 'flex';
  panel.innerHTML = '<div style="padding:12px;color:#fff">Загрузка...</div>';
  try {
    const rows = await api('/api/reels/' + reelId + '/comments');
    panel.innerHTML =
      '<div class="reel-cmt-list">' +
      (rows || []).map(function(c) {
        return '<div class="reel-cmt-item"><strong>' + ((c.author && c.author.display_name) || '') + '</strong>: ' +
          (c.text || '').replace(/</g,'&lt;') + '</div>';
      }).join('') +
      '</div>' +
      '<div class="reel-cmt-input-row">' +
      '<input type="text" id="reel-cmt-input" placeholder="Комментарий..." />' +
      '<button type="button" id="reel-cmt-send">OK</button></div>';
    document.getElementById('reel-cmt-send').onclick = async function() {
      const inp = document.getElementById('reel-cmt-input');
      const text = (inp && inp.value || '').trim();
      if (!text) return;
      try {
        await api('/api/reels/' + reelId + '/comments', { method: 'POST', body: JSON.stringify({ text: text }) });
        if (_reelFeedCache[_reelViewerIdx]) {
          _reelFeedCache[_reelViewerIdx].comments_count = (_reelFeedCache[_reelViewerIdx].comments_count || 0) + 1;
          const span = document.querySelector('#reel-cmt-btn span');
          if (span) span.textContent = _reelFeedCache[_reelViewerIdx].comments_count;
        }
        const panel = document.getElementById('reel-cmt-panel');
        if (panel) panel.style.display = 'none';
      } catch (e) { alert(e.message); }
    };
  } catch (e) {
    panel.innerHTML = '<div style="padding:12px;color:#fff">' + e.message + '</div>';
  }
};

window.showCreateReelInViewer = function() {
  const overlay = document.getElementById('reel-viewer');
  if (!overlay) return;
  let box = document.getElementById('reel-create-overlay');
  if (!box) {
    box = document.createElement('div');
    box.id = 'reel-create-overlay';
    box.className = 'reel-create-overlay';
    overlay.appendChild(box);
  }
  box.style.display = 'flex';
  box.innerHTML =
    '<div class="reel-create-card">' +
    '<h3>Новая публикация</h3>' +
    '<input type="file" id="reel-file-v" accept="image/*,video/*" class="search-box" style="color:#fff">' +
    '<input id="reel-caption-v" class="search-box" placeholder="Подпись">' +
    '<button type="button" class="btn btn-primary" id="reel-pub-btn">Опубликовать</button>' +
    '<button type="button" class="btn" id="reel-cancel-btn" style="background:#333;color:#fff;margin-top:8px">Отмена</button></div>';
  document.getElementById('reel-cancel-btn').onclick = function() { box.style.display = 'none'; };
  document.getElementById('reel-pub-btn').onclick = async function() {
    const f = document.getElementById('reel-file-v').files[0];
    if (!f) { alert('Выберите фото'); return; }
    const card = box.querySelector('.reel-create-card');
    const progress = document.createElement('div');
    progress.innerHTML = '<div style="margin:12px 0;text-align:center"><div style="height:8px;background:#333;border-radius:4px;overflow:hidden"><div id="reel-up-bar" style="height:100%;width:0%;background:#4f46e5;transition:width .2s"></div></div><div id="reel-up-pct">0%</div></div>';
    if (card) card.appendChild(progress);
    let pct = 0;
    const tick = setInterval(function() {
      pct = Math.min(90, pct + 8 + Math.floor(Math.random()*10));
      const bar = document.getElementById('reel-up-bar');
      const p = document.getElementById('reel-up-pct');
      if (bar) bar.style.width = pct + '%';
      if (p) p.textContent = pct + '%';
    }, 120);
    try {
      const fd = new FormData();
      fd.append('file', f);
      const up = await fetch('/api/uploads/media', { method: 'POST', headers: { Authorization: 'Bearer ' + token }, body: fd });
      const data = await up.json().catch(function() { return {}; });
      if (!up.ok) throw new Error(data.detail || 'Ошибка загрузки');
      const media_type = (f.type || '').startsWith('video') ? 'video' : 'image';
      const created = await api('/api/reels/', {
        method: 'POST',
        body: JSON.stringify({
          media_url: data.url,
          media_type: media_type,
          caption: (document.getElementById('reel-caption-v').value || '')
        })
      });
      clearInterval(tick);
      const bar = document.getElementById('reel-up-bar');
      const p = document.getElementById('reel-up-pct');
      if (bar) bar.style.width = '100%';
      if (p) p.textContent = '100%';
      setTimeout(function() {
        box.style.display = 'none';
        _reelFeedCache.unshift(created);
        openReelViewer(0);
      }, 300);
    } catch (e) {
      clearInterval(tick);
      alert(e.message);
    }
  };
};

window.closeReelViewer = function() {
  const overlay = document.getElementById('reel-viewer');
  if (overlay) {
    overlay.style.display = 'none';
    const v = overlay.querySelector('video');
    if (v) { try { v.pause(); } catch(e) {} }
  }
  document.body.classList.remove('reel-open');
};


async function renderReels(el) {
  const role = userRole();
  if (role === 'starosta') {
    el.innerHTML = '<div class="empty"><p>У аккаунта старосты нет Reels</p></div>';
    return;
  }
  el.innerHTML = `<div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
    ${role !== 'admin' ? '<button class="btn btn-primary" style="width:auto" onclick="showCreateReel()">+ Публикация</button>' : ''}
  </div>
  <div id="create-reel-box" class="card create-form"></div>
  <div class="reels-feed" id="reels-feed"><div class="empty"><i class="fas fa-spinner fa-spin"></i> Загрузка...</div></div>`;
  try {
    const data = await api('/api/reels/?offset=0&limit=30');
    let items = data.items || [];
    // shuffle for random start
    for (let i = items.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [items[i], items[j]] = [items[j], items[i]];
    }
    _reelFeedCache = items;
    if (!items.length) {
      el.querySelector('#reels-feed').innerHTML = '<div class="empty"><p>Пока нет публикаций. Нажмите «+ Публикация».</p></div>';
      return;
    }
    // show mini list + auto open fullscreen
    el.querySelector('#reels-feed').innerHTML = items.map((r, i) => renderReelCard(r, i)).join('');
    openReelViewer(0);
  } catch (e) {
    el.querySelector('#reels-feed').innerHTML = `<div class="empty"><p>${e.message}</p></div>`;
  }
}

window.showCreateReel = function() {
  const box = $('#create-reel-box');
  if (!box) return;
  box.classList.add('open');
  box.innerHTML = `
    <div class="card-title">Новая публикация</div>
    <input type="file" id="reel-file" accept="image/*,video/mp4,video/webm,video/quicktime,video/*" class="search-box">
    <input id="reel-caption" class="search-box" placeholder="Подпись">
    <button class="btn btn-primary" style="width:auto" onclick="publishReel()">Опубликовать</button>`;
};
window.publishReel = async function() {
  const f = $('#reel-file') && $('#reel-file').files && $('#reel-file').files[0];
  if (!f) { alert('Выберите фото или видео'); return; }
  try {
    const fd = new FormData();
    fd.append('file', f);
    const up = await fetch('/api/uploads/media', {
      method: 'POST',
      headers: { Authorization: 'Bearer ' + token },
      body: fd
    });
    const data = await up.json().catch(() => ({}));
    if (!up.ok) {
      const d = data.detail;
      throw new Error(typeof d === 'string' ? d : (d && JSON.stringify(d)) || 'Ошибка загрузки видео/фото');
    }
    const media_type = (f.type || '').startsWith('video') || (f.name || '').match(/\.(mp4|webm|mov|3gp)$/i) ? 'video' : 'image';
    await api('/api/reels/', {
      method: 'POST',
      body: JSON.stringify({
        media_url: data.url,
        media_type,
        caption: ($('#reel-caption') || {}).value || ''
      })
    });
    alert('Публикация создана!');
    navigate('reels');
  } catch (e) { alert(e.message); }
};
window.loadReelsFeed = async function(offset) {
  const feed = $('#reels-feed');
  if (!feed) return;
  try {
    const data = await api('/api/reels/?offset=' + (offset||0) + '&limit=15');
    const items = data.items || [];
    if (!items.length) {
      feed.innerHTML = '<div class="empty"><p>Вы посмотрели все рилсы которые опубликовано в приложении. Дождитесь новых публикаций.</p></div>';
      return;
    }
    _reelFeedCache = items;
    feed.innerHTML = items.map((r, i) => renderReelCard(r, i)).join('') +
      (data.exhausted ? '<p class="empty" style="padding:16px">Вы посмотрели все рилсы. Дождитесь новых публикаций — лента начнётся сначала.</p><button class="btn btn-primary" style="width:auto" onclick="loadReelsFeed(0)">Смотреть снова</button>' :
        `<button class="btn" style="width:auto;background:var(--bg);margin:12px 0" onclick="loadReelsFeed(${(offset||0)+15})">Ещё</button>`);
    // record views
    items.forEach(r => { api('/api/reels/' + r.id + '/view', { method:'POST' }).catch(()=>{}); });
  } catch(e) {
    feed.innerHTML = `<div class="empty"><p>${e.message}</p></div>`;
  }
};
function renderReelCard(r, idx) {
  const a = r.author || {};
  const av = a.avatar_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(a.display_name||'?')}&background=4f46e5&color=fff`;
  const media = r.media_type === 'video'
    ? `<video class="reel-media" src="${r.media_url}" controls playsinline></video>`
    : `<img class="reel-media" src="${r.media_url}" alt="">`;
  const mon = a.monetization_enabled;
  return `<div class="reel-card" data-id="${r.id}" onclick="if(!event.target.closest('button'))openReelViewer(${idx||0})">
    <div class="reel-author" onclick="openUserProfile(${a.id})">
      <img src="${av}" alt="">
      <div>
        <strong>${(a.display_name||'').replace(/</g,'&lt;')}</strong>
        ${a.is_pro ? '<span class="pro-badge">PRO</span>' : ''}
        <div style="font-size:12px;color:var(--text-secondary)">@${a.username||''}</div>
      </div>
    </div>
    ${media}
    <div class="reel-body">
      <div class="reel-actions">
        <button class="${r.liked_by_me?'liked':''}" onclick="toggleReelLike(${r.id}, this)"><i class="fas fa-heart"></i> <span>${r.likes_count||0}</span></button>
        <button onclick="showReelComments(${r.id})"><i class="fas fa-comment"></i> ${r.comments_count||0}</button>
        <button onclick="shareReel(${r.id})"><i class="fas fa-share"></i> ${r.shares_count||0}</button>
        <button onclick="toggleFollow(${a.id}, this)">${r.following_author ? 'Отписаться' : 'Подписка'}</button>
        ${mon ? `<button onclick="showGifts(${r.id})"><i class="fas fa-gift"></i></button>` : ''}
        <span style="font-size:12px;color:var(--text-secondary);margin-left:auto"><i class="fas fa-eye"></i> ${r.views_count||0}</span>
      </div>
      <div style="font-size:14px">${(r.caption||'').replace(/</g,'&lt;')}</div>
      <div id="comments-${r.id}" class="reel-comments"></div>
    </div>
  </div>`;
}
window.toggleReelLike = async function(id, btn) {
  try {
    const r = await api('/api/reels/' + id + '/like', { method:'POST' });
    if (btn) {
      btn.classList.toggle('liked', r.liked);
      const sp = btn.querySelector('span');
      if (sp) sp.textContent = r.likes_count;
    }
  } catch(e) { alert(e.message); }
};
window.showReelComments = async function(id) {
  const box = $('#comments-' + id);
  if (!box) return;
  const rows = await api('/api/reels/' + id + '/comments');
  box.innerHTML = (rows||[]).map(c => `<div style="margin:4px 0"><strong>${(c.author&&c.author.display_name)||''}</strong>: ${(c.text||'').replace(/</g,'&lt;')}</div>`).join('') +
    `<div style="display:flex;gap:6px;margin-top:8px">
      <input class="search-box" id="cmt-input-${id}" placeholder="Комментарий" style="margin:0;flex:1">
      <button class="btn btn-primary" style="width:auto;padding:8px 12px" onclick="sendReelComment(${id})">OK</button>
    </div>`;
};
window.sendReelComment = async function(id) {
  const inp = $('#cmt-input-' + id);
  const text = (inp && inp.value || '').trim();
  if (!text) return;
  try {
    await api('/api/reels/' + id + '/comments', { method:'POST', body: JSON.stringify({ text }) });
    showReelComments(id);
  } catch(e) { alert(e.message); }
};
window.shareReel = async function(id) {
  try {
    await api('/api/reels/' + id + '/share', { method:'POST' });
    if (navigator.share) navigator.share({ title: 'ClassMate Reels', url: location.href }).catch(()=>{});
    else alert('Поделено!');
  } catch(e) { alert(e.message); }
};
window.toggleFollow = async function(uid, btn) {
  try {
    const r = await api('/api/reels/follow/' + uid, { method:'POST' });
    if (btn) btn.textContent = r.following ? 'Отписаться' : 'Подписка';
  } catch(e) { alert(e.message); }
};
window.showGifts = async function(reelId) {
  const gifts = await api('/api/reels/gifts/list');
  const bal = await api('/api/coins/balance');
  const html = `<div class="modal-overlay" id="gift-modal" style="display:flex">
    <div class="modal-card">
      <h3>Подарок</h3>
      <p style="font-size:13px;margin-bottom:12px">Баланс: <strong>${bal.balance}</strong> монет</p>
      <div class="gift-grid">
        ${(gifts||[]).map(g => `<div class="gift-item" onclick="sendGift(${reelId}, '${g.id}')">${g.emoji}<br>${g.name}<br><small>${g.cost} 🪙</small></div>`).join('')}
      </div>
      <button class="btn" style="width:100%;margin-top:12px;background:var(--bg)" onclick="document.getElementById('gift-modal').remove()">Закрыть</button>
      <button class="btn btn-primary" style="width:100%;margin-top:8px" onclick="document.getElementById('gift-modal').remove();navigate('pro')">Купить монеты</button>
    </div></div>`;
  document.body.insertAdjacentHTML('beforeend', html);
};
window.sendGift = async function(reelId, giftId) {
  try {
    const r = await api('/api/reels/' + reelId + '/gift?gift_id=' + giftId, { method:'POST' });
    alert(r.message || 'Подарок отправлен!');
    const m = $('#gift-modal'); if (m) m.remove();
    navigate('reels');
  } catch(e) {
    alert(e.message);
    if ((e.message||'').includes('Недостаточно')) {
      const m = $('#gift-modal'); if (m) m.remove();
      navigate('pro');
    }
  }
};
window.openUserProfile = async function(uid) {
  try {
    const data = await api('/api/reels/user/' + uid);
    const u = data.user || {};
    const el = $('#page-content');
    $('#page-title').textContent = u.display_name || 'Профиль';
    const av = u.avatar_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(u.display_name||'?')}&background=4f46e5&color=fff&size=120`;
    el.innerHTML = `
      <div class="card" style="text-align:center">
        <img src="${av}" style="width:80px;height:80px;border-radius:50%;object-fit:cover">
        <h3>${u.display_name||''} ${u.is_pro?'<span class="pro-badge">PRO</span>':''}</h3>
        <p>@${u.username||''}</p>
        <div style="display:flex;justify-content:center;gap:20px;margin:12px 0;font-size:14px">
          <div><strong>${u.posts_count||0}</strong><br>публикаций</div>
          <div><strong>${u.followers_count||0}</strong><br>подписчиков</div>
          <div><strong>${u.following_count||0}</strong><br>подписок</div>
        </div>
        ${u.id !== currentUser.id ? `<button class="btn btn-primary" style="width:auto" onclick="toggleFollow(${u.id}, this)">${data.following?'Отписаться':'Подписаться'}</button>` : ''}
      </div>
      <div class="home-grid">
        ${(data.posts||[]).map(r => `
          <div class="card" style="margin:0;padding:0;overflow:hidden;cursor:pointer" onclick="navigate('reels')">
            <img src="${r.media_url}" style="width:100%;height:120px;object-fit:cover" onerror="this.style.display='none'">
          </div>`).join('') || '<p class="empty">Нет публикаций</p>'}
      </div>`;
  } catch(e) { alert(e.message); }
};



async function renderStarosta(el) {
  const role = userRole();
  if (role !== 'starosta' && role !== 'admin') {
    el.innerHTML = '<div class="empty"><p>Только для старосты</p></div>';
    return;
  }
  el.innerHTML = `
    <div class="card">
      <div class="card-title">Управление классом</div>
      <p style="font-size:13px;color:var(--text-secondary);margin-bottom:12px">Инструменты старосты — без доступа к настройкам всего приложения</p>
      <button class="btn btn-primary" style="width:auto;margin:4px" onclick="navigate('homework')">📚 Домашка</button>
      <button class="btn btn-primary" style="width:auto;margin:4px" onclick="navigate('schedule')">📅 Расписание</button>
      <button class="btn btn-primary" style="width:auto;margin:4px" onclick="navigate('announcements')">📢 Объявления</button>
      <button class="btn btn-primary" style="width:auto;margin:4px" onclick="navigate('polls')">📊 Опросы</button>
      <button class="btn btn-primary" style="width:auto;margin:4px" onclick="navigate('events')">⭐ События</button>
      <button class="btn btn-primary" style="width:auto;margin:4px" onclick="navigate('collections')">💰 Сборы</button>
      <button class="btn btn-primary" style="width:auto;margin:4px" onclick="navigate('classmates')">👥 Ученики</button>
      <button class="btn btn-primary" style="width:auto;margin:4px" onclick="navigate('chats')">💬 Чаты</button>
      <button class="btn btn-primary" style="width:auto;margin:4px" onclick="navigate('notifications')">🔔 Уведомления</button>
    </div>
    <div class="card">
      <div class="card-title">Чаты старосты</div>
      <p style="font-size:13px">1) Общий чат класса<br>2) Чат с администрацией (Админ ↔ Старосты)</p>
      <button class="btn btn-primary" style="width:auto" onclick="navigate('chats')">Открыть чаты</button>
    </div>
  `;
}


window.approvePayment = async function(id) {
  try {
    await api('/api/admin/payments/' + id + '/approve', { method: 'POST' });
    alert('PRO одобрен');
    navigate('admin');
  } catch (e) { alert(e.message); }
};
window.rejectPayment = async function(id) {
  const reason = prompt('Причина отказа:') || 'Отклонено';
  try {
    await api('/api/admin/payments/' + id + '/reject?reason=' + encodeURIComponent(reason), { method: 'POST' });
    alert('Отклонено');
    navigate('admin');
  } catch (e) { alert(e.message); }
};

function connectWS() {
  if (!token) return;
  try {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/api/chats/ws/${token}`);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'new_message' && currentChatId && data.message && data.message.chat_id === currentChatId) {
          const list = $('#messages-list');
          if (list) {
            list.insertAdjacentHTML('beforeend', renderMessage(data.message));
            list.scrollTop = list.scrollHeight;
          }
        }
        if (data.type === 'typing' && currentChatId && data.chat_id === currentChatId) {
          const tip = $('#typing-indicator');
          if (tip) {
            tip.style.display = 'block';
            tip.textContent = (data.username || 'Кто-то') + ' печатает...';
            clearTimeout(window._typingHide);
            window._typingHide = setTimeout(() => { tip.style.display = 'none'; }, 2000);
          }
        }
      } catch (e) {}
    };
    ws.onclose = () => setTimeout(connectWS, 3000);
  } catch (e) {}
}

window.addEventListener('popstate', function(e) {
  if (document.body.classList.contains('reel-open')) {
    const cmt = document.getElementById('reel-cmt-panel');
    if (cmt && cmt.style.display === 'flex') {
      cmt.style.display = 'none';
      history.pushState({ app: true, reel: true }, '');
      return;
    }
    const createBox = document.getElementById('reel-create-overlay');
    if (createBox && createBox.style.display === 'flex') {
      createBox.style.display = 'none';
      history.pushState({ app: true, reel: true }, '');
      return;
    }
    closeReelViewer();
    if (currentPage !== 'reels') navigate('reels');
    history.pushState({ app: true }, '');
    return;
  }
  if (document.body.classList.contains('chat-open')) {
    if (typeof closeChat === 'function') closeChat();
    else { document.body.classList.remove('chat-open'); navigate('chats'); }
    history.pushState({ app: true }, '');
    return;
  }
  if (currentPage && currentPage !== 'home') {
    navigate('home');
    history.pushState({ app: true }, '');
    return;
  }
});
try { history.pushState({ app: true }, ''); } catch (e) {}

try {
  if (token) showMain();
  else showAuth();
} catch (bootErr) {
  console.error('init error', bootErr);
  hideBootLoader();
  showAuth();
}

