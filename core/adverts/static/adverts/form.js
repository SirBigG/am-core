document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".advert-photo-control").forEach(function (control) {
    var inputs = Array.prototype.slice.call(
      control.querySelectorAll(".advert-photo-input")
    );
    var summary = control.querySelector("[data-advert-photo-summary]");

    function selectedFiles() {
      return inputs.reduce(function (files, input) {
        return files.concat(Array.prototype.slice.call(input.files || []));
      }, []);
    }

    function updateControl() {
      var files = selectedFiles();

      inputs.forEach(function (input) {
        var slot = input.closest(".advert-photo-slot");
        var filename = slot ? slot.querySelector("[data-advert-photo-filename]") : null;
        var names = Array.prototype.map.call(input.files || [], function (file) {
          return file.name;
        });

        if (slot) {
          slot.classList.toggle("advert-photo-slot--selected", names.length > 0);
        }
        if (filename) {
          filename.textContent = names.join(", ");
        }
      });

      if (summary) {
        if (files.length) {
          var names = files.map(function (file) {
            return file.name;
          });
          summary.textContent = files.length + " / " + inputs.length + " фото: " + names.join(", ");
        } else {
          summary.textContent = "Фото не обрано";
        }
      }
    }

    inputs.forEach(function (input) {
      input.addEventListener("change", function () {
        updateControl();
      });
    });

    updateControl();
  });
});
