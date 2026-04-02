<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function goInspect() {
  router.push('/inspect/discovery')
}

function goDesign() {
  router.push('/design')
}
</script>

<template>
  <div class="studio-home">
    <div class="home-hero">
      <div class="hero-icon">&#x25C6;</div>
      <h1 class="hero-title">ANIP <span class="hero-accent">Studio</span></h1>
      <p class="hero-subtitle">Explore, inspect, and design ANIP-powered agent services</p>
    </div>

    <div class="entry-cards">
      <div class="entry-card" @click="goInspect">
        <div class="card-icon">&#x1F50D;</div>
        <h2 class="card-title">Inspect</h2>
        <p class="card-desc">Connect to an ANIP service to explore its protocol surfaces</p>
        <button class="card-btn" @click.stop="goInspect">Connect</button>
      </div>

      <div class="entry-card" @click="goDesign">
        <div class="card-icon">&#x1F3A8;</div>
        <h2 class="card-title">Design</h2>
        <p class="card-desc">Browse example packs to understand what glue your design still requires</p>
        <button class="card-btn card-btn-design" @click.stop="goDesign">Browse</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.studio-home {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 2rem;
  text-align: center;
}

.home-hero {
  margin-bottom: 3rem;
}

.hero-icon {
  font-size: 56px;
  color: var(--accent);
  margin-bottom: 1rem;
  opacity: 0.7;
}

.hero-title {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
  letter-spacing: -0.5px;
}

.hero-accent {
  color: var(--accent);
  font-weight: 500;
}

.hero-subtitle {
  font-size: 15px;
  color: var(--text-secondary);
  margin: 0;
  max-width: 440px;
  line-height: 1.6;
}

.entry-cards {
  display: flex;
  gap: 24px;
  max-width: 680px;
  width: 100%;
}

.entry-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 2rem 1.5rem;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all var(--transition);
  text-align: center;
}

.entry-card:hover {
  border-color: var(--accent);
  background: var(--bg-hover);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}

.card-icon {
  font-size: 36px;
  margin-bottom: 1rem;
}

.card-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.card-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 1.5rem;
  flex: 1;
}

.card-btn {
  height: 38px;
  padding: 0 28px;
  background: var(--accent);
  border: none;
  border-radius: var(--radius-sm);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition);
}

.card-btn:hover {
  background: var(--accent-hover);
}

.card-btn-design {
  background: var(--accent);
}

@media (max-width: 600px) {
  .entry-cards {
    flex-direction: column;
  }
}
</style>
