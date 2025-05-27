<template>
    <div class="daily-needs-plugin-settings">
        <div class="categories-container">
            <div 
                v-for="(categoryData, categoryName) in formData" 
                :key="categoryName"
                class="category-section"
            >
                <!-- Category Header -->
                <div class="category-header">
                    <input 
                        type="text" 
                        :value="categoryName"
                        @input="renameCategory(categoryName, $event.target.value)"
                        class="category-name-input"
                        placeholder="Category name"
                    />
                    <button 
                        @click="deleteCategory(categoryName)"
                        class="delete-category-btn"
                        title="Delete category"
                    >
                        ×
                    </button>
                </div>

                <!-- Items List -->
                <div 
                    class="items-list"
                    @drop="onDrop($event, categoryName)"
                    @dragover.prevent
                    @dragenter.prevent
                >
                    <div
                        v-for="(itemData, itemName) in categoryData"
                        :key="itemName"
                        class="item-row"
                        :class="{ 'fixed-item': itemData.fixed }"
                        draggable="true"
                        @dragstart="onDragStart($event, categoryName, itemName)"
                    >
                        <div class="drag-handle">⋮⋮</div>
                        
                        <input 
                            type="text" 
                            :value="itemName"
                            @input="renameItem(categoryName, itemName, $event.target.value)"
                            class="item-name-input"
                            placeholder="Item name"
                        />
                        
                        <div class="item-controls">
                            <label class="freq-control">
                                Freq:
                                <input 
                                    type="number" 
                                    :value="itemData.freq || 0"
                                    @input="updateItemFreq(categoryName, itemName, parseInt($event.target.value) || 0)"
                                    min="0"
                                    class="freq-input"
                                />
                            </label>
                            
                            <label class="fixed-control">
                                <input 
                                    type="checkbox" 
                                    :checked="itemData.fixed || false"
                                    @change="toggleItemFixed(categoryName, itemName)"
                                />
                                Fixed
                            </label>
                            
                            <button 
                                @click="deleteItem(categoryName, itemName)"
                                class="delete-item-btn"
                                title="Delete item"
                            >
                                ×
                            </button>
                        </div>
                    </div>
                    
                    <!-- Add New Item Button -->
                    <button 
                        @click="addNewItem(categoryName)"
                        class="add-item-btn"
                    >
                        + Add Item
                    </button>
                </div>
            </div>
        </div>
        
        <!-- Add New Category Button -->
        <button 
            @click="addNewCategory"
            class="add-category-btn"
        >
            + Add Category
        </button>
        
        <!-- Save Button -->
        <button 
            @click="updateSettings"
            class="save-btn"
        >
            SAVE PLUGIN SETTINGS
        </button>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "dailySettings",
    props: {
        initialSettings: Object
    },
    mixins: [BasePluginComponent],
    data() {
        return {
            formData: {},
            draggedItem: null
        };
    },
    watch: {
        initialSettings: {
            handler(newVal) {
                if (newVal && Array.isArray(newVal) && newVal.length > 0) {
                    // Extract the first object from the array
                    this.formData = JSON.parse(JSON.stringify(newVal[0]));
                } else if (newVal && typeof newVal === 'object' && !Array.isArray(newVal)) {
                    this.formData = JSON.parse(JSON.stringify(newVal));
                } else {
                    this.formData = {};
                }
            },
            immediate: true,
            deep: true
        }
    },
    methods: {
        renameCategory(oldName, newName) {
            if (newName && newName !== oldName && !this.formData[newName]) {
                const categoryData = this.formData[oldName];
                this.$set(this.formData, newName, categoryData);
                this.$delete(this.formData, oldName);
            }
        },
        
        deleteCategory(categoryName) {
            if (confirm(`Are you sure you want to delete the "${categoryName}" category?`)) {
                this.$delete(this.formData, categoryName);
            }
        },
        
        addNewCategory() {
            const newName = prompt('Enter category name:');
            if (newName && !this.formData[newName]) {
                this.$set(this.formData, newName, {});
            }
        },
        
        renameItem(categoryName, oldItemName, newItemName) {
            if (newItemName && newItemName !== oldItemName && !this.formData[categoryName][newItemName]) {
                const itemData = this.formData[categoryName][oldItemName];
                this.$set(this.formData[categoryName], newItemName, itemData);
                this.$delete(this.formData[categoryName], oldItemName);
            }
        },
        
        deleteItem(categoryName, itemName) {
            if (confirm(`Are you sure you want to delete "${itemName}"?`)) {
                this.$delete(this.formData[categoryName], itemName);
            }
        },
        
        addNewItem(categoryName) {
            const newName = prompt('Enter item name:');
            if (newName && !this.formData[categoryName][newName]) {
                this.$set(this.formData[categoryName], newName, {
                    freq: 0,
                    fixed: false
                });
            }
        },
        
        updateItemFreq(categoryName, itemName, freq) {
            this.$set(this.formData[categoryName][itemName], 'freq', freq);
        },
        
        toggleItemFixed(categoryName, itemName) {
            const currentFixed = this.formData[categoryName][itemName].fixed || false;
            this.$set(this.formData[categoryName][itemName], 'fixed', !currentFixed);
        },
        
        onDragStart(event, categoryName, itemName) {
            this.draggedItem = {
                categoryName,
                itemName,
                data: this.formData[categoryName][itemName]
            };
            event.dataTransfer.effectAllowed = 'move';
        },
        
        onDrop(event, targetCategoryName) {
            event.preventDefault();
            
            if (!this.draggedItem) return;
            
            const { categoryName: sourceCategoryName, itemName, data } = this.draggedItem;
            
            // Don't move fixed items
            if (data.fixed) {
                this.draggedItem = null;
                return;
            }
            
            // Remove from source
            this.$delete(this.formData[sourceCategoryName], itemName);
            
            // Add to target (find unique name if needed)
            let targetItemName = itemName;
            let counter = 1;
            while (this.formData[targetCategoryName][targetItemName]) {
                targetItemName = `${itemName}_${counter}`;
                counter++;
            }
            
            this.$set(this.formData[targetCategoryName], targetItemName, data);
            
            this.draggedItem = null;
        }
    }
};
</script>

<style scoped>
.daily-needs-plugin-settings {
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
    font-family: Arial, sans-serif;
}

.categories-container {
    margin-bottom: 20px;
}

.category-section {
    border: 2px solid #ddd;
    border-radius: 8px;
    margin-bottom: 20px;
    background: #f9f9f9;
}

.category-header {
    display: flex;
    align-items: center;
    padding: 15px;
    background: #e9e9e9;
    border-bottom: 1px solid #ddd;
    border-radius: 6px 6px 0 0;
}

.category-name-input {
    flex: 1;
    padding: 8px 12px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 16px;
    font-weight: bold;
    background: white;
}

.delete-category-btn {
    margin-left: 10px;
    padding: 5px 10px;
    background: #ff6b6b;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 18px;
    font-weight: bold;
}

.delete-category-btn:hover {
    background: #ff5252;
}

.items-list {
    padding: 15px;
    min-height: 60px;
}

.item-row {
    display: flex;
    align-items: center;
    padding: 12px;
    margin-bottom: 8px;
    background: white;
    border: 1px solid #ddd;
    border-radius: 6px;
    transition: all 0.2s ease;
    cursor: move;
}

.item-row:hover {
    border-color: #007bff;
    box-shadow: 0 2px 8px rgba(0,123,255,0.1);
}

.fixed-item {
    border-color: #28a745;
    background: #f8fff9;
    transform: scale(1.02);
    box-shadow: 0 2px 12px rgba(40,167,69,0.2);
}

.fixed-item .drag-handle {
    color: #ccc;
    cursor: not-allowed;
}

.drag-handle {
    margin-right: 10px;
    color: #666;
    font-weight: bold;
    cursor: grab;
    user-select: none;
}

.drag-handle:active {
    cursor: grabbing;
}

.item-name-input {
    flex: 1;
    padding: 8px 12px;
    border: 1px solid #ddd;
    border-radius: 4px;
    margin-right: 15px;
}

.item-controls {
    display: flex;
    align-items: center;
    gap: 15px;
}

.freq-control {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 14px;
}

.freq-input {
    width: 60px;
    padding: 4px 8px;
    border: 1px solid #ddd;
    border-radius: 4px;
}

.fixed-control {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 14px;
}

.delete-item-btn {
    padding: 4px 8px;
    background: #ff6b6b;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
}

.delete-item-btn:hover {
    background: #ff5252;
}

.add-item-btn {
    width: 100%;
    padding: 10px;
    background: #007bff;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    margin-top: 10px;
}

.add-item-btn:hover {
    background: #0056b3;
}

.add-category-btn {
    width: 100%;
    padding: 15px;
    background: #28a745;
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 16px;
    margin-bottom: 20px;
}

.add-category-btn:hover {
    background: #218838;
}

.save-btn {
    width: 100%;
    padding: 15px;
    background: #17a2b8;
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 16px;
    font-weight: bold;
}

.save-btn:hover {
    background: #138496;
}
</style>