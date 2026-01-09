// Tag Feeds functionality

document.addEventListener('DOMContentLoaded', function() {
    const table = document.querySelector('.table-bordered');
    if (!table) return;

    table.addEventListener('mouseover', e => {
        if (e.target.matches('td, th')) {
            const colIndex = e.target.cellIndex;
            // Don't highlight the first column which contains row headers
            if (colIndex > 0) {
                for (const row of table.rows) {
                    if (row.cells[colIndex]) {
                        row.cells[colIndex].classList.add('hover-column');
                    }
                }
            }
        }
    });

    table.addEventListener('mouseout', e => {
        if (e.target.matches('td, th')) {
            const colIndex = e.target.cellIndex;
            if (colIndex > 0) {
                for (const row of table.rows) {
                     if (row.cells[colIndex]) {
                        row.cells[colIndex].classList.remove('hover-column');
                    }
                }
            }
        }
    });
});
