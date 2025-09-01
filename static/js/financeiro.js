// Financial module JavaScript for Sistema Neuropsicológico

// Initialize financial module
document.addEventListener('DOMContentLoaded', function() {
    initializeFinancialModule();
    setupFinancialEventListeners();
    loadFinancialData();
});

// Initialize financial components
function initializeFinancialModule() {
    // Initialize date pickers
    const datePickers = document.querySelectorAll('input[type="month"]');
    datePickers.forEach(picker => {
        picker.addEventListener('change', function() {
            updateFinancialReport();
        });
    });

    // Initialize financial charts
    if (typeof Chart !== 'undefined') {
        initializeFinancialCharts();
    }

    // Setup auto-calculation forms
    setupAutoCalculation();
}

// Setup financial event listeners
function setupFinancialEventListeners() {
    // Tax calculation events
    const taxInputs = document.querySelectorAll('[data-tax-input]');
    taxInputs.forEach(input => {
        input.addEventListener('input', function() {
            calculateTaxes();
        });
    });

    // Payment confirmation events
    const paymentButtons = document.querySelectorAll('[data-payment-action]');
    paymentButtons.forEach(button => {
        button.addEventListener('click', function() {
            const action = this.dataset.paymentAction;
            const id = this.dataset.paymentId;
            handlePaymentAction(action, id);
        });
    });

    // Export events
    const exportButtons = document.querySelectorAll('[data-export]');
    exportButtons.forEach(button => {
        button.addEventListener('click', function() {
            const format = this.dataset.export;
            exportFinancialData(format);
        });
    });

    // Real-time validation
    const amountInputs = document.querySelectorAll('input[type="number"][data-currency]');
    amountInputs.forEach(input => {
        input.addEventListener('input', function() {
            validateAmount(this);
        });
    });
}

// Load financial data
function loadFinancialData() {
    // Update financial summaries
    updateFinancialSummaries();
    
    // Load pending payments
    loadPendingPayments();
    
    // Update charts
    updateFinancialCharts();
}

// Initialize financial charts
function initializeFinancialCharts() {
    // Revenue trend chart
    const revenueTrendChart = document.getElementById('revenueTrendChart');
    if (revenueTrendChart) {
        createRevenueTrendChart(revenueTrendChart);
    }

    // Tax distribution chart
    const taxDistributionChart = document.getElementById('taxDistributionChart');
    if (taxDistributionChart) {
        createTaxDistributionChart(taxDistributionChart);
    }

    // Team performance chart
    const teamPerformanceChart = document.getElementById('teamPerformanceChart');
    if (teamPerformanceChart) {
        createTeamPerformanceChart(teamPerformanceChart);
    }

    // Monthly comparison chart
    const monthlyComparisonChart = document.getElementById('monthlyComparisonChart');
    if (monthlyComparisonChart) {
        createMonthlyComparisonChart(monthlyComparisonChart);
    }
}

// Create revenue trend chart
function createRevenueTrendChart(canvas) {
    const ctx = canvas.getContext('2d');
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun'],
            datasets: [{
                label: 'Faturamento Bruto',
                data: [45000, 52000, 48000, 61000, 58000, 67000],
                borderColor: '#0d6efd',
                backgroundColor: 'rgba(13, 110, 253, 0.1)',
                tension: 0.4,
                fill: true
            }, {
                label: 'Faturamento Líquido',
                data: [31500, 36400, 33600, 42700, 40600, 46900],
                borderColor: '#198754',
                backgroundColor: 'rgba(25, 135, 84, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Evolução do Faturamento'
                },
                legend: {
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return formatCurrency(value);
                        }
                    }
                }
            },
            interaction: {
                intersect: false
            }
        }
    });
}

// Create tax distribution chart
function createTaxDistributionChart(canvas) {
    const ctx = canvas.getContext('2d');
    
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Valor Líquido', 'IR (27.5%)', 'INSS (11%)', 'ISS (5%)'],
            datasets: [{
                data: [56.5, 27.5, 11, 5],
                backgroundColor: [
                    '#198754',
                    '#dc3545',
                    '#fd7e14',
                    '#6f42c1'
                ],
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Distribuição de Impostos'
                },
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.label + ': ' + context.parsed + '%';
                        }
                    }
                }
            }
        }
    });
}

// Create team performance chart
function createTeamPerformanceChart(canvas) {
    const ctx = canvas.getContext('2d');
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Equipe Alpha', 'Equipe Beta', 'Equipe Gamma', 'Independentes'],
            datasets: [{
                label: 'Faturamento (R$)',
                data: [85000, 72000, 96000, 45000],
                backgroundColor: [
                    'rgba(13, 110, 253, 0.8)',
                    'rgba(25, 135, 84, 0.8)',
                    'rgba(255, 193, 7, 0.8)',
                    'rgba(220, 53, 69, 0.8)'
                ],
                borderColor: [
                    '#0d6efd',
                    '#198754',
                    '#ffc107',
                    '#dc3545'
                ],
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Performance por Equipe'
                },
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return formatCurrency(value);
                        }
                    }
                }
            }
        }
    });
}

// Create monthly comparison chart
function createMonthlyComparisonChart(canvas) {
    const ctx = canvas.getContext('2d');
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun'],
            datasets: [{
                label: 'Ano Atual',
                data: [45000, 52000, 48000, 61000, 58000, 67000],
                backgroundColor: 'rgba(13, 110, 253, 0.6)'
            }, {
                label: 'Ano Anterior',
                data: [41000, 48000, 45000, 55000, 52000, 59000],
                backgroundColor: 'rgba(108, 117, 125, 0.6)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Comparação Anual'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return formatCurrency(value);
                        }
                    }
                }
            }
        }
    });
}

// Calculate taxes automatically
function calculateTaxes() {
    const grossAmount = parseFloat(document.getElementById('grossAmount')?.value || 0);
    const irRate = parseFloat(document.getElementById('irRate')?.value || 27.5) / 100;
    const inssRate = parseFloat(document.getElementById('inssRate')?.value || 11) / 100;
    const issRate = parseFloat(document.getElementById('issRate')?.value || 5) / 100;
    
    const irAmount = grossAmount * irRate;
    const inssAmount = grossAmount * inssRate;
    const issAmount = grossAmount * issRate;
    const totalTaxes = irAmount + inssAmount + issAmount;
    const netAmount = grossAmount - totalTaxes;
    
    // Update display
    updateTaxDisplay('irAmount', irAmount);
    updateTaxDisplay('inssAmount', inssAmount);
    updateTaxDisplay('issAmount', issAmount);
    updateTaxDisplay('totalTaxes', totalTaxes);
    updateTaxDisplay('netAmount', netAmount);
    
    // Animate the changes
    animateTaxChanges();
}

// Update tax display
function updateTaxDisplay(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = formatCurrency(value);
        element.classList.add('highlight');
        setTimeout(() => {
            element.classList.remove('highlight');
        }, 1000);
    }
}

// Animate tax changes
function animateTaxChanges() {
    const taxElements = document.querySelectorAll('[data-tax-result]');
    taxElements.forEach(element => {
        element.style.transform = 'scale(1.05)';
        setTimeout(() => {
            element.style.transform = 'scale(1)';
        }, 200);
    });
}

// Setup auto-calculation
function setupAutoCalculation() {
    // Session value calculation
    const sessionInputs = document.querySelectorAll('[data-session-calc]');
    sessionInputs.forEach(input => {
        input.addEventListener('input', function() {
            calculateSessionTotal();
        });
    });
    
    // Team percentage calculation
    const teamInputs = document.querySelectorAll('[data-team-calc]');
    teamInputs.forEach(input => {
        input.addEventListener('input', function() {
            calculateTeamShare();
        });
    });
}

// Calculate session total
function calculateSessionTotal() {
    const sessionCount = parseInt(document.getElementById('sessionCount')?.value || 0);
    const sessionValue = parseFloat(document.getElementById('sessionValue')?.value || 0);
    const maxSessions = parseInt(document.getElementById('maxSessions')?.value || 8);
    
    const completedValue = sessionCount * sessionValue;
    const remainingValue = (maxSessions - sessionCount) * sessionValue;
    const totalValue = completedValue + remainingValue;
    
    updateDisplay('completedValue', completedValue);
    updateDisplay('remainingValue', remainingValue);
    updateDisplay('totalValue', totalValue);
}

// Calculate team share
function calculateTeamShare() {
    const totalRevenue = parseFloat(document.getElementById('totalRevenue')?.value || 0);
    const teamPercentage = parseFloat(document.getElementById('teamPercentage')?.value || 0) / 100;
    
    const teamShare = totalRevenue * teamPercentage;
    const clinicShare = totalRevenue - teamShare;
    
    updateDisplay('teamShare', teamShare);
    updateDisplay('clinicShare', clinicShare);
}

// Update display helper
function updateDisplay(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        if (element.tagName === 'INPUT') {
            element.value = value.toFixed(2);
        } else {
            element.textContent = formatCurrency(value);
        }
    }
}

// Handle payment actions
function handlePaymentAction(action, id) {
    switch (action) {
        case 'approve':
            approvePayment(id);
            break;
        case 'reject':
            rejectPayment(id);
            break;
        case 'view':
            viewPaymentDetails(id);
            break;
        default:
            console.warn('Unknown payment action:', action);
    }
}

// Approve payment
function approvePayment(paymentId) {
    if (confirm('Confirmar aprovação do pagamento?')) {
        // Show loading state
        const button = document.querySelector(`[data-payment-id="${paymentId}"]`);
        if (button) {
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processando...';
            button.disabled = true;
        }
        
        // Simulate API call
        setTimeout(() => {
            showNotification('Pagamento aprovado com sucesso!', 'success');
            refreshPaymentsList();
        }, 2000);
    }
}

// Reject payment
function rejectPayment(paymentId) {
    const reason = prompt('Motivo da rejeição:');
    if (reason) {
        showNotification('Pagamento rejeitado.', 'warning');
        refreshPaymentsList();
    }
}

// View payment details
function viewPaymentDetails(paymentId) {
    // Implementation for viewing payment details
    const modal = new bootstrap.Modal(document.getElementById('paymentDetailsModal'));
    modal.show();
}

// Update financial summaries
function updateFinancialSummaries() {
    const summaryCards = document.querySelectorAll('[data-financial-summary]');
    summaryCards.forEach(card => {
        const type = card.dataset.financialSummary;
        updateSummaryCard(card, type);
    });
}

// Update summary card
function updateSummaryCard(card, type) {
    const valueElement = card.querySelector('[data-value]');
    if (valueElement) {
        // Animate value update
        animateValue(valueElement);
    }
}

// Animate value
function animateValue(element) {
    element.style.transform = 'scale(1.1)';
    element.style.transition = 'transform 0.3s ease';
    setTimeout(() => {
        element.style.transform = 'scale(1)';
    }, 300);
}

// Load pending payments
function loadPendingPayments() {
    const pendingContainer = document.getElementById('pendingPayments');
    if (!pendingContainer) return;
    
    // Show loading
    pendingContainer.innerHTML = '<div class="text-center"><i class="fas fa-spinner fa-spin"></i> Carregando pagamentos...</div>';
    
    // Simulate loading
    setTimeout(() => {
        refreshPaymentsList();
    }, 1000);
}

// Refresh payments list
function refreshPaymentsList() {
    const pendingContainer = document.getElementById('pendingPayments');
    if (pendingContainer) {
        // Force page refresh for now (replace with AJAX in production)
        window.location.reload();
    }
}

// Update financial report
function updateFinancialReport() {
    const month = document.getElementById('monthSelector')?.value;
    if (month) {
        // Update URL and reload
        const url = new URL(window.location);
        url.searchParams.set('mes', month);
        window.location.href = url.toString();
    }
}

// Update financial charts
function updateFinancialCharts() {
    // Update existing charts with new data
    if (window.financialCharts) {
        Object.values(window.financialCharts).forEach(chart => {
            chart.update();
        });
    }
}

// Export financial data
function exportFinancialData(format) {
    showNotification(`Exportando dados em formato ${format.toUpperCase()}...`, 'info');
    
    // Simulate export
    setTimeout(() => {
        showNotification('Dados exportados com sucesso!', 'success');
    }, 2000);
}

// Validate amount input
function validateAmount(input) {
    const value = parseFloat(input.value);
    const min = parseFloat(input.min || 0);
    const max = parseFloat(input.max || Infinity);
    
    if (isNaN(value) || value < min || value > max) {
        input.classList.add('is-invalid');
        input.classList.remove('is-valid');
    } else {
        input.classList.add('is-valid');
        input.classList.remove('is-invalid');
    }
}

// Format currency
function formatCurrency(value) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(value);
}

// Show notification (using dashboard utility if available)
function showNotification(message, type = 'info') {
    if (window.DashboardUtils && window.DashboardUtils.showNotification) {
        window.DashboardUtils.showNotification(message, type);
    } else {
        alert(message); // Fallback
    }
}

// Export financial utilities
window.FinancialUtils = {
    calculateTaxes,
    formatCurrency,
    updateDisplay,
    showNotification
};

// Add CSS for highlight animation
const style = document.createElement('style');
style.textContent = `
    .highlight {
        background-color: rgba(255, 193, 7, 0.3) !important;
        transition: background-color 0.5s ease;
    }
`;
document.head.appendChild(style);
