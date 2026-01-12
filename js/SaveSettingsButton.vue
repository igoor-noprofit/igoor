<template>
  <div class="save-settings-button">
    <button class="btn btn-secondary" @click="$emit('cancel')" :disabled="!hasChanges">
      {{ t('Cancel') }}
    </button>
    <button class="btn btn-primary" @click="$emit('save')" :disabled="!hasChanges">
      <span v-if="loading" class="loading-spinner"></span>
      {{ t('Save') }}
    </button>
  </div>
</template>

<script>
module.exports = {
  name: "SaveSettingsButton",
  props: {
    hasChanges: {
      type: Boolean,
      default: false,
    },
    loading: {
      type: Boolean,
      default: false,
    },
    t: {
      type: Function,
      default: (key) => key,
    },
  },
  emits: ['save', 'cancel'],
};
</script>

<style scoped>
.save-settings-button {
  display: flex;
  gap: 1rem;
}

.save-settings-button button {
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: #fff;
  animation: spin 0.8s linear infinite;
  margin-right: 0.5rem;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.save-settings-button button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
