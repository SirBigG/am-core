(function () {
  function getRubricSelect() {
    return (
      document.getElementById("id_rubric") ||
      document.querySelector('[name="rubric"]') ||
      document.querySelector("#id_rubric_from")
    );
  }

  function parseAppleRubricIds(select) {
    var raw = select.getAttribute("data-apple-rubric-ids") || "";
    return raw
      .split(",")
      .map(function (value) {
        return value.trim();
      })
      .filter(Boolean);
  }

  function updateAppleAttributeSections() {
    var rubricSelect = getRubricSelect();
    if (!rubricSelect) {
      return;
    }

    var appleRubricIds = parseAppleRubricIds(rubricSelect);
    var isAppleVariety = appleRubricIds.length > 0 && appleRubricIds.indexOf(rubricSelect.value) !== -1;
    var sections = document.querySelectorAll(".apple-variety-attributes");

    sections.forEach(function (section) {
      section.classList.toggle("is-visible", isAppleVariety);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var rubricSelect = getRubricSelect();
    updateAppleAttributeSections();

    if (rubricSelect) {
      rubricSelect.addEventListener("change", updateAppleAttributeSections);
    }
  });
})();
