<script setup lang="ts">
import type { ProjectIssueSummary } from '../design/project-issues'

defineProps<{
  issue?: ProjectIssueSummary
  title?: string
}>()
</script>

<template>
  <section v-if="issue && issue.count > 0" class="project-issue-banner" :class="`severity-${issue.severity}`">
    <div class="issue-banner-header">
      <div>
        <div class="issue-kicker">{{ issue.severity === 'error' ? 'Errors' : 'Warnings' }}</div>
        <h2>{{ title || 'This page needs attention' }}</h2>
      </div>
      <span class="issue-count">{{ issue.count }}</span>
    </div>
    <ul class="issue-list">
      <li v-for="message in issue.messages" :key="message">{{ message }}</li>
    </ul>
  </section>
</template>

<style scoped>
.project-issue-banner {
  border-radius: 18px;
  padding: 1rem 1.15rem;
  margin-bottom: 1rem;
}

.severity-error {
  border: 1px solid rgba(248, 113, 113, 0.36);
  background: rgba(127, 29, 29, 0.18);
}

.severity-warning {
  border: 1px solid rgba(251, 191, 36, 0.34);
  background: rgba(120, 53, 15, 0.18);
}

.issue-banner-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.issue-kicker {
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.issue-banner-header h2 {
  margin: 0.2rem 0 0;
  color: var(--text-primary);
  font-size: 16px;
}

.issue-count {
  min-width: 2rem;
  border-radius: 999px;
  padding: 0.25rem 0.6rem;
  background: var(--surface-depth-card);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 800;
  text-align: center;
}

.issue-list {
  margin: 0.75rem 0 0;
  padding-left: 1.1rem;
  color: var(--text-primary);
}

.issue-list li + li {
  margin-top: 0.45rem;
}

.issue-list li::marker {
  color: var(--text-secondary);
}
</style>
