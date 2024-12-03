<template>
    <div class="notification-plugin">
        <div v-for="(notification, index) in notifications" :key="index">
            <div class="card" :class="notification.plugin">
                <div class="card-body">
                    <p class="card-text">{{ notification.msg }}</p>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

module.exports = {
    name: "notification",
    mixins: [BasePluginComponent],
    data() {
        return {
            notifications: [],
            notificationDuration: 5000 // Duration in milliseconds (e.g., 5000ms = 5 seconds)
        }
    },
    methods: {
        handleIncomingNotification(event) {
            console.log("Custom notification handler in NOTIFICATION component:", event.data);
            const data = JSON.parse(event.data);
            console.table(data);
            this.notifications.unshift(data); // Add new notification to the beginning

            // Set a timeout to remove the notification after the specified duration
            setTimeout(() => {
                this.notifications.pop(); // Remove the oldest notification
            }, this.notificationDuration);
        }
    }
};
</script>

<style scoped>
.notification-plugin {
    display: flex;
    flex-direction: column;
}

.card-body {
    padding: 6px;
}
</style>