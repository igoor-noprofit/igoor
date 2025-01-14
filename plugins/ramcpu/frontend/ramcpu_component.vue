<template>
    <div class="ramcpu-plugin">
        <div class="usage-container">
            <div class="usage-item">
                <div class="label">RAM</div>
                <div class="progress-bar">
                    <div class="progress-total" :style="{ width: `${memoryPercent}%` }">
                        <div class="progress-app" :style="{ width: `${(memoryUsage / totalMemory) * 100}%` }"></div>
                    </div>
                    <div class="usage-text">
                        {{ (totalMemoryUsed / 1024).toFixed(1) }}GB/{{ (totalMemory / 1024).toFixed(1) }}GB
                    </div>
                </div>
            </div>
            <div class="usage-item">
                <div class="label">CPU</div>
                <div class="progress-bar">
                    <div class="progress-total" :style="{ width: `${totalCpuUsage}%` }">
                        <div class="progress-app" :style="{ width: `${cpuUsage}%` }"></div>
                    </div>
                    <div class="usage-text">
                        {{ totalCpuUsage.toFixed(1) }}%
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "ramcpu",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
            websocket: null,
            cpuUsage: 0.0,
            totalCpuUsage: 0.0,
            memoryUsage: 0.0,
            totalMemoryUsed: 0.0,
            totalMemory: 1,  // Default to 1 to avoid division by zero
            memoryPercent: 0.0
        };
    },
    methods: {
        handleIncomingMessage(event) {
            try {
                const data = JSON.parse(event.data);
                this.cpuUsage = data.cpu_usage;
                this.totalCpuUsage = data.total_cpu_usage;
                this.memoryUsage = data.memory_usage;
                this.totalMemoryUsed = data.total_memory_used;
                this.totalMemory = data.total_memory;
                this.memoryPercent = data.memory_percent;
            }
            catch(e){
                console.log('Error in RAMCPU data incoming');
            }
        }
    },
    created() {

    },
    beforeDestroy() {

    }
};
</script>
<style scoped>
.ramcpu-plugin {
    padding: 4px;
    min-width: 300px;
}

.usage-container {
    display: flex;
    flex-direction: row;
    gap: 12px;
    align-items: center;
}

.usage-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.label {
    font-size: 0.7em;
    color: #666;
    margin-bottom: -1px;
}

.progress-bar {
    height: 12px;
    background: #eee;
    border-radius: 2px;
    overflow: hidden;
    position: relative;
}

.progress-total {
    height: 100%;
    background: #2196F3;
    transition: width 0.3s ease;
}

.progress-app {
    height: 100%;
    background: #1976D2;
    transition: width 0.3s ease;
}

.usage-text {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: white;
    font-size: 0.7em;
    text-shadow: 0 0 2px rgba(0,0,0,0.5);
    white-space: nowrap;
}
</style>