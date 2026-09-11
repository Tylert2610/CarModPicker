/**
 * Content script for CarModPicker domains only. Sets the install marker
 * `data-carmodpicker-extension="installed"` for the web app to detect.
 */

const CARMODPICKER_HOST_PATTERN = /(^|\.)carmodpicker\.com$|^localhost$/i;
if (CARMODPICKER_HOST_PATTERN.test(window.location.hostname)) {
  document.documentElement.dataset["carmodpickerExtension"] = "installed";
}
