/**
 * Digital Dukan - Daily Sales Trend Visualization
 * Fetches aggregated sales data from /api/chart-data and renders with Chart.js.
 */

document.addEventListener('DOMContentLoaded', () => {
    initSalesChart();
});

async function initSalesChart() {
    const canvas = document.getElementById('salesChart');
    if (!canvas) return;

    const emptyNotice = document.getElementById('chartEmptyState');

    try {
        const response = await fetch('/api/chart-data');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const labels = data.labels || [];
        const values = data.values || [];

        if (labels.length === 0) {
            if (emptyNotice) emptyNotice.style.display = 'flex';
            canvas.style.display = 'none';
            return;
        }

        if (emptyNotice) emptyNotice.style.display = 'none';
        canvas.style.display = 'block';

        const ctx = canvas.getContext('2d');

        // Create gradient fill for smooth line/area chart
        const gradient = ctx.createLinearGradient(0, 0, 0, 280);
        gradient.addColorStop(0, 'rgba(37, 99, 235, 0.35)');
        gradient.addColorStop(1, 'rgba(37, 99, 235, 0.02)');

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Daily Revenue (₹)',
                    data: values,
                    borderColor: '#2563eb',
                    backgroundColor: gradient,
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.35,
                    pointBackgroundColor: '#2563eb',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: '#0f172a',
                        titleColor: '#cbd5e1',
                        bodyColor: '#ffffff',
                        padding: 10,
                        callbacks: {
                            label: function(context) {
                                return ` Revenue: ₹${context.parsed.y.toFixed(2)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#64748b',
                            font: {
                                size: 12
                            }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: '#e2e8f0',
                            drawBorder: false
                        },
                        ticks: {
                            color: '#64748b',
                            callback: function(val) {
                                return '₹' + val;
                            }
                        }
                    }
                }
            }
        });

    } catch (error) {
        console.error('Failed to load sales chart data:', error);
        if (emptyNotice) {
            emptyNotice.style.display = 'flex';
            emptyNotice.innerHTML = '<p style="color: var(--color-danger);">Unable to load sales trend chart data.</p>';
        }
    }
}
