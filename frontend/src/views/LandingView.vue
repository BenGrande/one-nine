<script setup lang="ts">
import { useHead } from '@unhead/vue'
import PreorderForm from '../components/PreorderForm.vue'

const heroSrc = '/hero.jpg'
const showcaseSrc = '/showcase.jpg'

const steps = [
  {
    title: 'One glass, nine holes',
    body: 'Each glass is etched with nine holes of a real course — fairway, rough, hazards, the works.',
  },
  {
    title: 'Two pints per glass',
    body: 'The front half of the glass tracks the first four or five holes. Refill, and the back half tracks the rest.',
  },
  {
    title: 'Drink to your score',
    body: 'Par? Drink to par. Bogey? Half-glass. Birdie? Bottoms up. The glass keeps score.',
  },
]

const organizationLd = {
  '@context': 'https://schema.org',
  '@type': 'Organization',
  name: 'Split the Tee',
  url: 'https://www.splitthetee.com/',
  logo: 'https://www.splitthetee.com/splitthetee.svg',
  sameAs: [],
  description: "Pint glasses etched with real golf courses. You've heard of split the G. This is split the Tee.",
}

const websiteLd = {
  '@context': 'https://schema.org',
  '@type': 'WebSite',
  name: 'Split the Tee',
  url: 'https://www.splitthetee.com/',
  potentialAction: {
    '@type': 'SearchAction',
    target: 'https://www.splitthetee.com/products?q={search_term_string}',
    'query-input': 'required name=search_term_string',
  },
}

useHead({
  title: 'Split the Tee — Drink your favorite golf course',
  meta: [
    {
      name: 'description',
      content: "You've heard of split the G. This is split the Tee. Pint glasses etched with real golf courses — drink to your score.",
    },
    { property: 'og:title', content: 'Split the Tee — Drink your favorite golf course' },
    {
      property: 'og:description',
      content: "You've heard of split the G. This is split the Tee. Pint glasses etched with real golf courses.",
    },
    { property: 'og:image', content: 'https://www.splitthetee.com/hero.jpg' },
    { property: 'og:url', content: 'https://www.splitthetee.com/' },
    { property: 'og:type', content: 'website' },
    { name: 'twitter:card', content: 'summary_large_image' },
  ],
  link: [{ rel: 'canonical', href: 'https://www.splitthetee.com/' }],
  script: [
    { type: 'application/ld+json', innerHTML: JSON.stringify(organizationLd) },
    { type: 'application/ld+json', innerHTML: JSON.stringify(websiteLd) },
  ],
})
</script>

<template>
  <div class="min-h-screen bg-emerald-950 text-white">
    <!-- Nav -->
    <header class="absolute top-0 inset-x-0 z-30 px-6 py-4 flex items-center justify-center">
      <img
        src="/splitthetee.svg"
        alt="Split the Tee"
        class="h-12 sm:h-16 w-auto"
        style="filter: brightness(0) invert(1)"
      />
    </header>

    <!-- Hero -->
    <section class="relative min-h-[100svh] flex items-center">
      <img
        :src="heroSrc"
        alt="Engraved Split the Tee pint glass on a wooden table overlooking a golf course"
        class="absolute inset-0 w-full h-full object-cover"
      />
      <div class="absolute inset-0 bg-gradient-to-b from-emerald-950/70 via-emerald-950/40 to-emerald-950"></div>

      <div class="relative z-10 px-6 pt-24 pb-16 max-w-3xl mx-auto text-center">
        <p class="uppercase tracking-[0.2em] text-emerald-300 text-xs sm:text-sm mb-4">
          Etched-glass golf scoring
        </p>
        <h1 class="text-4xl sm:text-6xl font-bold leading-tight mb-4">
          You've heard of split the G.
          <span class="block text-emerald-300">This is split the Tee.</span>
        </h1>
        <p class="text-emerald-100/90 text-base sm:text-lg mb-8 max-w-xl mx-auto">
          Your favorite course, etched into a set of pint glasses. Nine holes a glass, two pints a glass —
          score by where the beer line lands.
        </p>
        <PreorderForm />
        <p class="text-emerald-300/70 text-xs mt-3">
          Limited first run. Be the first to hear when it ships.
        </p>
      </div>
    </section>

    <!-- How it works -->
    <section class="px-6 py-20 max-w-5xl mx-auto">
      <div class="text-center mb-12">
        <h2 class="text-3xl sm:text-4xl font-bold mb-3">How it pours</h2>
        <p class="text-emerald-200/80 max-w-xl mx-auto">
          A drinking game with the soul of a real round. Nine holes a glass. Two pints a glass. One winner.
        </p>
      </div>
      <div class="grid sm:grid-cols-3 gap-6">
        <div
          v-for="(step, i) in steps"
          :key="step.title"
          class="bg-emerald-900/40 border border-emerald-800/50 rounded-2xl p-6"
        >
          <div class="w-9 h-9 rounded-full bg-emerald-500 text-emerald-950 font-bold flex items-center justify-center mb-4">
            {{ i + 1 }}
          </div>
          <h3 class="text-lg font-semibold mb-2">{{ step.title }}</h3>
          <p class="text-emerald-100/80 text-sm leading-relaxed">{{ step.body }}</p>
        </div>
      </div>
    </section>

    <!-- Showcase -->
    <section class="px-6 py-20 bg-emerald-900/30 border-y border-emerald-800/40">
      <div class="max-w-5xl mx-auto grid md:grid-cols-2 gap-10 items-center">
        <img
          :src="showcaseSrc"
          alt="Pint glass etched with a single golf hole layout, half full of beer on a wooden table at sunrise"
          class="rounded-2xl shadow-2xl w-full h-auto object-cover aspect-[3/4]"
        />
        <div>
          <p class="uppercase tracking-[0.2em] text-emerald-300 text-xs mb-3">
            Your course, your glass
          </p>
          <h2 class="text-3xl sm:text-4xl font-bold mb-4">
            Every fairway, every hazard.
          </h2>
          <p class="text-emerald-100/85 text-base mb-6">
            Pebble. Augusta. The muni you grew up on. Each glass is etched with a real hole layout —
            fairways, bunkers, water — so the beer line tracks your round.
          </p>
          <ul class="space-y-2 text-emerald-100/85 text-sm">
            <li class="flex gap-2"><span class="text-emerald-400">•</span> 9 holes per glass · 2 pints per glass</li>
            <li class="flex gap-2"><span class="text-emerald-400">•</span> Built from real course geometry</li>
            <li class="flex gap-2"><span class="text-emerald-400">•</span> Score lines etched at par, bogey, double</li>
            <li class="flex gap-2"><span class="text-emerald-400">•</span> Dishwasher safe. Hangover not included.</li>
          </ul>
        </div>
      </div>
    </section>

    <!-- Bottom CTA -->
    <section class="px-6 py-24 text-center">
      <h2 class="text-3xl sm:text-4xl font-bold mb-3">Get on the list.</h2>
      <p class="text-emerald-200/80 max-w-md mx-auto mb-8">
        Drop your email. We'll ask which course you'd want first, then ping you the moment we open preorders.
      </p>
      <PreorderForm />
    </section>

    <footer class="px-6 py-10 border-t border-emerald-900/60 text-center text-emerald-500 text-xs">
      <p>&copy; Split the Tee. You've heard of split the G. This is split the Tee.</p>
    </footer>
  </div>
</template>
