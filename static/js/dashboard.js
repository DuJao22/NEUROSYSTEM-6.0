// Dashboard JavaScript functionality for Sistema Neuropsicológico

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeDashboard();
    setupEventListeners();
    loadDashboardData();
});

// Initialize dashboard components
function initializeDashboard() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Add fade-in animation to cards
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {
        setTimeout(() => {
            card.classList.add('fade-in');
        }, index * 100);
    });
}

// Setup event listeners
function setupEventListeners() {
    // Form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });

    // Auto-refresh functionality
    const refreshBtn = document.getElementById('refreshDashboard');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            refreshDashboard();
        });
    }

    // Search functionality
    const searchInputs = document.querySelectorAll('[data-search]');
    searchInputs.forEach(input => {
        input.addEventListener('input', function() {
            const target = document.querySelector(this.dataset.search);
            if (target) {
                filterTable(target, this.value);
            }
        });
    });

    // Sort functionality
    const sortHeaders = document.querySelectorAll('[data-sort]');
    sortHeaders.forEach(header => {
        header.style.cursor = 'pointer';
        header.addEventListener('click', function() {
            const table = this.closest('table');
            const column = this.dataset.sort;
            sortTable(table, column);
        });
    });
}

// Load dashboard data
function loadDashboardData() {
    // Update real-time statistics
    updateStatistics();
    
    // Initialize charts if Chart.js is available
    if (typeof Chart !== 'undefined') {
        initializeCharts();
    }
    
    // Load recent activities
    loadRecentActivities();
}

// Update statistics
function updateStatistics() {
    const statCards = document.querySelectorAll('[data-stat]');
    statCards.forEach(card => {
        const stat = card.dataset.stat;
        animateNumber(card.querySelector('h3'), card.querySelector('h3').textContent);
    });
}

// Animate numbers
function animateNumber(element, finalValue) {
    const numericValue = parseFloat(finalValue.replace(/[^\d.-]/g, ''));
    if (isNaN(numericValue)) return;
    
    const duration = 1000;
    const startTime = performance.now();
    const startValue = 0;
    
    function updateNumber(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const currentValue = startValue + (numericValue - startValue) * easeOutQuart(progress);
        
        if (finalValue.includes('R$')) {
            element.textContent = 'R$ ' + currentValue.toFixed(2);
        } else {
            element.textContent = Math.floor(currentValue);
        }
        
        if (progress < 1) {
            requestAnimationFrame(updateNumber);
        } else {
            element.textContent = finalValue;
        }
    }
    
    requestAnimationFrame(updateNumber);
}

// Easing function
function easeOutQuart(t) {
    return 1 - (--t) * t * t * t;
}

// Initialize charts
function initializeCharts() {
    // Only initialize if Chart.js is available
    if (typeof Chart === 'undefined') {
        console.warn('Chart.js not loaded, skipping chart initialization');
        return;
    }
    
    // Financial chart
    const financialChart = document.getElementById('financialChart');
    if (financialChart) {
        createFinancialChart(financialChart);
    }
    
    // Performance chart
    const performanceChart = document.getElementById('performanceChart');
    if (performanceChart) {
        createPerformanceChart(performanceChart);
    }
    
    // Tax chart
    const taxChart = document.getElementById('taxChart');
    if (taxChart) {
        createTaxChart(taxChart);
    }
}

// Create financial chart
function createFinancialChart(canvas) {
    if (typeof Chart === 'undefined') {
        console.warn('Chart.js not available');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    
    // Chart configuration
    const config = {
        type: 'line',
        data: {
            labels: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun'],
            datasets: [{
                label: 'Faturamento',
                data: [12000, 19000, 15000, 25000, 22000, 30000],
                borderColor: 'rgb(13, 110, 253)',
                backgroundColor: 'rgba(13, 110, 253, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: true,
                    text: 'Evolução do Faturamento'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return 'R$ ' + value.toLocaleString('pt-BR');
                        }
                    }
                }
            }
        }
    };
    
    try {
        new Chart(ctx, config);
    } catch (error) {
        console.error('Error creating financial chart:', error);
    }
}

// Create performance chart
function createPerformanceChart(canvas) {
    const ctx = canvas.getContext('2d');
    
    const config = {
        type: 'bar',
        data: {
            labels: ['Dr. Silva', 'Dr. Santos', 'Dr. Oliveira', 'Dr. Costa'],
            datasets: [{
                label: 'Pacientes Atendidos',
                data: [25, 30, 20, 35],
                backgroundColor: [
                    'rgba(40, 167, 69, 0.8)',
                    'rgba(13, 110, 253, 0.8)',
                    'rgba(255, 193, 7, 0.8)',
                    'rgba(220, 53, 69, 0.8)'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: 'Performance dos Médicos'
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    };
    
    new Chart(ctx, config);
}

// Create tax chart
function createTaxChart(canvas) {
    const ctx = canvas.getContext('2d');
    
    const config = {
        type: 'doughnut',
        data: {
            labels: ['Líquido', 'IR', 'INSS', 'ISS'],
            datasets: [{
                data: [70, 12, 8, 10],
                backgroundColor: [
                    'rgba(40, 167, 69, 0.8)',
                    'rgba(220, 53, 69, 0.8)',
                    'rgba(255, 193, 7, 0.8)',
                    'rgba(13, 110, 253, 0.8)'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                title: {
                    display: true,
                    text: 'Distribuição de Impostos'
                }
            }
        }
    };
    
    new Chart(ctx, config);
}

// Load recent activities
function loadRecentActivities() {
    const activitiesContainer = document.getElementById('recentActivities');
    if (!activitiesContainer) return;
    
    // Add loading state
    activitiesContainer.innerHTML = '<div class="text-center"><i class="fas fa-spinner fa-spin"></i> Carregando...</div>';
    
    // Simulate loading (replace with actual data fetch)
    setTimeout(() => {
        const activities = [
            { patient: 'João Silva', action: 'Sessão 3 realizada', time: '2 horas atrás' },
            { patient: 'Maria Santos', action: 'Laudo enviado', time: '4 horas atrás' },
            { patient: 'Pedro Oliveira', action: 'Nova sessão agendada', time: '1 dia atrás' }
        ];
        
        let html = '<div class="list-group">';
        activities.forEach(activity => {
            html += `
                <div class="list-group-item">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${activity.patient}</h6>
                        <small>${activity.time}</small>
                    </div>
                    <p class="mb-1">${activity.action}</p>
                </div>
            `;
        });
        html += '</div>';
        
        activitiesContainer.innerHTML = html;
    }, 1000);
}

// Refresh dashboard
function refreshDashboard() {
    const refreshBtn = document.getElementById('refreshDashboard');
    if (refreshBtn) {
        refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Atualizando...';
        refreshBtn.disabled = true;
    }
    
    // Simulate refresh
    setTimeout(() => {
        loadDashboardData();
        
        if (refreshBtn) {
            refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Atualizar';
            refreshBtn.disabled = false;
        }
        
        // Show success message
        showNotification('Dashboard atualizado com sucesso!', 'success');
    }, 2000);
}

// Filter table
function filterTable(table, searchTerm) {
    const rows = table.querySelectorAll('tbody tr');
    const term = searchTerm.toLowerCase();
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(term) ? '' : 'none';
    });
}

// Sort table
function sortTable(table, column) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const headerIndex = Array.from(table.querySelectorAll('th')).findIndex(th => th.dataset.sort === column);
    
    if (headerIndex === -1) return;
    
    const isAscending = table.dataset.sortOrder !== 'asc';
    table.dataset.sortOrder = isAscending ? 'asc' : 'desc';
    
    rows.sort((a, b) => {
        const aValue = a.cells[headerIndex].textContent.trim();
        const bValue = b.cells[headerIndex].textContent.trim();
        
        // Try to parse as numbers
        const aNum = parseFloat(aValue.replace(/[^\d.-]/g, ''));
        const bNum = parseFloat(bValue.replace(/[^\d.-]/g, ''));
        
        if (!isNaN(aNum) && !isNaN(bNum)) {
            return isAscending ? aNum - bNum : bNum - aNum;
        }
        
        // Sort as strings
        return isAscending ? aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
    });
    
    // Clear tbody and append sorted rows
    tbody.innerHTML = '';
    rows.forEach(row => tbody.appendChild(row));
    
    // Update sort indicators
    table.querySelectorAll('th[data-sort]').forEach(th => {
        th.classList.remove('sort-asc', 'sort-desc');
    });
    
    const sortHeader = table.querySelector(`th[data-sort="${column}"]`);
    if (sortHeader) {
        sortHeader.classList.add(isAscending ? 'sort-asc' : 'sort-desc');
    }
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// Format currency
function formatCurrency(value) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(value);
}

// Format date
function formatDate(date) {
    return new Intl.DateTimeFormat('pt-BR').format(new Date(date));
}

// Export functions for use in other scripts
window.DashboardUtils = {
    showNotification,
    formatCurrency,
    formatDate,
    animateNumber,
    filterTable,
    sortTable
};
