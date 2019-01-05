// Graph state
var sigmaObject;
var sigmaFilter;
var buildingGraph = false;

// UI
var shuffleLayoutButton;
var refreshButton;
var buildGraphButton;
var invalidateGraphButton;
var minMatchCountSlider;
var minMatchCountSliderValue;
var minSimilaritySlider;
var minSimilaritySliderValue;
var summaryModal;
var progressBarContainer;

function initializeUI() {
    shuffleLayoutButton = $("#shuffle-layout-button");
    refreshButton = $("#refresh-graph-button");
    buildGraphButton = $("#build-graph-button");
    invalidateGraphButton = $("#invalidate-graph-button");
    minMatchCountSlider = $("#min-match-count-range");
    minMatchCountSliderValue = $("#min-match-count-range-value");
    minSimilaritySlider = $("#min-similarity-range");
    minSimilaritySliderValue = $("#min-similarity-range-value");
    summaryModal = $("#pair-comparisons-summary-modal");
    progressBarContainer = $("#load-progress");

    shuffleLayoutButton.on("click", _ => shuffleGraphLayout(sigmaObject));
    refreshButton.on("click", handleRefreshClick);
    buildGraphButton.on("click", drawGraphAsync);

    minMatchCountSlider.on("input", _ => {
        minMatchCountSliderValue.text(parseInt(minMatchCountSlider.val()));
    });
    minSimilaritySlider.on("input", _ => {
        minSimilaritySliderValue.text(parseFloat(minSimilaritySlider.val()));
    });

    invalidateGraphButton.on("click", _ => {
        startLoader("Invalidating server graph cache");
        $.ajax({
            url: "invalidate",
            type: "POST",
            dataType: "text",
            success: _ => stopLoader(),
            error: console.error,
            beforeSend: CSRFpreRequestCallback,
        });
    });

}

function startLoader(message) {
    progressBarContainer.children(".progress-bar").children("span.loader-message").text(message);
    progressBarContainer.show();
}

function stopLoader() {
    progressBarContainer.children(".progress-bar").children("span.loader-message").text('');
    progressBarContainer.hide();
}

// Add a X-CSRFToken header containing the Django generated CSRF token before sending requests
function CSRFpreRequestCallback(xhr) {
    const csrfToken = $("input[name=csrfmiddlewaretoken]").val();
    xhr.setRequestHeader("X-CSRFToken", csrfToken);
}

function handleEdgeClick(event) {
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

    // Get graph edge that was clicked
    const edge = event.data.edge;
    // Set modal title with match data from edge
    summaryModal.find("h4.modal-title").text(
            edge.source + " and " + edge.target + " have "
            + edge.matchesData.length + " submission pair" + (edge.matchesData.length > 1 ? 's' : '')
            + " with high similarity");
    // Convert match list to HTML list element and put into modal body
    summaryModal.find("div.modal-body").html(arrayToHTML(edge.matchesData.map(matchToHTML)));
    // Show modal
    summaryModal.modal("toggle");
    // TODO fire leave edge hover event to prevent edge highlighting from being stuck when returning from modal view
}

function handleRefreshClick() {
    startLoader("Updating graph");
    // Hide edges with weight less than the current min match count slider value
    applyMinEdgeWeightFilter(minMatchCountSlider.val());
    // Hide all nodes that have no edges after filtering
    applyDisconnectedNodesFilter();
    // Refresh graph rendering
    sigmaObject.refresh();
    stopLoader();
}

function applyMinEdgeWeightFilter(newMinEdgeWeight) {
    sigmaFilter
        // Clear existing filters by key
        .undo('min-edge-weight')
        // Include only edges with at least newMinEdgeWeight weights
        .edgesBy(e => e.weight >= newMinEdgeWeight, 'min-edge-weight')
        // Apply filter to graph
        .apply();
}

function applyDisconnectedNodesFilter() {
    sigmaFilter
        .undo('disconnected-nodes')
        .nodesBy(n => !sigmaObject.graph.adjacentEdges(n.id).every(e => e.hidden), 'disconnected-nodes')
        .apply();
}

function shuffleGraphLayout(s) {
    s.graph.nodes().forEach(n => {
        n.x = Math.random() - 0.5;
        n.y = Math.random() - 0.5;
    });
    s.refresh();
}

function buildGraph(graphData) {
    const s = new sigma({
        renderer: {
            container: "graph-container",
            type: 'canvas'
        },
        settings: {
            minEdgeSize: 1,
            maxEdgeSize: 10,
            enableEdgeHovering: true,
            defaultEdgeHoverColor: '#444',
            edgeHoverExtremities: true,
            edgeLabelSize: 'proportional',
            edgeLabelSizePowRatio: 1.5,
        }
    });

    graphData.nodes.forEach(node => {
        s.graph.addNode({
            id: node,
            label: node,
            size: 1,
            color: '#444',
        });
    });

    // Compute the edge with the largest weight to update the max value of the filter slider
    let maxMatchCount = 0;

    graphData.edges.forEach((edge, i) => {
        const matchCount = edge.matches_in_exercises.length;
        if (matchCount > maxMatchCount) {
            maxMatchCount = matchCount;
        }
        s.graph.addEdge({
            id: 'e' + i,
            source: edge.source,
            target: edge.target,
            size: matchCount * 10,
            label: '' + matchCount,
            color: '#ccc',
            hover_color: '#222',
            weight: matchCount,
            matchesData: Array.from(edge.matches_in_exercises),
        });
    });

    minMatchCountSlider.attr("max", maxMatchCount + 1);

    return s;
}

function drawGraph(graphData) {
    // Draw graph and assign resulting sigma.js object to global variable
    sigmaObject = buildGraph(graphData);
    sigmaObject.refresh();
    sigmaFilter = new sigma.plugins.filter(sigmaObject);

    shuffleGraphLayout(sigmaObject);

    sigmaObject.bind("clickEdge", handleEdgeClick);

    if (buildingGraph) {
        buildingGraph = false;
    }
    stopLoader();
}

function drawGraphFromJSON(dataString) {
    return drawGraph(JSON.parse(dataString));
}

// Main method for requesting graph data from the server and building the SigmaJS object
function drawGraphAsync() {
    buildingGraph = true;
    startLoader("Building graph");
    if (typeof sigmaObject !== "undefined") {
        // Clear all active hover effects
        sigmaObject.settings({enableEdgeHovering: false});
        sigmaObject.refresh();
        // Drop all edges and nodes
        sigmaObject.graph.clear();
        // Clear rendered graph from canvas
        sigmaObject.refresh();
    }

    let taskState = {
        task_id: '',
        ready: false,
        min_similarity: minSimilaritySlider.val(),
    };

    let pollIndex = 0;
    const pollSeconds = [1, 1, 1, 2, 2, 4, 4, 10, 30];

    function pollSuccess(newTaskState) {
        if (taskState.ready) {
            return;
        }
        taskState = newTaskState;
        if (taskState.ready) {
            pollIndex = 0;
            const graphDef = taskState.graph_data;
            if (graphDef.nodes && graphDef.edges) {
                drawGraph(graphDef);
                // Apply default filter settings to graph
                handleRefreshClick();
            } else {
                console.error("Server completed the data retrieval but returned an invalid graph definition object.");
            }
        } else {
            setTimeout(pollGraphData, 1000 * pollSeconds[pollIndex]);
            pollIndex = Math.min(pollSeconds.length - 1, pollIndex + 1);
        }
    }

    function pollError(response) {
        console.error("Failed to poll for API read task state:", response.responseText);
    }

    function pollGraphData() {
        if (taskState.ready) {
            return;
        }

        $.ajax({
            beforeSend: CSRFpreRequestCallback,
            url: "build", // /course_instance/graph/build
            method: "POST",
            dataType: "json",
            contentType: "application/json",
            data: JSON.stringify(taskState),
            success: pollSuccess,
            error: pollError,
        });
    }

    // Trigger graph build and poll for completion
    pollGraphData();
}

$(initializeUI);
