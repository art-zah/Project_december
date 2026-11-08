document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;

    searchInput.addEventListener('input', () => {
        const value = searchInput.value.toLowerCase().trim();
        const rows = document.querySelectorAll('tbody tr');
        let visibleCount = 0;

        rows.forEach(row => {
            const text = row.innerText.toLowerCase();
            const match = text.includes(value);
            row.style.display = match ? '' : 'none';
            if (match) visibleCount++;
        });

        document.querySelectorAll('.card').forEach(card => {
            if (card.id === 'noResults') return;
            const cardRows = card.querySelectorAll('tbody tr');
            if (cardRows.length > 0) {
                const cardVisibleRows = card.querySelectorAll('tbody tr:not([style*="display: none"])');
                card.style.display = cardVisibleRows.length > 0 ? '' : 'none';
            }
        });

        const noResults = document.getElementById('noResults');
        if (noResults) {
            noResults.style.display = (visibleCount === 0 && value !== '') ? 'block' : 'none';
        }
    });
});
