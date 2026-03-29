<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { store } from './store'
import { fetchDiscovery } from './api'

const router = useRouter()
const route = useRoute()

const urlInput = ref('')
const sidebarCollapsed = ref(false)
const connecting = ref(false)

const navItems = [
  { name: 'discovery', label: 'Discovery', icon: '\u{1F50D}', path: '/' },
  { name: 'manifest', label: 'Manifest', icon: '\u{1F4CB}', path: '/manifest' },
  { name: 'jwks', label: 'JWKS', icon: '\u{1F511}', path: '/jwks' },
  { name: 'audit', label: 'Audit', icon: '\u{1F4CA}', path: '/audit' },
  { name: 'checkpoints', label: 'Checkpoints', icon: '\u2713', path: '/checkpoints' },
  { name: 'invoke', label: 'Invoke', icon: '\u26A1', path: '/invoke' },
]

const activeRoute = computed(() => route.name as string)

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

function navigate(path: string) {
  router.push(path)
}

async function connect() {
  const url = urlInput.value.replace(/\/+$/, '')
  if (!url) return

  connecting.value = true
  store.error = ''

  try {
    await fetchDiscovery(url)
    store.baseUrl = url
    store.connected = true
  } catch (e: unknown) {
    store.error = e instanceof Error ? e.message : 'Connection failed'
  } finally {
    connecting.value = false
  }
}

function disconnect() {
  store.baseUrl = ''
  store.connected = false
  store.error = ''
  store.serviceId = ''
  urlInput.value = ''
}
</script>

<template>
  <div class="studio-app" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <button class="sidebar-toggle" @click="toggleSidebar" title="Toggle sidebar">
          <span class="toggle-icon">{{ sidebarCollapsed ? '\u25B6' : '\u25C0' }}</span>
        </button>
        <div class="brand">
          <span class="brand-logo">&#x25C6;</span>
          <span class="brand-name">ANIP <span class="brand-accent">Studio</span></span>
        </div>
      </div>

      <div class="header-center">
        <div v-if="store.connected" class="connected-badge" @click="disconnect">
          <span class="status-dot connected"></span>
          <span class="connected-url">{{ store.baseUrl }}</span>
          <span class="disconnect-hint">&times;</span>
        </div>
        <div v-else class="connect-bar">
          <input
            v-model="urlInput"
            type="text"
            class="url-input"
            placeholder="https://your-service.example.com"
            @keyup.enter="connect"
            :disabled="connecting"
          />
          <button class="connect-btn" @click="connect" :disabled="connecting || !urlInput">
            {{ connecting ? 'Connecting...' : 'Connect' }}
          </button>
        </div>
      </div>

      <div class="header-right">
        <span v-if="store.error" class="error-badge" :title="store.error">
          <span class="status-dot error"></span>
          Error
        </span>
        <span v-else-if="store.connected" class="status-badge">
          <span class="status-dot connected"></span>
          Connected
        </span>
        <span v-else class="status-badge muted">
          <span class="status-dot idle"></span>
          Not connected
        </span>
      </div>
    </header>

    <!-- Body -->
    <div class="body">
      <!-- Sidebar -->
      <nav class="sidebar">
        <ul class="nav-list">
          <li
            v-for="item in navItems"
            :key="item.name"
            class="nav-item"
            :class="{ active: activeRoute === item.name }"
            @click="navigate(item.path)"
            :title="item.label"
          >
            <span class="nav-icon">{{ item.icon }}</span>
            <span class="nav-label">{{ item.label }}</span>
          </li>
        </ul>
        <div class="sidebar-footer">
          <span class="version">v0.11.1</span>
        </div>
      </nav>

      <!-- Main Content -->
      <main class="content">
        <div v-if="!store.connected" class="welcome">
          <div class="welcome-icon">&#x25C6;</div>
          <h2 class="welcome-title">Connect to an ANIP service</h2>
          <p class="welcome-text">Enter a service URL to inspect its discovery document, manifest, capabilities, audit log, and more.</p>
          <div class="welcome-connect">
            <input
              v-model="urlInput"
              type="text"
              class="welcome-input"
              placeholder="https://your-service.example.com"
              @keyup.enter="connect"
              :disabled="connecting"
            />
            <button class="connect-btn welcome-btn" @click="connect" :disabled="connecting || !urlInput">
              {{ connecting ? 'Connecting...' : 'Connect' }}
            </button>
          </div>
          <p v-if="store.error" class="welcome-error">{{ store.error }}</p>
          <div class="welcome-examples">
            <span class="welcome-examples-label">Try a playground service:</span>
            <button class="example-link" @click="urlInput = 'https://travel.playground.anip.dev'; connect()">Travel</button>
            <button class="example-link" @click="urlInput = 'https://finance.playground.anip.dev'; connect()">Finance</button>
            <button class="example-link" @click="urlInput = 'https://devops.playground.anip.dev'; connect()">DevOps</button>
          </div>
        </div>
        <router-view v-else />
      </main>
    </div>
  </div>
</template>

<style scoped>
/* ── Theme tokens ── */
:root {
  --bg-app: #0f0f1a;
  --bg-header: #151525;
  --bg-sidebar: #12121f;
  --bg-content: #1a1a2e;
  --bg-input: #1e1e38;
  --bg-hover: #252545;
  --bg-active: #2a2a50;
  --border: #3a3a5c;
  --border-focus: #5c5cff;
  --text-primary: #e8e8f0;
  --text-secondary: #a0a0c0;
  --text-muted: #606080;
  --accent: #6c63ff;
  --accent-hover: #7b73ff;
  --accent-glow: rgba(108, 99, 255, 0.15);
  --success: #34d399;
  --error: #f87171;
  --radius: 8px;
  --radius-sm: 6px;
  --transition: 180ms ease;
}

/* ── Layout ── */
.studio-app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-app);
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.5;
}

/* ── Header ── */
.header {
  display: flex;
  align-items: center;
  gap: 16px;
  height: 56px;
  padding: 0 20px;
  background: var(--bg-header);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 180px;
}

.sidebar-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition);
  font-size: 10px;
}

.sidebar-toggle:hover {
  background: var(--bg-hover);
  color: var(--text-secondary);
  border-color: var(--text-muted);
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  user-select: none;
}

.brand-logo {
  font-size: 18px;
  color: var(--accent);
}

.brand-name {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.3px;
  color: var(--text-primary);
}

.brand-accent {
  color: var(--accent);
  font-weight: 500;
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
  max-width: 560px;
  margin: 0 auto;
}

.connect-bar {
  display: flex;
  width: 100%;
  gap: 8px;
}

.url-input {
  flex: 1;
  height: 36px;
  padding: 0 14px;
  background: var(--bg-input);
  border: 2px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  outline: none;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.url-input::placeholder {
  color: var(--text-secondary);
  opacity: 0.7;
}

.url-input:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px var(--accent-glow);
}

.connect-btn {
  height: 36px;
  padding: 0 20px;
  background: var(--accent);
  border: none;
  border-radius: var(--radius-sm);
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition);
  white-space: nowrap;
}

.connect-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}

.connect-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.connected-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 14px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition);
  max-width: 100%;
}

.connected-badge:hover {
  border-color: var(--error);
}

.connected-badge:hover .disconnect-hint {
  opacity: 1;
  color: var(--error);
}

.connected-url {
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.disconnect-hint {
  font-size: 16px;
  color: var(--text-muted);
  opacity: 0;
  transition: all var(--transition);
  margin-left: 4px;
}

.header-right {
  display: flex;
  align-items: center;
  min-width: 140px;
  justify-content: flex-end;
}

.status-badge,
.error-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  padding: 4px 10px;
  border-radius: 20px;
  background: var(--bg-input);
  border: 1px solid var(--border);
}

.status-badge.muted {
  color: var(--text-muted);
}

.error-badge {
  color: var(--error);
  border-color: rgba(248, 113, 113, 0.3);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.connected {
  background: var(--success);
  box-shadow: 0 0 6px rgba(52, 211, 153, 0.4);
}

.status-dot.idle {
  background: var(--text-muted);
}

.status-dot.error {
  background: var(--error);
  box-shadow: 0 0 6px rgba(248, 113, 113, 0.4);
}

/* ── Body ── */
.body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ── Sidebar ── */
.sidebar {
  width: 220px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width var(--transition);
  overflow: hidden;
}

.sidebar-collapsed .sidebar {
  width: 56px;
}

.nav-list {
  list-style: none;
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition);
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
}

.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--bg-active);
  color: var(--text-primary);
  box-shadow: inset 3px 0 0 var(--accent);
}

.nav-icon {
  font-size: 16px;
  width: 24px;
  text-align: center;
  flex-shrink: 0;
}

.nav-label {
  font-size: 13px;
  font-weight: 500;
  transition: opacity var(--transition);
}

.sidebar-collapsed .nav-label {
  opacity: 0;
  width: 0;
}

.sidebar-footer {
  margin-top: auto;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}

.version {
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.sidebar-collapsed .version {
  display: none;
}

/* ── Content ── */
.content {
  flex: 1;
  background: var(--bg-content);
  overflow-y: auto;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .header-left {
    min-width: auto;
  }

  .brand-name {
    display: none;
  }

  .header-right {
    min-width: auto;
  }

  .sidebar {
    width: 56px;
  }

  .nav-label {
    opacity: 0;
    width: 0;
  }

  .sidebar-footer .version {
    display: none;
  }
}

/* ── Welcome (not connected) ── */
.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 2rem;
  text-align: center;
}

.welcome-icon {
  font-size: 48px;
  color: var(--accent);
  margin-bottom: 1rem;
  opacity: 0.6;
}

.welcome-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.welcome-text {
  font-size: 14px;
  color: var(--text-secondary);
  max-width: 420px;
  line-height: 1.6;
  margin: 0 0 1.5rem;
}

.welcome-connect {
  display: flex;
  gap: 8px;
  width: 100%;
  max-width: 480px;
  margin-bottom: 1rem;
}

.welcome-input {
  flex: 1;
  height: 42px;
  padding: 0 16px;
  background: var(--bg-input);
  border: 2px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 14px;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  outline: none;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.welcome-input::placeholder {
  color: var(--text-secondary);
  opacity: 0.6;
}

.welcome-input:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px var(--accent-glow);
}

.welcome-btn {
  height: 42px;
  padding: 0 24px;
  font-size: 14px;
  border-radius: var(--radius);
}

.welcome-error {
  color: var(--error);
  font-size: 13px;
  margin: 0 0 1rem;
}

.welcome-examples {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 0.5rem;
}

.welcome-examples-label {
  font-size: 12px;
  color: var(--text-muted);
}

.example-link {
  background: none;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--accent);
  font-size: 12px;
  padding: 4px 12px;
  cursor: pointer;
  transition: all var(--transition);
}

.example-link:hover {
  background: var(--accent-glow);
  border-color: var(--accent);
}
</style>
