(function () {
    var pollCount = 0;
    var maxPollCount = 80;

    function styleSourceAreas(root) {
        var sourceAreas = (root || document).querySelectorAll(
            ".cke_source, textarea.cke_source, .cke_contents textarea"
        );
        sourceAreas.forEach(function (sourceArea) {
            sourceArea.style.setProperty("background", "#fff", "important");
            sourceArea.style.setProperty("color", "#111", "important");
            sourceArea.style.setProperty("caret-color", "#111", "important");
            sourceArea.style.setProperty("-webkit-text-fill-color", "#111", "important");
            sourceArea.style.setProperty("text-shadow", "none", "important");
        });
    }

    function styleSourceTextarea(editor) {
        if (!editor || !editor.container || !editor.container.$) {
            return;
        }

        styleSourceAreas(editor.container.$);

        if (editor.editable && editor.editable()) {
            var editableElement = editor.editable().$;
            if (editableElement) {
                editableElement.style.setProperty("background", "#fff", "important");
                editableElement.style.setProperty("color", "#111", "important");
                editableElement.style.setProperty("caret-color", "#111", "important");
                editableElement.style.setProperty("-webkit-text-fill-color", "#111", "important");
                editableElement.style.setProperty("text-shadow", "none", "important");
            }
        }
    }

    function bindEditor(editor) {
        if (editor._agromegaSourceStylesBound) {
            return;
        }
        editor._agromegaSourceStylesBound = true;

        styleSourceTextarea(editor);
        editor.on("mode", function () {
            window.setTimeout(function () {
                styleSourceTextarea(editor);
            }, 0);
            window.setTimeout(function () {
                styleSourceTextarea(editor);
            }, 100);
        });
    }

    function bindExistingEditors() {
        styleSourceAreas(document);

        if (!window.CKEDITOR) {
            if (pollCount < maxPollCount) {
                pollCount += 1;
                window.setTimeout(bindExistingEditors, 100);
            }
            return;
        }

        window.CKEDITOR.addCss(
            ".cke_source, .cke_contents textarea {" +
                "background: #fff !important;" +
                "color: #111 !important;" +
                "caret-color: #111 !important;" +
                "-webkit-text-fill-color: #111 !important;" +
                "text-shadow: none !important;" +
            "}"
        );

        Object.keys(window.CKEDITOR.instances).forEach(function (name) {
            bindEditor(window.CKEDITOR.instances[name]);
        });

        window.CKEDITOR.on("instanceReady", function (event) {
            bindEditor(event.editor);
        });
    }

    function observeDynamicSourceAreas() {
        if (!window.MutationObserver) {
            return;
        }

        var observer = new MutationObserver(function () {
            styleSourceAreas(document);
        });
        observer.observe(document.documentElement, {
            childList: true,
            subtree: true,
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            observeDynamicSourceAreas();
            bindExistingEditors();
        });
    } else {
        observeDynamicSourceAreas();
        bindExistingEditors();
    }
}());
