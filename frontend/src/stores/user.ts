import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const displayName = ref('李医生')
  const institution = ref('某三甲医院内分泌科')

  return {
    displayName,
    institution,
  }
})
