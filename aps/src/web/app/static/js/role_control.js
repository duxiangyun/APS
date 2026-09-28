/**
 * APS 前端角色感知脚本（Demo 阶段：仅控制菜单可见性，不做后端鉴权）。
 *
 * 角色来源优先级：URL 参数 ?role=xxx  >（iframe 内）sessionStorage 记住的角色
 *                >  window.APS_ROLE  >  'default'
 * 授权表来源：window.ROLE_MENUS（由 templates/base.html 从 app.constants.ROLE_MENUS 注入）
 * 授权值语义：full / read / partial 可见（read、partial 额外加 nav-item-limited 标记），null 不可见。
 *
 * 统一壳角色切换：
 *   方式 A（当前实现）：壳把角色拼进 iframe src（/aps/dashboard?role=sales），
 *                       切换角色 → iframe 带新参数重新加载 → 本脚本按 URL 应用权限；
 *   方式 B（备用）：window.postMessage({ type: 'ROLE_CHANGE', role: 'sales' }, '*') 无刷新切换。
 *
 * sessionStorage 说明：iframe 内点击 APS 侧边栏会整页跳转并丢掉 ?role=，
 *   故在 iframe 环境中记住本会话角色；直接打开 APS（非 iframe）时不受历史角色影响。
 */
var STORAGE_KEY = 'aps_role';

function readStoredRole() {
  try {
    return sessionStorage.getItem(STORAGE_KEY) || '';
  } catch (e) {
    return '';   // 隐私模式 / 禁用存储：静默降级
  }
}

function persistRole(role) {
  try {
    sessionStorage.setItem(STORAGE_KEY, role);
  } catch (e) {
    /* 忽略存储不可用 */
  }
}

function getCurrentRole() {
  var role = '';
  if (typeof URLSearchParams !== 'undefined') {
    role = new URLSearchParams(location.search).get('role') || '';
  } else {
    // 兜底：极老内核无 URLSearchParams
    var m = /[?&]role=([^&#]+)/.exec(location.search || '');
    role = m ? decodeURIComponent(m[1]) : '';
  }
  if (role) return role;
  // 仅 iframe 内沿用「本次会话记住的角色」，直接访问 APS 时仍走 APS_ROLE / default
  if (window.self !== window.top) {
    var saved = readStoredRole();
    if (saved) return saved;
  }
  return window.APS_ROLE || 'default';
}

function applyRolePermissions(role) {
  // 授权表缺失时保持现状（全显示），避免注入失败导致菜单被整体隐藏
  const TABLE = window.ROLE_MENUS;
  if (!TABLE) {
    console.warn('[role_control] ROLE_MENUS 未注入，跳过菜单权限控制');
    return;
  }
  window.APS_ROLE = role;
  persistRole(role);
  const menus = TABLE[role] || TABLE['default'];
  if (!menus) {
    console.warn('[role_control] 未知角色:', role);
    return;
  }
  document.querySelectorAll('[data-menu]').forEach((el) => {
    const key = el.getAttribute('data-menu');
    const perm = menus[key];
    if (perm === null || perm === undefined) {
      el.style.display = 'none';
      el.classList.remove('nav-item-limited');
    } else if (perm === 'read' || perm === 'partial') {
      el.style.display = '';
      el.classList.add('nav-item-limited');   // 只读/受限样式标记
    } else {
      el.style.display = '';
      el.classList.remove('nav-item-limited');
    }
  });
  // 把当前角色暴露到 body，便于调试
  document.body.dataset.role = role;
}

// 监听统一壳的角色切换消息（兼容 ROLE_CHANGE / role_change 两种写法）
window.addEventListener('message', (e) => {
  const type = e && e.data && e.data.type;
  if (e && e.data && e.data.role && (type === 'ROLE_CHANGE' || type === 'role_change')) {
    applyRolePermissions(e.data.role);
  }
});

// 页面加载时应用角色
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    applyRolePermissions(getCurrentRole());
  });
} else {
  applyRolePermissions(getCurrentRole());
}
