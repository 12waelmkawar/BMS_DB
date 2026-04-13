import { createApp } from 'vue'
import { createPinia } from 'pinia'
import VueECharts from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'

import App from './App.vue'
import router from './router'
import './style.css'

use([
  CanvasRenderer,
  BarChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
])

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.component('v-chart', VueECharts)
app.mount('#app')
