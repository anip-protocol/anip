<script setup lang="ts">
withDefaults(defineProps<{
  active: boolean
  title?: string
  message?: string
  detail?: string
  progressItems?: string[]
  cancelLabel?: string
  cancelDisabled?: boolean
}>(), {
  title: 'Assistant is working',
  message: 'Studio is asking the configured model to analyze the current design.',
  detail: 'This can take a little while. Keep this tab open.',
  progressItems: () => [],
  cancelLabel: 'Cancel request',
  cancelDisabled: false,
})

defineEmits<{
  cancel: []
}>()
</script>

<template>
  <Teleport to="body">
    <div v-if="active" class="assistant-working-overlay" role="alertdialog" aria-modal="true" :aria-label="title">
      <div class="assistant-working-card">
        <div class="shape-stage" aria-hidden="true">
          <span class="shape shape-one"></span>
          <span class="shape shape-two"></span>
          <span class="shape shape-three"></span>
          <span class="shape-core"></span>
        </div>
        <div class="assistant-working-copy">
          <span class="working-kicker">Studio Assistant</span>
          <h2>{{ title }}</h2>
          <p>{{ message }}</p>
          <small>{{ detail }}</small>
          <ol v-if="progressItems.length > 0" class="working-progress" aria-label="Assistant progress">
            <li v-for="item in progressItems.slice(-5)" :key="item">{{ item }}</li>
          </ol>
          <button
            class="working-cancel"
            type="button"
            :disabled="cancelDisabled"
            @click="$emit('cancel')"
          >
            {{ cancelLabel }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.assistant-working-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: grid;
  place-items: center;
  padding: 1.5rem;
  background:
    radial-gradient(circle at 28% 22%, rgba(20, 184, 166, 0.2), transparent 34%),
    radial-gradient(circle at 72% 70%, rgba(245, 158, 11, 0.16), transparent 34%),
    rgba(2, 6, 23, 0.74);
  backdrop-filter: blur(12px);
}

.assistant-working-card {
  width: min(520px, 100%);
  display: grid;
  grid-template-columns: 132px minmax(0, 1fr);
  gap: 1.25rem;
  align-items: center;
  border: 1px solid var(--surface-border-card);
  border-radius: 28px;
  padding: 1.35rem;
  background:
    linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(17, 24, 39, 0.92)),
    var(--bg-content);
  box-shadow: 0 24px 90px rgba(2, 6, 23, 0.42);
}

.shape-stage {
  position: relative;
  width: 112px;
  height: 112px;
  border-radius: 28px;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(20, 184, 166, 0.12), rgba(251, 191, 36, 0.1)),
    rgba(15, 23, 42, 0.8);
}

.shape,
.shape-core {
  position: absolute;
  display: block;
}

.shape {
  width: 42px;
  height: 42px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  background: rgba(20, 184, 166, 0.28);
  animation: morph 2.4s ease-in-out infinite;
}

.shape-one {
  top: 18px;
  left: 18px;
}

.shape-two {
  right: 16px;
  top: 28px;
  background: rgba(251, 191, 36, 0.24);
  animation-delay: 0.28s;
}

.shape-three {
  left: 38px;
  bottom: 18px;
  background: rgba(96, 165, 250, 0.22);
  animation-delay: 0.56s;
}

.shape-core {
  inset: 39px;
  border-radius: 999px;
  background: #f8fafc;
  box-shadow: 0 0 28px rgba(20, 184, 166, 0.52);
  animation: pulse-core 1.5s ease-in-out infinite;
}

.working-kicker {
  display: inline-flex;
  margin-bottom: 0.45rem;
  color: #99f6e4;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.assistant-working-copy h2 {
  margin: 0;
  color: #f8fafc;
  font-size: 22px;
  line-height: 1.2;
}

.assistant-working-copy p {
  margin: 0.6rem 0 0;
  color: #cbd5e1;
  line-height: 1.5;
}

.assistant-working-copy small {
  display: block;
  margin-top: 0.65rem;
  color: #94a3b8;
  line-height: 1.45;
}

.working-progress {
  display: grid;
  gap: 0.34rem;
  margin: 0.85rem 0 0;
  padding: 0;
  color: #cbd5e1;
  font-size: 12px;
  list-style: none;
}

.working-progress li {
  position: relative;
  padding-left: 1rem;
  line-height: 1.35;
}

.working-progress li::before {
  position: absolute;
  top: 0.48em;
  left: 0;
  width: 6px;
  height: 6px;
  content: '';
  border-radius: 999px;
  background: #2dd4bf;
  box-shadow: 0 0 14px rgba(45, 212, 191, 0.54);
}

.working-cancel {
  margin-top: 1rem;
  border: 1px solid rgba(248, 250, 252, 0.26);
  border-radius: 999px;
  padding: 0.54rem 0.92rem;
  color: #f8fafc;
  font-weight: 800;
  background: rgba(15, 23, 42, 0.62);
  cursor: pointer;
}

.working-cancel:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.working-cancel:not(:disabled):hover {
  border-color: rgba(248, 250, 252, 0.48);
  background: rgba(30, 41, 59, 0.78);
}

@keyframes morph {
  0%,
  100% {
    border-radius: 12px;
    transform: translate3d(0, 0, 0) rotate(0deg) scale(1);
  }

  50% {
    border-radius: 999px 18px 999px 18px;
    transform: translate3d(4px, -5px, 0) rotate(24deg) scale(1.08);
  }
}

@keyframes pulse-core {
  0%,
  100% {
    transform: scale(0.92);
    opacity: 0.72;
  }

  50% {
    transform: scale(1.1);
    opacity: 1;
  }
}

@media (max-width: 640px) {
  .assistant-working-card {
    grid-template-columns: 1fr;
    text-align: center;
  }

  .shape-stage {
    margin: 0 auto;
  }
}
</style>
