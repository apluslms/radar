var sigmaObject;
var sigmaFilter;
const forceAtlasConfig = {
  // compute algorithm using a web worker
  worker: true,
  // running time optimization for large graphs
  barnesHutOptimize: true,
  // seems to increase the repulsion between nodes
  outboundAttractionDistribution: true
};


function applyMinEdgeSizeFilter(newMinEdgeSize) {
  sigmaFilter
    .undo('min-edge-size')
    .edgesBy(e => e.size >= newMinEdgeSize, 'min-edge-size')
    .apply();
}

function applyMinEdgeWeightFilter(newMinEdgeWeight) {
  sigmaFilter
    .undo('min-edge-weight')
    .edgesBy(e => e.weight >= newMinEdgeWeight, 'min-edge-weight')
    .apply();
}

function applyDisconnectedNodesFilter() {
  sigmaFilter
    .undo('disconnected-nodes')
    .nodesBy(n => !sigmaObject.graph.adjacentEdges(n.id).every(e => e.hidden), 'disconnected-nodes')
    .apply();
}

function shuffleGraphLayout(s) {
  s.killForceAtlas2();
  s.graph.nodes().forEach(n => {
    n.x = Math.random() - 0.5;
    n.y = Math.random() - 0.5;
  });
  s.refresh();
}

function drawGraph(graphData) {
  let s = new sigma({
    renderer: {
      container: "graph-container",
      type: 'canvas'
    },
    settings: {
      minEdgeSize: 1,
      maxEdgeSize: 10,
      enableEdgeHovering: true,
      defaultEdgeHoverColor: '#222',
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
  graphData.edges.forEach((edge, i) => {
    const matchCount = edge.matches_in_exercises.length;
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

  sigmaFilter = new sigma.plugins.filter(s);

  shuffleGraphLayout(s);

  return s;
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

var buildingGraph = false;

function buildGraph(graphData) {
    const shuffleLayoutButton = $("#shuffle-layout-button");
    const forceAtlasButton = $("#toggle-forceatlas-button");
    const buildGraphButton = $("#build-graph-button");
    const minMatchCountSlider = $("#min-match-count-range");
    const minMatchCountSliderValue = $("#min-match-count-range-value");
    const minSimilaritySlider = $("#min-similarity-range");
    const minSimilaritySliderValue = $("#min-similarity-value");
    const summaryModal = $("#pair-comparisons-summary-modal");

    function handleEdgeClick(event) {
        const edge = event.data.edge;
        summaryModal.find("h4.modal-title").text(edge.source + " and " + edge.target + " have " + edge.matchesData.length + " submission pairs with high similarity");
        summaryModal.find("div.modal-body").html(arrayToHTML(edge.matchesData.map(matchToHTML)));
        summaryModal.modal("toggle");
        // TODO fire leave edge hover event to prevent edge highlighting from being stuck when returning from modal view
    }

    // Draw graph and assign resulting sigma.js object to global variable
    sigmaObject = drawGraph(graphData);

    sigmaObject.bind("clickEdge", handleEdgeClick);

    shuffleLayoutButton.on("click", _ => {
        shuffleGraphLayout(sigmaObject);
        if (forceAtlasButton.hasClass("active")) {
            // shuffleGraphLayout kills force atlas, fix inconsistent visual state
            forceAtlasButton.button("toggle");
        }
    });

    forceAtlasButton.on("click", _ => {
        if (!sigmaObject.isForceAtlas2Running()) {
            sigmaObject.startForceAtlas2(forceAtlasConfig);
        } else {
            sigmaObject.stopForceAtlas2();
        }
    });

    buildGraphButton.on("click", _ => {
        buildingGraph = true;
        sigmaObject.killForceAtlas2();
        // Assuming we are at graph, do POST to graph/build, with build args in body
        const minSimilarity = minSimilaritySlider.val();
        const minMatchCount = minMatchCountSlider.val();
        const csrfToken = $("input[name=csrfmiddlewaretoken]").val();
        $.ajax({
            url: "build",
            type: "POST",
            data: {
                minSimilarity: minSimilarity,
                minMatchCount: minMatchCount,
            },
            dataType: "json",
            success: buildGraph,
            error: console.error,
            beforeSend: xhr => xhr.setRequestHeader("X-CSRFToken", csrfToken),
        });
    });

    minMatchCountSlider.on("input", _ => {
        const newMinSize = parseInt(minMatchCountSlider.val());
        minMatchCountSliderValue.text(newMinSize);
        applyMinEdgeWeightFilter(newMinSize);
        applyDisconnectedNodesFilter();
    });

    if (buildingGraph) {
        buildingGraph = false;
    }
}

function buildGraphFromJSON(elementID) {
    return buildGraph(JSON.parse($("#" + elementID).text()));
}
