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
            <svg class="icon icon-m error-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <span>{{ errorMessage }}</span>
        </div>

        <div v-if="successMessage" class="success-message">
            <svg class="icon icon-m success-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 17"></polyline>
                <path d="M20 12L6 12"></path>
            </svg>
            <span>{{ successMessage }}</span>
        </div>

        <!-- Left Column: Document List -->
        <div class="rag-left">
            <div class="documents-header">
                <h3>{{ t('Documents') }}</h3>
                <button class="btn-refresh" @click="refreshDocuments" :disabled="isUploading" :title="t('Refresh')">
                    <svg class="icon icon-m" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 12a9 9 0 1 1-9 9 9 9 0 0 1-9 9"></path>
                        <path d="M9 21h.01"></path>
                        <path d="M9 9a9 9 0 1 0 0-9-9 9 9 0 0 1 9 9"></path>
                        <path d="M15 9l-3 3"></path>
                        <path d="M12 15l3-3"></path>
                    </svg>
                </button>
            </div>

            <div class="documents-list-container">
                <div v-if="isLoading" class="loading-state">
                    <div class="spinner"></div>
                    <span>{{ t('Loading documents...') }}</span>
                </div>

                <div v-else-if="documents.length === 0" class="empty-state">
                    <svg class="icon icon-xl empty-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2-3h9a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2z"></path>
                        <polyline points="16 1 20 17 20 17 20"></polyline>
                    </svg>
                    <p>{{ t('No documents uploaded yet') }}</p>
                </div>

                <div v-else class="documents-list">
                    <div v-for="doc in documents" :key="doc.id" class="document-item">
                        <div class="document-info">
                            <div class="document-title">{{ doc.title }}</div>
                            <div class="document-meta">
                                <span class="document-filename">{{ doc.filename }}</span>
                                <span class="document-separator">•</span>
                                <span class="document-date">{{ formatDate(doc.created_at) }}</span>
                            </div>
                        </div>
                        <button
                            class="btn-delete"
                            @click="deleteDocument(doc.id)"
                            :disabled="isUploading"
                            :aria-label="t('Delete')"
                        >
                            <svg class="icon icon-s" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v2"></path>
                                <line x1="10" y1="11" x2="10" y2="17"></line>
                                <line x1="14" y1="11" x2="14" y2="17"></line>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Right Column: Upload Zone -->
        <div class="rag-right">
            <h3>{{ t('Upload Documents') }}</h3>

            <div
                class="drop-zone"
                :class="{ 'drop-zone--active': isDragOver, 'drop-zone--disabled': isUploading }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
            >
                <div v-if="isUploading" class="upload-status">
                    <div class="spinner"></div>
                    <span>{{ t('Uploading and ingesting documents...') }}</span>
                </div>
                <div v-else class="drop-zone-content">
                    <svg class="icon icon-xl drop-zone-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="17 8 12 3 12 3"></polyline>
                        <polyline points="12 3 7 17 7 17"></polyline>
                    </svg>
                    <p class="drop-zone-text">{{ t('Drag and drop files here') }}</p>
                    <p class="drop-zone-hint">{{ t('Supported: .txt, .md, .pdf') }}</p>
                </div>
            </div>

            <div class="browse-button-container">
                <button class="btn btn-primary btn-full" @click="triggerFileInput" :disabled="isUploading">
                    <svg class="icon icon-m" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                        <line x1="12" y1="18" x2="12" y2="18"></line>
                        <line x1="16" y1="13" x2="16" y2="13"></line>
                        <line x1="8" y1="13" x2="8" y2="13"></line>
                    </svg>
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
            isLoading: false,
            isUploading: false,
            isDragOver: false,
            errorMessage: '',
            successMessage: ''
        };
    },
    mounted() {
        this.loadDocuments();
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
    max-height: calc(100vh - 100px);
}

.documents-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom:1px solid rgba(74, 92, 96, 0.3);
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
}

.document-item:hover {
    background: rgba(26, 188, 156, 0.15);
}

.document-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.document-title {
    font-size: 1rem;
    font-weight: 600;
    color: #ecf0f1;
}

.document-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.9rem;
    color: #95a5a6;
}

.document-filename {
    font-weight: 500;
    color: #bdc3c7;
}

.document-separator {
    color: #4a5c60;
}

.document-date {
    color: #7f8c8d;
}

.btn-delete {
    background: #c0392b;
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
    margin-left: 12px;
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
}

.rag-right h3 {
    margin: 0 0 12px 0;
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
