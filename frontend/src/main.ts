import 'element-plus/dist/index.css';
import 'vxe-table/lib/style.css';
import './styles/theme.css';

import ElementPlus from 'element-plus';
import { createPinia } from 'pinia';
import VXETable from 'vxe-table';
import { createApp } from 'vue';

import App from './App.vue';
import router from './router';
import { useThemeStore } from './stores/theme';

const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
app.use(router);
app.use(ElementPlus);
app.use(VXETable);

useThemeStore(pinia).initialize();

app.mount('#app');
