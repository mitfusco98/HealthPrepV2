/**
 * Screening Performance Optimization
 * Handles performance optimization for screening workflows
 */

class ScreeningPerformance {
    constructor() {
        this.debounceTimers = {};
        this.cache = new Map();
        this.initializePerformanceMonitoring();
        this.initializeOptimizations();
    }

    initializePerformanceMonitoring() {
        // Monitor page load performance
        if (window.performance && window.performance.timing) {
            window.addEventListener('load', () => {
                setTimeout(() => {
                    this.logPerformanceMetrics();
                }, 100);
            });
        }

        // Monitor user interactions
        this.initializeInteractionMonitoring();
    }

    initializeOptimizations() {
        // Optimize table rendering
        this.optimizeTableRendering();
        
        // Optimize form interactions
        this.optimizeFormInteractions();
        
        // Optimize API calls
        this.optimizeApiCalls();
        
        // Initialize lazy loading
        this.initializeLazyLoading();
        
        // Optimize memory usage
        this.initializeMemoryOptimization();
    }

    logPerformanceMetrics() {
        const timing = window.performance.timing;
        const metrics = {
            loadTime: timing.loadEventEnd - timing.navigationStart,
            domReady: timing.domContentLoadedEventEnd - timing.navigationStart,
            networkTime: timing.responseEnd - timing.fetchStart,
            renderTime: timing.loadEventEnd - timing.domContentLoadedEventStart
        };

        console.log('Page Performance Metrics:', metrics);

        // Send to analytics if needed
        this.sendPerformanceMetrics(metrics);
    }

    initializeInteractionMonitoring() {
        // Monitor button clicks
        document.addEventListener('click', (e) => {
            if (e.target.matches('button, .btn')) {
                const startTime = performance.now();
                
                requestAnimationFrame(() => {
                    const endTime = performance.now();
                    const responseTime = endTime - startTime;
                    
                    if (responseTime > 100) {
                        console.warn(`Slow button response: ${responseTime}ms`);
                    }
                });
            }
        });

        // Monitor form submissions
        document.addEventListener('submit', (e) => {
            const form = e.target;
            const startTime = performance.now();
            
            form.setAttribute('data-submit-time', startTime);
        });
    }

    optimizeTableRendering() {
        const tables = document.querySelectorAll('.table-large, .screening-table');
        
        tables.forEach(table => {
            this.implementVirtualScrolling(table);
            this.optimizeTableSorting(table);
        });
    }

    implementVirtualScrolling(table) {
        const tbody = table.querySelector('tbody');
        if (!tbody || tbody.children.length < 50) return;

        const rows = Array.from(tbody.children);
        const rowHeight = 60; // Approximate row height
        const visibleRows = Math.ceil(window.innerHeight / rowHeight) + 5;
        
        let startIndex = 0;
        let endIndex = Math.min(visibleRows, rows.length);

        const renderVisibleRows = () => {
            // Hide all rows
            rows.forEach((row, index) => {
                if (index >= startIndex && index < endIndex) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        };

        const handleScroll = this.debounce(() => {
            const scrollTop = window.pageYOffset;
            const newStartIndex = Math.floor(scrollTop / rowHeight);
            const newEndIndex = Math.min(newStartIndex + visibleRows, rows.length);

            if (newStartIndex !== startIndex || newEndIndex !== endIndex) {
                startIndex = newStartIndex;
                endIndex = newEndIndex;
                renderVisibleRows();
            }
        }, 16); // ~60fps

        window.addEventListener('scroll', handleScroll);
        renderVisibleRows();
    }

    optimizeTableSorting(table) {
        const headers = table.querySelectorAll('th[data-sortable]');
        
        headers.forEach(header => {
            header.addEventListener('click', this.debounce((e) => {
                this.performTableSort(table, header);
            }, 150));
        });
    }

    performTableSort(table, header) {
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const column = header.getAttribute('data-column');
        const currentSort = header.getAttribute('data-sort') || 'asc';
        const newSort = currentSort === 'asc' ? 'desc' : 'asc';

        // Show loading state
        table.classList.add('table-loading');

        // Use requestAnimationFrame for smooth sorting
        requestAnimationFrame(() => {
            const sortedRows = this.sortTableRows(rows, column, newSort);
            
            // Update DOM efficiently
            const fragment = document.createDocumentFragment();
            sortedRows.forEach(row => fragment.appendChild(row));
            tbody.appendChild(fragment);

            // Update sort indicators
            headers.forEach(h => {
                h.removeAttribute('data-sort');
                h.classList.remove('sort-asc', 'sort-desc');
            });
            
            header.setAttribute('data-sort', newSort);
            header.classList.add(`sort-${newSort}`);

            // Remove loading state
            table.classList.remove('table-loading');
        });
    }

    sortTableRows(rows, column, direction) {
        return rows.sort((a, b) => {
            const aValue = this.getCellValue(a, column);
            const bValue = this.getCellValue(b, column);
            
            let comparison = 0;
            
            if (this.isNumeric(aValue) && this.isNumeric(bValue)) {
                comparison = parseFloat(aValue) - parseFloat(bValue);
            } else if (this.isDate(aValue) && this.isDate(bValue)) {
                comparison = new Date(aValue) - new Date(bValue);
            } else {
                comparison = aValue.localeCompare(bValue);
            }
            
            return direction === 'desc' ? -comparison : comparison;
        });
    }

    getCellValue(row, column) {
        const cell = row.querySelector(`[data-column="${column}"]`) || 
                    row.children[parseInt(column)] ||
                    row.querySelector(`td:nth-child(${parseInt(column) + 1})`);
        
        return cell ? (cell.getAttribute('data-value') || cell.textContent.trim()) : '';
    }

    isNumeric(value) {
        return !isNaN(value) && !isNaN(parseFloat(value));
    }

    isDate(value) {
        return !isNaN(Date.parse(value));
    }

    optimizeFormInteractions() {
        // Optimize form validation
        const forms = document.querySelectorAll('form');
        
        forms.forEach(form => {
            this.optimizeFormValidation(form);
            this.implementFormCaching(form);
        });
    }

    optimizeFormValidation(form) {
        const inputs = form.querySelectorAll('input, select, textarea');
        
        inputs.forEach(input => {
            // Debounce validation
            input.addEventListener('input', this.debounce((e) => {
                this.validateFieldOptimized(input);
            }, 300));

            // Immediate validation on blur
            input.addEventListener('blur', (e) => {
                this.validateFieldOptimized(input);
            });
        });
    }

    validateFieldOptimized(field) {
        // Use cached validation rules
        const cacheKey = `validation-${field.name}`;
        let rules = this.cache.get(cacheKey);
        
        if (!rules) {
            rules = this.extractValidationRules(field);
            this.cache.set(cacheKey, rules);
        }

        return this.applyValidationRules(field, rules);
    }

    extractValidationRules(field) {
        return {
            required: field.hasAttribute('required'),
            pattern: field.getAttribute('pattern'),
            min: field.getAttribute('min'),
            max: field.getAttribute('max'),
            minLength: field.getAttribute('minlength'),
            maxLength: field.getAttribute('maxlength'),
            type: field.getAttribute('type')
        };
    }

    applyValidationRules(field, rules) {
        const value = field.value.trim();
        
        // Quick validation checks
        if (rules.required && !value) {
            this.setFieldError(field, 'This field is required');
            return false;
        }
        
        if (value && rules.pattern && !new RegExp(rules.pattern).test(value)) {
            this.setFieldError(field, 'Invalid format');
            return false;
        }
        
        // Clear errors if validation passes
        this.clearFieldError(field);
        return true;
    }

    implementFormCaching(form) {
        const cacheKey = `form-data-${form.id || 'default'}`;
        
        // Load cached data
        const cachedData = this.getFromLocalStorage(cacheKey);
        if (cachedData) {
            this.populateFormFromCache(form, cachedData);
        }

        // Save data on input
        const saveFormData = this.debounce(() => {
            const formData = this.extractFormData(form);
            this.saveToLocalStorage(cacheKey, formData);
        }, 1000);

        form.addEventListener('input', saveFormData);
        
        // Clear cache on successful submission
        form.addEventListener('submit', () => {
            this.removeFromLocalStorage(cacheKey);
        });
    }

    optimizeApiCalls() {
        // Implement request caching
        this.apiCache = new Map();
        this.pendingRequests = new Map();
        
        // Override fetch for caching
        this.originalFetch = window.fetch;
        window.fetch = this.cachedFetch.bind(this);
    }

    cachedFetch(url, options = {}) {
        const cacheKey = this.generateCacheKey(url, options);
        
        // Return cached response if available
        if (options.method === 'GET' && this.apiCache.has(cacheKey)) {
            const cached = this.apiCache.get(cacheKey);
            if (Date.now() - cached.timestamp < 300000) { // 5 minutes
                return Promise.resolve(cached.response.clone());
            }
        }

        // Return pending request if one exists
        if (this.pendingRequests.has(cacheKey)) {
            return this.pendingRequests.get(cacheKey);
        }

        // Make new request
        const request = this.originalFetch(url, options)
            .then(response => {
                // Cache successful GET requests
                if (options.method === 'GET' && response.ok) {
                    this.apiCache.set(cacheKey, {
                        response: response.clone(),
                        timestamp: Date.now()
                    });
                }
                
                this.pendingRequests.delete(cacheKey);
                return response;
            })
            .catch(error => {
                this.pendingRequests.delete(cacheKey);
                throw error;
            });

        this.pendingRequests.set(cacheKey, request);
        return request;
    }

    generateCacheKey(url, options) {
        return `${options.method || 'GET'}-${url}`;
    }

    initializeLazyLoading() {
        // Lazy load images
        const images = document.querySelectorAll('img[data-src]');
        
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.getAttribute('data-src');
                        img.removeAttribute('data-src');
                        imageObserver.unobserve(img);
                    }
                });
            });

            images.forEach(img => imageObserver.observe(img));
        }

        // Lazy load content sections
        this.initializeContentLazyLoading();
    }

    initializeContentLazyLoading() {
        const lazyElements = document.querySelectorAll('[data-lazy-load]');
        
        if ('IntersectionObserver' in window) {
            const contentObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        this.loadLazyContent(entry.target);
                        contentObserver.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.1 });

            lazyElements.forEach(element => contentObserver.observe(element));
        }
    }

    loadLazyContent(element) {
        const url = element.getAttribute('data-lazy-load');
        if (!url) return;

        element.innerHTML = '<div class="text-center p-3"><div class="spinner-healthcare"></div></div>';

        fetch(url)
            .then(response => response.text())
            .then(html => {
                element.innerHTML = html;
                
                // Initialize any new components
                this.initializeNewComponents(element);
            })
            .catch(error => {
                console.error('Error loading lazy content:', error);
                element.innerHTML = '<div class="alert alert-warning">Failed to load content</div>';
            });
    }

    initializeMemoryOptimization() {
        // Clean up event listeners on navigation
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });

        // Periodic cache cleanup
        setInterval(() => {
            this.cleanupCache();
        }, 300000); // 5 minutes
    }

    cleanupCache() {
        const now = Date.now();
        
        // Clean API cache
        for (const [key, value] of this.apiCache.entries()) {
            if (now - value.timestamp > 600000) { // 10 minutes
                this.apiCache.delete(key);
            }
        }

        // Clean local storage cache
        this.cleanupLocalStorageCache();
    }

    // Utility methods
    debounce(func, wait) {
        const key = func.toString();
        
        return (...args) => {
            clearTimeout(this.debounceTimers[key]);
            this.debounceTimers[key] = setTimeout(() => func.apply(this, args), wait);
        };
    }

    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    // Local storage helpers
    saveToLocalStorage(key, data) {
        try {
            localStorage.setItem(key, JSON.stringify(data));
        } catch (e) {
            console.warn('Failed to save to localStorage:', e);
        }
    }

    getFromLocalStorage(key) {
        try {
            const data = localStorage.getItem(key);
            return data ? JSON.parse(data) : null;
        } catch (e) {
            console.warn('Failed to read from localStorage:', e);
            return null;
        }
    }

    removeFromLocalStorage(key) {
        try {
            localStorage.removeItem(key);
        } catch (e) {
            console.warn('Failed to remove from localStorage:', e);
        }
    }

    cleanupLocalStorageCache() {
        const keys = Object.keys(localStorage);
        keys.forEach(key => {
            if (key.startsWith('form-data-') || key.startsWith('cache-')) {
                try {
                    const data = JSON.parse(localStorage.getItem(key));
                    if (data.timestamp && Date.now() - data.timestamp > 86400000) { // 24 hours
                        localStorage.removeItem(key);
                    }
                } catch (e) {
                    // Invalid data, remove it
                    localStorage.removeItem(key);
                }
            }
        });
    }

    // Form helpers
    extractFormData(form) {
        const formData = new FormData(form);
        const data = {};
        
        for (const [key, value] of formData.entries()) {
            data[key] = value;
        }
        
        return { data, timestamp: Date.now() };
    }

    populateFormFromCache(form, cachedData) {
        if (!cachedData.data) return;
        
        Object.entries(cachedData.data).forEach(([key, value]) => {
            const field = form.querySelector(`[name="${key}"]`);
            if (field && field.type !== 'password') {
                field.value = value;
            }
        });
    }

    setFieldError(field, message) {
        field.classList.add('is-invalid');
        
        let feedback = field.parentElement.querySelector('.invalid-feedback');
        if (!feedback) {
            feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            field.parentElement.appendChild(feedback);
        }
        
        feedback.textContent = message;
    }

    clearFieldError(field) {
        field.classList.remove('is-invalid');
        
        const feedback = field.parentElement.querySelector('.invalid-feedback');
        if (feedback) {
            feedback.remove();
        }
    }

    initializeNewComponents(container) {
        // Re-initialize modals, tooltips, etc. in the new content
        if (typeof bootstrap !== 'undefined') {
            // Initialize Bootstrap components
            const tooltips = container.querySelectorAll('[data-bs-toggle="tooltip"]');
            tooltips.forEach(el => new bootstrap.Tooltip(el));
            
            const popovers = container.querySelectorAll('[data-bs-toggle="popover"]');
            popovers.forEach(el => new bootstrap.Popover(el));
        }
    }

    sendPerformanceMetrics(metrics) {
        // Send to analytics endpoint if configured
        if (window.analytics && typeof window.analytics.track === 'function') {
            window.analytics.track('Page Performance', metrics);
        }
    }

    cleanup() {
        // Clear all timers
        Object.values(this.debounceTimers).forEach(timer => clearTimeout(timer));
        
        // Clear caches
        this.cache.clear();
        this.apiCache.clear();
        this.pendingRequests.clear();
        
        // Restore original fetch
        if (this.originalFetch) {
            window.fetch = this.originalFetch;
        }
    }
}

// Initialize performance optimization
document.addEventListener('DOMContentLoaded', function() {
    window.screeningPerformance = new ScreeningPerformance();
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ScreeningPerformance;
}
