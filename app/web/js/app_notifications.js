let notifications = [];
let notificationDrawerTimer = null;
let notificationDrawerFrame = null;
let notificationDrawerFocusReturn = null;

function loadNotifications() {
  try {
    notifications = JSON.parse(localStorage.getItem('notifications') || '[]');
  } catch (e) {
    notifications = [];
  }
  renderNotifications();
}

function saveNotifications() {
  localStorage.setItem('notifications', JSON.stringify(notifications));
}

function notifySystem(title, message) {
  try {
    if (!('Notification' in window)) return;
    if (Notification.permission === 'granted') {
      new Notification(title, { body: message });
    } else if (Notification.permission !== 'denied') {
      Notification.requestPermission().then(permission => {
        if (permission === 'granted') new Notification(title, { body: message });
      });
    }
  } catch (e) {}
}

function addNotification(title, message, type = 'info', action = null) {
  const safeAction = action && typeof action.action === 'function'
    ? { label: action.label || 'Open', view: action.view || null, spriteFolder: action.spriteFolder || null }
    : action;
  const newNotif = {
    id: Date.now() + Math.random().toString(36).substr(2, 9),
    title,
    message,
    type,
    time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    action: safeAction
  };
  notifications.unshift(newNotif);
  if (notifications.length > 100) {
    notifications = notifications.slice(0, 100);
  }
  saveNotifications();
  renderNotifications();
  toast(title);
  if (type === 'success' || type === 'error' || type === 'warning') notifySystem(title, message);
}

function renderNotifications() {
  const list = $('#notificationList');
  const badge = $('#notificationBadge');
  if (!list) return;
  clearNode(list);
  if (notifications.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty-notifications';
    empty.style.color = 'var(--muted)';
    empty.style.textAlign = 'center';
    empty.style.marginTop = '40px';
    empty.textContent = 'No notifications yet.';
    list.appendChild(empty);
    if (badge) {
      badge.textContent = '0';
      badge.style.display = 'none';
    }
    return;
  }
  if (badge) {
    badge.textContent = notifications.length;
    badge.style.display = 'block';
  }
  notifications.forEach(n => {
    const item = document.createElement('div');
    item.className = `notification-item ${n.type}`;
    const h4 = document.createElement('h4');
    h4.textContent = n.title;
    item.appendChild(h4);
    const closeBtn = document.createElement('button');
    closeBtn.className = 'close-btn';
    closeBtn.textContent = '×';
    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      removeNotification(n.id);
    });
    item.appendChild(closeBtn);
    const p = document.createElement('p');
    p.textContent = n.message;
    item.appendChild(p);
    if (n.action) {
      const actBtn = document.createElement('button');
      actBtn.className = 'action-btn';
      actBtn.textContent = n.action.label;
      actBtn.addEventListener('click', () => {
        if (n.action.spriteFolder) {
          openResultPreview(n.action.spriteFolder);
        } else if (n.action.view) {
          showView(n.action.view);
        }
      });
      item.appendChild(actBtn);
    }
    const timeSpan = document.createElement('span');
    timeSpan.className = 'time';
    timeSpan.textContent = n.time;
    item.appendChild(timeSpan);
    list.appendChild(item);
  });
}

function removeNotification(id) {
  notifications = notifications.filter(n => n.id !== id);
  saveNotifications();
  renderNotifications();
}

function clearAllNotifications() {
  notifications = [];
  saveNotifications();
  renderNotifications();
}

function setNotificationDrawer(open) {
  const drawer = $('#notificationDrawer');
  const trigger = $('#notificationTrigger');
  if (!drawer) return;
  if (notificationDrawerTimer) window.clearTimeout(notificationDrawerTimer);
  if (notificationDrawerFrame) window.cancelAnimationFrame(notificationDrawerFrame);
  notificationDrawerTimer = null;
  notificationDrawerFrame = null;
  if (open) {
    notificationDrawerFocusReturn = document.activeElement;
    drawer.classList.remove('hidden');
    drawer.setAttribute('aria-hidden', 'false');
    trigger?.setAttribute('aria-expanded', 'true');
    notificationDrawerFrame = window.requestAnimationFrame(() => {
      notificationDrawerFrame = null;
      if (drawer.getAttribute('aria-hidden') === 'true') return;
      drawer.classList.add('show');
      $('#closeDrawerBtn')?.focus();
    });
    return;
  }
  drawer.classList.remove('show');
  drawer.setAttribute('aria-hidden', 'true');
  trigger?.setAttribute('aria-expanded', 'false');
  notificationDrawerTimer = window.setTimeout(() => drawer.classList.add('hidden'), 320);
  const focusTarget = notificationDrawerFocusReturn;
  notificationDrawerFocusReturn = null;
  if (focusTarget && typeof focusTarget.focus === 'function') focusTarget.focus();
}

function initNotifications() {
  const trigger = $('#notificationTrigger');
  const drawer = $('#notificationDrawer');
  if (trigger && drawer) {
    trigger.setAttribute('aria-controls', 'notificationDrawer');
    trigger.setAttribute('aria-expanded', 'false');
    drawer.setAttribute('aria-hidden', 'true');
    trigger.addEventListener('click', () => setNotificationDrawer(drawer.getAttribute('aria-hidden') !== 'false'));
  }
  if ($('#closeDrawerBtn')) $('#closeDrawerBtn').addEventListener('click', () => setNotificationDrawer(false));
  if ($('#clearNotificationsBtn')) $('#clearNotificationsBtn').addEventListener('click', clearAllNotifications);
}

window.setNotificationDrawer = setNotificationDrawer;

if (window.onSpriteForgeReady) {
  window.onSpriteForgeReady(initNotifications);
} else if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initNotifications, { once: true });
} else {
  initNotifications();
}
