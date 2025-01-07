<template>
    <div class="daily container daily-plugin" v-if="appview == 'daily'">
        <div v-if="currentView === 'main'" class="categories-grid">
            <div v-for="(category, index) in mainCategories" :key="index" class="category-column">
                <h3 class="category-title">{{ translateCategory(category.name) }}</h3>
                <div class="cards-container">
                    <div v-for="(item, key) in category.items" :key="key" class="card"
                        :class="{ 'card-large': item.freq >= 8, 'card-small': item.freq < 8 }"
                        @click="handleCardClick(category.name, key, item)">
                        {{ translateItem(key) }}
                    </div>
                </div>
            </div>

            <!-- Navigation Arrow -->
            <button class="nav-arrow" @click="switchToSecondaryView">
                <span class="arrow-icon">→</span>
            </button>
        </div>

        <!-- Secondary Categories View -->
        <div v-else class="categories-grid">
            <div v-for="(category, index) in secondaryCategories" :key="index" class="category-column">
                <h3 class="category-title">{{ translateCategory(category.name) }}</h3>
                <div class="cards-container">
                    <div v-for="(item, key) in category.items" :key="key" class="card"
                        :class="{ 'card-large': item.freq >= 8, 'card-small': item.freq < 8 }"
                        @click="handleCardClick(category.name, key, item)">
                        {{ translateItem(key) }}
                    </div>
                </div>
            </div>
            <!-- Back Arrow -->
            <button class="nav-arrow back" @click="switchToMainView">
                <span class="arrow-icon">←</span>
            </button>
        </div>
        <div v-else></div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

module.exports = {
    name: "daily",
    mixins: [BasePluginComponent],
    data() {
        return {
            currentView: 'main',
            dailyData: [],
            mainCategories: [],
            secondaryCategories: []
        };
    },
    mounted() {
        console.log('DAILY MOUNTED');
        this.sendMsgToBackend({ socket: "ready" });
    },
    methods: {
        async $_abandonConversation() {
            try {
                this.sendMsgToBackend({ "action": "abandon_conversation" });

            } catch (error) {
                console.error("Error abandoning conversation:", error);
            }
        },
        handleIncomingMessage(event) {
            console.log('DAILY receiving message');
            try {
                console.log(event.data);
                const data = JSON.parse(event.data);
                console.log(data);
                if (data.dailyData) {
                    this.dailyData = data.dailyData;
                    this.processCategories();
                }
            } catch (error) {
                console.error('Error processing message:', error);
            }
        },
        processCategories() {
            // Process first array item for main categories
            this.mainCategories = this.extractCategories(this.dailyData[0]);
            // Process second array item for secondary categories
            this.secondaryCategories = this.extractCategories(this.dailyData[1]);
        },
        extractCategories(data) {
            return Object.entries(data).map(([name, items]) => ({
                name,
                items
            }));
        },
        translateCategory(category) {
            // Add your translation logic here
            return category;
        },
        translateItem(item) {
            // Add your translation logic here
            return item;
        },
        handleCardClick(category, item, data) {
            this.sendMsgToBackend({
                action: 'cardClicked',
                category,
                item,
                data
            });
        },
        switchToSecondaryView() {
            this.currentView = 'secondary';
        },
        switchToMainView() {
            this.currentView = 'main';
        }
    }
};
</script>

<style scoped>
.daily-plugin {
    margin: 10px 0;
    flex-direction: row;
    display: flex;
    border: 1px solid #f00;
}

.daily-container {
    padding: 1rem;
    height: 100%;
    width: 100%;
}

.categories-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 1rem;
    position: relative;
    height: 100%;
}

.category-column {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.category-title {
    color: #fff;
    text-transform: uppercase;
    font-size: 0.8rem;
    margin-bottom: 0.5rem;
}

.cards-container {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.card {
    background-color: #2F4F4F;
    color: white;
    border-radius: 8px;
    cursor: pointer;
    transition: background-color 0.2s;
    padding: 0.8rem;
}

.card:hover {
    background-color: #3D6363;
}

.card-large {
    font-size: 1.1rem;
    min-height: 3rem;
}

.card-small {
    font-size: 0.9rem;
    min-height: 2.5rem;
}

.nav-arrow {
    position: absolute;
    right: -1rem;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    color: white;
    font-size: 2rem;
    cursor: pointer;
    padding: 1rem;
}

.nav-arrow.back {
    left: -1rem;
    right: auto;
}

.arrow-icon {
    display: inline-block;
    transition: transform 0.2s;
}

.nav-arrow:hover .arrow-icon {
    transform: scale(1.2);
}
</style>