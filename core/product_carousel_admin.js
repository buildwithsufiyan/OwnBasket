document.addEventListener('DOMContentLoaded', function() {
    const sourceTypeField = document.querySelector('#id_source_type');
    if (!sourceTypeField) {
        return;
    }

    const categoryRow = document.querySelector('.form-row.field-category');
    const brandRow = document.querySelector('.form-row.field-brand');
    const manualProductsRow = document.querySelector('.form-row.field-manual_products');

    function toggleSourceFields() {
        const selectedSource = sourceTypeField.value;

        if (categoryRow) {
            categoryRow.style.display = selectedSource === 'category' ? 'block' : 'none';
        }
        if (brandRow) {
            brandRow.style.display = selectedSource === 'brand' ? 'block' : 'none';
        }
        if (manualProductsRow) {
            manualProductsRow.style.display = selectedSource === 'manual' ? 'block' : 'none';
        }
    }

    // Initial toggle on page load
    toggleSourceFields();

    // Add event listener for changes
    sourceTypeField.addEventListener('change', toggleSourceFields);

    // For Django 4.2+ with admin views that might load content dynamically
    // This ensures our script re-runs if the form is re-rendered via JS.
    // Using a simple interval as a fallback for complex admin scenarios.
    setInterval(function() {
        if (document.querySelector('#id_source_type') && !document.querySelector('#id_source_type').hasAttribute('data-event-attached')) {
            document.querySelector('#id_source_type').addEventListener('change', toggleSourceFields);
            document.querySelector('#id_source_type').setAttribute('data-event-attached', 'true');
        }
    }, 1000);
});