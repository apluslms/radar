var button;
$(function() {
    function CSRFpreRequestCallback(xhr) {
        const csrfToken = $("input[name=csrfmiddlewaretoken]").val();
        xhr.setRequestHeader("X-CSRFToken", csrfToken);
    }

    $("button[name=match-all-unmatched-for-exercise]").click(_ => {
        button = $(this);
        // Get exercise key of the row this button was on
        const exerciseKey = $(this).siblings("input[name=exercise_key]").val();
        $.ajax({
            url: "json",
            type: "POST",
            data: {"exercise_key": exerciseKey, "match-all-unmatched-for-exercise": true},
            success: console.log,
            error: console.error,
            beforeSend: CSRFpreRequestCallback,
        });
    });
});
