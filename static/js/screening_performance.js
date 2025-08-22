/*!
 * Screening Performance JavaScript - Health-Prep v2
 * Performance optimization and UI enhancements for screening workflows
 */

/**
 * ScreeningPerformance - Optimizes screening list performance and user experience
 */
class ScreeningPerformance {
    constructor() {
        this.initialized = false;
        this.observerCallbacks = new Map();
        this.debounceTimers = new Map();
        this.cache = new Map();
        this.virtualScrollEnabled = false;
        
        this.init();
    }

    /**
     * Initialize performance optimizations
     */
    init() {
        if (this.initialized) return;
        
        this.setupIntersectionObserver();
        this.setupVirtualScrolling();
        this.setupLazyLoading();
        this.setupDebouncedActions();
        this.setupKeyboardShortcuts();
        this.setupTooltipOptimization();
        this.setupTableOptimizations();
        
        this.initialized = true;
        console.log('ScreeningPerformance initialized');
    }

    /**
     * Setup intersection observer for lazy loading
     */
    setupIntersectionObserver() {
        if (!window.IntersectionObserver) return;

        this.intersectionObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const element = entry.target;
                    const callback = this.observerCallbacks.get(element);
                    if (callback) {
                        callback(element);
                        this.intersectionObserver.unobserve(element);
                        this.observerCallbacks.delete(element);
                    }
                }
            });
        }, {
            rootMargin: '50px',
            threshold: 0.1
        });
    }

    /**
     * Setup virtual scrolling for large datasets
     */
    setupVirtualScrolling() {
        const largeTable = document.querySelector('.screening-table tbody');
        if (!largeTable) return;

        const rows = largeTable.querySelectorAll('tr');
        if (rows.length > 100) {
            this.enableVirtualScrolling(largeTable, rows);
        }
    }

    /**
     * Enable virtual scrolling for large tables
     */
    enableVirtualScrolling(container, rows) {
        this.virtualScrollEnabled = true;
        const rowHeight = 60; // Approximate row height
        const viewportHeight = window.innerHeight;
        const visibleRows = Math.ceil(viewportHeight / rowHeight) + 5; // Add buffer
        
        let scrollTop = 0;
        let startIndex = 0;
        
        const updateVisibleRows = () => {
            const newStartIndex = Math.floor(scrollTop / rowHeight);
            const endIndex = Math.min(newStartIndex + visibleRows, rows.length);
            
            if (newStartIndex !== startIndex) {
                startIndex = newStartIndex;
                
                // Hide all rows
                rows.forEach((row, index) => {
                    if (index < startIndex || index >= endIndex) {
                        row.style.display = 'none';
                    } else {
                        row.style.display = '';
                    }
                });
            }
        };

        // Throttled scroll handler
        const scrollHandler = this.throttle(() => {
            scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            updateVisibleRows();
        }, 16); // 60fps

        window.addEventListener('scroll', scrollHandler);
        updateVisibleRows(); // Initial render
    }

    /**
     * Setup lazy loading for heavy content
     */
    setupLazyLoading() {
        // Lazy load document previews
        const documentPreviews = document.querySelectorAll('[data-lazy-content]');
        documentPreviews.forEach(element => {
            this.observeElement(element, this.loadLazyContent.bind(this));
        });

        // Lazy load screening keywords
        const keywordContainers = document.querySelectorAll('.keywords-badges-container');
        keywordContainers.forEach(container => {
            this.observeElement(container, this.loadScreeningKeywords.bind(this));
        });
    }

    /**
     * Observe element with intersection observer
     */
    observeElement(element, callback) {
        if (!this.intersectionObserver) return;
        
        this.observerCallbacks.set(element, callback);
        this.intersectionObserver.observe(element);
    }

    /**
     * Load lazy content
     */
    loadLazyContent(element) {
        const contentType = element.dataset.lazyContent;
        const contentId = element.dataset.contentId;
        
        switch (contentType) {
            case 'document-preview':
                this.loadDocumentPreview(element, contentId);
                break;
            case 'screening-details':
                this.loadScreeningDetails(element, contentId);
                break;
            default:
                console.warn('Unknown lazy content type:', contentType);
        }
    }

    /**
     * Load screening keywords with caching
     */
    loadScreeningKeywords(container) {
        const screeningTypeId = container.id.replace('keywords-display-', '');
        const cacheKey = `keywords-${screeningTypeId}`;
        
        // Check cache first
        if (this.cache.has(cacheKey)) {
            this.displayKeywords(container, this.cache.get(cacheKey));
            return;
        }

        // Show loading state
        container.innerHTML = '<div class="loading-inline"><span class="loading-spinner loading-spinner-sm me-2"></span>Loading keywords...</div>';

        fetch(`/api/screening-keywords/${screeningTypeId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.keywords) {
                    this.cache.set(cacheKey, data.keywords);
                    this.displayKeywords(container, data.keywords);
                } else {
                    container.innerHTML = '<small class="text-muted">No keywords defined</small>';
                }
            })
            .catch(error => {
                console.error('Error loading keywords:', error);
                container.innerHTML = '<small class="text-danger">Error loading keywords</small>';
            });
    }

    /**
     * Display keywords as badges
     */
    displayKeywords(container, keywords) {
        if (!keywords || keywords.length === 0) {
            container.innerHTML = '<small class="text-muted">No keywords defined</small>';
            return;
        }

        const keywordsHtml = keywords.map(keyword => 
            `<span class="badge bg-primary me-1 mb-1">${this.escapeHtml(keyword)}</span>`
        ).join('');

        container.innerHTML = keywordsHtml;
    }

    /**
     * Setup debounced actions
     */
    setupDebouncedActions() {
        // Debounced search
        const searchInputs = document.querySelectorAll('[data-search-target]');
        searchInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                this.debounce('search', () => {
                    this.performSearch(e.target);
                }, 300);
            });
        });

        // Debounced filter updates
        const filterSelects = document.querySelectorAll('[data-filter-target]');
        filterSelects.forEach(select => {
            select.addEventListener('change', (e) => {
                this.debounce('filter', () => {
                    this.performFilter(e.target);
                }, 150);
            });
        });
    }

    /**
     * Debounce function execution
     */
    debounce(key, callback, delay) {
        if (this.debounceTimers.has(key)) {
            clearTimeout(this.debounceTimers.get(key));
        }

        const timer = setTimeout(() => {
            callback();
            this.debounceTimers.delete(key);
        }, delay);

        this.debounceTimers.set(key, timer);
    }

    /**
     * Throttle function execution
     */
    throttle(callback, delay) {
        let lastCall = 0;
        return function(...args) {
            const now = Date.now();
            if (now - lastCall >= delay) {
                lastCall = now;
                callback.apply(this, args);
            }
        };
    }

    /**
     * Perform search with highlighting
     */
    performSearch(input) {
        const searchTerm = input.value.toLowerCase().trim();
        const targetSelector = input.dataset.searchTarget;
        const searchableElements = document.querySelectorAll(targetSelector);

        searchableElements.forEach(element => {
            const text = element.textContent.toLowerCase();
            const shouldShow = !searchTerm || text.includes(searchTerm);
            
            // Show/hide element
            const row = element.closest('tr');
            if (row) {
                row.style.display = shouldShow ? '' : 'none';
                
                // Add highlighting
                if (shouldShow && searchTerm) {
                    this.highlightSearchTerm(element, searchTerm);
                } else {
                    this.removeHighlighting(element);
                }
            }
        });

        // Update result count
        this.updateSearchResultCount(searchableElements, searchTerm);
    }

    /**
     * Highlight search terms
     */
    highlightSearchTerm(element, searchTerm) {
        const originalText = element.dataset.originalText || element.textContent;
        if (!element.dataset.originalText) {
            element.dataset.originalText = originalText;
        }

        const regex = new RegExp(`(${this.escapeRegex(searchTerm)})`, 'gi');
        const highlightedText = originalText.replace(regex, '<mark class="medical-search-highlight">$1</mark>');
        element.innerHTML = highlightedText;
    }

    /**
     * Remove search highlighting
     */
    removeHighlighting(element) {
        if (element.dataset.originalText) {
            element.textContent = element.dataset.originalText;
            delete element.dataset.originalText;
        }
    }

    /**
     * Update search result count
     */
    updateSearchResultCount(elements, searchTerm) {
        const visibleCount = Array.from(elements).filter(el => {
            const row = el.closest('tr');
            return row && row.style.display !== 'none';
        }).length;

        const countElement = document.querySelector('.search-result-count');
        if (countElement) {
            if (searchTerm) {
                countElement.textContent = `Showing ${visibleCount} results`;
                countElement.style.display = 'block';
            } else {
                countElement.style.display = 'none';
            }
        }
    }

    /**
     * Perform filtering
     */
    performFilter(select) {
        const filterValue = select.value.toLowerCase();
        const targetSelector = select.dataset.filterTarget;
        const filterableElements = document.querySelectorAll(targetSelector);

        filterableElements.forEach(element => {
            const filterData = element.dataset.filterValue || element.textContent.toLowerCase();
            const shouldShow = !filterValue || filterData.includes(filterValue);
            
            const row = element.closest('tr');
            if (row) {
                row.style.display = shouldShow ? '' : 'none';
            }
        });
    }

    /**
     * Setup keyboard shortcuts
     */
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K for search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                const searchInput = document.querySelector('[data-search-target]');
                if (searchInput) {
                    searchInput.focus();
                    searchInput.select();
                }
            }

            // Escape to clear search
            if (e.key === 'Escape') {
                const searchInput = document.querySelector('[data-search-target]');
                if (searchInput && searchInput.value) {
                    searchInput.value = '';
                    this.performSearch(searchInput);
                    searchInput.blur();
                }
            }

            // Ctrl/Cmd + R for refresh
            if ((e.ctrlKey || e.metaKey) && e.key === 'r' && e.shiftKey) {
                e.preventDefault();
                const refreshButton = document.querySelector('[data-modal-action="refresh-screenings"]');
                if (refreshButton) {
                    refreshButton.click();
                }
            }
        });
    }

    /**
     * Setup tooltip optimization
     */
    setupTooltipOptimization() {
        // Use event delegation for tooltips
        document.addEventListener('mouseenter', (e) => {
            if (e.target && e.target.matches && e.target.matches('[data-bs-toggle="tooltip"]')) {
                this.showTooltip(e.target);
            }
        }, true);

        document.addEventListener('mouseleave', (e) => {
            if (e.target && e.target.matches && e.target.matches('[data-bs-toggle="tooltip"]')) {
                this.hideTooltip(e.target);
            }
        }, true);
    }

    /**
     * Show tooltip with delay
     */
    showTooltip(element) {
        this.debounce(`tooltip-${element.dataset.bsOriginalTitle}`, () => {
            if (!element.tooltip) {
                element.tooltip = new bootstrap.Tooltip(element);
            }
            element.tooltip.show();
        }, 300);
    }

    /**
     * Hide tooltip
     */
    hideTooltip(element) {
        if (element.tooltip) {
            element.tooltip.hide();
        }
    }

    /**
     * Setup table optimizations
     */
    setupTableOptimizations() {
        const tables = document.querySelectorAll('.table-responsive table');
        tables.forEach(table => {
            this.optimizeTable(table);
        });
    }

    /**
     * Optimize table performance
     */
    optimizeTable(table) {
        // Add table-layout: fixed for better performance
        table.style.tableLayout = 'fixed';
        
        // Optimize column widths
        const headers = table.querySelectorAll('th');
        headers.forEach((header, index) => {
            if (!header.style.width) {
                switch (index) {
                    case 0: // Patient name
                        header.style.width = '20%';
                        break;
                    case 1: // Screening type
                        header.style.width = '25%';
                        break;
                    case 2: // Status
                        header.style.width = '15%';
                        break;
                    case 3: // Last completed
                        header.style.width = '15%';
                        break;
                    case 4: // Frequency
                        header.style.width = '12%';
                        break;
                    case 5: // Matched documents
                        header.style.width = '13%';
                        break;
                }
            }
        });

        // Add row hover optimization
        this.setupRowHoverOptimization(table);
    }

    /**
     * Setup optimized row hover effects
     */
    setupRowHoverOptimization(table) {
        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        tbody.addEventListener('mouseenter', (e) => {
            if (e.target.matches('tr')) {
                e.target.classList.add('table-hover-active');
            }
        }, true);

        tbody.addEventListener('mouseleave', (e) => {
            if (e.target.matches('tr')) {
                e.target.classList.remove('table-hover-active');
            }
        }, true);
    }

    /**
     * Load document preview
     */
    loadDocumentPreview(element, documentId) {
        const cacheKey = `document-preview-${documentId}`;
        
        if (this.cache.has(cacheKey)) {
            element.innerHTML = this.cache.get(cacheKey);
            return;
        }

        element.innerHTML = '<div class="loading-inline"><span class="loading-spinner loading-spinner-sm me-2"></span>Loading preview...</div>';

        // Simulate document preview loading
        setTimeout(() => {
            const previewHtml = `
                <div class="medical-document-preview">
                    <div class="document-preview-header">
                        <strong>Document Preview</strong>
                        <span class="badge confidence-high ms-2">High Confidence</span>
                    </div>
                    <div class="document-preview-content">
                        Preview content would be loaded here...
                    </div>
                </div>
            `;
            
            this.cache.set(cacheKey, previewHtml);
            element.innerHTML = previewHtml;
        }, 500);
    }

    /**
     * Load screening details
     */
    loadScreeningDetails(element, screeningId) {
        const cacheKey = `screening-details-${screeningId}`;
        
        if (this.cache.has(cacheKey)) {
            element.innerHTML = this.cache.get(cacheKey);
            return;
        }

        element.innerHTML = '<div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text"></div>';

        // Simulate screening details loading
        setTimeout(() => {
            const detailsHtml = `
                <div class="screening-details">
                    <div class="row">
                        <div class="col-6">
                            <small class="text-muted">Status</small>
                            <div class="fw-bold">Due Soon</div>
                        </div>
                        <div class="col-6">
                            <small class="text-muted">Due Date</small>
                            <div class="fw-bold">2024-03-15</div>
                        </div>
                    </div>
                </div>
            `;
            
            this.cache.set(cacheKey, detailsHtml);
            element.innerHTML = detailsHtml;
        }, 300);
    }

    /**
     * Clear cache
     */
    clearCache(pattern = null) {
        if (pattern) {
            for (const key of this.cache.keys()) {
                if (key.includes(pattern)) {
                    this.cache.delete(key);
                }
            }
        } else {
            this.cache.clear();
        }
    }

    /**
     * Get performance metrics
     */
    getPerformanceMetrics() {
        return {
            cacheSize: this.cache.size,
            observedElements: this.observerCallbacks.size,
            virtualScrollEnabled: this.virtualScrollEnabled,
            debounceTimers: this.debounceTimers.size
        };
    }

    /**
     * Utility: Escape HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Utility: Escape regex
     */
    escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    /**
     * Clean up resources
     */
    destroy() {
        if (this.intersectionObserver) {
            this.intersectionObserver.disconnect();
        }

        this.debounceTimers.forEach(timer => clearTimeout(timer));
        this.debounceTimers.clear();
        this.observerCallbacks.clear();
        this.cache.clear();
        
        this.initialized = false;
    }
}

// Initialize screening performance when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.screeningPerformance = new ScreeningPerformance();
});

// Handle page visibility changes to pause/resume optimizations
document.addEventListener('visibilitychange', function() {
    if (window.screeningPerformance) {
        if (document.hidden) {
            // Pause optimizations when page is hidden
            window.screeningPerformance.clearCache();
        } else {
            // Resume optimizations when page is visible
            window.screeningPerformance.init();
        }
    }
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ScreeningPerformance;
}

