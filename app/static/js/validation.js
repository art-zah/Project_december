document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', event => {
            const requiredFields = form.querySelectorAll('[required]');
            let firstInvalid = null;

            requiredFields.forEach(field => {
                if (!field.value || !field.value.trim()) {
                    if (!firstInvalid) firstInvalid = field;
                }
            });

            if (firstInvalid) {
                event.preventDefault();
                firstInvalid.focus();
                alert('Пожалуйста, заполните все обязательные поля.');
            }
        });
    });
});
