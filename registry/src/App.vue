<script setup lang="ts">
import { dateTimeDisplayMode, dateTimeDisplayOptions } from './datetime'
import { ANIP_SPEC_VERSION, REGISTRY_VERSION } from './version'
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <div class="topbar-title">
        <router-link class="brand" to="/packages">ANIP Registry</router-link>
        <span class="version-pill">Registry {{ REGISTRY_VERSION }}</span>
        <span class="version-pill neutral">ANIP {{ ANIP_SPEC_VERSION }}</span>
      </div>
      <nav class="topnav" aria-label="Registry sections">
        <router-link to="/packages">Packages</router-link>
        <router-link to="/templates">Templates</router-link>
        <router-link to="/publisher">Publisher</router-link>
        <router-link to="/admin">Admin</router-link>
      </nav>
      <span class="subtitle">Portable package records, receipts, and provenance</span>
      <label class="datetime-selector">
        <span>Time display</span>
        <select v-model="dateTimeDisplayMode">
          <option
            v-for="option in dateTimeDisplayOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </select>
      </label>
    </header>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>
