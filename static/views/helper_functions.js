// Export functions

// Connect the slider value to the display
export function connectSliderValueDisplay(slider, display, parser) {
  slider.on("input", _ => display.text(parser(slider.val())));
}
