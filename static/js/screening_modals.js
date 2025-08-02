/**
 * Screening Modals JavaScript
 * Handles modal interactions for screening management
 */

// Global modal management
class ScreeningModals {
    constructor() {
        this.initializeModals();
        this.bindEvents();
    }

    initializeModals() {
        // Initialize all Bootstrap modals
        this.modals = {
            addScreening: new bootstrap.Modal(document.getElementById('addScreeningModal') || document.createElement('div')),
            editScreening: new bootstrap.Modal(document.getElementById('editScreeningModal') || document.createElement('div')),
            deleteScreening: new bootstrap.Modal(document.getElementById('deleteScreeningModal') || document.createElement('div')),
            viewKeywords: new bootstrap.Modal(document.getElementById('viewKeywordsModal') || document.createElement('div')),
            importPresets: new bootstrap.Modal(document.getElementById('importPresetsModal') || document.createElement('div'))
        };
    }

    bindEvents() {
        // Add screening modal
        this.bindAddScreeningEvents();
        
        // Edit screening modal
        this.bindEditScreeningEvents();
        
        // Delete confirmation modal
        this.bindDeleteScreeningEvents();
        
        // Keywords view modal
        this.bindKeywordsViewEvents();
        
        // Import presets modal
        this.bindImportPresetsEvents();
        
        // Global modal events
        this.bindGlobalModalEvents();
    }

    bindAddScreeningEvents() {
        const addButtons = document.querySelectorAll('.btn-add-screening');
        const addModal = document.getElementById('addScreeningModal');
        
        if (!addModal) return;
        
        addButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                this.openAddScreeningModal();
            });
        });

        // Form submission
        const addForm = addModal.querySelector('form');
        if (addForm) {
            addForm.addEventListener('submit', (e) => {
                this.handleAddScreeningSubmit(e);
            });
        }

        // Keywords input enhancement
        const keywordsInput = addModal.querySelector('#keywords');
        if (keywordsInput) {
            this.enhanceKeywordsInput(keywordsInput);
        }
    }

    bindEditScreeningEvents() {
        const editButtons = document.querySelectorAll('.btn-edit-screening');
        const editModal = document.getElementById('editScreeningModal');
        
        if (!editModal) return;
        
        editButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const screeningId = button.getAttribute('data-screening-id');
                this.openEditScreeningModal(screeningId);
            });
        });

        // Form submission
        const editForm = editModal.querySelector('form');
        if (editForm) {
            editForm.addEventListener('submit', (e) => {
                this.handleEditScreeningSubmit(e);
            });
        }
    }

    bindDeleteScreeningEvents() {
        const deleteButtons = document.querySelectorAll('.btn-delete-screening');
        const deleteModal = document.getElementById('deleteScreeningModal');
        
        if (!deleteModal) return;
        
        deleteButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const screeningId = button.getAttribute('data-screening-id');
                const screeningName = button.getAttribute('data-screening-name');
                this.openDeleteScreeningModal(screeningId, screeningName);
            });
        });

        // Confirm delete
        const confirmButton = deleteModal.querySelector('.btn-confirm-delete');
        if (confirmButton) {
            confirmButton.addEventListener('click', (e) => {
                this.handleDeleteConfirm(e);
            });
        }
    }

    bindKeywordsViewEvents() {
        const keywordButtons = document.querySelectorAll('.btn-view-keywords');
        
        keywordButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const screeningId = button.getAttribute('data-screening-id');
                this.openKeywordsViewModal(screeningId);
            });
        });
    }

    bindImportPresetsEvents() {
        const importButton = document.querySelector('.btn-import-presets');
        const importModal = document.getElementById('importPresetsModal');
        
        if (!importButton || !importModal) return;
        
        importButton.addEventListener('click', (e) => {
            e.preventDefault();
            this.openImportPresetsModal();
        });

        // Preset selection
        const presetCards = importModal.querySelectorAll('.preset-card');
        presetCards.forEach(card => {
            card.addEventListener('click', (e) => {
                this.selectPreset(card);
            });
        });

        // Import confirmation
        const importConfirmButton = importModal.querySelector('.btn-import-confirm');
        if (importConfirmButton) {
            importConfirmButton.addEventListener('click', (e) => {
                this.handleImportPresets(e);
            });
        }
    }

    bindGlobalModalEvents() {
        // Close modals on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeAllModals();
            }
        });

        // Form validation enhancement
        document.querySelectorAll('.modal form').forEach(form => {
            this.enhanceFormValidation(form);
        });
    }

    openAddScreeningModal() {
        const modal = document.getElementById('addScreeningModal');
        if (!modal) return;
        
        // Reset form
        const form = modal.querySelector('form');
        if (form) {
            form.reset();
            this.clearFormErrors(form);
        }

        // Focus first input
        setTimeout(() => {
            const firstInput = modal.querySelector('input, select, textarea');
            if (firstInput) firstInput.focus();
        }, 300);

        this.modals.addScreening.show();
    }

    openEditScreeningModal(screeningId) {
        const modal = document.getElementById('editScreeningModal');
        if (!modal) return;
        
        // Show loading state
        this.setModalLoading(modal, true);
        this.modals.editScreening.show();

        // Load screening data
        this.loadScreeningData(screeningId)
            .then(data => {
                this.populateEditForm(modal, data);
                this.setModalLoading(modal, false);
                
                // Focus first input
                setTimeout(() => {
                    const firstInput = modal.querySelector('input, select, textarea');
                    if (firstInput) firstInput.focus();
                }, 100);
            })
            .catch(error => {
                console.error('Error loading screening data:', error);
                this.setModalLoading(modal, false);
                this.showModalError(modal, 'Failed to load screening data.');
            });
    }

    openDeleteScreeningModal(screeningId, screeningName) {
        const modal = document.getElementById('deleteScreeningModal');
        if (!modal) return;
        
        // Update modal content
        const nameElement = modal.querySelector('.screening-name');
        if (nameElement) {
            nameElement.textContent = screeningName;
        }

        // Store screening ID for deletion
        const confirmButton = modal.querySelector('.btn-confirm-delete');
        if (confirmButton) {
            confirmButton.setAttribute('data-screening-id', screeningId);
        }

        this.modals.deleteScreening.show();
    }

    openKeywordsViewModal(screeningId) {
        const modal = document.getElementById('viewKeywordsModal');
        if (!modal) return;
        
        // Show loading state
        this.setModalLoading(modal, true);
        this.modals.viewKeywords.show();

        // Load keywords
        fetch(`/api/screening-keywords/${screeningId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.displayKeywords(modal, data.keywords, data.screening_type);
                } else {
                    throw new Error(data.error || 'Failed to load keywords');
                }
                this.setModalLoading(modal, false);
            })
            .catch(error => {
                console.error('Error loading keywords:', error);
                this.setModalLoading(modal, false);
                this.showModalError(modal, 'Failed to load keywords.');
            });
    }

    openImportPresetsModal() {
        const modal = document.getElementById('importPresetsModal');
        if (!modal) return;
        
        // Reset selection
        modal.querySelectorAll('.preset-card').forEach(card => {
            card.classList.remove('selected');
        });

        this.modals.importPresets.show();
    }

    handleAddScreeningSubmit(e) {
        const form = e.target;
        const submitButton = form.querySelector('button[type="submit"]');
        
        // Show loading state
        this.setButtonLoading(submitButton, true);
        this.clearFormErrors(form);

        // Let the form submit normally
        // The server will handle validation and redirect
    }

    handleEditScreeningSubmit(e) {
        const form = e.target;
        const submitButton = form.querySelector('button[type="submit"]');
        
        // Show loading state
        this.setButtonLoading(submitButton, true);
        this.clearFormErrors(form);

        // Let the form submit normally
        // The server will handle validation and redirect
    }

    handleDeleteConfirm(e) {
        const button = e.target;
        const screeningId = button.getAttribute('data-screening-id');
        
        if (!screeningId) return;

        // Show loading state
        this.setButtonLoading(button, true);

        // Create form and submit
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/screening/delete-type/${screeningId}`;
        
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

    handleImportPresets(e) {
        const modal = document.getElementById('importPresetsModal');
        const selectedCard = modal.querySelector('.preset-card.selected');
        
        if (!selectedCard) {
            this.showModalError(modal, 'Please select a preset to import.');
            return;
        }

        const presetType = selectedCard.getAttribute('data-preset-type');
        const button = e.target;
        
        // Show loading state
        this.setButtonLoading(button, true);

        // Create form and submit
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/screening/import-presets';
        
        const presetInput = document.createElement('input');
        presetInput.type = 'hidden';
        presetInput.name = 'preset_type';
        presetInput.value = presetType;
        form.appendChild(presetInput);
        
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

    async loadScreeningData(screeningId) {
        // In a real implementation, this would fetch from an API
        // For now, return mock data structure
        return {
            id: screeningId,
            name: '',
            description: '',
            keywords: '',
            gender_criteria: 'All',
            min_age: null,
            max_age: null,
            frequency_number: 12,
            frequency_unit: 'months',
            trigger_conditions: '',
            is_active: true
        };
    }

    populateEditForm(modal, data) {
        const form = modal.querySelector('form');
        if (!form) return;

        // Populate form fields
        Object.keys(data).forEach(key => {
            const field = form.querySelector(`[name="${key}"]`);
            if (field) {
                if (field.type === 'checkbox') {
                    field.checked = data[key];
                } else {
                    field.value = data[key] || '';
                }
            }
        });

        // Update form action if needed
        form.action = form.action.replace(/\/\d+$/, `/${data.id}`);
    }

    displayKeywords(modal, keywords, screeningType) {
        const container = modal.querySelector('.keywords-container');
        const titleElement = modal.querySelector('.modal-title');
        
        if (titleElement) {
            titleElement.textContent = `Keywords for ${screeningType}`;
        }

        if (!container) return;

        if (keywords && keywords.length > 0) {
            container.innerHTML = keywords.map(keyword => 
                `<span class="badge bg-primary me-1 mb-1">${keyword}</span>`
            ).join('');
        } else {
            container.innerHTML = '<p class="text-muted">No keywords defined for this screening type.</p>';
        }
    }

    selectPreset(card) {
        const modal = document.getElementById('importPresetsModal');
        
        // Remove selection from other cards
        modal.querySelectorAll('.preset-card').forEach(c => {
            c.classList.remove('selected');
        });

        // Select this card
        card.classList.add('selected');

        // Enable import button
        const importButton = modal.querySelector('.btn-import-confirm');
        if (importButton) {
            importButton.disabled = false;
        }
    }

    enhanceKeywordsInput(input) {
        // Add real-time validation and suggestions
        let timeout;
        
        input.addEventListener('input', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                this.validateKeywords(input);
                this.showKeywordSuggestions(input);
            }, 300);
        });
    }

    validateKeywords(input) {
        const value = input.value.trim();
        const container = input.closest('.form-group') || input.parentElement;
        
        // Remove existing feedback
        const existingFeedback = container.querySelector('.keyword-feedback');
        if (existingFeedback) {
            existingFeedback.remove();
        }

        if (value) {
            const keywords = value.split(',').map(k => k.trim()).filter(k => k);
            
            if (keywords.length > 0) {
                const feedback = document.createElement('div');
                feedback.className = 'keyword-feedback mt-2';
                feedback.innerHTML = `
                    <small class="text-muted">
                        <i class="fas fa-info-circle"></i>
                        ${keywords.length} keyword(s) defined
                    </small>
                `;
                container.appendChild(feedback);
            }
        }
    }

    showKeywordSuggestions(input) {
        // This would integrate with the backend API for suggestions
        // For now, just a placeholder
        console.log('Keyword suggestions would appear here');
    }

    enhanceFormValidation(form) {
        const inputs = form.querySelectorAll('input, select, textarea');
        
        inputs.forEach(input => {
            input.addEventListener('blur', () => {
                this.validateField(input);
            });
        });
    }

    validateField(field) {
        const value = field.value.trim();
        const required = field.hasAttribute('required');
        
        this.clearFieldError(field);

        if (required && !value) {
            this.showFieldError(field, 'This field is required.');
            return false;
        }

        // Add specific validation based on field type
        if (field.type === 'number') {
            const min = field.getAttribute('min');
            const max = field.getAttribute('max');
            const numValue = parseFloat(value);
            
            if (value && isNaN(numValue)) {
                this.showFieldError(field, 'Please enter a valid number.');
                return false;
            }
            
            if (min && numValue < parseFloat(min)) {
                this.showFieldError(field, `Value must be at least ${min}.`);
                return false;
            }
            
            if (max && numValue > parseFloat(max)) {
                this.showFieldError(field, `Value must not exceed ${max}.`);
                return false;
            }
        }

        return true;
    }

    showFieldError(field, message) {
        field.classList.add('is-invalid');
        
        const feedback = document.createElement('div');
        feedback.className = 'invalid-feedback';
        feedback.textContent = message;
        
        field.parentElement.appendChild(feedback);
    }

    clearFieldError(field) {
        field.classList.remove('is-invalid');
        
        const feedback = field.parentElement.querySelector('.invalid-feedback');
        if (feedback) {
            feedback.remove();
        }
    }

    clearFormErrors(form) {
        form.querySelectorAll('.is-invalid').forEach(field => {
            field.classList.remove('is-invalid');
        });
        
        form.querySelectorAll('.invalid-feedback').forEach(feedback => {
            feedback.remove();
        });
        
        this.hideModalError(form.closest('.modal'));
    }

    setModalLoading(modal, loading) {
        const content = modal.querySelector('.modal-body');
        const footer = modal.querySelector('.modal-footer');
        
        if (loading) {
            modal.classList.add('modal-loading');
            if (content) content.style.opacity = '0.6';
            if (footer) footer.style.opacity = '0.6';
        } else {
            modal.classList.remove('modal-loading');
            if (content) content.style.opacity = '1';
            if (footer) footer.style.opacity = '1';
        }
    }

    setButtonLoading(button, loading) {
        if (loading) {
            button.classList.add('btn-loading');
            button.disabled = true;
            button.setAttribute('data-original-text', button.textContent);
            button.textContent = 'Loading...';
        } else {
            button.classList.remove('btn-loading');
            button.disabled = false;
            const originalText = button.getAttribute('data-original-text');
            if (originalText) {
                button.textContent = originalText;
            }
        }
    }

    showModalError(modal, message) {
        this.hideModalError(modal);
        
        const alert = document.createElement('div');
        alert.className = 'alert alert-danger modal-error';
        alert.innerHTML = `
            <i class="fas fa-exclamation-triangle"></i>
            <span>${message}</span>
        `;
        
        const modalBody = modal.querySelector('.modal-body');
        if (modalBody) {
            modalBody.insertBefore(alert, modalBody.firstChild);
        }
    }

    hideModalError(modal) {
        const existingError = modal.querySelector('.modal-error');
        if (existingError) {
            existingError.remove();
        }
    }

    closeAllModals() {
        Object.values(this.modals).forEach(modal => {
            if (modal._element && modal._element.classList.contains('show')) {
                modal.hide();
            }
        });
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (typeof bootstrap !== 'undefined') {
        window.screeningModals = new ScreeningModals();
    }
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ScreeningModals;
}
