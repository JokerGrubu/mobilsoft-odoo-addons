/**
 * MobilSoft Portal — Ortak JS Yardımcıları
 */
document.addEventListener('DOMContentLoaded', function () {
    // Mobilde sidebar dışına tıklayınca kapat
    const overlay = document.querySelector('.ms-portal__overlay');
    if (overlay) {
        overlay.addEventListener('click', function () {
            const sidebar = document.querySelector('.ms-portal__sidebar');
            if (sidebar) sidebar.classList.remove('show');
        });
    }
});
