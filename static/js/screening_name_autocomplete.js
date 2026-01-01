/**
 * Screening Name Autocomplete System
 * Provides fuzzy detection and standardized name suggestions for screening types
 */

function escapeHtml(str) {
    if (typeof str !== 'string') return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

let screeningNameTimeout;

/**
 * Initialize screening name autocomplete
 */
function initializeScreeningNameAutocomplete() {
    const input = document.getElementById('screeningNameInput');
    const dropdown = document.getElementById('screeningNameAutocomplete');
    
    if (!input || !dropdown) return;
    
    // Setup input event listener
    input.addEventListener('input', function() {
        clearTimeout(screeningNameTimeout);
        const query = this.value.trim();
        
        if (query.length < 2) {
            hideScreeningNameAutocomplete();
            return;
        }
        
        screeningNameTimeout = setTimeout(() => {
            searchScreeningNames(query);
        }, 300);
    });
    
    // Handle keyboard navigation
    input.addEventListener('keydown', function(e) {
        const dropdown = document.getElementById('screeningNameAutocomplete');
        const items = dropdown.querySelectorAll('.autocomplete-item');
        
        if (items.length === 0) return;
        
        let selectedIndex = -1;
        items.forEach((item, index) => {
            if (item.classList.contains('selected')) {
                selectedIndex = index;
            }
        });
        
        switch(e.key) {
            case 'ArrowDown':
                e.preventDefault();
                selectedIndex = (selectedIndex + 1) % items.length;
                updateSelection(items, selectedIndex);
                break;
            case 'ArrowUp':
                e.preventDefault();
                selectedIndex = selectedIndex <= 0 ? items.length - 1 : selectedIndex - 1;
                updateSelection(items, selectedIndex);
                break;
            case 'Enter':
                e.preventDefault();
                if (selectedIndex >= 0) {
                    selectScreeningName(items[selectedIndex].textContent);
                }
                break;
            case 'Escape':
                hideScreeningNameAutocomplete();
                break;
        }
    });
    
    // Hide autocomplete when clicking outside
    document.addEventListener('click', function(e) {
        if (!input.contains(e.target) && !dropdown.contains(e.target)) {
            hideScreeningNameAutocomplete();
        }
    });
    
    // Check for standardization on blur
    input.addEventListener('blur', function() {
        setTimeout(() => {
            checkScreeningNameStandardization(this.value);
        }, 200);
    });
}

/**
 * Search for screening name suggestions
 */
async function searchScreeningNames(query) {
    try {
        const response = await fetch(`/api/screening-name-suggestions?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        
        if (data.success && data.suggestions.length > 0) {
            showScreeningNameAutocomplete(data.suggestions);
        } else {
            hideScreeningNameAutocomplete();
        }
    } catch (error) {
        console.error('Error searching screening names:', error);
        hideScreeningNameAutocomplete();
    }
}

/**
 * Show autocomplete dropdown with suggestions
 */
function showScreeningNameAutocomplete(suggestions) {
    const dropdown = document.getElementById('screeningNameAutocomplete');
    if (!dropdown) return;
    
    dropdown.innerHTML = '';
    
    suggestions.forEach((suggestion, index) => {
        const item = document.createElement('div');
        item.className = 'autocomplete-item';
        if (index === 0) item.classList.add('selected');
        item.textContent = suggestion;
        item.onclick = () => selectScreeningName(suggestion);
        dropdown.appendChild(item);
    });
    
    dropdown.style.display = 'block';
}

/**
 * Hide autocomplete dropdown
 */
function hideScreeningNameAutocomplete() {
    const dropdown = document.getElementById('screeningNameAutocomplete');
    if (dropdown) {
        dropdown.style.display = 'none';
    }
}

/**
 * Select a screening name from suggestions
 */
function selectScreeningName(name) {
    const input = document.getElementById('screeningNameInput');
    if (input) {
        input.value = name;
        hideScreeningNameAutocomplete();
        
        // Show success message
        showScreeningNameFeedback(`Selected standardized name: "${name}"`, 'success');
        
        // Trigger change event for any listeners
        input.dispatchEvent(new Event('change'));
    }
}

/**
 * Update keyboard selection in dropdown
 */
function updateSelection(items, selectedIndex) {
    items.forEach((item, index) => {
        if (index === selectedIndex) {
            item.classList.add('selected');
        } else {
            item.classList.remove('selected');
        }
    });
}

/**
 * Check if the entered name should be standardized
 */
async function checkScreeningNameStandardization(inputName) {
    if (!inputName || inputName.trim().length < 3) return;
    
    try {
        const response = await fetch(`/api/standardize-screening-name?name=${encodeURIComponent(inputName)}`);
        const data = await response.json();
        
        if (data.success && data.was_standardized) {
            // Show suggestion to use standardized name
            showStandardizationSuggestion(data.original_name, data.standardized_name, data.suggestions);
        }
    } catch (error) {
        console.error('Error checking name standardization:', error);
    }
}

/**
 * Show standardization suggestion
 */
function showStandardizationSuggestion(originalName, standardizedName, suggestions) {
    // Create or update suggestion element
    let suggestionDiv = document.getElementById('nameStandardizationSuggestion');
    if (!suggestionDiv) {
        suggestionDiv = document.createElement('div');
        suggestionDiv.id = 'nameStandardizationSuggestion';
        suggestionDiv.className = 'alert alert-info alert-sm mt-2';
        
        const nameContainer = document.querySelector('#screeningNameInput').closest('.mb-3');
        if (nameContainer) {
            nameContainer.appendChild(suggestionDiv);
        }
    }
    
    const escapedName = escapeHtml(standardizedName);
    let html = `
        <div class="d-flex justify-content-between align-items-start">
            <div>
                <strong>Suggestion:</strong> Did you mean "<strong>${escapedName}</strong>"?
            </div>
            <div>
                <button type="button" class="btn btn-sm btn-outline-primary me-1" 
                        onclick="acceptStandardization('${escapedName}')">
                    Use This
                </button>
                <button type="button" class="btn btn-sm btn-outline-secondary" 
                        onclick="dismissStandardization()">
                    Dismiss
                </button>
            </div>
        </div>
    `;
    
    if (suggestions && suggestions.length > 0) {
        html += `
            <div class="mt-2">
                <small>Other suggestions: </small>
                ${suggestions.slice(0, 3).map(s => {
                    const escapedS = escapeHtml(s);
                    return `<button type="button" class="btn btn-xs btn-outline-info me-1" 
                             onclick="acceptStandardization('${escapedS}')">${escapedS}</button>`;
                }).join('')}
            </div>
        `;
    }
    
    suggestionDiv.innerHTML = html;
    suggestionDiv.style.display = 'block';
}

/**
 * Accept a standardization suggestion
 */
function acceptStandardization(standardizedName) {
    const input = document.getElementById('screeningNameInput');
    if (input) {
        input.value = standardizedName;
        showScreeningNameFeedback(`Updated to standardized name: "${standardizedName}"`, 'success');
        dismissStandardization();
    }
}

/**
 * Dismiss the standardization suggestion
 */
function dismissStandardization() {
    const suggestionDiv = document.getElementById('nameStandardizationSuggestion');
    if (suggestionDiv) {
        suggestionDiv.style.display = 'none';
    }
}

/**
 * Show popular screening names
 */
function showPopularScreenings() {
    const popularScreenings = [
        'Mammogram',
        'Pap Smear', 
        'Colonoscopy',
        'A1C Test',
        'Lipid Panel',
        'Blood Pressure Monitoring',
        'DEXA Scan',
        'Comprehensive Eye Exam',
        'Chest X-ray',
        'Complete Blood Count (CBC)',
        'Electrocardiogram (ECG)',
        'Skin Cancer Screening'
    ];
    
    showScreeningNameAutocomplete(popularScreenings);
}

/**
 * Show feedback message for screening name operations
 */
function showScreeningNameFeedback(message, type = 'info') {
    // Create or update feedback element
    let feedbackDiv = document.getElementById('screeningNameFeedback');
    if (!feedbackDiv) {
        feedbackDiv = document.createElement('div');
        feedbackDiv.id = 'screeningNameFeedback';
        
        const nameContainer = document.querySelector('#screeningNameInput').closest('.mb-3');
        if (nameContainer) {
            nameContainer.appendChild(feedbackDiv);
        }
    }
    
    feedbackDiv.className = `alert alert-${type} alert-sm mt-1`;
    feedbackDiv.textContent = message;
    feedbackDiv.style.display = 'block';
    
    // Auto-hide after 3 seconds
    setTimeout(() => {
        if (feedbackDiv) {
            feedbackDiv.style.display = 'none';
        }
    }, 3000);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeScreeningNameAutocomplete();
});