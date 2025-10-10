<template>
  <div class="daily-settings container daily-plugin main">
    <div class="settings-actions">
      <button class="btn btn-secondary" @click="resetSettings" :disabled="!hasUnsavedChanges">{{ t('Cancel') }}</button>
      <div v-if="editingCategory" class="settings-breadcrumb">
        <button type="button" class="breadcrumb-link" @click="exitCategoryEdit">{{ t('Categories') }}</button>
        <span class="breadcrumb-separator">›</span>
        <span v-if="editingCategory && editingCategoryEditing" class="breadcrumb-current">
          <input ref="breadcrumbCategoryInput"
            v-model="editingCategoryNameInput"
            @blur="saveEditingCategoryBreadcrumb"
            @keyup.enter="saveEditingCategoryBreadcrumb"
            @keyup.esc="cancelEditingCategoryBreadcrumb"
            class="breadcrumb-current-input" />
        </span>
        <span v-else class="breadcrumb-current" @click="startEditingCategoryBreadcrumb">{{
            currentEditingCategoryName
          }}</span>
        <button v-if="editingCategory" type="button" class="delete-btn settings-delete-category-btn" @mousedown.stop
          @touchstart.stop @pointerdown.stop @click="deleteCurrentEditingCategory"
          aria-label="Delete category">{{ t('Delete category') }}</button>
      </div>
      <button v-if="!editingCategory && currentView === 'main'" class="btn btn-side btn-side-right"
        @click="switchToSecondaryView"><svg class="icon icon-l">
          <use xlink:href="/img/svgdefs.svg#icon-chevron_right" />
        </svg></button>
      <button v-if="!editingCategory && currentView === 'secondary'" class="btn btn-side btn-side-left"
        @click="switchToMainView"><svg class="icon icon-l">
          <use xlink:href="/img/svgdefs.svg#icon-chevron_left" />
        </svg></button>
      <button class="btn btn-primary" @click="saveSettings" :disabled="!hasUnsavedChanges">{{ t('Save') }}</button>
    </div>
    <div v-if="currentView === 'main'" class="options">
      <draggable v-model="mainCategories" group="categories" class="categories-row" :move="canDragCategory"
        :options="categoryDragOptions('main')" item-key="name">
        <template #item="{ element: category, index: catIdx }">
          <div :key="category.name" :class="categoryClasses('main', catIdx)">
            <div v-if="!isEditingCategory('main', catIdx)" class="category-header">
              <button v-if="!category.editing" class="switch-btn" @mousedown.stop @touchstart.stop @pointerdown.stop
                @click="toggleCategoryPlacement('main', catIdx)">
                <span class="arrow">➡</span></button>
              <span v-if="!category.editing" @click="editCategoryName('main', catIdx, $event)"
                :class="categoryTitleClasses('main', catIdx)"><span class="category_name-label">{{
                  category.name }}</span></span>
              <input v-else v-model="category.editName" :ref="categoryEditorRef('main', catIdx)" ref-in-for
                @blur="saveCategoryName('main', catIdx)" @keyup.enter="saveCategoryName('main', catIdx)" />
            </div>
            <button type="button" class="category-edit-btn" v-if="!isEditingCategory('main', catIdx)"
              @mousedown.stop @touchstart.stop @pointerdown.stop @click="startCategoryEdit('main', catIdx)">{{
                t('Edit') }}</button>
            <input v-if="isEditingCategory('main', catIdx)" class="add-item-input" v-model="category.newItem"
              @keyup.enter="addItem('main', catIdx)" v-bind:placeholder="t('+ Item')" />
            <draggable class="items-list" :class="{ 'items-list--empty': !category.itemsArr.length }"
              v-model="category.itemsArr" :group="'items'" :move="canDragItem"
              :options="itemDragOptions('main', catIdx)"
              item-key="key">
              <template #item="{ element: item, index: itemIdx }">
                <div :key="item.key" :class="itemRowClasses('main', catIdx, item)">
                  <div class="favorite-wrapper" v-if="isEditingCategory('main', catIdx)">
                    <button type="button" class="favorite-btn" :class="{ 'favorite-btn--active': item.fixed }"
                      :aria-pressed="item.fixed ? 'true' : 'false'" @mousedown.stop @touchstart.stop @pointerdown.stop
                      @click="toggleItemFixed('main', catIdx, itemIdx)">
                      <span v-if="item.fixed">★</span>
                      <span v-else>☆</span>
                    </button>
                  </div>
                  <button v-if="isEditingCategory('main', catIdx)" type="button"
                    :class="['item-handle', { 'item-handle--disabled': item.editing }]"
                    :aria-label="t('Reorder item')">⬍</button>
                  <span v-if="!item.editing" @pointerdown="handleItemTitlePointerDown('main', catIdx, itemIdx, $event)"
                    @click="editItemName('main', catIdx, itemIdx, $event)" :class="itemTitleClasses('main', catIdx)">{{
                      item.key }}</span>
                  <input v-else v-model="item.editName" :ref="itemEditorRef('main', catIdx, itemIdx)" ref-in-for
                    @blur="saveItemName('main', catIdx, itemIdx)"
                    @keyup.enter="saveItemName('main', catIdx, itemIdx)" />

                  <button v-if="isEditingCategory('main', catIdx)" class="delete-btn" @mousedown.stop @touchstart.stop
                    @pointerdown.stop @click="deleteItem('main', catIdx, itemIdx)">✕</button>
                </div>
              </template>
              <template #footer>
                <div v-if="!category.itemsArr.length" class="items-list__hint">{{ t('Drag item here') }}</div>
              </template>
            </draggable>
          </div>
        </template>
      </draggable>
      <div v-if="!editingCategory && mainCategories.length < 6" class="add-category-container">
        <input class="add-category-input" v-model="newMainCategory" @keyup.enter="addCategory('main')"
          v-bind:placeholder="t('+ Category')" />
      </div>
    </div>
    <div v-if="currentView === 'secondary'" class="options secondary">
      <draggable v-model="secondaryCategories" group="categories" class="categories-row" :move="canDragCategory"
        :options="categoryDragOptions('secondary')" item-key="name">
        <template #item="{ element: category, index: catIdx }">
          <div :key="category.name" :class="categoryClasses('secondary', catIdx)">
            <div v-if="!isEditingCategory('secondary', catIdx)" class="category-header">
              <button v-if="!category.editing" class="switch-btn" @mousedown.stop @touchstart.stop @pointerdown.stop
                @click="toggleCategoryPlacement('secondary', catIdx)"><span class="arrow">⬅</span></button>

              <span v-if="!category.editing" @click="editCategoryName('secondary', catIdx, $event)"
                :class="categoryTitleClasses('secondary', catIdx)"><span class="category_name-label">{{
                  category.name }}</span></span>
              <input v-else v-model="category.editName" :ref="categoryEditorRef('secondary', catIdx)" ref-in-for
                @blur="saveCategoryName('secondary', catIdx)" @keyup.enter="saveCategoryName('secondary', catIdx)" />
            </div>
            <button type="button" class="category-edit-btn" v-if="!isEditingCategory('secondary', catIdx)"
              @mousedown.stop @touchstart.stop @pointerdown.stop @click="startCategoryEdit('secondary', catIdx)">{{
                t('Edit') }}</button>
            <input v-if="isEditingCategory('secondary', catIdx)" class="add-item-input" v-model="category.newItem"
              @keyup.enter="addItem('secondary', catIdx)" v-bind:placeholder="t('+ Item')" />
            <draggable class="items-list" :class="{ 'items-list--empty': !category.itemsArr.length }"
              v-model="category.itemsArr" :group="'items'" :move="canDragItem"
              :options="itemDragOptions('secondary', catIdx)"
              item-key="key">
              <template #item="{ element: item, index: itemIdx }">
                <div :key="item.key" :class="itemRowClasses('secondary', catIdx, item)">

                  <div class="favorite-wrapper" v-if="isEditingCategory('secondary', catIdx)">
                    <button type="button" class="favorite-btn" :class="{ 'favorite-btn--active': item.fixed }"
                      :aria-pressed="item.fixed ? 'true' : 'false'" @mousedown.stop @touchstart.stop @pointerdown.stop
                      @click="toggleItemFixed('secondary', catIdx, itemIdx)">
                      <span v-if="item.fixed">★</span>
                      <span v-else>☆</span>
                    </button>
                  </div>

                  <button v-if="isEditingCategory('secondary', catIdx)" type="button"
                    :class="['item-handle', { 'item-handle--disabled': item.editing }]"
                    :aria-label="t('Reorder item')">☰</button>
                  <span class="itemTitle" v-if="!item.editing"
                    @pointerdown="handleItemTitlePointerDown('secondary', catIdx, itemIdx, $event)"
                    @click="editItemName('secondary', catIdx, itemIdx, $event)"
                    :class="itemTitleClasses('secondary', catIdx)">{{
                      item.key }}</span>
                  <input v-else v-model="item.editName" :ref="itemEditorRef('secondary', catIdx, itemIdx)" ref-in-for
                    @blur="saveItemName('secondary', catIdx, itemIdx)"
                    @keyup.enter="saveItemName('secondary', catIdx, itemIdx)" />

                  <button v-if="isEditingCategory('secondary', catIdx)" class="delete-btn" @mousedown.stop
                    @touchstart.stop @pointerdown.stop @click="deleteItem('secondary', catIdx, itemIdx)">✕</button>
                </div>
              </template>
              <template #footer>
                <div v-if="!category.itemsArr.length" class="items-list__hint">{{ t('Drag item here') }}</div>
              </template>
            </draggable>
          </div>
        </template>
      </draggable>
      <div v-if="!editingCategory && secondaryCategories.length < 6">
        <input class="add-category-input" v-model="newSecondaryCategory" @keyup.enter="addCategory('secondary')"
          v-bind:placeholder="t('+ Category')" />
      </div>
    </div>
    <transition name="dialog-fade">
      <div v-if="dialogVisible" class="dialog-backdrop" role="dialog" aria-modal="true"
        @click.self="handleDialogBackdrop">
        <div class="dialog-panel">
          <div class="dialog-message">{{ dialogMessage }}</div>
          <div class="dialog-actions">
            <button v-if="dialogMode === 'confirm'" class="dialog-btn dialog-btn--secondary"
              @click="handleDialogAction(false)">{{ t('Cancel') }}</button>
            <button class="dialog-btn dialog-btn--primary" @click="handleDialogAction(true)">{{ dialogMode === 'confirm'
              ?
              t('Confirm') : t('OK') }}</button>
          </div>
        </div>
      </div>
    </transition>
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
    document.querySelectorAll('.item-row input, .item-row button:not(.item-handle)').forEach(el => {
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
      originalSettings: null,
      dialogVisible: false,
      dialogMessage: '',
      dialogMode: 'alert',
      dialogResolve: null,
      editingCategory: null,
      editingCategoryEditing: false,
      editingCategoryNameInput: ''
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
    },
    currentEditingCategoryName() {
      const category = this.currentEditingCategory();
      return category ? category.name : '';
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
          this.exitCategoryEdit();
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
      this.exitCategoryEdit();
      this.currentView = 'secondary';
    },
    switchToMainView() {
      this.exitCategoryEdit();
      this.currentView = 'main';
    },
    categoryDragOptions(view) {
      const base = {
        animation: 150,
        direction: 'horizontal',
        handle: '.category_name-label',
        draggable: '.category-col',
        preventOnFilter: true
      };
      if (this.editingCategory && this.editingCategory.view === view) {
        return { ...base, filter: '.category_name-label' };
      }
      return { ...base, filter: '.category-header button, .category-edit-btn' };
    },
    startCategoryEdit(view, catIdx) {
      this.clearEditingStates();
      this.editingCategory = { view, index: catIdx };
      this.editingCategoryEditing = false;
      this.editingCategoryNameInput = '';
    },
    exitCategoryEdit() {
      if (!this.editingCategory) return;
      this.editingCategory = null;
      this.clearEditingStates();
      this.editingCategoryEditing = false;
      this.editingCategoryNameInput = '';
    },
    clearEditingStates() {
      const reset = cats => {
        cats.forEach(cat => {
          cat.editing = false;
          cat.editName = cat.name;
          cat.itemsArr.forEach(item => {
            item.editing = false;
            item.editName = item.key;
          });
        });
      };
      reset(this.mainCategories);
      reset(this.secondaryCategories);
    },
    isEditingCategory(view, catIdx) {
      return this.editingCategory && this.editingCategory.view === view && this.editingCategory.index === catIdx;
    },
    isOtherCategoryHidden(view, catIdx) {
      return this.editingCategory && !this.isEditingCategory(view, catIdx);
    },
    categoryTitleClasses(view, catIdx) {
      return {
        category_name: true,
        'category_name--editable': this.isEditingCategory(view, catIdx),
        'category_name--static': !this.isEditingCategory(view, catIdx)
      };
    },
    itemTitleClasses(view, catIdx) {
      return {
        itemTitle: true,
        'itemTitle--editable': this.isEditingCategory(view, catIdx),
        'itemTitle--draggable': !this.isEditingCategory(view, catIdx)
      };
    },
    itemRowClasses(view, catIdx, item) {
      return {
        'item-row': true,
        'fixed-item': item.fixed,
        'item-row--editing': this.isEditingCategory(view, catIdx)
      };
    },
    categoryClasses(view, catIdx) {
      return {
        'category-col': true,
        'category-col--expanded': this.isEditingCategory(view, catIdx),
        'category-col--hidden': this.isOtherCategoryHidden(view, catIdx)
      };
    },
    itemDragOptions(view, catIdx) {
      const editing = this.isEditingCategory(view, catIdx);
      return {
        animation: 150,
        handle: editing ? '.item-handle' : '.itemTitle',
        filter: editing ? '.itemTitle, .fixed-item, .favorite-btn, .delete-btn' : '.fixed-item, .favorite-btn, .delete-btn',
        preventOnFilter: true,
        draggable: '.item-row:not(.fixed-item)'
      };
    },
    normalizeEditingCategory() {
      if (!this.editingCategory) return;
      const list = this.editingCategory.view === 'main' ? this.mainCategories : this.secondaryCategories;
      if (!list[this.editingCategory.index]) {
        this.editingCategory = null;
        this.editingCategoryEditing = false;
        this.editingCategoryNameInput = '';
      }
    },
    currentEditingCategory() {
      if (!this.editingCategory) return null;
      const list = this.editingCategory.view === 'main' ? this.mainCategories : this.secondaryCategories;
      return list[this.editingCategory.index] || null;
    },
    async deleteCurrentEditingCategory() {
      if (!this.editingCategory) return;
      const { view, index } = this.editingCategory;
      await this.deleteCategory(view, index);
    },
    async toggleCategoryPlacement(view, catIdx) {
      const sourceArr = view === 'main' ? this.mainCategories : this.secondaryCategories;
      const targetArr = view === 'main' ? this.secondaryCategories : this.mainCategories;
      if (!sourceArr[catIdx]) return;
      if (targetArr.length >= 6) {
        await this.showDialog({ message: this.t('Maximum categories reached on the destination page.'), mode: 'alert' });
        return;
      }
      const [category] = sourceArr.splice(catIdx, 1);
      if (category) {
        category.editing = false;
        category.editName = category.name;
        targetArr.push(category);
        if (this.isEditingCategory(view, catIdx)) {
          this.editingCategory = null;
          this.editingCategoryEditing = false;
          this.editingCategoryNameInput = '';
        }
        this.normalizeEditingCategory();
      }
    },
    editCategoryName(view, catIdx, evt) {
      if (!this.isEditingCategory(view, catIdx)) return;
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
    async deleteCategory(view, catIdx) {
      const arr = view === 'main' ? this.mainCategories : this.secondaryCategories;
      const confirmed = await this.showDialog({
        message: this.t('Do you really want to delete this delete this category?'),
        mode: 'confirm'
      });
      if (confirmed) {
        const wasEditing = this.isEditingCategory(view, catIdx);
        arr.splice(catIdx, 1);
        if (wasEditing) {
          this.editingCategory = null;
          this.clearEditingStates();
          this.editingCategoryEditing = false;
          this.editingCategoryNameInput = '';
        } else {
          this.normalizeEditingCategory();
        }
      }
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
      if (!this.isEditingCategory(view, catIdx)) return;
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
    async deleteItem(view, catIdx, itemIdx) {
      const arr = view === 'main' ? this.mainCategories : this.secondaryCategories;
      const confirmed = await this.showDialog({
        message: this.t('Do you really want to delete this delete this item?'),
        mode: 'confirm'
      });
      if (confirmed) arr[catIdx].itemsArr.splice(itemIdx, 1);
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
    startEditingCategoryBreadcrumb() {
      if (!this.editingCategory || this.editingCategoryEditing) return;
      const category = this.currentEditingCategory();
      if (!category) return;
      this.editingCategoryNameInput = category.name;
      this.editingCategoryEditing = true;
      this.$nextTick(() => {
        const input = this.$refs.breadcrumbCategoryInput;
        if (input && typeof input.focus === 'function') {
          input.focus({ preventScroll: true });
          const length = input.value.length;
          if (typeof input.setSelectionRange === 'function') {
            input.setSelectionRange(length, length);
          }
        }
      });
    },
    cancelEditingCategoryBreadcrumb() {
      this.editingCategoryEditing = false;
      this.editingCategoryNameInput = '';
    },
    saveEditingCategoryBreadcrumb() {
      if (!this.editingCategory) {
        this.cancelEditingCategoryBreadcrumb();
        return;
      }
      const category = this.currentEditingCategory();
      if (!category) {
        this.cancelEditingCategoryBreadcrumb();
        return;
      }
      const newName = (this.editingCategoryNameInput || '').trim();
      const list = this.editingCategory.view === 'main' ? this.mainCategories : this.secondaryCategories;
      const index = this.editingCategory.index;
      if (!newName || list.some((cat, i) => i !== index && cat.name === newName)) {
        this.cancelEditingCategoryBreadcrumb();
        return;
      }
      if (newName !== category.name) {
        category.name = newName;
        category.editName = newName;
      }
      this.editingCategoryEditing = false;
      this.editingCategoryNameInput = '';
    },
    handleItemTitlePointerDown(view, catIdx, itemIdx, evt) {
      if (!evt) return;
      if (!this.isEditingCategory(view, catIdx)) return;
      const arr = view === 'main' ? this.mainCategories : this.secondaryCategories;
      const item = arr?.[catIdx]?.itemsArr?.[itemIdx];
      if (!item || item.editing) return;
      evt.stopPropagation();
      evt.preventDefault();
    },
    showDialog({ message, mode = 'alert' }) {
      return new Promise(resolve => {
        this.dialogMessage = message;
        this.dialogMode = mode;
        this.dialogVisible = true;
        this.dialogResolve = resolve;
      });
    },
    handleDialogAction(confirmed) {
      if (!this.dialogResolve) {
        this.dialogVisible = false;
        return;
      }
      const resolve = this.dialogResolve;
      this.dialogResolve = null;
      this.dialogVisible = false;
      const result = this.dialogMode === 'confirm' ? !!confirmed : true;
      resolve(result);
      this.dialogMessage = '';
    },
    handleDialogBackdrop() {
      if (this.dialogMode === 'confirm') {
        this.handleDialogAction(false);
      } else {
        this.handleDialogAction(true);
      }
    },
    canDragItem(evt) {
      const original = evt && evt.originalEvent;
      if (!original) return true;
      const type = original.type;
      if (!['mousedown', 'touchstart', 'pointerdown'].includes(type)) return true;
      const target = original.target;
      if (!target) return true;
      if (this.editingCategory && !target.closest('.item-handle')) return false;
      if (target.closest('.fixed-item')) return false;
      if (target.closest('.delete-btn')) return false;
      if (target.closest('input')) return false;
      if (target.closest('.favorite-btn')) return false;
      return true;
    },
    canDragCategory(evt) {
      const original = evt && evt.originalEvent;
      if (!original) return true;
      if (this.editingCategory) return false;
      const type = original.type;
      if (!['mousedown', 'touchstart', 'pointerdown'].includes(type)) return true;
      const target = original.target;
      if (!target) return true;
      if (target.closest('.switch-btn')) return false;
      if (target.closest('.delete-btn')) return false;
      if (target.closest('.category-edit-btn')) return false;
      if (!target.closest('.category_name-label')) return false;
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
        this.exitCategoryEdit();
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
  /* border:1px solid #0f0; */
}


.options {
  display: flex;
  margin: 0;
  padding: 0;
}

.itemTitle {
  flex-grow: 1;
  font-size: 0.95rem;
  height: 50px;
  display: flex;
  align-items: center;
  padding: 0 0.75rem;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  transition: background 0.2s ease;
}

.itemTitle--draggable {
  cursor: grab;
  user-select: none;
}

.itemTitle--draggable:active {
  cursor: grabbing;
}

.itemTitle--editable {
  cursor: text;
  background: rgba(255, 255, 255, 0.08);
  user-select: text;
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  height: 100%;
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
  width: 100%;
}


.category-col {
  background-color: #28373b;
  border-radius: 8px;
  display: flex;
  flex: 1 1 0;
  min-width: 0;
  flex-direction: column;
  justify-content: flex-start;
  gap: 0.5rem;
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.35);
}

.category-col--hidden {
  display: none;
}

.category-col--expanded {
  flex: 0 0 50%;
  margin: 5px auto 25px auto;
}

.category-col--expanded .items-list {
  gap: 0.5rem;
}

.category-header {
  display: flex;
  align-items: center;
  margin-bottom: 0.5rem;
  gap: 0.5rem;
  cursor:grab;
}

.category-header--expanded {
  justify-content: space-between;
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

.category-edit-btn {
  align-self: flex-start;
  padding: 0.35rem 0.9rem;
  border-radius: 6px;
  border: none;
  background: #1abc9c;
  color: #102026;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s ease, opacity 0.15s ease;
  width: 100%;
}

.category-edit-btn:hover {
  transform: translateY(-1px);
}

.category-edit-btn:focus-visible {
  outline: 2px solid #f1f4f6;
  outline-offset: 2px;
}

.category_name--editable {
  cursor: text;
  background: rgba(255, 255, 255, 0.08);
}

.category_name--static {
  cursor: default;
  user-select: none;
}

.add-category-container {
  /* border: 1px dashed #00f; */
  display: flex;
  width: auto !important;
  justify-content: center;
}


.category_name {
  background: #28373b;
  padding: 0.45rem 0.75rem;
  border-radius: 6px;
  font-size: 0.95rem;
  flex-grow: 1;
}

.category_name-label {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  cursor: grab;
}

.category_name--editable .category_name-label {
  cursor: text;
}

.category_name--static .category_name-label:active {
  cursor: grabbing;
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
  background: #407d1c;
  border: none;
  color: #eee;
  cursor: pointer;
  padding: 0 !important;
  height: 50px;
  width: 50px;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 0 !important;
}

.arrow {
  font-size: 39px;
  transform: translateY(-3px)
}

.item-row {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  margin: 0.3rem 0 0 0;
  background: #2f535b;
  border-radius: 4px;
  padding: 0 0.5rem;
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
  z-index: 20;
  position: relative;
  width: 100% !important;
}

.favorite-wrapper {
  width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 0.5rem 0 0;
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
  filter: grayscale(0.85);
}

.favorite-btn span {
  color: rgba(255, 255, 255, 0.35);
}

button.favorite-btn--active {
  background: #216776;
  transform: scale(1.05);
  filter: grayscale(0);
}

.favorite-btn--active span {
  color: #fff;
}

.item-handle {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.75);
  font-size: 1.2rem;
  cursor: grab !important;
  transition: background 0.2s ease, color 0.2s ease;
}

.item-handle:hover {
  background: rgba(255, 255, 255, 0.12);
}

.item-handle:active {
  cursor: grabbing;
}

.item-handle--disabled {
  pointer-events: none;
  opacity: 0.55;
  cursor: default;
}

.item-handle:focus-visible {
  outline: 2px solid #1abc9c;
  outline-offset: 2px;
}

.item-row--editing {
  gap: 2rem;
  background: #305a63;
}

.add-item-input,
.add-category-input {

  padding: 0.25rem;
  border-radius: 4px;
  /* border: 1px solid #34495e; */
  background: #1a2329;
  color: #fff;
  margin-left: 10px;
  margin-right: 10px;
}

input.add-item-input {
  margin-top: 0.5rem;
  width: auto;
  max-width: none;
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
  background-color: #55595c;
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
  justify-content: space-between;
  padding: 0 10px;
}

.settings-actions button {
  display: flex;
  align-items: center;
  justify-content: center;
}

.settings-actions .btn-secondary {
  background-color: #ccc;
}

button.settings-delete-category-btn {
  background: #a66355;
  border: none;
  height: 40px !important;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  cursor: pointer;
  width: auto;
  margin-left: 100px;
}

.settings-breadcrumb {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.95rem;
  color: #f1f4f6;
  flex: 1;
  justify-content: center;
}

.breadcrumb-link {
  background: none;
  border: none;
  color: #1abc9c;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.breadcrumb-link:focus-visible {
  outline: 2px solid #1abc9c;
  outline-offset: 2px;
}

.item-row:not(.item-row--editing) {
  padding: 0;
}

.item-row.fixed-item:not(.item-row--editing) {
  background: #216776;
}

.item-row.fixed-item {
  font-weight: bold;
}

.breadcrumb-separator {
  opacity: 0.7;
}

.breadcrumb-current {
  font-weight: 600;
  text-transform: uppercase;
  cursor: text;
}

.breadcrumb-current-input {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 4px;
  color: #f1f4f6;
  padding: 0.1rem 0.35rem;
  text-transform: uppercase;
  font-weight: 600;
  min-width: 160px;
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
  justify-content: center;
  display: flex;
  align-items: center;
}

button.btn-side {
  height: 50px;
}

.btn-side-right,
.btn-side-left {
  position: relative;
}

.btn-secondary {
  background-color: #ccc;
}

.dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 4000;
}

.dialog-panel {
  background: #1f2c31;
  border: 1px solid #3c4b52;
  border-radius: 12px;
  padding: 1.5rem;
  width: min(90vw, 360px);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.35);
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.dialog-message {
  font-size: 1rem;
  line-height: 1.5;
  color: #f1f4f6;
  text-align: center;
}

.dialog-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: center;
}

.dialog-btn {
  min-width: 110px;
  padding: 0.55rem 1rem;
  border-radius: 6px;
  border: none;
  font-size: 0.95rem;
  cursor: pointer;
  transition: transform 0.15s ease, opacity 0.15s ease;
}

.dialog-btn:hover {
  transform: translateY(-1px);
}

.dialog-btn--primary {
  background: #1abc9c;
  color: #102026;
}

button.dialog-btn--secondary {
  background: #55595c;
  color: #f1f4f6;
}

.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: opacity 0.2s ease;
}

.dialog-fade-enter-from,
.dialog-fade-leave-to {
  opacity: 0;
}
</style>