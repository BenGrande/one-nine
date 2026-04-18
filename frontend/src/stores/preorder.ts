import { defineStore } from 'pinia'
import { ref } from 'vue'

export type PreorderStep = 'email' | 'course' | 'done'

export interface CourseSelection {
  course_id: number | null
  course_name: string
  course_location: string | null
}

export const usePreorderStore = defineStore('preorder', () => {
  const step = ref<PreorderStep>('email')
  const preorderId = ref<string | null>(null)
  const email = ref('')
  const submitting = ref(false)
  const error = ref('')

  async function submitEmail(value: string): Promise<boolean> {
    error.value = ''
    submitting.value = true
    try {
      const res = await fetch('/api/v1/preorders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: value }),
      })
      if (!res.ok) {
        error.value = res.status === 422
          ? 'Please enter a valid email.'
          : 'Something went wrong. Try again.'
        return false
      }
      const data = await res.json()
      preorderId.value = data.id
      email.value = data.email
      step.value = data.course_name ? 'done' : 'course'
      return true
    } catch {
      error.value = 'Network error. Try again.'
      return false
    } finally {
      submitting.value = false
    }
  }

  async function submitCourse(selection: CourseSelection): Promise<boolean> {
    if (!preorderId.value) return false
    error.value = ''
    submitting.value = true
    try {
      const res = await fetch(`/api/v1/preorders/${preorderId.value}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(selection),
      })
      if (!res.ok) {
        error.value = 'Could not save your course. Try again.'
        return false
      }
      step.value = 'done'
      return true
    } catch {
      error.value = 'Network error. Try again.'
      return false
    } finally {
      submitting.value = false
    }
  }

  function reset() {
    step.value = 'email'
    preorderId.value = null
    email.value = ''
    error.value = ''
  }

  return { step, preorderId, email, submitting, error, submitEmail, submitCourse, reset }
})
