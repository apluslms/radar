$(_ => {
    const shuffleLayoutButton = $("#shuffle-layout-button");
    const forceAtlasButton = $("#toggle-forceatlas-button");
    const buildGraphButton = $("#build-graph-button");
    const minMatchCountSlider = $("#min-match-count-range");
    const minMatchCountSliderValue = $("#min-match-count-range-value");
    const summaryModal = $("#pair-comparisons-summary-modal");

    function getSliderValue() {
        return parseInt(minMatchCountSlider.val());
    }

    function arrayToHTML(strings) {
        return "<ul>" + strings.map(s => "<li>" + s + "</li>").join("\n") + "</ul>";
    }

    function matchToHTML(match) {
        const elements = [
            "Exercise: <a href='" + match.exercise_url + "'>" + match.exercise_name + "</a>",
            "Comparison view: <a href='" + match.comparison_url + "'>link</a>",
            "Maximum similarity: " + match.max_similarity,
        ];
        return arrayToHTML(elements);
    }

    function handleEdgeClick(event) {
        const edge = event.data.edge;
        summaryModal.find("h4.modal-title").text(edge.source + " and " + edge.target + " have " + edge.matchesData.length + " submission pairs with high similarity");
        summaryModal.find("div.modal-body").html(arrayToHTML(edge.matchesData.map(matchToHTML)));
        summaryModal.modal("toggle");
    }

    const js = new JS();
    // TODO: build graph in parallel with UI thread using a WebWorker
    const s = js.drawGraph(js.parseJSON($("#graph-json")));

    s.bind("clickEdge", handleEdgeClick);

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
