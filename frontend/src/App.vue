<template>
  <div class="min-h-screen flex flex-col">
    <nav class="bg-white shadow-sm py-4 sticky top-0 z-50">
      <div class="container mx-auto px-4 flex justify-between items-center gap-4 flex-wrap">
        <div class="flex items-center">
          <i class="fas fa-stethoscope text-2xl text-blue-600 mr-2"></i>
          <div>
            <span class="text-xl font-bold text-gray-800">CholecInsight</span>
            <p class="text-xs text-gray-500">面向腹腔镜胆囊切除术的外科培训与评估系统</p>
          </div>
        </div>
        <div class="flex space-x-4 text-sm">
          <router-link to="/" class="btn-secondary">
          <i class="fas fa-house mr-2"></i>首页</router-link>
        </div>
      </div>
    </nav>


    <main class="flex-1">
      <router-view />
    </main>

    <footer class="bg-gray-900 text-white py-6 mt-8">
      <div class="container mx-auto px-4 text-center text-gray-400 text-sm">
        © 2026 CholecInsight. 专注于数据驱动的外科见解。
      </div>
    </footer>
  </div>
</template>
