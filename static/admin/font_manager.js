(function () {
    function createElement(tagName, className, textContent) {
        const element = document.createElement(tagName);
        if (className) {
            element.className = className;
        }
        if (typeof textContent === 'string') {
            element.textContent = textContent;
        }
        return element;
    }

    function enhanceDropzone(input) {
        if (!input || input.dataset.fontDropzoneReady === 'true') {
            return;
        }
        input.dataset.fontDropzoneReady = 'true';

        const shell = createElement('div', 'font-dropzone-shell');
        const label = createElement('div', 'font-dropzone-label', 'Drag and drop a file here');
        const hint = createElement('div', 'font-dropzone-hint', 'You can also click below to browse files.');
        const meta = createElement('div', 'font-dropzone-meta', 'No file selected');

        input.parentNode.insertBefore(shell, input);
        shell.appendChild(label);
        shell.appendChild(hint);
        shell.appendChild(meta);
        shell.appendChild(input);

        function updateMeta() {
            if (input.files && input.files[0]) {
                meta.textContent = input.files[0].name;
                return;
            }
            meta.textContent = 'No file selected';
        }

        ['dragenter', 'dragover'].forEach(function (eventName) {
            shell.addEventListener(eventName, function (event) {
                event.preventDefault();
                shell.classList.add('is-dragover');
            });
        });

        ['dragleave', 'drop'].forEach(function (eventName) {
            shell.addEventListener(eventName, function (event) {
                event.preventDefault();
                shell.classList.remove('is-dragover');
            });
        });

        shell.addEventListener('drop', function (event) {
            if (!event.dataTransfer || !event.dataTransfer.files.length) {
                return;
            }
            input.files = event.dataTransfer.files;
            input.dispatchEvent(new Event('change', { bubbles: true }));
        });

        input.addEventListener('change', updateMeta);
        updateMeta();
    }

    function initFontManager() {
        document.querySelectorAll('.font-dropzone-input').forEach(enhanceDropzone);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFontManager);
    } else {
        initFontManager();
    }
}());
