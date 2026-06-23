<template>
  <!-- Renders nothing when there is nothing to show, so the component is safe
       to drop into any settings row even when help text is absent. -->
  <span v-if="text || url" class="help-popover" ref="root">
    <button
      type="button"
      class="help-trigger"
      :class="{ 'is-open': open }"
      :aria-label="resolvedAriaLabel"
      :aria-expanded="open"
      @click="toggle"
    >
      <i class="ph-light ph-question"></i>
    </button>

    <transition name="help-popover">
      <div
        v-if="open"
        class="help-bubble"
        role="dialog"
        :aria-label="resolvedAriaLabel"
      >
        <p v-if="text" class="help-text">{{ text }}</p>
        <a
          v-if="url"
          :href="url"
          target="_blank"
          rel="noopener noreferrer"
          class="help-link"
        >
          {{ commonT('Learn more') }} →
        </a>
      </div>
    </transition>
  </span>
</template>

<script>
module.exports = {
  name: 'HelpPopover',
  props: {
    // Already-translated help text. The caller resolves it via its own t().
    text: {
      type: String,
      default: '',
    },
    // Fully resolved docs URL. The caller resolves it per language via t()
    // because docs paths differ fully between languages.
    url: {
      type: String,
      default: '',
    },
    t: {
      type: Function,
      default: (key) => key,
    },
    lang: {
      type: String,
      default: 'en_EN',
    },
    ariaLabel: {
      type: String,
      default: '',
    },
  },
  data() {
    return {
      open: false,
      commonTranslations: {},
    };
  },
  computed: {
    resolvedAriaLabel() {
      return this.ariaLabel || this.commonT('More information');
    },
  },
  watch: {
    lang() {
      this.loadCommonTranslations();
    },
  },
  mounted() {
    this.loadCommonTranslations();
    document.addEventListener('click', this.onDocumentClick);
    document.addEventListener('keydown', this.onKeydown);
  },
  beforeDestroy() {
    document.removeEventListener('click', this.onDocumentClick);
    document.removeEventListener('keydown', this.onKeydown);
  },
  methods: {
    toggle() {
      this.open = !this.open;
    },
    // Dismiss when a click happens outside this component.
    onDocumentClick(event) {
      if (!this.open) return;
      if (this.$refs.root && !this.$refs.root.contains(event.target)) {
        this.open = false;
      }
    },
    onKeydown(event) {
      if (this.open && event.key === 'Escape') {
        this.open = false;
      }
    },
    async loadCommonTranslations() {
      try {
        const lang = this.lang || 'en_EN';
        if (lang === 'en_EN') {
          // English has no common file (keys are their own values), per project convention.
          this.commonTranslations = {};
          return;
        }
        const url = `/locales/${lang}/common_${lang}.json`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Could not load ${url}`);
        this.commonTranslations = await response.json();
      } catch (e) {
        console.warn('Failed to load common translations for HelpPopover:', e);
        this.commonTranslations = {};
      }
    },
    commonT(key) {
      if (this.commonTranslations[key]) {
        return this.commonTranslations[key];
      }
      if (typeof this.t === 'function') {
        return this.t(key);
      }
      return key;
    },
  },
};
</script>

<style scoped>
.help-popover {
  position: relative;
  display: inline-flex;
  vertical-align: middle;
}

.help-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  margin-left: 8px;
  padding: 0;
  border: none;
  background: transparent;
  color: #9bb4b4;
  cursor: pointer;
  border-radius: 50%;
  transition: background 0.2s, color 0.2s;
}

.help-trigger:hover,
.help-trigger:focus-visible {
  background: rgba(255, 255, 255, 0.08);
  color: #e0e0e0;
  outline: none;
}

.help-trigger.is-open {
  background: rgba(0, 149, 192, 0.18);
  color: #fff;
}

.help-trigger i {
  /* Fixed size so the icon stays clearly visible regardless of the
     (often small) inherited label font-size. Big target for eye-tracking. */
  font-size: 18px;
  line-height: 1;
}

.help-bubble {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  z-index: 9999;
  min-width: 220px;
  max-width: 320px;
  padding: 10px 12px;
  background: #1d1d1d;
  border: 1px solid #333;
  border-radius: 8px;
  color: #ddd;
  font-size: 0.85em;
  line-height: 1.4;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.45);
}

.help-text {
  margin: 0 0 6px 0;
  white-space: normal;
}

.help-text:last-child {
  margin-bottom: 0;
}

.help-link {
  display: inline-block;
  color: #0095c0;
  text-decoration: none;
  font-weight: 600;
}

.help-link:hover {
  text-decoration: underline;
}

.help-popover-enter-active,
.help-popover-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.help-popover-enter-from,
.help-popover-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
