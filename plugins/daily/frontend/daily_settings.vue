<template>
  <div class="daily-settings container daily-plugin main">
    <div class="settings-actions">
      <button class="btn btn-secondary" @click="resetSettings" :disabled="!hasUnsavedChanges">{{ t('Cancel') }}</button>
      <button v-if="currentView === 'main'" class="btn btn-side btn-side-right" @click="switchToSecondaryView"><svg
          class="icon icon-l">
          <use xlink:href="/img/svgdefs.svg#icon-chevron_right" />
        </svg></button>
      <button v-if="currentView === 'secondary'" class="btn btn-side btn-side-left" @click="switchToMainView"><svg
          class="icon icon-l">
          <use xlink:href="/img/svgdefs.svg#icon-chevron_left" />
        </svg></button>
      <button class="btn btn-primary" @click="saveSettings" :disabled="!hasUnsavedChanges">{{ t('Save') }}</button>
    </div>
    <div v-if="currentView === 'main'" class="options">
      <draggable v-model="mainCategories" group="categories" class="categories-row"
        :move="canDragCategory"
        :options="{ animation: 150, direction: 'horizontal', handle: '.category_name', filter: '.category-header button', preventOnFilter: true }" item-key="name">
        <template #item="{ element: category, index: catIdx }">
          <div :key="category.name" class="options-col category-col bordered">
            <div class="category-header">
              <button class="switch-btn" @mousedown.stop @touchstart.stop @pointerdown.stop @click="toggleCategoryPlacement('main', catIdx)">⇄</button>
              <span v-if="!category.editing" @click="editCategoryName('main', catIdx, $event)" class="category_name">{{
                category.name }}</span>
              <input v-else v-model="category.editName" :ref="categoryEditorRef('main', catIdx)" ref-in-for
                @blur="saveCategoryName('main', catIdx)"
                @keyup.enter="saveCategoryName('main', catIdx)" />

              <button class="delete-btn" @mousedown.stop @touchstart.stop @pointerdown.stop @click="deleteCategory('main', catIdx)">✕</button>
            </div>
            <draggable class="items-list" :class="{ 'items-list--empty': !category.itemsArr.length }" v-model="category.itemsArr" :group="'items'"
              :move="canDragItem"
              :options="{ animation: 150, handle: '.itemTitle', filter: '.fixed-item, .favorite-btn, .delete-btn', preventOnFilter: true, draggable: '.item-row:not(.fixed-item)' }"
              item-key="key">
              <template #item="{ element: item, index: itemIdx }">
                <div :key="item.key" class="item-row" :class="{ 'fixed-item': item.fixed }">

                  <div class="favorite-wrapper">
                    <button type="button" class="favorite-btn" :class="{ 'favorite-btn--active': item.fixed }"
                      :aria-pressed="item.fixed ? 'true' : 'false'"
                      @mousedown.stop @touchstart.stop @pointerdown.stop
                      @click="toggleItemFixed('main', catIdx, itemIdx)">
                      <span v-if="item.fixed">★</span>
                      <span v-else>☆</span>
                    </button>
                  </div>
                  <!--button class="switch-btn">✣</button-->
                  <span class="itemTitle" v-if="!item.editing" @click="editItemName('main', catIdx, itemIdx, $event)">{{
                    item.key }}</span>
                  <input v-else v-model="item.editName" :ref="itemEditorRef('main', catIdx, itemIdx)" ref-in-for
                    @blur="saveItemName('main', catIdx, itemIdx)"
                    @keyup.enter="saveItemName('main', catIdx, itemIdx)" />



                  <!--span class="drag-handle" v-if="!item.fixed">☰</span-->
                  <button class="delete-btn" @mousedown.stop @touchstart.stop @pointerdown.stop @click="deleteItem('main', catIdx, itemIdx)">✕</button>
                </div>
              </template>
              <template #footer>
                <div v-if="!category.itemsArr.length" class="items-list__hint">{{ t('Drag item here') }}</div>
              </template>
            </draggable>
            <input class="add-item-input" v-model="category.newItem" @keyup.enter="addItem('main', catIdx)"
              v-bind:placeholder="t('+ Item')" />
          </div>
        </template>
      </draggable>
      <div v-if="mainCategories.length < 6" class="add-category-container">
        <input class="add-category-input" v-model="newMainCategory" @keyup.enter="addCategory('main')"
          v-bind:placeholder="t('+ Category')" />
      </div>
    </div>
    <div v-if="currentView === 'secondary'" class="options secondary">
      <draggable v-model="secondaryCategories" group="categories" class="categories-row"
        :move="canDragCategory"
        :options="{ animation: 150, direction: 'horizontal', handle: '.category_name', filter: '.category-header button', preventOnFilter: true }" item-key="name">
        <template #item="{ element: category, index: catIdx }">
          <div :key="category.name" class="options-col category-col bordered">
            <div class="category-header">
              <button class="switch-btn" @mousedown.stop @touchstart.stop @pointerdown.stop @click="toggleCategoryPlacement('secondary', catIdx)">⇄</button>

              <span v-if="!category.editing" @click="editCategoryName('secondary', catIdx, $event)" class="category_name">{{
                category.name }}</span>
              <input v-else v-model="category.editName" :ref="categoryEditorRef('secondary', catIdx)" ref-in-for
                @blur="saveCategoryName('secondary', catIdx)"
                @keyup.enter="saveCategoryName('secondary', catIdx)" />
              <button class="delete-btn" @mousedown.stop @touchstart.stop @pointerdown.stop @click="deleteCategory('secondary', catIdx)">✕</button>
            </div>
            <draggable class="items-list" :class="{ 'items-list--empty': !category.itemsArr.length }" v-model="category.itemsArr" :group="'items'"
              :move="canDragItem"
              :options="{ animation: 150, handle: '.itemTitle', filter: '.fixed-item, .favorite-btn, .delete-btn', preventOnFilter: true, draggable: '.item-row:not(.fixed-item)' }"
              item-key="key">
              <template #item="{ element: item, index: itemIdx }">
                <div :key="item.key" class="item-row" :class="{ 'fixed-item': item.fixed }">

                  <div class="favorite-wrapper">
                    <button type="button" class="favorite-btn" :class="{ 'favorite-btn--active': item.fixed }"
                      :aria-pressed="item.fixed ? 'true' : 'false'"
                      @mousedown.stop @touchstart.stop @pointerdown.stop
                      @click="toggleItemFixed('secondary', catIdx, itemIdx)">
                      <span v-if="item.fixed">★</span>
                      <span v-else>☆</span>
                    </button>
                  </div>

                  <span class="itemTitle" v-if="!item.editing" @click="editItemName('secondary', catIdx, itemIdx, $event)">{{
                    item.key }}</span>
                  <input v-else v-model="item.editName" :ref="itemEditorRef('secondary', catIdx, itemIdx)" ref-in-for
                    @blur="saveItemName('secondary', catIdx, itemIdx)"
                    @keyup.enter="saveItemName('secondary', catIdx, itemIdx)" />

                  <!--span class="drag-handle" v-if="!item.fixed">☰</span-->
                  <button class="delete-btn" @mousedown.stop @touchstart.stop @pointerdown.stop @click="deleteItem('secondary', catIdx, itemIdx)">✕</button>
                </div>
              </template>
              <template #footer>
                <div v-if="!category.itemsArr.length" class="items-list__hint">{{ t('Drag item here') }}</div>
              </template>
            </draggable>
            <input class="add-item-input" v-model="category.newItem" @keyup.enter="addItem('secondary', catIdx)"
              v-bind:placeholder="t('+ Item')" />
          </div>
        </template>
      </draggable>
      <div v-if="secondaryCategories.length < 6">
        <input class="add-category-input" v-model="newSecondaryCategory" @keyup.enter="addCategory('secondary')"
          v-bind:placeholder="t('+ Category')" />
      </div>
    </div>
  </div>
</template>

<script>

import BasePluginComponent from '/js/BasePluginComponent.js';

module.exports = {
  name: "dailySettings",
  mixins: [BasePluginComponent],
  components: { draggable: window['vuedraggable'] },
  props: {
    initialSettings: Object
  },
  mounted() {
    console.warn("SETTINGS LANG =" + this.lang);
    // Always extract needs from initialSettings, whether it's an object or array
    let needs = this.initialSettings && this.initialSettings.needs ? this.initialSettings.needs : this.initialSettings;
    if (needs && Array.isArray(needs) && needs.length > 1) {
      this.mainCategories = this.processCategories(needs[0]);
      this.secondaryCategories = this.processCategories(needs[1]);
      this.originalSettings = JSON.parse(JSON.stringify(needs));
    }
    document.querySelectorAll('.item-row input, .item-row button').forEach(el => {
      el.addEventListener('touchstart', (e) => e.stopPropagation(), { passive: false });
      el.addEventListener('mousedown', (e) => e.stopPropagation());
    });
  },
  data() {
    return {
      currentView: 'main',
      mainCategories: [],
      secondaryCategories: [],
      newMainCategory: '',
      newSecondaryCategory: '',
      originalSettings: null
    };
  },
  computed: {
    hasUnsavedChanges() {
      // Helper to convert categories to backend format for comparison
      const toObj = cats => {
        const obj = {};
        cats.forEach(cat => {
          const items = {};
          cat.itemsArr.forEach(item => {
            items[item.key] = { fixed: item.fixed, freq: item.freq };
          });
          obj[cat.name] = items;
        });
        return obj;
      };
      const current = [toObj(this.mainCategories), toObj(this.secondaryCategories)];
      return JSON.stringify(current) !== JSON.stringify(this.originalSettings);
    }
  },
  watch: {
    initialSettings: {
      handler(newVal) {
        let needs = newVal && newVal.needs ? newVal.needs : newVal;
        if (needs && Array.isArray(needs) && needs.length > 1) {
          this.mainCategories = this.processCategories(needs[0]);
          this.secondaryCategories = this.processCategories(needs[1]);
          this.originalSettings = JSON.parse(JSON.stringify(needs));
        }
      },
      immediate: true,
      deep: true
    }
  },
  methods: {
    processCategories(data) {
      console.warn('Processing categories:', data);
      return Object.entries(data).map(([name, items]) => ({
        name,
        editName: name,
        editing: false,
        newItem: '',
        itemsArr: Object.entries(items).map(([key, val]) => ({
          key,
          editName: key,
          editing: false,
          fixed: val.fixed || false,
          freq: val.freq || 0
        }))
      }));
    },
    switchToSecondaryView() {
      this.currentView = 'secondary';
    },
    switchToMainView() {
      this.currentView = 'main';
    },
    toggleCategoryPlacement(view, catIdx) {
      const sourceArr = view === 'main' ? this.mainCategories : this.secondaryCategories;
      const targetArr = view === 'main' ? this.secondaryCategories : this.mainCategories;
      if (!sourceArr[catIdx]) return;
      if (targetArr.length >= 6) {
        alert(this.t('Maximum categories reached on the destination page.'));
        return;
      }
      const [category] = sourceArr.splice(catIdx, 1);
      if (category) {
        category.editing = false;
        category.editName = category.name;
        targetArr.push(category);
      }
    },
    editCategoryName(view, catIdx, evt) {
      if (evt) {
        evt.stopPropagation();
      }
      const arr = view === 'main' ? this.mainCategories : this.secondaryCategories;
      arr[catIdx].editing = true;
      arr[catIdx].editName = arr[catIdx].name;
      this.$nextTick(() => {
        setTimeout(() => {
          const refKey = this.categoryEditorRef(view, catIdx);
          const inputRef = this.$refs[refKey];
          const input = Array.isArray(inputRef) ? inputRef[0] : inputRef;
          if (input) {
            input.focus({ preventScroll: true });
            const length = input.value.length;
            input.setSelectionRange(length, length);
          }
        }, 0);
      });
    },
    saveCategoryName(view, catIdx) {
      const arr = view === 'main' ? this.mainCategories : this.secondaryCategories;
      const newName = arr[catIdx].editName.trim();
      if (newName && !arr.some((c, i) => i !== catIdx && c.name === newName)) {
        arr[catIdx].name = newName;
        arr[catIdx].editing = false;
      }
    },
    deleteCategory(view, catIdx) {
      const arr = view === 'main' ? this.mainCategories : this.secondaryCategories;
      if (confirm(this.t('Do you really want to delete this delete this category?'))) arr.splice(catIdx, 1);
    },
    addCategory(view) {
      const arr = view === 'main' ? this.mainCategories : this.secondaryCategories;
      const newCat = view === 'main' ? this.newMainCategory.trim() : this.newSecondaryCategory.trim();
      if (newCat && !arr.some(c => c.name === newCat)) {
        arr.push({ name: newCat, editName: newCat, editing: false, newItem: '', itemsArr: [] });
        if (view === 'main') this.newMainCategory = '';
        else this.newSecondaryCategory = '';
      }
    },
    editItemName(view, catIdx, itemIdx, evt) {
      if (evt) {
        evt.stopPropagation();
      }
      const arr = view === 'main' ? this.mainCategories : this.secondaryCategories;
      arr[catIdx].itemsArr[itemIdx].editing = true;
      arr[catIdx].itemsArr[itemIdx].editName = arr[catIdx].itemsArr[itemIdx].key;
      this.$nextTick(() => {
        setTimeout(() => {
          const refKey = this.itemEditorRef(view, catIdx, itemIdx);
          const inputRef = this.$refs[refKey];
          const input = Array.isArray(inputRef) ? inputRef[0] : inputRef;
          if (input) {
            input.focus({ preventScroll: true });
            const length = input.value.length;
            input.setSelectionRange(length, length);
          }
        }, 0);
      });
    },
    itemEditorRef(view, catIdx, itemIdx) {
      return `item-editor-${view}-${catIdx}-${itemIdx}`;
    },
    categoryEditorRef(view, catIdx) {
      return `category-editor-${view}-${catIdx}`;
    },
    saveItemName(view, catIdx, itemIdx) {
      const arr = view === 'main' ? this.mainCategories : this.secondaryCategories;
      const item = arr[catIdx].itemsArr[itemIdx];
      const newName = item.editName.trim();
      if (newName && !arr[catIdx].itemsArr.some((it, i) => i !== itemIdx && it.key === newName)) {
        item.key = newName;
        item.editing = false;
      }
    },
    deleteItem(view, catIdx, itemIdx) {
      const arr = view === 'main' ? this.mainCategories : this.secondaryCategories;
      if (confirm(this.t('Do you really want to delete this delete this item?'))) arr[catIdx].itemsArr.splice(itemIdx, 1);
    },
    addItem(view, catIdx) {
      const arr = view === 'main' ? this.mainCategories : this.secondaryCategories;
      const newItem = arr[catIdx].newItem.trim();
      if (newItem && !arr[catIdx].itemsArr.some(it => it.key === newItem)) {
        arr[catIdx].itemsArr.push({ key: newItem, editName: newItem, editing: false, fixed: false, freq: 0 });
        arr[catIdx].newItem = '';
      }
    },
    toggleItemFixed(view, catIdx, itemIdx) {
      const arr = view === 'main' ? this.mainCategories : this.secondaryCategories;
      const item = arr?.[catIdx]?.itemsArr?.[itemIdx];
      if (item) {
        item.fixed = !item.fixed;
      }
    },
    canDragItem(evt) {
      const original = evt && evt.originalEvent;
      if (!original) return true;
      const type = original.type;
      if (!['mousedown', 'touchstart', 'pointerdown'].includes(type)) return true;
      const target = original.target;
      if (!target) return true;
      if (target.closest('.fixed-item')) return false;
      if (target.closest('.delete-btn')) return false;
      if (target.closest('input')) return false;
      if (target.closest('.favorite-btn')) return false;
      return true;
    },
    canDragCategory(evt) {
      const original = evt && evt.originalEvent;
      if (!original) return true;
      const type = original.type;
      if (!['mousedown', 'touchstart', 'pointerdown'].includes(type)) return true;
      const target = original.target;
      if (!target) return true;
      if (target.closest('.switch-btn')) return false;
      if (target.closest('.delete-btn')) return false;
      if (!target.closest('.category_name')) return false;
      return true;
    },
    saveSettings() {
      // Convert categories/items back to backend format
      const toObj = cats => {
        const obj = {};
        cats.forEach(cat => {
          const items = {};
          cat.itemsArr.forEach(item => {
            items[item.key] = { fixed: item.fixed, freq: item.freq };
          });
          obj[cat.name] = items;
        });
        return obj;
      };
      const payload = [toObj(this.mainCategories), toObj(this.secondaryCategories)];
      this.originalSettings = JSON.parse(JSON.stringify(payload));
      let plugin_name = this.$options.name;
      if (plugin_name.endsWith("Settings")) {
        plugin_name = plugin_name.substring(0, plugin_name.length - "Settings".length);
      }
      window.pywebview.api.trigger_hook_sync("custom_save_settings", {
        plugin_name: plugin_name,
        settings: payload
      });
      console.log('Settings saved:', payload);
    },
    resetSettings() {
      if (this.originalSettings) {
        this.mainCategories = this.processCategories(this.originalSettings[0]);
        this.secondaryCategories = this.processCategories(this.originalSettings[1]);
      }
      else {
        console.warn('No original settings to reset to.');
      }
    }
  }
};
</script>

<style scoped>
.daily-settings {
  width: 100vw;
  /* border:1px solid #0f0; */
}


.options {
  display: flex;
  margin: 0;
  padding: 0;
  /* border: 1px solid #0f0; */
}

.itemTitle {
  flex-grow: 1;
  font-size: 1rem;
  cursor: grab;
  height: 50px;
  display: flex;
  align-items: center;
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-height: 3rem;
}

.items-list--empty {
  border: 1px dashed rgba(255, 255, 255, 0.3);
  border-radius: 4px;
  padding: 0.75rem;
  align-items: center;
  justify-content: center;
}

.items-list__hint {
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
}


.categories-row {
  display: flex;
  flex-direction: row;
  box-sizing: border-box;
  flex-wrap: wrap;
  /* border: 1px solid #f00; */
  gap: 0.7rem;
}


.category-col {
  background-color: #1e2223;
  border: 2px solid #2c3e50;
  border-radius: 8px;
  /* padding: 0.4rem; */
  justify-content: space-between;
  display: flex;
  flex: 1 1 0;
  border: 1px solid #ff0;
  min-width: 0;
  flex-direction: column;
  justify-content: flex-start;
}

.category-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
  gap: 0.5rem;

}

.category-header input {
  flex: 1;
  height: 46px;
  border-radius: 4px;
  border: 1px solid #4a5c60;
  background: #1f2c31;
  color: #fff;
  padding: 0 0.75rem;
  text-transform: uppercase;
}

.add-category-container {
  /* border: 1px dashed #00f; */
  display: flex;

  justify-content: center;
}


.category_name {
  background: #28373b;
  padding: 6px 12px;
  /* border-radius: 4px; */
  cursor: pointer;
  font-size: 1.1vw;
}

.category-header span {
  text-transform: uppercase;
}

button.delete-btn {
  background: #a66355 !important;
  border: none;
  font-size: 1.2em;
  cursor: pointer;
  height: 50px !important;
  width: 50px;
}

button.switch-btn {
  background: #eee;
  border: none;
  color: #1abc9c;
  font-size: 1.2em;
  cursor: pointer;
  padding: 7px 10px !important;
  height: 50px;
  width: 50px;
}

.item-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0.5rem 0 0 0;
  background: #2f535b;
  border-radius: 4px;
  justify-content: space-between;
  /* padding: 0.25rem 0.5rem; */
  text-align: left;
  height: 50px;
}

.item-row input {
  flex: 1;
  height: 40px;
  border-radius: 4px;
  border: 1px solid #4a5c60;
  background: #1f2c31;
  color: #fff;
  padding: 0 0.75rem;
}

.favorite-wrapper {
  width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 1rem 0 0;
}

.favorite-btn {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: #394a50;
  font-size: 1.8rem;
  line-height: 1;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.favorite-btn span {
  color: rgba(255, 255, 255, 0.35);
}

.favorite-btn--active {
  background: #f1c40f;
  transform: scale(1.05);
}

.favorite-btn--active span {
  color: #fff;
}

.add-item-input,
.add-category-input {
  margin-top: 0.5rem;
  padding: 0.25rem;
  border-radius: 4px;
  /* border: 1px solid #34495e; */
  background: #1a2329;
  color: #fff;
}

.switch {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
}

.switch input {
  display: none;
}

.item-row label,
.item-row .delete-btn {
  position: relative;
}

/*
.item-row label::before,
.item-row .delete-btn::before {
  content: '';
  position: absolute;
  top: -12px;
  bottom: -12px;
  left: -12px;
  right: -12px;

}
  /* This pseudo-element extends the clickable area */

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #ccc;
  border-radius: 20px;
  transition: .4s;
  width: 35px;
}

.switch input:checked+.slider {
  background-color: #2196F3;
}

.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 2px;
  bottom: 2px;
  background-color: white;
  border-radius: 50%;
  transition: .4s;
}

.switch input:checked+.slider:before {
  transform: translateX(16px);
}

.drag-handle {
  cursor: grab;
  color: #aaa;
  font-size: 1.2em;
  margin-left: 0.5em;
}

.settings-actions {
  margin: 10px 0 20px 0;
  display: flex;
  gap: 1rem;
  justify-content: space-around;
}

.settings-actions button {
  display: flex;
  align-items: center;
  justify-content: center;
}

.settings-actions .btn-secondary {
  background-color: #ccc;
}

.item-row[data-draggable="true"],
.category-col[data-draggable="true"] .category-header {
  cursor: grab;
}

.fixed-item {
  pointer-events: auto;
  opacity: 1;
  font-size: 1.2rem;
  /*
  padding-top: 14px;
  padding-bottom: 14px;
  */
}

.onboarding.plugin .item-row label {
  /* margin: 10px 0 6px 0 */
  margin: 0;
}

button.delete-btn {
  padding: 8px;
  justify-content: center;
  display: flex;
  align-items: center;
}

.btn-side-right,
.btn-side-left {
  position: relative;
}

.btn-secondary {
  background-color: #ccc;
}
</style>