<template>
    <div class="rag-settings form-grid main">
        <input
            type="file"
            ref="fileInput"
            multiple
            accept=".txt,.md,.pdf"
            style="display: none"
            @change="handleFileSelect"
        />

        <div v-if="errorMessage" class="error-message">
            <span>⚠</span>
            <span>{{ errorMessage }}</span>
        </div>

        <div v-if="successMessage" class="success-message">
            <span>✓</span>
            <span>{{ successMessage }}</span>
        </div>

        <!-- Left Column: Document List -->
        <div class="rag-left">
            <div class="documents-header">
                <h3>{{ t('Documents') }}</h3>
                <button class="btn-refresh" @click="refreshDocuments" :disabled="isUploading" :title="t('Refresh')">
                    ⟳
                </button>
            </div>

            <div class="search-container">
                <input
                    type="text"
                    v-model="searchTerm"
                    class="search-input"
                    :placeholder="t('Search documents...')"
                    :disabled="isUploading"
                />
            </div>

            <div class="documents-list-container">
                <div v-if="isLoading" class="loading-state">
                    <div class="spinner"></div>
                    <span>{{ t('Loading documents...') }}</span>
                </div>

                <div v-else-if="filteredDocuments.length === 0" class="empty-state">
                    <span class="empty-icon">📁</span>
                    <p>{{ documents.length === 0 ? t('No documents uploaded yet') : t('No matching documents') }}</p>
                </div>

                <div v-else class="documents-list">
                    <div v-for="doc in filteredDocuments" :key="doc.id" class="document-item" :class="{'document-item--always-send': doc.always_send}">
                        <div class="document-info">
                            <div class="document-title">{{ doc.title }}</div>
                            <div class="document-date">{{ formatDate(doc.created_at) }}</div>
                        </div>
                        <div class="document-actions">
                            <button
                                class="btn-toggle-always-send"
                                :class="{'active': doc.always_send}"
                                @click="toggleAlwaysSend(doc.id, doc.always_send)"
                                :title="doc.always_send ? t('Always sent') : t('Send with every call')"
                                :disabled="isUploading"
                            >
                                <span v-if="doc.always_send">★</span>
                                <span v-else>☆</span>
                            </button>
                            <button
                                class="btn-delete"
                                @click="deleteDocument(doc.id)"
                                :disabled="isUploading"
                                :aria-label="t('Delete')"
                            >
                                ✕
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Right Column: Upload Zone -->
        <div class="rag-right">
            <h3>{{ t('Upload Documents') }}</h3>

            <div
                class="drop-zone"
                :class="{ 'drop-zone--active': isDragOver, 'drop-zone--disabled': !canUploadDocuments }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
            >
                <div v-if="isPluginLoading" class="upload-status">
                    <div class="spinner"></div>
                    <span>{{ t('Loading the model, you will be able to upload documents in a few minutes') }}</span>
                </div>
                <div v-else-if="isUploading" class="upload-status">
                    <div class="spinner"></div>
                    <span>{{ t('Uploading and ingesting documents...') }}</span>
                </div>
                <div v-else class="drop-zone-content">
                    <i class="ph ph-file-arrow-up"></i>
                    <p class="drop-zone-text">{{ t('Drag and drop files here') }}</p>
                    <p class="drop-zone-hint">{{ t('Supported: .txt, .md, .pdf') }}</p>
                </div>
            </div>

            <div class="browse-button-container">
                <button class="btn btn-primary" @click="triggerFileInput" :disabled="!canUploadDocuments">
                    <i class="ph-light ph-folder"></i>
                    <span>{{ t('Browse Files') }}</span>
                </button>
            </div>
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "ragSettings",
    mixins: [BasePluginComponent],
    data() {
        return {
            documents: [],
            searchTerm: '',
            isLoading: false,
            isUploading: false,
            isDragOver: false,
            errorMessage: '',
            successMessage: '',
            isPluginReady: false,
            isPluginLoading: true,
            statusCheckInterval: null
        };
    },
    computed: {
        filteredDocuments() {
            if (!this.searchTerm || this.searchTerm.trim() === '') {
                return this.documents;
            }
            const searchLower = this.searchTerm.toLowerCase();
            return this.documents.filter(doc =>
                doc.title.toLowerCase().includes(searchLower)
            );
        },
        canUploadDocuments() {
            return this.isPluginReady && !this.isUploading;
        }
    },
    mounted() {
        this.loadDocuments();
        this.checkPluginStatus();
        this.statusCheckInterval = setInterval(() => {
            if (!this.isPluginReady) {
                this.checkPluginStatus();
            } else {
                clearInterval(this.statusCheckInterval);
            }
        }, 2000);
    },
    beforeUnmount() {
        if (this.statusCheckInterval) {
            clearInterval(this.statusCheckInterval);
        }
    },
    methods: {
        async loadDocuments() {
            this.isLoading = true;
            this.errorMessage = '';
            this.successMessage = '';
            try {
                const response = await this.callPluginRestEndpoint('rag', 'documents');
                this.documents = response || [];
            } catch (error) {
                console.error('Error loading documents:', error);
                this.errorMessage = this.t('Failed to load documents');
            } finally {
                this.isLoading = false;
            }
        },

        refreshDocuments() {
            this.loadDocuments();
        },

        async checkPluginStatus() {
            try {
                const response = await this.callPluginRestEndpoint('rag', 'status');
                if (response && response.ready !== undefined) {
                    this.isPluginReady = response.ready;
                    this.isPluginLoading = !response.ready;
                }
            } catch (error) {
                console.error('Error checking plugin status:', error);
            }
        },

        triggerFileInput() {
            this.$refs.fileInput.click();
        },

        handleFileSelect(event) {
            const files = Array.from(event.target.files);
            if (files.length > 0) {
                this.uploadFiles(files);
            }
            event.target.value = '';
        },

        handleDragOver(event) {
            this.isDragOver = true;
        },

        handleDragLeave(event) {
            this.isDragOver = false;
        },

        handleDrop(event) {
            this.isDragOver = false;
            const files = Array.from(event.dataTransfer.files);
            if (files.length > 0) {
                this.uploadFiles(files);
            }
        },

        async uploadFiles(files) {
            if (!this.isPluginReady) {
                this.errorMessage = this.t('Plugin is not ready yet. Please wait for the model to finish loading.');
                return;
            }

            this.isUploading = true;
            this.errorMessage = '';
            this.successMessage = '';

            try {
                const formData = new FormData();
                files.forEach(file => {
                    formData.append('files', file);
                });

                const response = await fetch('/api/plugins/rag/documents', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const result = await response.json();
                    this.successMessage = this.t('{count} document(s) uploaded successfully', { count: result.created });
                    await this.loadDocuments();
                } else {
                    const errorData = await response.json();
                    if (response.status === 409) {
                        const errors = errorData.detail.errors || [];
                        this.errorMessage = this.t('Upload errors: {errors}', { errors: errors.join(', ') });
                    } else {
                        this.errorMessage = this.t('Failed to upload documents');
                    }
                }
            } catch (error) {
                console.error('Error uploading files:', error);
                this.errorMessage = this.t('Failed to upload documents');
            } finally {
                this.isUploading = false;
            }
        },

        async deleteDocument(documentId) {
            const confirmed = confirm(this.t('Are you sure you want to delete this document?'));
            if (!confirmed) return;

            this.isUploading = true;
            this.errorMessage = '';
            this.successMessage = '';

            try {
                await this.callPluginRestEndpoint('rag', `documents/${documentId}`, { method: 'DELETE' });
                this.successMessage = this.t('Document deleted successfully');
                await this.loadDocuments();
            } catch (error) {
                console.error('Error deleting document:', error);
                this.errorMessage = this.t('Failed to delete document');
            } finally {
                this.isUploading = false;
            }
        },

        formatDate(dateString) {
            if (!dateString) return '';
            const date = new Date(dateString);
            return date.toLocaleString();
        },

        async toggleAlwaysSend(documentId, currentStatus) {
            try {
                const response = await this.callPluginRestEndpoint(
                    'rag',
                    `documents/${documentId}/always_send`,
                    { method: 'PUT' }
                );

                const doc = this.documents.find(d => d.id === documentId);
                if (doc) {
                    doc.always_send = response.always_send;
                }

                this.successMessage = response.always_send
                    ? this.t('Document will be sent with every call')
                    : this.t('Document will only be sent based on relevance');
            } catch (error) {
                console.error('Error toggling always send:', error);
                this.errorMessage = this.t('Failed to update document setting');
            }
        }
    }
};
</script>

<style scoped>
.rag-settings.form-grid {
    display: flex;
    gap: 18px;
    align-items: start;
    background: none;
    flex-wrap: wrap;
    max-height: 80vh;
    overflow: hidden;
    padding: 10px;
}

/* Error and Success Messages */
.error-message,
.success-message {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 20px;
    border-radius: 8px;
    margin-bottom: 12px;
}

.error-message {
    background: #a66355;
    color: #fff;
}

.success-message {
    background: #27ae60;
    color: #fff;
}

.error-icon,
.success-icon {
    color: #fff;
}

/* Left Column - Document List */
.rag-left {
    flex: 1;
    min-width: 300px;
    background: rgba(42, 62, 80, 0.3);
    border-radius: 12px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    max-height: 70vh;
}

.documents-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom:1px solid rgba(74, 92, 96, 0.3);
}

.search-container {
    margin-bottom: 16px;
}

.search-input {
    width: 100%;
    padding: 12px 16px;
    border: 1px solid rgba(74, 92, 96, 0.3);
    border-radius: 8px;
    background: rgba(42, 62, 80, 0.3);
    color: #ecf0f1;
    font-size: 1rem;
    transition: border-color 0.2s ease, background 0.2s ease;
}

.search-input:focus {
    border-color: #ffffff;
}

.search-input:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.documents-header h3 {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
    color: #ecf0f1;
}

.btn-refresh {
    background: transparent;
    border: none;
    color: #1abc9c;
    cursor: pointer;
    padding: 8px;
    transition: transform 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
}

.btn-refresh:hover:not(:disabled) {
    transform: rotate(180deg);
}

.btn-refresh:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

.documents-list-container {
    flex: 1;
    overflow-y: auto;
}

.loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    padding: 40px 20px;
}

.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    padding: 40px 20px;
    color: #95a5a6;
}

.empty-icon {
    color: #4a5c60;
}

.documents-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.document-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: rgba(42, 62, 80, 0.4);
    border-radius: 8px;
    transition: background 0.2s ease;
    gap: 12px;
}

.document-item--always-send {
    background: rgba(26, 188, 156, 0.2);
    border: 1px solid rgba(26, 188, 156, 0.5);
}

.document-item:hover {
    background: rgba(26, 188, 156, 0.15);
}

.document-info {
    flex: 1;
}

.document-title {
    font-size: 1rem;
    font-weight: 600;
    color: #ecf0f1;
    text-align: left;
}

.document-date {
    font-size: 0.9rem;
    color: #7f8c8d;
    text-align: right;
    white-space: nowrap;
}

.document-actions {
    display: flex;
    gap: 8px;
}

.btn-toggle-always-send {
    background: rgba(236, 240, 241, 0.1);
    color: #95a5a6;
    border: none;
    border-radius: 6px;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s ease;
}

.btn-toggle-always-send:hover:not(:disabled) {
    background: rgba(236, 240, 241, 0.2);
    color: #ecf0f1;
}

.btn-toggle-always-send.active {
    background: rgba(241, 196, 15, 0.2);
    color: #f1c40f;
}

.btn-delete {
    background: #c0392b !important;
    color: #fff;
    border: none;
    border-radius: 6px;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: background 0.2s ease;
    flex-shrink: 0;
}

.btn-delete:hover:not(:disabled) {
    background: #a93226;
}

.btn-delete:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

/* Right Column - Upload Zone */
.rag-right {
    flex: 1;
    min-width: 300px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    overflow: auto;
}

.rag-right h3 {
    margin: 16px 0 12px 0;
    font-size: 1.1rem;
    font-weight: 600;
    color: #ecf0f1;
}

.drop-zone {
    border: 2px dashed #4a5c60;
    border-radius: 12px;
    padding: 40px 20px;
    text-align: center;
    background: rgba(42, 62, 80, 0.3);
    transition: border-color 0.2s ease, background 0.2s ease;
    min-height: 200px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.drop-zone--active {
    border-color: #1abc9c;
    background: rgba(26, 188, 156, 0.1);
}

.drop-zone--disabled {
    pointer-events: none;
    opacity: 0.6;
}

.drop-zone-icon {
    color: #4a5c60;
    margin-bottom: 16px;
}

.drop-zone-text {
    font-size: 1.1rem;
    color: #ecf0f1;
    margin: 0 0 8px 0;
}

.drop-zone-hint {
    font-size: 0.9rem;
    color: #95a5a6;
    margin: 0;
}

.upload-status {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
}

.spinner {
    width: 40px;
    height: 40px;
    border: 4px solid rgba(236, 240, 241, 0.1);
    border-top-color: #1abc9c;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.browse-button-container {
    display: flex;
    gap: 12px;
}

.btn {
    border: none;
    border-radius: 8px;
    padding: 12px 24px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.15s ease, opacity 0.15s ease, background 0.2s ease;
    display: flex;
    align-items: center;
    gap: 8px;
}

.btn:hover:not(:disabled) {
    transform: translateY(-2px);
}

.btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.btn-primary {
    background: #1abc9c;
    color: #102026;
}

.btn-primary:hover:not(:disabled) {
    background: #16a085;
}

.btn-full {
    width: 100%;
}

.icon {
    width: 24px;
    height: 24px;
}

.icon-m {
    width: 24px;
    height: 24px;
}

.icon-s {
    width: 18px;
    height: 18px;
}

.icon-xl {
    width: 48px;
    height: 48px;
}
</style>
