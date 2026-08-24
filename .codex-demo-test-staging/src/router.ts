import { createRouter, createWebHashHistory } from "vue-router";
import BlankPage from "./views/BlankPage.vue";
import ImportPage from "./views/ImportPage.vue";
import TermsPage from "./views/TermsPage.vue";
import BaseDataPage from "./views/BaseDataPage.vue";
import RulesPage from "./views/RulesPage.vue";
import QualityPage from "./views/QualityPage.vue";

export const pages = [
  { path: "/quality", name: "quality", label: "质控" },
  { path: "/rules", name: "rules", label: "规则库" },
  { path: "/terms", name: "terms", label: "术语库" },
  { path: "/base", name: "base", label: "基础数据" },
  { path: "/import", name: "import", label: "数据导入" },
  { path: "/check", name: "check", label: "规则自检" },
] as const;

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: "/quality" },
    ...pages.map(page => ({
      path: page.path,
      name: page.name,
      component: page.name === "import" ? ImportPage : page.name === "terms" ? TermsPage : page.name === "base" ? BaseDataPage : page.name === "rules" ? RulesPage : page.name === "quality" ? QualityPage : BlankPage,
      meta: { label: page.label },
    })),
  ],
});
