// Functions

// Initialize the UI
function initializeUI() {
  // Build control UI
  buildControl = {};
  buildControl.buildButton = $("#build-graph-button");
  buildControl.invalidateCacheButton = $("#invalidate-graph-button");
  buildControl.minSimilaritySlider = $(".build-args-ui .slider-container input.similarity-slider");
  buildControl.minSimilaritySliderValue = $(".build-args-ui .slider-container p.similarity-slider-value");
  buildControl.minMatchCountSlider = $(".build-args-ui .slider-container input.match-count-slider");
  buildControl.minMatchCountSliderValue = $(".build-args-ui .slider-container p.match-count-slider-value");
  buildControl.uniqueCheckbox = $("#use-unique-checkbox");
  buildControl.buildButton.on("click", buildTable);

  // Connect the slider value display to the slider
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
    startLoader("Invalidating server table cache");
    $.ajax({
        url: "../graph/invalidate",
        type: "POST",
        dataType: "text",
        success: _ => stopLoader(),
        error: console.error,
        beforeSend: CSRFpreRequestCallback,
    });
  });

  progressBarContainer = $("#load-progress");
}


// Build the table
function buildTable() {
  startLoader("Building table");

  clearTable();

  // Data to be sent to the server for the request
  let taskState = {
    task_id: '',
    ready: false,
    min_similarity: buildControl.minSimilaritySlider.val(),
    min_matches: buildControl.minMatchCountSlider.val(),
    unique_exercises: buildControl.uniqueCheckbox.is(":checked"),
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
      let tableDefinition = taskState.graph_data;
      if (tableDefinition.nodes && tableDefinition.edges) {
        // Update the table
        updateTable(tableDefinition);

        // Show the date and time
        showDatetime(tableDefinition['date_time']);

        // Stop the loader
        stopLoader();
      } else {
        console.error("Server completed the data retrieval but returned an invalid table definition object.");
      }
    } else {
      setTimeout(pollTableData, 1000 * pollSeconds[pollIndex]);
      pollIndex = Math.min(pollSeconds.length - 1, pollIndex + 1);
    }
  }

  // Poll the server for the table data
  function pollTableData() {
    if (taskState.ready) {
      return;
    }

    $.ajax({
      beforeSend: CSRFpreRequestCallback,
      url: "../graph/build", // /course_instance/graph/build
      method: "POST",
      dataType: "json",
      contentType: "application/json",
      data: JSON.stringify(taskState),
      success: pollSuccess,
      error: pollError,
    });
  }

  // Trigger table build and poll for completion
  pollTableData(taskState);
}


// Save the clusters
function saveClusters(tableDefinition, clusters) {
  // Get the cluster parameters
  let clustersData = {
    min_similarity: tableDefinition['min_similarity'],
    min_matches: tableDefinition['min_matches'],
    unique_exercises: tableDefinition['unique_exercises'],
    date_time: tableDefinition['date_time'],
    clusters: clusters,
  };

  // Save the clusters to the server
  $.ajax({
    beforeSend: CSRFpreRequestCallback,
    url: "save",
    method: "POST",
    dataType: "json",
    contentType: "application/json",
    data: JSON.stringify(clustersData),
    success: _ => {},
    error: pollError,
  });
}


// On request error
function pollError(response) {
  console.error("Failed to poll for API read task state:", response.responseText);
}


// Add a X-CSRFToken header containing the Django generated CSRF token before sending requests
function CSRFpreRequestCallback(xhr) {
  const csrfToken = $("input[name=csrfmiddlewaretoken]").val();
  xhr.setRequestHeader("X-CSRFToken", csrfToken);
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


// Update the table
function updateTable(tableDefinition) {
  // Get the clusters from the data
  let clusters = getClusters(tableDefinition.edges);

  // Save the clusters
  saveClusters(tableDefinition, clusters);

  // Get the data table
  let table = $('#clustersdatatable').DataTable();

  // Add the clusters to the table
  clusters.forEach(function(cluster, index) {
    table.row.add([
      `<a href="${index + 1}">Cluster ${index + 1}</a>`,
      cluster['students'].join(", "),
      (cluster['similarity'] * 100).toFixed(0) + "%",
      cluster['students'].length
    ]);
  });

  table.draw();
}


// Helper function for getting the clusters from data
function getClusters(students) {
  var clusters = [];

  students.forEach(function(student) {
    // Check if the student source or target is already in a group
    var found = false;

    // Loop through the clusters
    for (let index = 0; index < clusters.length; index++) {
      if (clusters[index]['students'].has(student['source']) || clusters[index]['students'].has(student['target'])) {

        clusters[index]['students'].add(student['source']);
        clusters[index]['students'].add(student['target']);

        student['matches_in_exercises'].forEach(function(exercise) {
          clusters[index]['similarity'].push(exercise['max_similarity']);
        });

        found = true;
        break;
      }
    };

    // If the student is not in any cluster, create a new one
    if (!found) {
      var similarity = [];

      student['matches_in_exercises'].forEach(function(exercise) {
        similarity.push(exercise['max_similarity'])
      });

      clusters.push({
        'students': new Set([student['source'], student['target']]),
        'similarity': similarity
      });
    }
  });

  // Merge the linked groups if they share a student
  clusters.forEach(function(cluster) {
    clusters.forEach(function(otherCluster) {

      // Skip if same cluster
      if (cluster['students'] !== otherCluster['students']) {
        for (let index = 0; index < cluster['students'].size; index++) {
          // Check if other cluster has the student
          if (otherCluster['students'].has(Array.from(cluster['students'])[index])) {
            // Merge the clusters
            cluster['students'] = new Set([...cluster['students'], ...otherCluster['students']]);
            cluster['similarity'] = cluster['similarity'].concat(otherCluster['similarity']);

            var clusterIndex;

            // Remove the other cluster from the list
            while ((clusterIndex = clusters.indexOf(otherCluster)) != -1){
              clusters.splice(clusterIndex, 1);
            }

            break;
          }
        };
      }
    });
  });

  return sortClusters(clusters);
}


// Sort Clusters
function sortClusters(clusters) {
  // Sort the students in each cluster
  var collator = new Intl.Collator(undefined, {numeric: true, sensitivity: 'base'})

  // Sort the clusters and get average similarity
  for (let index = 0; index < clusters.length; index++) {
    clusters[index]['students'] = Array.from(clusters[index]['students']).sort(collator.compare);
    clusters[index]['similarity'] = clusters[index]['similarity'].reduce((a, b) => a + b, 0) / clusters[index]['similarity'].length;
  }

  // Sort the clusters by average similarity
  clusters.sort(function(a, b) {
    if (a['similarity'] === b['similarity']) {
      return b['students'].size - a['students'].size;
    }

    return b['similarity'] - a['similarity'];
  });

  return clusters
}


//Show the date and time
function showDatetime(dateTime) {;
  $('#datetime').text("Date & Time clusters created: " + dateTime);
}


// Clear the table
function clearTable() {
  $('#clustersdatatable').DataTable().clear().draw();
  $('#datetime').text('');
}


// Connect the slider value to the display
function connectSliderValueDisplay(slider, display, parser) {
  slider.on("input", _ => display.text(parser(slider.val())));
}


// Initialize the table
function initializeTable() {
  $('#clustersdatatable').DataTable( {
    lengthMenu: [
      [-1, 10, 25, 100],
      ["All", 10, 25, 100] ],
    columnDefs: [
      { type: 'natural', targets: [0,1] },
      { targets: [2], orderData: [0, 2]},
      { className: 'dt-left', targets: '_all' },
    ]
  });
}


$(initializeUI);
$(initializeTable);
