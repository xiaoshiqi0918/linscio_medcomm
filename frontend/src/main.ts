import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// @ts-ignore - Element Plus 中文
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import VueViewer from 'v-viewer'
import 'viewerjs/dist/viewer.css'
import './styles/global.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.use(VueViewer)

app.mount('#app')
