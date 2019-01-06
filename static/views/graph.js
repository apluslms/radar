// Graph state
var sigmaObject;
var buildingGraph = false;
// Backup of the original nodes and edges arrays, as returned by the server
var graphDefinition;
// Most recent coordinates for each node
var graphLayout;

// UI
var buildControl;
var graphControl;
var summaryModal;
var progressBarContainer;


function connectSliderValueDisplay(slider, display, parser) {
    slider.on("input", _ => display.text(parser(slider.val())));
}


function initializeUI() {
    graphControl = {};
    graphControl.shuffleLayoutButton = $("#shuffle-layout-button");
    graphControl.refreshButton = $("#refresh-graph-button");
    graphControl.minMatchCountSlider = $(".filter-ui .slider-container input.match-count-slider");
    graphControl.minMatchCountSliderValue = $(".filter-ui .slider-container p.match-count-slider-value");
    graphControl.shuffleLayoutButton.on("click", _ => {
        shuffleGraphLayout();
        applyGraphLayout();
    });
    graphControl.refreshButton.on("click", handleRefreshClick);
    connectSliderValueDisplay(
        graphControl.minMatchCountSlider,
        graphControl.minMatchCountSliderValue,
        parseInt
    );

    buildControl = {};
    buildControl.buildButton = $("#build-graph-button");
    buildControl.invalidateCacheButton = $("#invalidate-graph-button");
    buildControl.minSimilaritySlider = $(".build-args-ui .slider-container input.similarity-slider");
    buildControl.minSimilaritySliderValue = $(".build-args-ui .slider-container p.similarity-slider-value");
    buildControl.minMatchCountSlider = $(".build-args-ui .slider-container input.match-count-slider");
    buildControl.minMatchCountSliderValue = $(".build-args-ui .slider-container p.match-count-slider-value");
    buildControl.buildButton.on("click", drawGraphAsync);
    connectSliderValueDisplay(
        buildControl.minMatchCountSlider,
        buildControl.minMatchCountSliderValue,
        parseInt
    );
    connectSliderValueDisplay(
        buildControl.minSimilaritySlider,
        buildControl.minSimilaritySliderValue,
        parseFloat
    );

    buildControl.invalidateCacheButton.on("click", _ => {
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

    summaryModal = $("#pair-comparisons-summary-modal");
    progressBarContainer = $("#load-progress");
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

    // Opening a modal seems to mess up edge hover mouse tracking, we fix it by forcing removal of all edge hover effects and then putting them back on
    sigmaObject.settings({enableEdgeHovering: false});
    sigmaObject.refresh();
    sigmaObject.settings({enableEdgeHovering: true});

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
}

function handleRefreshClick() {
    // Rebuild graph to filter by edge weight
    redrawGraph(graphDefinition, {minEdgeWeight: graphControl.minMatchCountSlider.val()});
    applyGraphLayout();
}

function shuffleGraphLayout() {
    for (node_id in graphLayout) {
        const node = graphLayout[node_id];
        node.x = Math.random() - 0.5;
        node.y = Math.random() - 0.5;
    }
}

function applyGraphLayout() {
    sigmaObject.graph.nodes().forEach(node => {
        const pos = graphLayout[node.id];
        node.x = pos.x;
        node.y = pos.y;
    });
    sigmaObject.refresh();
}

function buildGraph(graphData, config) {
    if (graphData.nodes.length === 0 && graphData.edges.length === 0) {
        console.error("buildGraph cannot render an empty graph definition:", graphData);
        return;
    }

    const s = new sigma({
        renderer: {
            container: "graph-container",
            type: 'canvas'
        },
        settings: {
            enableEdgeHovering: true,
            defaultEdgeHoverColor: '#444',
            edgeHoverExtremities: true,
            edgeLabelSize: 'proportional',
            edgeLabelSizePowRatio: 1.5,
            minNodeSize: 5,
            maxNodeSize: 10,
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

    let minEdgeWeightFilter;
    if (config) {
        minEdgeWeightFilter = config.minEdgeWeight || 0;
    }

    // Compute the largest and smallest edge weights to set the graph control slider boundaries
    let minMatchCount = Infinity;
    let maxMatchCount = 0;

    graphData.edges.forEach((edge, i) => {
        const matchCount = edge.matches_in_exercises.length;
        if (matchCount < minEdgeWeightFilter) {
            return;
        }
        minMatchCount = Math.min(minMatchCount, matchCount);
        maxMatchCount = Math.max(maxMatchCount, matchCount);
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

    s.settings({
        minEdgeSize: 2 + minMatchCount,
        maxEdgeSize: 2 + maxMatchCount,
    });

    graphLayout.minMatchCount = minMatchCount;
    graphLayout.maxMatchCount = maxMatchCount;

    return s;
}

function clearSigmaGraph() {
    if (typeof sigmaObject !== "undefined") {
        sigmaObject.graph.clear();
        sigmaObject.refresh();
    }
}

function redrawGraph(graphData, config) {
    startLoader("Re-drawing graph");

    // Render blank canvas
    clearSigmaGraph();

    // Overwrite global sigma.js object with a new one
    sigmaObject = buildGraph(graphData, config);
    // Open modal with match list by clicking edges
    sigmaObject.bind("clickEdge", handleEdgeClick);

    if (config && config.resetControlUI) {
        // Update graph control slider
        const minMatchCount = graphLayout.minMatchCount;
        const maxMatchCount = graphLayout.maxMatchCount;
        graphControl.minMatchCountSlider.prop("min", minMatchCount);
        graphControl.minMatchCountSlider.prop("max", maxMatchCount);
        buildControl.minMatchCountSlider.prop("max", maxMatchCount);
        graphControl.minMatchCountSlider.prop("value", minMatchCount);
        graphControl.minMatchCountSliderValue.text(minMatchCount);
    }

    const graph = sigmaObject.graph;

    // Drop all nodes that have no edges
    graph.nodes().forEach(node => {
        if (!graph.degree(node.id))
            graph.dropNode(node.id);
    });
    // Set node sizes linearly proportional to their degree
    graph.nodes().forEach(node => {
        node.size = 1 + 2 * graph.degree(node.id);
    });

    // Re-render with applied changes
    sigmaObject.refresh();

    if (buildingGraph) {
        buildingGraph = false;
    }
    stopLoader();
}

function drawGraphFromJSON(dataString) {
    redrawGraph(JSON.parse(dataString));
}

// Main method for requesting graph data from the server and building the SigmaJS object
function drawGraphAsync() {
    startLoader("Building graph");

    clearSigmaGraph();

    buildingGraph = true;
    graphDefinition = {};
    graphLayout = {};

    let taskState = {
        task_id: '',
        ready: false,
        min_similarity: buildControl.minSimilaritySlider.val(),
        min_matches: buildControl.minMatchCountSlider.val(),
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
            graphDefinition = taskState.graph_data;
            if (graphDefinition.nodes && graphDefinition.edges) {
                // Store all node ids and get random positions for nodes
                graphDefinition.nodes.forEach(node_id => graphLayout[node_id] = {});
                shuffleGraphLayout();
                redrawGraph(graphDefinition, {resetControlUI: true});
                applyGraphLayout();
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
