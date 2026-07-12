import flatpickr from "flatpickr";
import { Ukrainian } from "flatpickr/dist/l10n/uk.js";
import imageCompression from "browser-image-compression";
import "flatpickr/dist/flatpickr.min.css";

flatpickr.localize(Ukrainian);
window.flatpickr = flatpickr;
window.imageCompression = imageCompression;
