import 'element-plus/dist/index.css';
import 'vxe-table/lib/style.css';

import ElementPlus from 'element-plus';
import { createPinia } from 'pinia';
import VXETable from 'vxe-table';
import { createApp } from 'vue';

import App from './App.vue';
import router from './router';

const app = createApp(App);

app.use(createPinia());
app.use(router);
app.use(ElementPlus);
app.use(VXETable);

app.mount('#app');
