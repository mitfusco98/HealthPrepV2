/*!
 * Screening Modals JavaScript - Health-Prep v2
 * Modal management for screening types and patient interactions
 */

/**
 * ScreeningModals - Manages modal dialogs for screening operations
 */
class ScreeningModals {
    constructor() {
        this.initializeModals();
        this.bindEvents();
        this.currentScreeningId = null;
        this.confirmationCallbacks = new Map();
    }

    /**
     * Initialize all modal elements
     */
    initializeModals() {
        // Create modal container if it doesn't exist
        if (!document.getElementById('modal-container')) {
            const container = document.createElement('div');
            container.id = 'modal-container';
            document.body.appendChild(container);
        }

        this.modalContainer = document.getElementById('modal-container');
        this.loadingOverlay = this.createLoadingOverlay();
    }

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Listen for modal trigger buttons
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-modal-action]')) {
                e.preventDefault();
                this.handleModalAction(e.target);
            }
        });

        // Listen for form submissions in modals
        document.addEventListener('submit', (e) => {
            if (e.target.closest('.modal')) {
                this.handleModalFormSubmit(e);
            }
        });

        // Listen for modal close events
        document.addEventListener('click', (e) => {
            if (e.target.matches('.modal-backdrop') || e.target.matches('[data-bs-dismiss="modal"]')) {
                this.closeActiveModal();
            }
        });

        // Listen for escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.getActiveModal()) {
                this.closeActiveModal();
            }
        });
    }

    /**
     * Handle modal action clicks
     */
    handleModalAction(element) {
        const action = element.dataset.modalAction;
        const screeningId = element.dataset.screeningId;
        const patientId = element.dataset.patientId;

        switch (action) {
            case 'add-screening-type':
                this.showAddScreeningTypeModal();
                break;
            case 'edit-screening-type':
                this.showEditScreeningTypeModal(screeningId);
                break;
            case 'delete-screening-type':
                this.showDeleteConfirmationModal(screeningId, 'screening_type');
                break;
            case 'view-screening-details':
                this.showScreeningDetailsModal(screeningId);
                break;
            case 'refresh-screenings':
                this.showRefreshConfirmationModal();
                break;
            case 'import-preset':
                this.showImportPresetModal();
                break;
            case 'export-preset':
                this.showExportPresetModal();
                break;
            case 'view-document':
                this.showDocumentViewModal(element.dataset.documentId);
                break;
            default:
                console.warn('Unknown modal action:', action);
        }
    }

    /**
     * Show add screening type modal
     */
    showAddScreeningTypeModal() {
        const modalHtml = `
            <div class="modal fade" id="addScreeningTypeModal" tabindex="-1" aria-labelledby="addScreeningTypeModalLabel" aria-hidden="true">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="addScreeningTypeModalLabel">
                                <i class="fas fa-plus-circle me-2"></i>Add New Screening Type
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <form action="/screening-types/add" method="POST" class="screening-form">
                            <div class="modal-body">
                                <div class="row">
                                    <div class="col-md-8">
                                        <div class="mb-3">
                                            <label for="screeningName" class="form-label">Screening Name *</label>
                                            <input type="text" class="form-control" id="screeningName" name="name" required 
                                                   placeholder="e.g., Mammogram, Colonoscopy">
                                        </div>
                                    </div>
                                    <div class="col-md-4">
                                        <div class="mb-3">
                                            <label for="screeningGender" class="form-label">Gender</label>
                                            <select class="form-select" id="screeningGender" name="gender">
                                                <option value="All">All Genders</option>
                                                <option value="F">Female</option>
                                                <option value="M">Male</option>
                                            </select>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="screeningDescription" class="form-label">Description</label>
                                    <textarea class="form-control" id="screeningDescription" name="description" rows="2"
                                              placeholder="Brief description of the screening"></textarea>
                                </div>
                                
                                <div class="row">
                                    <div class="col-md-3">
                                        <div class="mb-3">
                                            <label for="ageMin" class="form-label">Min Age</label>
                                            <input type="number" class="form-control" id="ageMin" name="age_min" 
                                                   min="0" max="120" placeholder="18">
                                        </div>
                                    </div>
                                    <div class="col-md-3">
                                        <div class="mb-3">
                                            <label for="ageMax" class="form-label">Max Age</label>
                                            <input type="number" class="form-control" id="ageMax" name="age_max" 
                                                   min="0" max="120" placeholder="75">
                                        </div>
                                    </div>
                                    <div class="col-md-3">
                                        <div class="mb-3">
                                            <label for="frequencyNumber" class="form-label">Frequency *</label>
                                            <input type="number" class="form-control" id="frequencyNumber" name="frequency_number" 
                                                   min="1" max="100" value="1" required>
                                        </div>
                                    </div>
                                    <div class="col-md-3">
                                        <div class="mb-3">
                                            <label for="frequencyUnit" class="form-label">Unit *</label>
                                            <select class="form-select" id="frequencyUnit" name="frequency_unit" required>
                                                <option value="years">Years</option>
                                                <option value="months">Months</option>
                                                <option value="days">Days</option>
                                            </select>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="keywords" class="form-label">Keywords</label>
                                    <textarea class="form-control" id="keywords" name="keywords" rows="2"
                                              placeholder="Comma-separated keywords for document matching (e.g., mammogram, breast imaging, mammography)"></textarea>
                                    <div class="form-text">Keywords help match relevant documents to this screening type</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="triggerConditions" class="form-label">Trigger Conditions</label>
                                    <textarea class="form-control" id="triggerConditions" name="trigger_conditions" rows="2"
                                              placeholder="Comma-separated conditions that trigger this screening (e.g., diabetes, hypertension)"></textarea>
                                    <div class="form-text">Medical conditions that make this screening applicable</div>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                <button type="submit" class="btn btn-primary">
                                    <i class="fas fa-save me-2"></i>Add Screening Type
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;

        this.showModal(modalHtml);
    }

    /**
     * Show edit screening type modal
     */
    async showEditScreeningTypeModal(screeningId) {
        this.showLoadingOverlay('Loading screening details...');
        
        try {
            // In a real implementation, this would fetch screening data
            // For now, we'll show the modal with empty fields
            const modalHtml = `
                <div class="modal fade" id="editScreeningTypeModal" tabindex="-1" aria-labelledby="editScreeningTypeModalLabel" aria-hidden="true">
                    <div class="modal-dialog modal-lg">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="editScreeningTypeModalLabel">
                                    <i class="fas fa-edit me-2"></i>Edit Screening Type
                                </h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <form action="/screening-types/${screeningId}/edit" method="POST" class="screening-form">
                                <div class="modal-body">
                                    <div class="alert alert-info">
                                        <i class="fas fa-info-circle me-2"></i>
                                        Editing screening type will trigger a refresh of related screenings.
                                    </div>
                                    
                                    <!-- Same form fields as add modal -->
                                    <div class="row">
                                        <div class="col-md-8">
                                            <div class="mb-3">
                                                <label for="editScreeningName" class="form-label">Screening Name *</label>
                                                <input type="text" class="form-control" id="editScreeningName" name="name" required>
                                            </div>
                                        </div>
                                        <div class="col-md-4">
                                            <div class="mb-3">
                                                <label for="editScreeningGender" class="form-label">Gender</label>
                                                <select class="form-select" id="editScreeningGender" name="gender">
                                                    <option value="All">All Genders</option>
                                                    <option value="F">Female</option>
                                                    <option value="M">Male</option>
                                                </select>
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <div class="mb-3">
                                        <label for="editScreeningDescription" class="form-label">Description</label>
                                        <textarea class="form-control" id="editScreeningDescription" name="description" rows="2"></textarea>
                                    </div>
                                    
                                    <!-- Add other fields similar to add modal -->
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                    <button type="submit" class="btn btn-primary">
                                        <i class="fas fa-save me-2"></i>Update Screening Type
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            `;

            this.hideLoadingOverlay();
            this.showModal(modalHtml);
        } catch (error) {
            this.hideLoadingOverlay();
            this.showErrorModal('Failed to load screening details', error.message);
        }
    }

    /**
     * Show delete confirmation modal
     */
    showDeleteConfirmationModal(itemId, itemType) {
        const itemName = itemType.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
        
        const modalHtml = `
            <div class="modal fade" id="deleteConfirmationModal" tabindex="-1" aria-labelledby="deleteConfirmationModalLabel" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header border-0">
                            <h5 class="modal-title text-danger" id="deleteConfirmationModalLabel">
                                <i class="fas fa-exclamation-triangle me-2"></i>Confirm Deletion
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-danger">
                                <strong>Warning:</strong> This action cannot be undone.
                            </div>
                            <p class="mb-3">Are you sure you want to delete this ${itemName.toLowerCase()}?</p>
                            <p class="text-muted small">
                                <i class="fas fa-info-circle me-1"></i>
                                This will permanently remove the ${itemName.toLowerCase()} and all associated data.
                            </p>
                        </div>
                        <div class="modal-footer border-0">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-danger" onclick="screeningModals.confirmDelete('${itemId}', '${itemType}')">
                                <i class="fas fa-trash me-2"></i>Delete ${itemName}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.showModal(modalHtml);
    }

    /**
     * Show screening details modal
     */
    async showScreeningDetailsModal(screeningId) {
        this.showLoadingOverlay('Loading screening details...');

        try {
            // Mock screening details - in real implementation would fetch from API
            const modalHtml = `
                <div class="modal fade" id="screeningDetailsModal" tabindex="-1" aria-labelledby="screeningDetailsModalLabel" aria-hidden="true">
                    <div class="modal-dialog modal-xl">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="screeningDetailsModalLabel">
                                    <i class="fas fa-clipboard-list me-2"></i>Screening Details
                                </h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body">
                                <div class="row">
                                    <div class="col-md-6">
                                        <div class="card">
                                            <div class="card-header">
                                                <h6 class="mb-0">Screening Information</h6>
                                            </div>
                                            <div class="card-body">
                                                <div class="screening-details-loading">
                                                    <div class="skeleton skeleton-text"></div>
                                                    <div class="skeleton skeleton-text"></div>
                                                    <div class="skeleton skeleton-text"></div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col-md-6">
                                        <div class="card">
                                            <div class="card-header">
                                                <h6 class="mb-0">Matched Documents</h6>
                                            </div>
                                            <div class="card-body">
                                                <div class="documents-loading">
                                                    <div class="skeleton skeleton-text"></div>
                                                    <div class="skeleton skeleton-text"></div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            this.hideLoadingOverlay();
            this.showModal(modalHtml);

            // Simulate loading real data
            setTimeout(() => {
                this.loadScreeningDetailsContent(screeningId);
            }, 1000);
        } catch (error) {
            this.hideLoadingOverlay();
            this.showErrorModal('Failed to load screening details', error.message);
        }
    }

    /**
     * Show refresh confirmation modal
     */
    showRefreshConfirmationModal() {
        const modalHtml = `
            <div class="modal fade" id="refreshConfirmationModal" tabindex="-1" aria-labelledby="refreshConfirmationModalLabel" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="refreshConfirmationModalLabel">
                                <i class="fas fa-sync-alt me-2"></i>Refresh Screenings
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle me-2"></i>
                                This will recalculate all screening statuses based on current documents and criteria.
                            </div>
                            <p>Are you sure you want to refresh all screenings? This process may take a few minutes.</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" onclick="screeningModals.confirmRefresh()">
                                <i class="fas fa-sync-alt me-2"></i>Refresh Screenings
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.showModal(modalHtml);
    }

    /**
     * Show document view modal
     */
    async showDocumentViewModal(documentId) {
        const modalHtml = `
            <div class="modal fade" id="documentViewModal" tabindex="-1" aria-labelledby="documentViewModalLabel" aria-hidden="true">
                <div class="modal-dialog modal-xl">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="documentViewModalLabel">
                                <i class="fas fa-file-medical me-2"></i>Document View
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div class="document-viewer">
                                <div class="text-center p-4">
                                    <div class="loading-spinner loading-spinner-lg text-primary mb-3"></div>
                                    <p>Loading document content...</p>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            <a href="/document/${documentId}/download" class="btn btn-primary" target="_blank">
                                <i class="fas fa-download me-2"></i>Download
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.showModal(modalHtml);
    }

    /**
     * Show error modal
     */
    showErrorModal(title, message) {
        const modalHtml = `
            <div class="modal fade" id="errorModal" tabindex="-1" aria-labelledby="errorModalLabel" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header border-0">
                            <h5 class="modal-title text-danger" id="errorModalLabel">
                                <i class="fas fa-exclamation-circle me-2"></i>${title}
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-danger">
                                <strong>Error:</strong> ${message}
                            </div>
                            <p class="text-muted">Please try again or contact support if the problem persists.</p>
                        </div>
                        <div class="modal-footer border-0">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.showModal(modalHtml);
    }

    /**
     * Handle modal form submissions
     */
    handleModalFormSubmit(event) {
        const form = event.target;
        const submitButton = form.querySelector('button[type="submit"]');
        
        if (submitButton) {
            // Add loading state
            submitButton.classList.add('btn-loading');
            submitButton.disabled = true;
            
            // Show loading text
            const originalText = submitButton.innerHTML;
            submitButton.innerHTML = '<span class="loading-spinner loading-spinner-sm me-2"></span>Processing...';
            
            // Reset after delay (form will handle actual submission)
            setTimeout(() => {
                submitButton.classList.remove('btn-loading');
                submitButton.disabled = false;
                submitButton.innerHTML = originalText;
            }, 2000);
        }
    }

    /**
     * Confirm delete action
     */
    confirmDelete(itemId, itemType) {
        this.showLoadingOverlay('Deleting...');
        
        // Create and submit delete form
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/screening-types/${itemId}/delete`;
        
        // Add CSRF token if available
        const csrfToken = document.querySelector('meta[name="csrf-token"]');
        if (csrfToken) {
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrf_token';
            csrfInput.value = csrfToken.getAttribute('content');
            form.appendChild(csrfInput);
        }
        
        document.body.appendChild(form);
        form.submit();
    }

    /**
     * Confirm refresh action
     */
    confirmRefresh() {
        this.closeActiveModal();
        this.showLoadingOverlay('Refreshing screenings...');
        
        // Submit refresh request
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/api/refresh-screenings';
        
        // Add CSRF token if available
        const csrfToken = document.querySelector('meta[name="csrf-token"]');
        if (csrfToken) {
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrf_token';
            csrfInput.value = csrfToken.getAttribute('content');
            form.appendChild(csrfInput);
        }
        
        document.body.appendChild(form);
        form.submit();
    }

    /**
     * Load screening details content
     */
    loadScreeningDetailsContent(screeningId) {
        const modal = document.getElementById('screeningDetailsModal');
        if (!modal) return;

        // Simulate loading real content
        const detailsContainer = modal.querySelector('.screening-details-loading');
        const documentsContainer = modal.querySelector('.documents-loading');

        if (detailsContainer) {
            detailsContainer.innerHTML = `
                <dl class="row">
                    <dt class="col-sm-4">Status:</dt>
                    <dd class="col-sm-8"><span class="badge bg-warning">Due Soon</span></dd>
                    <dt class="col-sm-4">Last Completed:</dt>
                    <dd class="col-sm-8">2023-03-15</dd>
                    <dt class="col-sm-4">Due Date:</dt>
                    <dd class="col-sm-8">2024-03-15</dd>
                    <dt class="col-sm-4">Frequency:</dt>
                    <dd class="col-sm-8">1 year</dd>
                </dl>
            `;
        }

        if (documentsContainer) {
            documentsContainer.innerHTML = `
                <div class="list-group list-group-flush">
                    <div class="list-group-item d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-1">Mammography Report</h6>
                            <small class="text-muted">2023-03-15 • 85% confidence</small>
                        </div>
                        <span class="badge confidence-high">High</span>
                    </div>
                    <div class="list-group-item d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-1">Breast Imaging Study</h6>
                            <small class="text-muted">2023-03-10 • 92% confidence</small>
                        </div>
                        <span class="badge confidence-high">High</span>
                    </div>
                </div>
            `;
        }
    }

    /**
     * Show modal with HTML content
     */
    showModal(modalHtml) {
        this.modalContainer.innerHTML = modalHtml;
        const modal = this.modalContainer.querySelector('.modal');
        
        if (modal) {
            // Initialize Bootstrap modal
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
            
            // Clean up when modal is hidden
            modal.addEventListener('hidden.bs.modal', () => {
                this.modalContainer.innerHTML = '';
            });
        }
    }

    /**
     * Get active modal
     */
    getActiveModal() {
        return document.querySelector('.modal.show');
    }

    /**
     * Close active modal
     */
    closeActiveModal() {
        const activeModal = this.getActiveModal();
        if (activeModal) {
            const bsModal = bootstrap.Modal.getInstance(activeModal);
            if (bsModal) {
                bsModal.hide();
            }
        }
    }

    /**
     * Create loading overlay
     */
    createLoadingOverlay() {
        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        overlay.style.display = 'none';
        overlay.innerHTML = `
            <div class="loading-overlay-content">
                <div class="loading-overlay-spinner">
                    <div class="loading-spinner loading-spinner-lg text-primary"></div>
                </div>
                <div class="loading-overlay-text">Loading...</div>
                <div class="loading-overlay-subtext">Please wait</div>
            </div>
        `;
        document.body.appendChild(overlay);
        return overlay;
    }

    /**
     * Show loading overlay
     */
    showLoadingOverlay(message = 'Loading...', subtext = 'Please wait') {
        if (this.loadingOverlay) {
            const textElement = this.loadingOverlay.querySelector('.loading-overlay-text');
            const subtextElement = this.loadingOverlay.querySelector('.loading-overlay-subtext');
            
            if (textElement) textElement.textContent = message;
            if (subtextElement) subtextElement.textContent = subtext;
            
            this.loadingOverlay.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
    }

    /**
     * Hide loading overlay
     */
    hideLoadingOverlay() {
        if (this.loadingOverlay) {
            this.loadingOverlay.style.display = 'none';
            document.body.style.overflow = '';
        }
    }

    /**
     * Show toast notification
     */
    showToast(message, type = 'info', duration = 5000) {
        const toastContainer = this.getOrCreateToastContainer();
        const toastId = 'toast-' + Date.now();
        
        const toastHtml = `
            <div class="toast align-items-center text-white bg-${type} border-0" id="${toastId}" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="fas fa-${this.getToastIcon(type)} me-2"></i>
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `;
        
        toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, { delay: duration });
        toast.show();
        
        // Clean up after toast is hidden
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }

    /**
     * Get or create toast container
     */
    getOrCreateToastContainer() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            container.style.zIndex = '9999';
            document.body.appendChild(container);
        }
        return container;
    }

    /**
     * Get toast icon for type
     */
    getToastIcon(type) {
        const icons = {
            'success': 'check-circle',
            'danger': 'exclamation-circle',
            'warning': 'exclamation-triangle',
            'info': 'info-circle'
        };
        return icons[type] || 'info-circle';
    }
}

// Initialize screening modals when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.screeningModals = new ScreeningModals();
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ScreeningModals;
}

