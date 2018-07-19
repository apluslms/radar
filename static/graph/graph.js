$(_ => {
    const shuffleLayoutButton = $("#shuffle-layout-button");
    const forceAtlasButton = $("#toggle-forceatlas-button");
    const buildGraphButton = $("#build-graph-button");
    const minMatchCountSlider = $("#min-match-count-range");
    const minMatchCountSliderValue = $("#min-match-count-range-value");

    function getSliderValue() {
        return parseInt(minMatchCountSlider.val());
    };

    const js = new JS();
    // TODO: build graph in parallel with UI thread using a WebWorker
    const s = js.drawGraph(js.parseJSON($("#graph-json")));

    shuffleLayoutButton.on("click", _ => {
        shuffleGraphLayout(s);
        if (forceAtlasButton.hasClass("active")) {
            // shuffleGraphLayout kills force atlas, fix inconsistent visual state
            forceAtlasButton.button("toggle");
        }
    });
    forceAtlasButton.on("click", _ => {
        if (!s.isForceAtlas2Running()) {
            s.startForceAtlas2(forceAtlasConfig);
        } else {
            s.stopForceAtlas2();
        }
    });
    buildGraphButton.on("click", _ => {
        s.killForceAtlas2();
    });
    minMatchCountSlider.on("change", _ => {
        const newMinSize = getSliderValue();
        minMatchCountSliderValue.text(newMinSize);
        applyMinEdgeWeightFilter(newMinSize);
        applyDisconnectedNodesFilter();
    });

    s.startForceAtlas2(forceAtlasConfig);
    let timeoutID = window.setTimeout(_ => {
        sigmaObject.stopForceAtlas2();
        window.clearTimeout(timeoutID);
        [shuffleLayoutButton, forceAtlasButton].forEach(button => {
            button.attr("disabled", false);
        });
    }, 2000);
});
