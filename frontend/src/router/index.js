import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Analysis from '../views/Analysis.vue'

const routes = [
  { path: '/', name: 'Home', component: Home },
  { path: '/analysis', name: 'Analysis', component: Analysis },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
