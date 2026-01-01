/**
 * Inline Condition Management System
 * For managing trigger conditions directly in add/edit forms
 */

let inlineConditions = [];

/**
 * Initialize inline condition management
 * @param {Array} existingConditions - Existing conditions for edit forms
 */
function initializeInlineConditions(existingConditions = []) {
    inlineConditions = [...existingConditions];
    displayInlineConditions();
    setupInlineConditionAutocomplete();
    updateHiddenTextarea();
}

/**
 * Display inline conditions as tags
 */
function displayInlineConditions() {
    const container = document.getElementById('inlineConditionTags');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (inlineConditions.length === 0) {
        container.innerHTML = '<small class="text-muted">No conditions added yet</small>';
        return;
    }
    
    inlineConditions.forEach((condition, index) => {
        const conditionElement = document.createElement('span');
        conditionElement.className = 'badge condition-tag me-1 mb-1';
        
        const textNode = document.createTextNode(condition);
        conditionElement.appendChild(textNode);
        
        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'btn-close btn-close-white ms-1';
        removeBtn.setAttribute('aria-label', 'Remove');
        removeBtn.onclick = () => removeInlineCondition(index);
        conditionElement.appendChild(removeBtn);
        
        container.appendChild(conditionElement);
    });
}

/**
 * Add a new inline condition
 */
function addInlineCondition() {
    const input = document.getElementById('inlineConditionInput');
    if (!input) return;
    
    const condition = input.value.trim();
    
    if (!condition) {
        showInlineError('Please enter a condition');
        return;
    }
    
    // Check for duplicates
    if (inlineConditions.includes(condition)) {
        showInlineError('Condition already exists');
        return;
    }
    
    // Add condition
    inlineConditions.push(condition);
    input.value = '';
    displayInlineConditions();
    updateHiddenTextarea();
    hideInlineConditionAutocomplete();
    clearInlineError();
}

/**
 * Remove an inline condition by index
 * @param {number} index - The condition index to remove
 */
function removeInlineCondition(index) {
    inlineConditions.splice(index, 1);
    displayInlineConditions();
    updateHiddenTextarea();
}

/**
 * Import medical conditions for inline management
 */
async function importInlineConditions() {
    try {
        // Get screening name from form or use generic
        const nameInput = document.querySelector('input[name="name"]');
        const screeningName = nameInput ? nameInput.value.trim() : 'Generic';
        
        if (!screeningName) {
            showInlineError('Please enter a screening type name first');
            return;
        }
        
        // Show loading state
        const importBtn = document.querySelector('.btn-import-conditions');
        const originalText = importBtn.textContent;
        importBtn.textContent = 'Importing...';
        importBtn.disabled = true;
        
        const response = await fetch(`/api/import-conditions/0?screening_name=${encodeURIComponent(screeningName)}`);
        const data = await response.json();
        
        if (data.success) {
            const importedConditions = data.conditions || [];
            
            // Merge with existing, avoiding duplicates
            const newConditions = importedConditions.filter(c => !inlineConditions.includes(c));
            inlineConditions = [...inlineConditions, ...newConditions];
            
            displayInlineConditions();
            updateHiddenTextarea();
            
            if (newConditions.length > 0) {
                showInlineSuccess(`Imported ${newConditions.length} new conditions`);
            } else {
                showInlineSuccess('All standard conditions are already present');
            }
        } else {
            showInlineError(data.error || 'Failed to import conditions');
        }
    } catch (error) {
        console.error('Error importing conditions:', error);
        showInlineError('Failed to import conditions');
    } finally {
        // Restore button state
        const importBtn = document.querySelector('.btn-import-conditions');
        if (importBtn) {
            importBtn.textContent = originalText;
            importBtn.disabled = false;
        }
    }
}

/**
 * Setup autocomplete for inline condition input
 */
function setupInlineConditionAutocomplete() {
    const input = document.getElementById('inlineConditionInput');
    const dropdown = document.getElementById('inlineConditionAutocomplete');
    
    if (!input || !dropdown) return;
    
    let timeoutId;
    
    input.addEventListener('input', function() {
        clearTimeout(timeoutId);
        const query = this.value.trim();
        
        if (query.length < 2) {
            hideInlineConditionAutocomplete();
            return;
        }
        
        timeoutId = setTimeout(() => {
            searchInlineConditions(query);
        }, 300);
    });
    
    // Add condition on Enter key
    input.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            addInlineCondition();
        }
    });
    
    // Hide autocomplete when clicking outside
    document.addEventListener('click', function(e) {
        if (!input.contains(e.target) && !dropdown.contains(e.target)) {
            hideInlineConditionAutocomplete();
        }
    });
}

/**
 * Search for inline condition suggestions
 */
async function searchInlineConditions(query) {
    try {
        const response = await fetch(`/api/condition-suggestions?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        
        if (data.success && data.suggestions.length > 0) {
            showInlineConditionAutocomplete(data.suggestions);
        } else {
            hideInlineConditionAutocomplete();
        }
    } catch (error) {
        console.error('Error searching conditions:', error);
        hideInlineConditionAutocomplete();
    }
}

/**
 * Show autocomplete dropdown for inline conditions
 */
function showInlineConditionAutocomplete(suggestions) {
    const dropdown = document.getElementById('inlineConditionAutocomplete');
    if (!dropdown) return;
    
    dropdown.innerHTML = '';
    
    suggestions.forEach(suggestion => {
        // Skip if already in current conditions
        if (inlineConditions.includes(suggestion)) return;
        
        const item = document.createElement('div');
        item.className = 'autocomplete-item';
        item.textContent = suggestion;
        item.onclick = () => selectInlineConditionSuggestion(suggestion);
        dropdown.appendChild(item);
    });
    
    dropdown.style.display = dropdown.children.length > 0 ? 'block' : 'none';
}

/**
 * Hide autocomplete dropdown for inline conditions
 */
function hideInlineConditionAutocomplete() {
    const dropdown = document.getElementById('inlineConditionAutocomplete');
    if (dropdown) {
        dropdown.style.display = 'none';
    }
}

/**
 * Select a suggestion from autocomplete
 */
function selectInlineConditionSuggestion(suggestion) {
    const input = document.getElementById('inlineConditionInput');
    if (input) {
        input.value = suggestion;
        hideInlineConditionAutocomplete();
        addInlineCondition();
    }
}

/**
 * Update the hidden textarea with current conditions
 */
function updateHiddenTextarea() {
    const textarea = document.querySelector('textarea[name="trigger_conditions"]');
    if (textarea) {
        textarea.value = JSON.stringify(inlineConditions);
    }
}

/**
 * Show inline error message
 * @param {string} message - The error message
 */
function showInlineError(message) {
    // Create or update error element
    let errorDiv = document.getElementById('inlineConditionError');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.id = 'inlineConditionError';
        errorDiv.className = 'alert alert-danger alert-sm mt-1';
        
        const container = document.querySelector('.condition-management-container');
        if (container) {
            container.appendChild(errorDiv);
        }
    }
    
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    
    // Auto-hide after 3 seconds
    setTimeout(() => {
        if (errorDiv) {
            errorDiv.style.display = 'none';
        }
    }, 3000);
}

/**
 * Show inline success message
 * @param {string} message - The success message
 */
function showInlineSuccess(message) {
    // Create or update success element
    let successDiv = document.getElementById('inlineConditionSuccess');
    if (!successDiv) {
        successDiv = document.createElement('div');
        successDiv.id = 'inlineConditionSuccess';
        successDiv.className = 'alert alert-success alert-sm mt-1';
        
        const container = document.querySelector('.condition-management-container');
        if (container) {
            container.appendChild(successDiv);
        }
    }
    
    successDiv.textContent = message;
    successDiv.style.display = 'block';
    
    // Auto-hide after 3 seconds
    setTimeout(() => {
        if (successDiv) {
            successDiv.style.display = 'none';
        }
    }, 3000);
}

/**
 * Clear inline error message
 */
function clearInlineError() {
    const errorDiv = document.getElementById('inlineConditionError');
    if (errorDiv) {
        errorDiv.style.display = 'none';
    }
}

// Auto-initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on an edit page and have existing conditions
    const textarea = document.querySelector('textarea[name="trigger_conditions"]');
    if (textarea && textarea.value) {
        try {
            const existingConditions = JSON.parse(textarea.value);
            initializeInlineConditions(existingConditions);
        } catch (e) {
            // If not JSON, try to parse as comma-separated
            const conditions = textarea.value.split(',').map(c => c.trim()).filter(c => c);
            initializeInlineConditions(conditions);
        }
    } else {
        initializeInlineConditions([]);
    }
});