/**
 * Trigger Conditions Modal Management System
 * Similar to keywords modal but for medical trigger conditions
 */

let currentConditions = [];
let currentScreeningTypeId = null;

/**
 * Open trigger conditions modal for a screening type
 * @param {number} screeningTypeId - The screening type ID
 * @param {string} screeningName - The screening type name
 */
async function openConditionsModal(screeningTypeId, screeningName) {
    currentScreeningTypeId = screeningTypeId;
    currentConditions = [];
    
    // Update modal title
    document.getElementById('conditionModalTitle').textContent = `Manage Trigger Conditions - ${screeningName}`;
    
    try {
        // Load existing conditions
        const response = await fetch(`/api/screening-conditions/${screeningTypeId}`);
        const data = await response.json();
        
        if (data.success) {
            currentConditions = data.conditions || [];
            displayConditions();
        } else {
            showConditionError(data.error || 'Failed to load conditions');
        }
    } catch (error) {
        console.error('Error loading conditions:', error);
        showConditionError('Failed to load conditions');
    }
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('conditionsModal'));
    modal.show();
}

/**
 * Display current conditions as tags
 */
function displayConditions() {
    const container = document.getElementById('conditionTags');
    container.innerHTML = '';
    
    currentConditions.forEach((condition, index) => {
        const conditionElement = document.createElement('span');
        conditionElement.className = 'badge bg-primary me-2 mb-2 condition-tag';
        
        const textNode = document.createTextNode(condition + ' ');
        conditionElement.appendChild(textNode);
        
        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'btn-close btn-close-white ms-2';
        removeBtn.setAttribute('aria-label', 'Remove');
        removeBtn.onclick = () => removeCondition(index);
        conditionElement.appendChild(removeBtn);
        
        container.appendChild(conditionElement);
    });
}

/**
 * Remove a condition by index
 * @param {number} index - The condition index to remove
 */
function removeCondition(index) {
    currentConditions.splice(index, 1);
    displayConditions();
}

/**
 * Add a new condition
 */
function addCondition() {
    const input = document.getElementById('newConditionInput');
    const condition = input.value.trim();
    
    if (!condition) {
        showConditionError('Please enter a condition');
        return;
    }
    
    // Check for duplicates
    if (currentConditions.includes(condition)) {
        showConditionError('Condition already exists');
        return;
    }
    
    // Add condition
    currentConditions.push(condition);
    input.value = '';
    displayConditions();
    clearConditionError();
    
    // Hide autocomplete dropdown
    hideConditionAutocomplete();
}

/**
 * Import medical conditions for the current screening type
 */
async function importMedicalConditions() {
    if (!currentScreeningTypeId) {
        showConditionError('No screening type selected');
        return;
    }
    
    try {
        // Show loading state
        const importBtn = document.getElementById('importConditionsBtn');
        const originalText = importBtn.textContent;
        importBtn.textContent = 'Importing...';
        importBtn.disabled = true;
        
        const response = await fetch(`/api/import-conditions/${currentScreeningTypeId}`);
        const data = await response.json();
        
        if (data.success) {
            currentConditions = data.conditions;
            displayConditions();
            
            // Show import summary
            const newCount = data.new_conditions ? data.new_conditions.length : 0;
            if (newCount > 0) {
                showConditionSuccess(`Imported ${newCount} new trigger conditions`);
            } else {
                showConditionSuccess('All standard trigger conditions are already present');
            }
        } else {
            showConditionError(data.error || 'Failed to import conditions');
        }
    } catch (error) {
        console.error('Error importing conditions:', error);
        showConditionError('Failed to import conditions');
    } finally {
        // Restore button state
        const importBtn = document.getElementById('importConditionsBtn');
        importBtn.textContent = originalText;
        importBtn.disabled = false;
    }
}

/**
 * Setup autocomplete for condition input
 */
function setupConditionAutocomplete() {
    const input = document.getElementById('newConditionInput');
    const dropdown = document.getElementById('conditionAutocompleteDropdown');
    
    if (!input || !dropdown) return;
    
    let timeoutId;
    
    input.addEventListener('input', function() {
        clearTimeout(timeoutId);
        const query = this.value.trim();
        
        if (query.length < 2) {
            hideConditionAutocomplete();
            return;
        }
        
        timeoutId = setTimeout(() => {
            searchConditions(query);
        }, 300);
    });
    
    // Hide autocomplete when clicking outside
    document.addEventListener('click', function(e) {
        if (!input.contains(e.target) && !dropdown.contains(e.target)) {
            hideConditionAutocomplete();
        }
    });
}

/**
 * Search for condition suggestions
 */
async function searchConditions(query) {
    try {
        const response = await fetch(`/api/condition-suggestions?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        
        if (data.success && data.suggestions.length > 0) {
            showConditionAutocomplete(data.suggestions);
        } else {
            hideConditionAutocomplete();
        }
    } catch (error) {
        console.error('Error searching conditions:', error);
        hideConditionAutocomplete();
    }
}

/**
 * Show autocomplete dropdown for conditions
 */
function showConditionAutocomplete(suggestions) {
    const dropdown = document.getElementById('conditionAutocompleteDropdown');
    if (!dropdown) return;
    
    dropdown.innerHTML = '';
    
    suggestions.forEach(suggestion => {
        // Skip if already in current conditions
        if (currentConditions.includes(suggestion)) return;
        
        const item = document.createElement('div');
        item.className = 'autocomplete-item';
        item.textContent = suggestion;
        item.onclick = () => selectConditionSuggestion(suggestion);
        dropdown.appendChild(item);
    });
    
    dropdown.style.display = dropdown.children.length > 0 ? 'block' : 'none';
}

/**
 * Hide autocomplete dropdown for conditions
 */
function hideConditionAutocomplete() {
    const dropdown = document.getElementById('conditionAutocompleteDropdown');
    if (dropdown) {
        dropdown.style.display = 'none';
    }
}

/**
 * Select a suggestion from autocomplete
 */
function selectConditionSuggestion(suggestion) {
    const input = document.getElementById('newConditionInput');
    input.value = suggestion;
    hideConditionAutocomplete();
    addCondition();
}

/**
 * Save trigger conditions
 */
async function saveConditions() {
    if (!currentScreeningTypeId) {
        showConditionError('No screening type selected');
        return;
    }
    
    try {
        // Show loading state
        const saveBtn = document.getElementById('saveConditionsBtn');
        const originalText = saveBtn.textContent;
        saveBtn.textContent = 'Saving...';
        saveBtn.disabled = true;
        
        const response = await fetch(`/api/screening-conditions/${currentScreeningTypeId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                conditions: currentConditions
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Close modal and refresh page
            const modal = bootstrap.Modal.getInstance(document.getElementById('conditionsModal'));
            modal.hide();
            
            // Show success message
            showNotification(`Saved ${currentConditions.length} trigger conditions successfully`, 'success');
            
            // Refresh page to show updated conditions
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showConditionError(data.error || 'Failed to save conditions');
        }
    } catch (error) {
        console.error('Error saving conditions:', error);
        showConditionError('Failed to save conditions');
    } finally {
        // Restore button state
        const saveBtn = document.getElementById('saveConditionsBtn');
        saveBtn.textContent = originalText;
        saveBtn.disabled = false;
    }
}

/**
 * Show error message in the modal
 * @param {string} message - The error message
 */
function showConditionError(message) {
    const errorDiv = document.getElementById('conditionError');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    
    // Hide success message
    const successDiv = document.getElementById('conditionSuccess');
    if (successDiv) {
        successDiv.style.display = 'none';
    }
}

/**
 * Show success message in the modal
 * @param {string} message - The success message
 */
function showConditionSuccess(message) {
    const successDiv = document.getElementById('conditionSuccess');
    if (successDiv) {
        successDiv.textContent = message;
        successDiv.style.display = 'block';
    }
    
    // Hide error message
    const errorDiv = document.getElementById('conditionError');
    errorDiv.style.display = 'none';
    
    // Auto-hide after 3 seconds
    setTimeout(() => {
        if (successDiv) {
            successDiv.style.display = 'none';
        }
    }, 3000);
}

/**
 * Clear error message in the modal
 */
function clearConditionError() {
    const errorDiv = document.getElementById('conditionError');
    errorDiv.style.display = 'none';
}

/**
 * Show notification message
 * @param {string} message - The notification message
 * @param {string} type - The notification type ('success', 'error', 'info')
 */
function showNotification(message, type = 'info') {
    // Create notification element if it doesn't exist
    let notification = document.getElementById('notification');
    if (!notification) {
        notification = document.createElement('div');
        notification.id = 'notification';
        notification.className = 'position-fixed top-0 end-0 p-3';
        notification.style.zIndex = '9999';
        document.body.appendChild(notification);
    }
    
    const alertClass = type === 'success' ? 'alert-success' : 
                     type === 'error' ? 'alert-danger' : 'alert-info';
    
    notification.innerHTML = `
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        const alert = notification.querySelector('.alert');
        if (alert) {
            alert.classList.remove('show');
            setTimeout(() => {
                notification.innerHTML = '';
            }, 500);
        }
    }, 5000);
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Add condition on Enter key
    const newConditionInput = document.getElementById('newConditionInput');
    if (newConditionInput) {
        newConditionInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                addCondition();
            }
        });
    }
    
    // Clear error when typing
    if (newConditionInput) {
        newConditionInput.addEventListener('input', function() {
            clearConditionError();
        });
    }
    
    // Setup autocomplete
    setupConditionAutocomplete();
});