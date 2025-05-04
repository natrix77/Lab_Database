/**
 * Main JavaScript file for the Student Register Book web application
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Add event listener for semester selection
    const semesterSelect = document.getElementById('semester-select');
    if (semesterSelect) {
        semesterSelect.addEventListener('change', function() {
            if (this.value === 'new') {
                const newSemesterForm = document.getElementById('new-semester-form');
                if (newSemesterForm) {
                    newSemesterForm.classList.remove('d-none');
                }
            } else {
                const newSemesterForm = document.getElementById('new-semester-form');
                if (newSemesterForm) {
                    newSemesterForm.classList.add('d-none');
                }
            }
        });
    }

    // Toggle all checkboxes in a table
    const selectAllCheckbox = document.getElementById('select-all');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            const checkboxes = document.querySelectorAll('.student-checkbox');
            checkboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
        });
    }

    // Form validation
    const forms = document.querySelectorAll('.needs-validation');
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
}); 