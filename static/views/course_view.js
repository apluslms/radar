// Variables
const progressBarContainer = $("#load-progress");

// Functions

// Initialize the UI
function initializeUI() {
  //Add event listener to the reload button
  $('#reload-form').on('submit', handleReloadButtonClick);

  //Add event listener to the recompare all button
  $('#recompare_all-button').on('click', _ => {
    startLoader('Recomparing All Submissions...');
  });

  //Add event listener to the recompare button
  $('#unmatched-button').on('click', _ => {
    startLoader('Matching Submissions...');
  });

  // Change background color of unmatched submissions
  changeBackgroundColorUnmatched();
}


// Function to handle the reload button click
function handleReloadButtonClick(event) {
  startLoader('Reloading Submissions...');

  event.preventDefault(); // Prevent the default form submission
  console.log("Trying to reload all exercises.");

  // Get the CSRF token and the exercises table
  const csrfToken = $('input[name="csrfmiddlewaretoken"]').val();
  const exercises = $('#exercises-table tbody tr');

  // Loop through each exercise and send a POST request to reload it
  for(let i = 0; i < exercises.length; i++) {
    // Get the exercise button and its href attribute
    const exercise = exercises[i];
    const exerciseButton = exercise.querySelector('.btn');
    const exerciseHref = exerciseButton.getAttribute('href');

    // Get the form data and append the CSRF token
    const formData = new URLSearchParams();
    formData.append('csrfmiddlewaretoken', csrfToken);
    formData.append('provider_reload', '');

    fetch(`${exerciseHref}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': csrfToken,
      },
      body: formData.toString()
    }).then(response => {
      if (response.ok) {
        console.log(`Exercise reloaded successfully.`);
      } else {
        console.error(`Failed to reload exercise.`);
      }
    }).catch(error => {
      console.error(`Error reloading exercise`, error);
    });
  };

  stopLoader();

  setTimeout(() => {
    history.replaceState(null, null, location.href);
    location.reload();
  }, 2000);
}


// Function to change the background color of unmatched submissions
function changeBackgroundColorUnmatched() {
  var exercises = $('#exercises-table tbody tr');

  exercises.each(function() {
    // Get 4th column value (Pending submissions)
    var pendingCount = parseInt($(this).find('td:nth-child(4)').text().trim());

    // Get 5th column value (Not matched submissions)
    var unmatchedCount = parseInt($(this).find('td:nth-child(5)').text().trim());

    if (pendingCount > 0) {
      // Change background color of the row
      $(this).css('background-color', '#fee8c8');
    } else if (unmatchedCount > 0) {
      // Change background color of the row
      $(this).css('background-color', '#fdbb83');
    }
  });
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


$(initializeUI);
