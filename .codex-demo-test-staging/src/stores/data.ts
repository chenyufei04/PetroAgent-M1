import { defineStore } from "pinia";
import { ruleRecords, termRecords } from "../data/seed";

export const useDataStore = defineStore("data", {
  state: () => ({ termCount: termRecords.length, ruleCount: ruleRecords.length }),
  actions: {
    addImported(terms: number, rules: number) {
      this.termCount += terms;
      this.ruleCount += rules;
    },
  },
});
