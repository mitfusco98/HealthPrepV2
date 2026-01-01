
// Medical Terminology JavaScript
// Handles medical term highlighting, tooltips, and terminology assistance

document.addEventListener('DOMContentLoaded', function() {
    // Only initialize if explicitly requested via data attribute
    if (document.body.hasAttribute('data-enable-medical-highlighting')) {
        initializeMedicalTerminology();
        initializeConfidenceIndicators();
        initializeMedicalTooltips();
    } else {
        // Initialize only autocomplete and helpers, skip highlighting
        initializeMedicalAutocomplete();
        initializeKeywordHelpers();
    }
});

// Initialize medical terminology features
function initializeMedicalTerminology() {
    // Highlight medical terms in content
    highlightMedicalTerms();
    
    // Initialize medical term autocomplete
    initializeMedicalAutocomplete();
    
    // Initialize medical keyword helpers
    initializeKeywordHelpers();
}

// Highlight medical terms in text content
function highlightMedicalTerms() {
    const medicalTerms = [
        'hypertension', 'diabetes', 'cardiovascular', 'pulmonary', 'hepatic',
        'renal', 'neurological', 'oncology', 'cardiology', 'endocrinology',
        'gastroenterology', 'nephrology', 'dermatology', 'ophthalmology',
        'otolaryngology', 'orthopedics', 'urology', 'gynecology', 'psychiatry',
        'radiology', 'pathology', 'anesthesiology', 'emergency medicine'
    ];
    
    const textElements = document.querySelectorAll('p, div, span, td');
    
    textElements.forEach(element => {
        if (element.children.length === 0) { // Only process text nodes
            const originalText = element.textContent;
            const termsPattern = new RegExp(`\\b(${medicalTerms.join('|')})\\b`, 'gi');
            
            if (termsPattern.test(originalText)) {
                const fragment = document.createDocumentFragment();
                let lastIndex = 0;
                
                termsPattern.lastIndex = 0;
                let match;
                while ((match = termsPattern.exec(originalText)) !== null) {
                    if (match.index > lastIndex) {
                        fragment.appendChild(document.createTextNode(originalText.slice(lastIndex, match.index)));
                    }
                    const span = document.createElement('span');
                    span.className = 'medical-term';
                    span.title = `Medical Term: ${match[0].toLowerCase()}`;
                    span.textContent = match[0];
                    fragment.appendChild(span);
                    lastIndex = termsPattern.lastIndex;
                }
                if (lastIndex < originalText.length) {
                    fragment.appendChild(document.createTextNode(originalText.slice(lastIndex)));
                }
                
                element.textContent = '';
                element.appendChild(fragment);
            }
        }
    });
}

// Initialize confidence indicators
function initializeConfidenceIndicators() {
    const confidenceElements = document.querySelectorAll('[data-confidence]');
    
    confidenceElements.forEach(element => {
        const confidence = parseFloat(element.dataset.confidence);
        const confidenceClass = getConfidenceClass(confidence);
        
        // Add confidence indicator
        if (!element.querySelector('.confidence-indicator')) {
            const indicator = document.createElement('span');
            indicator.className = `confidence-indicator ${confidenceClass}`;
            indicator.title = `Confidence: ${Math.round(confidence * 100)}%`;
            element.insertBefore(indicator, element.firstChild);
        }
    });
}

// Get confidence class based on confidence score
function getConfidenceClass(confidence) {
    if (confidence >= 0.8) return 'confidence-high';
    if (confidence >= 0.6) return 'confidence-medium';
    if (confidence >= 0.0) return 'confidence-low';
    return 'confidence-unknown';
}

// Initialize medical tooltips
function initializeMedicalTooltips() {
    // Initialize Bootstrap tooltips for medical terms
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"], .medical-term'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl, {
            container: 'body',
            delay: { show: 500, hide: 100 }
        });
    });
}

// Initialize medical term autocomplete
function initializeMedicalAutocomplete() {
    const medicalInputs = document.querySelectorAll('.medical-input, input[data-medical-terms]');
    
    medicalInputs.forEach(input => {
        // Add medical term suggestions
        input.addEventListener('input', function(e) {
            const value = e.target.value.toLowerCase();
            if (value.length >= 2) {
                showMedicalSuggestions(e.target, value);
            } else {
                hideMedicalSuggestions(e.target);
            }
        });
        
        // Hide suggestions when clicking outside
        document.addEventListener('click', function(e) {
            if (!input.contains(e.target)) {
                hideMedicalSuggestions(input);
            }
        });
    });
}

// Show medical term suggestions
function showMedicalSuggestions(input, value) {
    const suggestions = getMedicalSuggestions(value);
    
    if (suggestions.length > 0) {
        let suggestionContainer = input.parentNode.querySelector('.medical-suggestions');
        
        if (!suggestionContainer) {
            suggestionContainer = document.createElement('div');
            suggestionContainer.className = 'medical-suggestions';
            input.parentNode.appendChild(suggestionContainer);
        }
        
        // Clear existing suggestions safely
        suggestionContainer.textContent = '';
        
        // Build suggestions using safe DOM methods
        suggestions.forEach(suggestion => {
            const item = document.createElement('div');
            item.className = 'suggestion-item';
            item.dataset.value = suggestion;
            item.textContent = suggestion;
            item.addEventListener('click', function() {
                input.value = this.dataset.value;
                hideMedicalSuggestions(input);
                input.dispatchEvent(new Event('change'));
            });
            suggestionContainer.appendChild(item);
        });
        
        suggestionContainer.style.display = 'block';
    }
}

// Hide medical term suggestions
function hideMedicalSuggestions(input) {
    const suggestionContainer = input.parentNode.querySelector('.medical-suggestions');
    if (suggestionContainer) {
        suggestionContainer.style.display = 'none';
    }
}

// Get medical term suggestions based on input
function getMedicalSuggestions(value) {
    const medicalTerms = [
        'hypertension', 'diabetes mellitus', 'cardiovascular disease', 'pulmonary embolism',
        'hepatic dysfunction', 'renal failure', 'neurological disorder', 'oncology screening',
        'cardiology consultation', 'endocrinology referral', 'gastroenterology evaluation',
        'nephrology assessment', 'dermatology examination', 'ophthalmology screening',
        'otolaryngology consultation', 'orthopedic evaluation', 'urology screening',
        'gynecology examination', 'psychiatry evaluation', 'radiology imaging',
        'pathology review', 'anesthesiology consultation', 'emergency medicine',
        'primary care', 'specialty care', 'preventive care', 'diagnostic imaging',
        'laboratory testing', 'medication management', 'chronic disease management'
    ];
    
    return medicalTerms.filter(term => 
        term.toLowerCase().includes(value) || term.toLowerCase().startsWith(value)
    ).slice(0, 5);
}

// Initialize keyword helpers
function initializeKeywordHelpers() {
    const keywordBadges = document.querySelectorAll('.keyword-badge');
    
    keywordBadges.forEach(badge => {
        badge.addEventListener('click', function() {
            const targetInput = document.getElementById(this.dataset.target);
            if (targetInput) {
                const currentValue = targetInput.value;
                const keyword = this.textContent.trim();
                
                if (currentValue) {
                    targetInput.value = currentValue + ', ' + keyword;
                } else {
                    targetInput.value = keyword;
                }
                
                targetInput.dispatchEvent(new Event('input'));
                targetInput.focus();
            }
        });
    });
}

// Medical form validation helpers
function validateMedicalForm(form) {
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
            field.classList.add('is-valid');
        }
    });
    
    return isValid;
}

// Medical data processing indicators
function showProcessingIndicator(element, message = 'Processing medical data...') {
    const indicator = document.createElement('div');
    indicator.className = 'medical-processing-indicator';
    indicator.innerHTML = `
        <div class="spinner-border spinner-border-sm me-2" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
        ${message}
    `;
    
    element.appendChild(indicator);
    return indicator;
}

function hideProcessingIndicator(element) {
    const indicator = element.querySelector('.medical-processing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

// Export functions for use in other scripts
window.MedicalTerminology = {
    highlightMedicalTerms,
    initializeConfidenceIndicators,
    validateMedicalForm,
    showProcessingIndicator,
    hideProcessingIndicator,
    getConfidenceClass
};
