<template>
  <Sidebar v-if="auth.isAuthenticated" />
  <router-view />
</template>

<script setup>
import { useAuthStore } from './stores/auth'
import Sidebar from './components/Sidebar.vue'
const auth = useAuthStore()
auth.init()
</script>
