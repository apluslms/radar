// Variables

// Backup of the original nodes and edges arrays, as returned by the server
var graphDefinition;

// Most recent coordinates and colors for each node
var graphLayout;

// Select the element to append the graph to
var element = '#network-graph';

// Legend
var legend = "#network-graph-legend";

// Radius of the nodes
var radius = 10;

// Simulation of the graph
var simulation;

// UI
var buildControl;
var graphControl;
var summaryModal;
var progressBarContainer;

//Functions

// Initialize the UI
function initializeUI() {
  // Graph control UI
  graphControl = {};
  graphControl.refreshButton = $("#refresh-graph-button");
  graphControl.minMatchCountSlider = $(".filter-ui .slider-container input.match-count-slider");
  graphControl.minMatchCountSliderValue = $(".filter-ui .slider-container p.match-count-slider-value");
  graphControl.clustersButton = $("#student-clusters-button");
  graphControl.refreshButton.on("click", handleRefreshClick);
  graphControl.clustersButton.on("click", handleClustersClick);
  connectSliderValueDisplay(
      graphControl.minMatchCountSlider,
      graphControl.minMatchCountSliderValue,
      parseInt
  );

  // Build control UI
  buildControl = {};
  buildControl.buildButton = $("#build-graph-button");
  buildControl.invalidateCacheButton = $("#invalidate-graph-button");
  buildControl.minSimilaritySlider = $(".build-args-ui .slider-container input.similarity-slider");
  buildControl.minSimilaritySliderValue = $(".build-args-ui .slider-container p.similarity-slider-value");
  buildControl.minMatchCountSlider = $(".build-args-ui .slider-container input.match-count-slider");
  buildControl.minMatchCountSliderValue = $(".build-args-ui .slider-container p.match-count-slider-value");
  buildControl.uniqueCheckbox = $("#use-unique-checkbox");
  buildControl.buildButton.on("click", buildGraph);
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

  // Send request to invalidate the cache
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


// Connect the slider value to the display
function connectSliderValueDisplay(slider, display, parser) {
  slider.on("input", _ => display.text(parser(slider.val())));
}


// Handle the refresh button click for "Apply filter"
function handleRefreshClick() {
  startLoader("Re-drawing graph");

  clearGraph();

  // Filter by edge weight
  var filteredEdges = graphDefinition.edges.filter(function(edge) {
    return edge.matches_in_exercises.length >= graphControl.minMatchCountSlider.val();

  });


  // Filter nodes by the filtered edges
  var filteredNodes = graphDefinition.nodes.filter(function(node) {
    return filteredEdges.some(function(edge) {
      return edge.source.id == node.id || edge.target.id == node.id;
    });
  });

  // Update the graph layout
  graphLayout = {"nodes": filteredNodes, "edges": filteredEdges};

  // Rebuild graph to filter by edge weight
  buildD3Graph(graphLayout, graphDefinition.clusters);


  stopLoader();
}


// Handle the clusters button click
function handleClustersClick() {
  //Navigate to the clusters view
  window.location.href = "../clusters";
}


// Show loading bar
function startLoader(message) {
  progressBarContainer.children(".progress-bar").children("span.loader-message").text(message);
  progressBarContainer.show();
}


// Hide loading bar
function stopLoader() {
  progressBarContainer.children(".progress-bar").children("span.loader-message").text('');
  progressBarContainer.hide();
}


// Build the graph
function buildGraph() {
  startLoader("Building graph");

  clearGraph();

  graphDefinition = {};

  // Data to be sent to the server for the request
  let taskState = {
    task_id: '',
    ready: false,
    min_similarity: buildControl.minSimilaritySlider.val(),
    min_matches: buildControl.minMatchCountSlider.val(),
    unique_exercises: buildControl.uniqueCheckbox.is(":checked"),
    origin: 'graph',
  };

  // Poll timeouts
  let pollIndex = 0;
  const pollSeconds = [1, 1, 1, 2, 2, 4, 4, 10, 30];

  // On request success
  function pollSuccess(newTaskState) {
    if (taskState.ready) {
      return;
    }
    taskState = newTaskState;
    if (taskState.ready) {
      pollIndex = 0;
      graphDefinition = taskState.graph_data;
      graphDefinition.clusters = taskState.clusters;
      if (graphDefinition.nodes && graphDefinition.edges) {
        // Get nodes
        var nodes = []

        graphDefinition.nodes.forEach((element, index) => {
          nodes.push({"id": element});
        });

        graphDefinition.nodes = nodes;

        // Build the graph layout
        graphLayout = {"nodes": graphDefinition.nodes, "edges": graphDefinition.edges};

        // Build the D3 graph
        buildD3Graph(graphLayout, graphDefinition.clusters);

        // Show the date and time
        showDatetime(graphDefinition['date_time']);

        // Stop the loader
        stopLoader();
      } else {
        console.error("Server completed the data retrieval but returned an invalid graph definition object.");
      }
    } else {
      setTimeout(pollGraphData, 1000 * pollSeconds[pollIndex]);
      pollIndex = Math.min(pollSeconds.length - 1, pollIndex + 1);
    }
  }

  // On request error
  function pollError(response) {
    console.error("Failed to poll for API read task state:", response.responseText);
  }

  // Poll the server for the graph data
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


// Add a X-CSRFToken header containing the Django generated CSRF token before sending requests
function CSRFpreRequestCallback(xhr) {
  const csrfToken = $("input[name=csrfmiddlewaretoken]").val();
  xhr.setRequestHeader("X-CSRFToken", csrfToken);
}


//Show the date and time
function showDatetime(dateTime) {;
  $('#datetime').text("Date & Time graph created: " + dateTime);
}


// Clear the graph and the legend
function clearGraph() {
  d3.select(element).selectAll("*").remove();
  d3.select(legend).selectAll("*").remove();
  $('#datetime').text('');
}


// Build the force directed graph using D3.js
function buildD3Graph(data, clusters) {

  // Append the svg object to the body of the page
  var svg = d3
    .select(element)
    .append("svg")
    .attr("width", "100%")

  // Get the width and height of the element
  var width = d3.select(element).select('svg').style("width");
  width = width.substring(0, width.length - 2);
  var height = d3.select(element).select('svg').style("height");
  height = height.substring(0, height.length - 2);

  // Initialize the cluster highlight lines
  var clusterHighlight = svg
    .selectAll(".node_group")
    .data(data.edges)
    .enter()
    .append("line")
      .attr("class", "node_group")
      .style("stroke-width", radius*3)
      .style("stroke-linecap", "round")

  // Assign a color to each cluster
  assignClusterColors(clusterHighlight._groups[0], clusters);

  // Initialize the edges
  var edge = svg
    .selectAll(".edge")
    .data(data.edges)
    .enter()
    .append("line")
      .attr("class", "edge")
      .style("stroke", "#aaa")
      .style("stroke-width", radius/3)
    .on("click", handleEdgeClick)
    .on("mouseover", function(edge) {
      handleEdgeMouseover(this, edge, node);
    })
    .on("mouseout", function(edge) {
      handleEdgeMouseout(this, edge, node);
    });

  // Initialize the nodes
  var node = svg
    .selectAll("circle")
    .data(data.nodes)
    .enter()
    .append("circle")
      .attr("r", radius)
      .attr("stroke", "white")
      .attr("fill", function(node){
        return fillNode(node);
      })
    .call(callDrag, this)
    .on("mouseover", function(node) {
      handleNodeMouseover(this, node);
    })
    .on("mouseout", function(node) {
      handleNodeMouseout(this, node);
    });

  // Initialize the node labels
  var nodeLabel = svg
    .append("g")
    .selectAll("text")
    .data(data.nodes)
    .enter()
    .append("text")
      .attr("display", "none")
      .attr("fill", "white")
      .attr("font-size", radius * 1.5)
      .attr("pointer-events", "none")
      .attr("id", function(node) {
        return "node_label_" + node.id;
      })
      .text(function(node) {
        return node.id;
      });

  // Initialize the edge labels
  var edgeLabel = svg
    .append("g")
    .selectAll("text")
    .data(data.edges)
    .enter()
    .append("text")
      .attr("display", "none")
      .attr("fill", "white")
      .attr("font-size", radius * 1.25)
      .attr("pointer-events", "none")
      .attr("id", function(edge) {
        return "edge_label_" + edge.source + "_" + edge.target;
      })
      .text(function(edge) {
        return edge.matches_in_exercises.length;
      });

  // List forces to apply on the nodes and edges
  simulation = d3.forceSimulation(data.nodes) // Force algorithm is applied to data.nodes
    .force("link", d3.forceLink()             // This force provides links between nodes
      .id(function(d) { return d.id; })       // This provide the id of a node
      .links(data.edges)                      // This is the list of links
      .strength(0.25)                         // This force makes links stronger
    )
    // This adds repulsion between nodes
    .force("nodes", d3.forceManyBody().strength(-200))
    // This force attracts nodes to the center of the svg area
    .force("center", d3.forceCenter(width / 2, height / 2))
    // This force attracts nodes to the center of the svg area also?
    .force("radial", d3.forceRadial(radius, width / 2, height / 2).strength(0.1))
    .on("tick", ticked);

  // Update the position of the nodes and edges
  function ticked() {
    edge
      .attr("x1", function(d) { return Math.max(radius, Math.min(width - radius, d.source.x)); })
      .attr("y1", function(d) { return Math.max(radius, Math.min(height - radius, d.source.y)); })
      .attr("x2", function(d) { return Math.max(radius, Math.min(width - radius, d.target.x)); })
      .attr("y2", function(d) { return Math.max(radius, Math.min(height - radius, d.target.y)); });

    node
      .attr("cx", function(d) {
        return (d.x = Math.max(radius, Math.min(width - radius, d.x)));
      })
      .attr("cy", function(d) {
        return (d.y = Math.max(radius, Math.min(height - radius, d.y)));
      })

    nodeLabel
      .attr("x", function(d) {
        return (d.x = Math.max(radius, Math.min(width - radius, d.x - radius * 0.80)));
      })
      .attr("y", function(d) {
        return (d.y = Math.max(radius, Math.min(height - radius, d.y + radius/2)));
      })

    edgeLabel
      .attr("x", function(d) {
        x = ((d.source.x + d.target.x) / 2);
        return (d.x = Math.max(radius, Math.min(width - radius, x + radius/2.5)));
      })
      .attr("y", function(d) {
        y = ((d.source.y + d.target.y) / 2);
        return (d.y = Math.max(radius, Math.min(height - radius, y)));
      })

    clusterHighlight
      .attr("x1", function(d) { return Math.min(width, d.source.x + radius*0.75); })
      .attr("y1", function(d) { return Math.min(height, d.source.y - radius/2); })
      .attr("x2", function(d) { return Math.min(width, d.target.x + radius*0.75); })
      .attr("y2", function(d) { return Math.min(height, d.target.y - radius/2); });
  }
}


// Assign a color to each cluster
function assignClusterColors(clusterHighlight, clusters) {

  // Get the colors for the clusters
  var clusterColors = getClusterColors(clusters.length);

  // Assign a color to each cluster
  clusterHighlight.forEach(function(d) {
    var i = 0;
    clusters.forEach(function(list) {
      if (list.includes(d.__data__.source) || list.includes(d.__data__.target)) {
        d3.select(d).style("stroke", clusterColors[i]);
        return;
      } else {
        i++;
      }
    });
  });
}


// Get a random color for each cluster
function getClusterColors(size){
  var colors = [];

  for (var i = 0; i < size; i++) {
    colors.push(
      "hsl(" + 360 * Math.random() + ',' +
      (25 + 70 * Math.random()) + '%,' +
      (85 + 10 * Math.random()) + '%)'
    );
  }

  return colors;
}


// Handle click event on a edge
function handleEdgeClick(edge) {
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

  // Set modal title with match data from edge
  summaryModal.find("h4.modal-title").text(
          edge.source.id + " and " + edge.target.id + " have "
          + edge.matches_in_exercises.length + " submission pair" + (edge.matches_in_exercises.length > 1 ? 's' : '')
          + " with high similarity");
  // Convert match list to HTML list element and put into modal body
  summaryModal.find("div.modal-body").html(arrayToHTML(edge.matches_in_exercises.map(matchToHTML)));
  // Show modal
  summaryModal.modal("toggle");
}


// Handle edge mouseover event
function handleEdgeMouseover(current, edge, nodes) {
  // Get nodes connected by the edge
  nodes.filter(function(node){
    return node.id == edge.source.id || node.id == edge.target.id;
  }).attr('r', radius*1.25);

  d3.select(current).style("stroke-width", radius * 1.5).style("stroke", "red");
  d3.select("#node_label_" + edge.source.id).style("display", "block");
  d3.select("#node_label_" + edge.target.id).style("display", "block");
  d3.select("#edge_label_" + edge.source.id + "_" + edge.target.id).style("display", "block");
}


// Handle edge mouseout event
function handleEdgeMouseout(current, edge, nodes) {
  // Get nodes connected by the link
  nodes.filter(function(node){
    return node.id == edge.source.id || node.id == edge.target.id;
  }).attr('r', radius);

  d3.select(current).style("stroke-width", radius/3).style("stroke", "#aaa");
  d3.select("#node_label_" + edge.source.id).style("display", "none");
  d3.select("#node_label_" + edge.target.id).style("display", "none");
  d3.select("#edge_label_" + edge.source.id + "_" + edge.target.id).style("display", "none");
}


// Fill the nodes with a random color
function fillNode(node) {
  var color = getNodeColor();
  addLegend(color, node.id);
  return color;
}


// Generate a random color for each node
function getNodeColor() {
  var letters = '0123456789ABCDEF';
  var color = '#';
  for (var i = 0; i < 6; i++) {
    color += letters[Math.floor(Math.random() * 16)];
  }
  return color;
}


// Add a legend to the graph
function addLegend(color, label) {
  $(legend).append('<text style="color: ' + color + '; text-align: center;">	&#9679;' + label + '</text>');
}


// Enable dragging of the nodes
function callDrag(node) {
  function dragstarted(d) {
    simulation.alphaTarget(0.5).restart();
    d.fx = d.x + radius*0.8;
    d.fy = d.y - radius/2;
  }

  function dragged(d) {
    d.fx = d3.event.x + radius*0.8;
    d.fy = d3.event.y - radius/2;
  }

  function dragended(d) {
    simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
  }

  node.call(d3.drag()
    .on("start", dragstarted)
    .on("drag", dragged)
    .on("end", dragended)
  );
}


// Handle node mouseover event
function handleNodeMouseover(current, node) {
  d3.select(current).attr('r', radius*1.25);
  d3.select("#node_label_" + node.id).style("display", "block");
}


// Handle node mouseout event
function handleNodeMouseout(current, node) {
  d3.select(current).attr('r', radius);
  d3.select("#node_label_" + node.id).style("display", "none");
}


$(initializeUI);
