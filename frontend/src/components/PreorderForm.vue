<script setup lang="ts">
import { ref } from 'vue'
import { usePreorderStore } from '../stores/preorder'
import CourseSearch from './CourseSearch.vue'

interface PrefillCourse {
  course_id: number | null
  course_name: string
  course_location: string | null
}

const props = defineProps<{
  prefillCourse?: PrefillCourse
}>()

const preorder = usePreorderStore()
const emailInput = ref('')

async function onEmailSubmit() {
  const value = emailInput.value.trim()
  if (!value) {
    preorder.error = 'Enter your email to get on the list.'
    return
  }
  const ok = await preorder.submitEmail(value)
  if (ok && props.prefillCourse) {
    await preorder.submitCourse(props.prefillCourse)
  }
}

async function onCourseSelect(s: { course_id: number; course_name: string; course_location: string | null }) {
  await preorder.submitCourse(s)
}

async function onCourseFreeText(name: string) {
  await preorder.submitCourse({ course_id: null, course_name: name, course_location: null })
}
</script>

<template>
  <div class="w-full max-w-md mx-auto">
    <!-- Step: email -->
    <form
      v-if="preorder.step === 'email'"
      @submit.prevent="onEmailSubmit"
      class="flex flex-col sm:flex-row gap-2"
    >
      <input
        v-model="emailInput"
        type="email"
        required
        placeholder="you@golf.com"
        class="flex-1 px-4 py-3 bg-emerald-900/80 border border-emerald-700 rounded-xl text-white placeholder-emerald-600 focus:outline-none focus:border-emerald-400 focus:ring-1 focus:ring-emerald-400"
      />
      <button
        type="submit"
        :disabled="preorder.submitting"
        class="px-5 py-3 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-60 rounded-xl font-semibold text-emerald-950 transition-colors"
      >
        {{ preorder.submitting ? 'Saving...' : 'Preorder' }}
      </button>
    </form>

    <!-- Step: course (hidden when prefilled) -->
    <div v-else-if="preorder.step === 'course' && !props.prefillCourse" class="text-left">
      <p class="text-emerald-200 text-sm mb-2">
        You're on the list. Which course would you love to play split-the-tee on?
      </p>
      <CourseSearch @select="onCourseSelect" @free-text="onCourseFreeText" />
    </div>

    <!-- Step: done -->
    <div v-else class="text-center bg-emerald-900/50 border border-emerald-700/60 rounded-xl px-5 py-4">
      <p class="text-emerald-200 font-semibold">You're on the list. We'll be in touch.</p>
      <p class="text-emerald-400 text-xs mt-1">Tell a foursome — preorders pour faster than a fresh keg.</p>
    </div>

    <p v-if="preorder.error" class="text-red-300 text-sm mt-2 text-center">{{ preorder.error }}</p>
  </div>
</template>
