$(function() {
    const automaticFetchButton = $("button[name=provider-fetch-automatic]");
    const manualFetchButton = $("button[name=provider-fetch-manual]");
    const progressBarContainer = $("#load-progress");

    function startLoader(message) {
        progressBarContainer.children(".progress-bar").children("span.loader-message").text(message);
        progressBarContainer.show();
    }

    function stopLoader() {
        progressBarContainer.children(".progress-bar").children("span.loader-message").text('');
        progressBarContainer.hide();
    }

    function updateUI(resultHTML) {
        $("#exercise-config-table").html(resultHTML);
    }

    function CSRFpreRequestCallback(xhr) {
        const csrfToken = $("input[name=csrfmiddlewaretoken]").val();
        xhr.setRequestHeader("X-CSRFToken", csrfToken);
    }

    // The initial state is rendered into the document by the server
    let taskState = JSON.parse($("#pending-api-read").text());

    // Poll the server at taskState.poll_URL until it returns a string of the results rendered as a POSTable HTML form
    function poll() {
        if (taskState.ready === "true") {
            return;
        }

        function pollSuccess(newTaskState) {
            taskState = newTaskState;
            if (taskState.ready === "true") {
                stopLoader();
                if (taskState.resultHTML.length > 0) {
                    updateUI(taskState.resultHTML);
                } else {
                    console.error("Server completed the data retrieval but returned an empty result.");
                }
            } else {
                setTimeout(poll, 1000 * taskState.poll_interval_seconds);
            }
        }

        function pollError(response) {
            console.error("Failed to poll for API read task state:", response.responseText);
        }

        $.ajax({
            beforeSend: CSRFpreRequestCallback,
            url: taskState.poll_URL,
            method: "POST",
            dataType: "json",
            data: taskState,
            success: pollSuccess,
            error: pollError,
        });
    }

    function beginPolling(configType) {
        if (taskState.task_id !== null) {
            console.error("Data retrieval already pending");
            return;
        }
        startLoader("Retrieving course data");
        taskState.config_type = configType;
        poll();
    }

    automaticFetchButton.on("click", _ => beginPolling("automatic"));
    manualFetchButton.on("click", _ => beginPolling("manual"));
});
