// Provider Feeds functionality

const selectAll = document.getElementById("select_all");
if (selectAll) {
    selectAll.addEventListener("change", function () {
        document.querySelectorAll(".selection-item").forEach(function (item) {
            item.checked = selectAll.checked;
        });
    });
}
