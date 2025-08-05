/**
 * Screening Keywords Modal Management
 * Handles the tag-based keyword system for screening types
 */

let currentScreeningTypeId = null;
let currentKeywords = [];

/**
 * Open the keyword manager modal
 * @param {number} screeningTypeId - The screening type ID
 * @param {string} screeningName - The screening type name
 */
function openKeywordManager(screeningTypeId, screeningName) {
    currentScreeningTypeId = screeningTypeId;
    
    // Update modal title
    document.getElementById('keywordModalTitle').textContent = `Manage Keywords: ${screeningName}`;
    
    // Load existing keywords
    loadKeywords(screeningTypeId);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('keywordManagerModal'));
    modal.show();
}

/**
 * Load keywords from the server
 * @param {number} screeningTypeId - The screening type ID
 */
async function loadKeywords(screeningTypeId) {
    try {
        const response = await fetch(`/api/screening-keywords/${screeningTypeId}`);
        const data = await response.json();
        
        if (data.success) {
            currentKeywords = data.keywords || [];
            displayKeywords();
        } else {
            console.error('Error loading keywords:', data.error);
            showKeywordError('Failed to load keywords');
        }
    } catch (error) {
        console.error('Error loading keywords:', error);
        showKeywordError('Failed to load keywords');
    }
}

/**
 * Display keywords in the modal
 */
function displayKeywords() {
    const container = document.getElementById('keywordsContainer');
    container.innerHTML = '';
    
    if (currentKeywords.length === 0) {
        container.innerHTML = '<p class="text-muted text-center">No keywords added yet.</p>';
        return;
    }
    
    currentKeywords.forEach((keyword, index) => {
        const keywordElement = document.createElement('div');
        keywordElement.className = 'keyword-tag';
        keywordElement.innerHTML = `
            <span class="badge bg-primary me-2 mb-2 p-2">
                ${escapeHtml(keyword)}
                <button type="button" class="btn-close btn-close-white ms-2" 
                        onclick="removeKeyword(${index})" aria-label="Remove keyword"></button>
            </span>
        `;
        container.appendChild(keywordElement);
    });
}

/**
 * Add a new keyword
 */
function addKeyword() {
    const input = document.getElementById('newKeywordInput');
    const keyword = input.value.trim();
    
    if (!keyword) {
        showKeywordError('Please enter a keyword');
        return;
    }
    
    // Check for duplicates
    if (currentKeywords.includes(keyword)) {
        showKeywordError('Keyword already exists');
        return;
    }
    
    // Add keyword
    currentKeywords.push(keyword);
    input.value = '';
    displayKeywords();
    clearKeywordError();
}

/**
 * Remove a keyword by index
 * @param {number} index - The index of the keyword to remove
 */
function removeKeyword(index) {
    if (index >= 0 && index < currentKeywords.length) {
        currentKeywords.splice(index, 1);
        displayKeywords();
    }
}

/**
 * Save keywords to the server
 */
async function saveKeywords() {
    if (!currentScreeningTypeId) {
        showKeywordError('No screening type selected');
        return;
    }
    
    try {
        // Show loading state
        const saveBtn = document.getElementById('saveKeywordsBtn');
        const originalText = saveBtn.textContent;
        saveBtn.textContent = 'Saving...';
        saveBtn.disabled = true;
        
        const response = await fetch(`/api/screening-keywords/${currentScreeningTypeId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                keywords: currentKeywords
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('keywordManagerModal'));
            modal.hide();
            
            // Show success message
            showAlert('success', data.message || 'Keywords updated successfully');
            
            // Refresh the page or update the display
            if (typeof refreshKeywordDisplay === 'function') {
                refreshKeywordDisplay();
            } else {
                // Fallback: reload page
                window.location.reload();
            }
        } else {
            showKeywordError(data.error || 'Failed to save keywords');
        }
    } catch (error) {
        console.error('Error saving keywords:', error);
        showKeywordError('Failed to save keywords');
    } finally {
        // Restore button state
        const saveBtn = document.getElementById('saveKeywordsBtn');
        saveBtn.textContent = originalText;
        saveBtn.disabled = false;
    }
}

/**
 * Show error message in the modal
 * @param {string} message - The error message
 */
function showKeywordError(message) {
    const errorDiv = document.getElementById('keywordError');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
}

/**
 * Clear error message in the modal
 */
function clearKeywordError() {
    const errorDiv = document.getElementById('keywordError');
    errorDiv.style.display = 'none';
}

/**
 * Get CSRF token from meta tag
 * @returns {string} CSRF token
 */
function getCSRFToken() {
    const token = document.querySelector('meta[name="csrf-token"]');
    return token ? token.getAttribute('content') : '';
}

/**
 * Escape HTML to prevent XSS
 * @param {string} unsafe - Unsafe string
 * @returns {string} Safe HTML string
 */
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

/**
 * Show alert message
 * @param {string} type - Alert type (success, error, warning, info)
 * @param {string} message - Alert message
 */
function showAlert(type, message) {
    // Create alert element
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Insert at top of main content
    const main = document.querySelector('main') || document.querySelector('.container').firstElementChild;
    main.insertBefore(alertDiv, main.firstChild);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Add keyword on Enter key
    const newKeywordInput = document.getElementById('newKeywordInput');
    if (newKeywordInput) {
        newKeywordInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                addKeyword();
            }
        });
    }
    
    // Clear error when typing
    if (newKeywordInput) {
        newKeywordInput.addEventListener('input', function() {
            clearKeywordError();
        });
    }
});