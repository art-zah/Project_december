document.addEventListener('DOMContentLoaded', () => {
    const controls = document.querySelectorAll('.sort-control');
    if (!controls.length) return;

    const weekdays = {
        'Понедельник': 1,
        'Вторник': 2,
        'Среда': 3,
        'Четверг': 4,
        'Пятница': 5,
        'Суббота': 6,
        'Воскресенье': 7
    };

    function parseConstraintSlot(val) {
        const parts = val.split('/');
        const day = parts[0] ? parts[0].trim() : '';
        const lesson = parts[1] ? parseInt(parts[1].replace(/\D+/g, ''), 10) || 0 : 0;
        return { day: weekdays[day] || 0, lesson };
    }

    function applySorting(event) {
        const changedControl = event.target;
        const table = changedControl.closest('table');
        if (!table) return;

        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        table.querySelectorAll('.sort-control').forEach(ctrl => {
            if (ctrl !== changedControl) ctrl.value = '';
        });

        const activeSorts = Array.from(table.querySelectorAll('.sort-control')).filter(x => x.value !== '');
        if (!activeSorts.length) return;

        const rows = Array.from(tbody.querySelectorAll('tr'));

        rows.sort((a, b) => {
            for (const sort of activeSorts) {
                const column = parseInt(sort.dataset.column, 10);
                const type = sort.dataset.type;
                const direction = sort.value;

                if (!a.cells[column] || !b.cells[column]) continue;
                const valueA = a.cells[column].innerText.trim();
                const valueB = b.cells[column].innerText.trim();

                let result = 0;
                if (type === 'number') {
                    const numA = parseFloat(valueA.replace(/\s+/g, '').replace(',', '.')) || 0;
                    const numB = parseFloat(valueB.replace(/\s+/g, '').replace(',', '.')) || 0;
                    result = numA - numB;
                } else if (type === 'weekday') {
                    const wA = weekdays[valueA] || 0;
                    const wB = weekdays[valueB] || 0;
                    result = wA - wB;
                } else if (type === 'weekday_constraint') {
                    const slotA = parseConstraintSlot(valueA);
                    const slotB = parseConstraintSlot(valueB);
                    result = (slotA.day - slotB.day) || (slotA.lesson - slotB.lesson);
                } else {
                    result = valueA.localeCompare(valueB, 'ru', { numeric: true, sensitivity: 'base' });
                }

                if (direction === 'desc') result *= -1;
                if (result !== 0) return result;
            }

            if (activeSorts.length === 1 && activeSorts[0].dataset.type === 'weekday') {
                const dayCol = parseInt(activeSorts[0].dataset.column, 10);
                const nextCol = dayCol + 1;
                if (a.cells[nextCol] && b.cells[nextCol]) {
                    const lA = parseInt(a.cells[nextCol].innerText.replace(/\D+/g, ''), 10) || 0;
                    const lB = parseInt(b.cells[nextCol].innerText.replace(/\D+/g, ''), 10) || 0;
                    if (lA !== lB) return lA - lB;
                }
            }

            return 0;
        });

        rows.forEach(row => tbody.appendChild(row));
    }

    controls.forEach(control => {
        control.addEventListener('change', applySorting);
    });
});
