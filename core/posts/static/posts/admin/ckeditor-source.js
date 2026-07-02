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
            "}" +
            ".article-note, .important-note {" +
                "margin: 0 0 1.35rem;" +
                "padding: 0.95rem 1rem;" +
                "background: #f0f7f2;" +
                "border-left: 4px solid #2f7d45;" +
                "color: #203829;" +
            "}" +
            ".important-note {" +
                "background: #f8e2d4;" +
                "border-color: rgba(178, 34, 34, 0.18);" +
                "border-left-color: #b22222;" +
            "}" +
            "table {" +
                "width: 100% !important;" +
                "min-width: 100%;" +
                "max-width: 100%;" +
                "table-layout: fixed !important;" +
                "margin: 1.35rem 0;" +
                "border: 1px solid rgba(47, 125, 69, 0.18);" +
                "border-collapse: collapse;" +
                "color: #223044;" +
                "font-size: 0.86em;" +
                "line-height: 1.55;" +
            "}" +
            "thead th, table tr:first-child th, table tr:first-child td {" +
                "background: #dcefd7;" +
                "color: #223044;" +
                "font-weight: 800;" +
            "}" +
            "th, td {" +
                "width: auto !important;" +
                "padding: 0.75rem 0.875rem;" +
                "border: 1px solid rgba(47, 125, 69, 0.16);" +
                "text-align: left;" +
                "vertical-align: top;" +
            "}" +
            "col {" +
                "width: auto !important;" +
            "}" +
            "tbody tr:nth-child(even) td {" +
                "background: #fbfdfb;" +
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
