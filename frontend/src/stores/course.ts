import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useCourseStore = defineStore('course', () => {
  const courses = ref<any[]>([])
  const selectedCourse = ref<any>(null)
  const courseData = ref<any>(null)
  const loading = ref(false)

  async function search(query: string) {
    if (!query.trim()) return
    loading.value = true
    try {
      const res = await fetch(`/api/v1/search?q=${encodeURIComponent(query)}`)
      const data = await res.json()
      courses.value = data.courses || []
    } finally {
      loading.value = false
    }
  }

  async function loadCourse(course: any) {
    selectedCourse.value = course
    loading.value = true
    try {
      const lat = course.location?.latitude
      const lng = course.location?.longitude
      let url = `/api/v1/course-holes?courseId=${course.id}`
      if (lat != null && lng != null) url += `&lat=${lat}&lng=${lng}`
      const res = await fetch(url)
      const data = await res.json()
      // Normalize snake_case API response to camelCase for frontend
      data.courseName = data.course_name || data.courseName || course.course_name
      data.fontHint = data.font_hint || null
      courseData.value = data
    } finally {
      loading.value = false
    }
  }

  return { courses, selectedCourse, courseData, loading, search, loadCourse }
})
