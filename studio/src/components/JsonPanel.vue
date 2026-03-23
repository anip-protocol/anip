<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  data: any
  title?: string
  collapsed?: boolean
}>()

const isCollapsed = ref(props.collapsed ?? true)
const copied = ref(false)

const jsonString = computed(() => JSON.stringify(props.data, null, 2))

function toggle() {
  isCollapsed.value = !isCollapsed.value
}

async function copyJson() {
  try {
    await navigator.clipboard.writeText(jsonString.value)
    copied.value = true
    setTimeout(() => { copied.value = false }, 1500)
  } catch { /* clipboard not available */ }
}
</script>

<template>
  <div class="json-panel">
    <div class="json-header" @click="toggle">
      <span class="toggle-arrow">{{ isCollapsed ? '\u25B6' : '\u25BC' }}</span>
      <span class="json-title">{{ title || 'Raw JSON' }}</span>
      <button class="copy-btn" @click.stop="copyJson" :title="copied ? 'Copied!' : 'Copy JSON'">
        {{ copied ? 'Copied' : 'Copy' }}
      </button>
    </div>
    <div v-if="!isCollapsed" class="json-body">
      <JsonNode :value="data" :depth="0" />
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, h, ref as vRef, type VNode } from 'vue'

const JsonNode: ReturnType<typeof defineComponent> = defineComponent({
  name: 'JsonNode',
  props: {
    value: { type: null, required: true },
    depth: { type: Number, default: 0 },
    keyName: { type: String, default: '' },
  },
  setup(props): () => VNode {
    const collapsed = vRef(props.depth > 2)

    return (): VNode => {
      const val = props.value
      const indent = props.depth * 16

      // Null
      if (val === null || val === undefined) {
        return h('div', { class: 'json-line', style: { paddingLeft: `${indent}px` } }, [
          props.keyName ? h('span', { class: 'json-key' }, `${props.keyName}: `) : null,
          h('span', { class: 'json-null' }, 'null'),
        ])
      }

      // Boolean
      if (typeof val === 'boolean') {
        return h('div', { class: 'json-line', style: { paddingLeft: `${indent}px` } }, [
          props.keyName ? h('span', { class: 'json-key' }, `${props.keyName}: `) : null,
          h('span', { class: 'json-bool' }, String(val)),
        ])
      }

      // Number
      if (typeof val === 'number') {
        return h('div', { class: 'json-line', style: { paddingLeft: `${indent}px` } }, [
          props.keyName ? h('span', { class: 'json-key' }, `${props.keyName}: `) : null,
          h('span', { class: 'json-number' }, String(val)),
        ])
      }

      // String
      if (typeof val === 'string') {
        return h('div', { class: 'json-line', style: { paddingLeft: `${indent}px` } }, [
          props.keyName ? h('span', { class: 'json-key' }, `${props.keyName}: `) : null,
          h('span', { class: 'json-string' }, `"${val}"`),
        ])
      }

      // Array
      if (Array.isArray(val)) {
        if (val.length === 0) {
          return h('div', { class: 'json-line', style: { paddingLeft: `${indent}px` } }, [
            props.keyName ? h('span', { class: 'json-key' }, `${props.keyName}: `) : null,
            h('span', { class: 'json-bracket' }, '[]'),
          ])
        }
        return h('div', { style: { paddingLeft: `${indent}px` } }, [
          h('div', {
            class: 'json-line json-toggle',
            onClick: (e: Event) => { e.stopPropagation(); collapsed.value = !collapsed.value },
          }, [
            h('span', { class: 'toggle-icon' }, collapsed.value ? '\u25B6' : '\u25BC'),
            props.keyName ? h('span', { class: 'json-key' }, `${props.keyName}: `) : null,
            h('span', { class: 'json-bracket' }, collapsed.value ? `[ ... ${val.length} items ]` : '['),
          ]),
          ...(collapsed.value ? [] : [
            ...val.map((item: unknown, i: number) => h(JsonNode, { value: item, depth: props.depth + 1, keyName: String(i), key: i })),
            h('div', { class: 'json-line', style: { paddingLeft: `${indent}px` } }, [
              h('span', { class: 'json-bracket' }, ']'),
            ]),
          ]),
        ])
      }

      // Object
      if (typeof val === 'object') {
        const keys = Object.keys(val as Record<string, unknown>)
        if (keys.length === 0) {
          return h('div', { class: 'json-line', style: { paddingLeft: `${indent}px` } }, [
            props.keyName ? h('span', { class: 'json-key' }, `${props.keyName}: `) : null,
            h('span', { class: 'json-bracket' }, '{}'),
          ])
        }
        return h('div', { style: { paddingLeft: `${indent}px` } }, [
          h('div', {
            class: 'json-line json-toggle',
            onClick: (e: Event) => { e.stopPropagation(); collapsed.value = !collapsed.value },
          }, [
            h('span', { class: 'toggle-icon' }, collapsed.value ? '\u25B6' : '\u25BC'),
            props.keyName ? h('span', { class: 'json-key' }, `${props.keyName}: `) : null,
            h('span', { class: 'json-bracket' }, collapsed.value ? `{ ... ${keys.length} keys }` : '{'),
          ]),
          ...(collapsed.value ? [] : [
            ...keys.map((k) => h(JsonNode, { value: (val as Record<string, unknown>)[k], depth: props.depth + 1, keyName: k, key: k })),
            h('div', { class: 'json-line', style: { paddingLeft: `${indent}px` } }, [
              h('span', { class: 'json-bracket' }, '}'),
            ]),
          ]),
        ])
      }

      // Fallback
      return h('div', { class: 'json-line', style: { paddingLeft: `${indent}px` } }, [
        h('span', { class: 'json-string' }, String(val)),
      ])
    }
  },
})
</script>

<style scoped>
.json-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.json-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--bg-hover);
  cursor: pointer;
  user-select: none;
  transition: background 150ms ease;
}

.json-header:hover {
  background: var(--bg-active);
}

.toggle-arrow {
  font-size: 10px;
  color: var(--text-muted);
  width: 14px;
}

.json-title {
  flex: 1;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.copy-btn {
  padding: 3px 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 11px;
  cursor: pointer;
  transition: all 150ms ease;
}

.copy-btn:hover {
  background: var(--bg-input);
  color: var(--text-primary);
  border-color: var(--accent);
}

.json-body {
  padding: 12px 14px;
  background: var(--bg-app);
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 12px;
  line-height: 1.6;
  overflow-x: auto;
  max-height: 600px;
  overflow-y: auto;
}

.json-line {
  white-space: nowrap;
}

.json-toggle {
  cursor: pointer;
}

.json-toggle:hover {
  background: rgba(108, 99, 255, 0.06);
  border-radius: 3px;
}

.toggle-icon {
  display: inline-block;
  width: 14px;
  font-size: 9px;
  color: var(--text-muted);
  text-align: center;
}

.json-key {
  color: var(--accent);
}

.json-string {
  color: #34d399;
}

.json-number {
  color: #fb923c;
}

.json-bool {
  color: #60a5fa;
}

.json-null {
  color: #606080;
  font-style: italic;
}

.json-bracket {
  color: var(--text-muted);
}
</style>
