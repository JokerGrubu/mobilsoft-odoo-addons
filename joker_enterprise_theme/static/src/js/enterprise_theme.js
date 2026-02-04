/** @odoo-module **/

/**
 * Joker Enterprise Theme
 * Additional UI enhancements for Enterprise-like experience
 */

import { Component, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";

// Add smooth transitions to page loads
document.addEventListener('DOMContentLoaded', function() {
    // Add enterprise theme class to body
    document.body.classList.add('joker-enterprise-theme');

    // Smooth scroll behavior
    document.documentElement.style.scrollBehavior = 'smooth';
});

// Add hover effects enhancement
const enhanceHoverEffects = () => {
    const cards = document.querySelectorAll('.o_kanban_record, .o_form_sheet');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
        });
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
};

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhanceHoverEffects);
} else {
    enhanceHoverEffects();
}
